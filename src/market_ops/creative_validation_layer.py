"""Phase 1.3: Creative Intelligence Validation Layer.

Validates that CreativeEntity V2 can drive production decisions.
Discovers winning patterns from 176 real creatives, builds
performance-grounded scoring, and defines the Generation Input Contract.

DO NOT generate images. Only analyze and discover patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
from typing import Any, Optional

from .creative_entity_v2 import CreativeEntity, HookType, GameplayGenre
from .creative_entity_v2_adapters import CreativeEntityBuilder


# ═══════════════════════════════════════════════════════════
# 1. CreativeEntityIndex
# ═══════════════════════════════════════════════════════════

class CreativeEntityIndex:
    """Fast multi-dimensional lookup index for CreativeEntities."""

    def __init__(self, entities: list[CreativeEntity]) -> None:
        self._entities = entities

        # Primary index
        self.by_id: dict[str, CreativeEntity] = {}
        self.by_roas: list[CreativeEntity] = []
        self.by_hook: dict[str, list[CreativeEntity]] = defaultdict(list)
        self.by_gameplay: dict[str, list[CreativeEntity]] = defaultdict(list)
        self.by_reward: dict[str, list[CreativeEntity]] = defaultdict(list)
        self.by_visual: dict[str, list[CreativeEntity]] = defaultdict(list)
        self.by_tier: dict[str, list[CreativeEntity]] = defaultdict(list)

        # Winners and losers
        self.winners: list[CreativeEntity] = []
        self.losers: list[CreativeEntity] = []
        self.neutrals: list[CreativeEntity] = []

        self._build()

    def _build(self) -> None:
        for e in self._entities:
            self.by_id[e.creative_id] = e

            # By hook type
            hook = e.dna.hook.type
            if hook:
                self.by_hook[hook].append(e)

            # By gameplay genre
            genre = e.dna.gameplay.genre
            if genre:
                self.by_gameplay[genre].append(e)

            # By reward type
            reward = e.dna.reward.type
            if reward:
                self.by_reward[reward].append(e)

            # By visual composition
            comp = e.dna.visual.composition
            if comp:
                self.by_visual[comp].append(e)

            # By tier
            if e.is_winner:
                self.winners.append(e)
                self.by_tier["winner"].append(e)
            elif e.performance.roas_d1 is not None and e.performance.roas_d1 > 0:
                self.losers.append(e)
                self.by_tier["loser"].append(e)
            else:
                self.neutrals.append(e)
                self.by_tier["neutral"].append(e)

        # Sort by ROAS
        self.by_roas = sorted(
            [e for e in self._entities if e.performance.roas_d1 is not None],
            key=lambda e: e.performance.roas_d1, reverse=True,
        )

    def get(self, creative_id: str) -> Optional[CreativeEntity]:
        return self.by_id.get(creative_id)

    def top_winners(self, n: int = 10) -> list[CreativeEntity]:
        return self.by_roas[:n]

    def top_losers(self, n: int = 10) -> list[CreativeEntity]:
        return sorted(self.losers, key=lambda e: e.performance.spend or 0, reverse=True)[:n]

    @property
    def total(self) -> int:
        return len(self._entities)

    @property
    def winner_count(self) -> int:
        return len(self.winners)

    @property
    def loser_count(self) -> int:
        return len(self.losers)

    def stats(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "winners": self.winner_count,
            "losers": self.loser_count,
            "neutrals": len(self.neutrals),
            "with_image": sum(1 for e in self._entities if e.has_image),
            "with_performance": sum(1 for e in self._entities if e.has_performance),
            "with_dna": sum(1 for e in self._entities if e.has_dna),
            "hook_types": len(self.by_hook),
            "reward_types": len(self.by_reward),
            "visual_types": len(self.by_visual),
        }


# ═══════════════════════════════════════════════════════════
# 2. WinnerPatternMiner
# ═══════════════════════════════════════════════════════════

@dataclass
class WinnerPattern:
    """A discovered winning creative pattern."""
    pattern_id: str = ""
    name: str = ""
    sample_count: int = 0
    sample_ids: list[str] = field(default_factory=list)

    avg_roas: float = 0.0
    avg_spend: float = 0.0
    avg_revenue: float = 0.0
    avg_ctr: float = 0.0
    avg_cvr: float = 0.0

    hook_type: str = ""
    reward_type: str = ""
    gameplay_genre: str = ""
    visual_composition: str = ""
    visual_color: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WinnerPatternMiner:
    """Discover winning patterns from CreativeEntityIndex.

    Patterns are identified by combining DNA dimensions
    (hook × reward × gameplay × visual) and ranked by performance.
    """

    MIN_SAMPLES = 3  # Minimum samples to form a pattern

    def __init__(self, index: CreativeEntityIndex) -> None:
        self.index = index

    def mine(self) -> list[WinnerPattern]:
        patterns: list[WinnerPattern] = []

        # Strategy 1: Hook × Reward patterns
        patterns.extend(self._mine_hook_reward())

        # Strategy 2: Hook × Visual composition
        patterns.extend(self._mine_hook_composition())

        # Strategy 3: Hook × Color
        patterns.extend(self._mine_hook_color())

        # Sort by avg_roas descending
        patterns.sort(key=lambda p: p.avg_roas, reverse=True)
        return patterns

    def _mine_hook_reward(self) -> list[WinnerPattern]:
        """Mine hook × reward combinations."""
        patterns = []
        groups: dict[str, list[CreativeEntity]] = defaultdict(list)

        for e in self.index._entities:
            if not e.performance.roas_d1:
                continue
            key = f"{e.dna.hook.type}×{e.dna.reward.type}"
            if e.dna.hook.type and e.dna.reward.type:
                groups[key].append(e)
            elif e.dna.hook.type:
                groups[e.dna.hook.type].append(e)

        for key, entities in groups.items():
            if len(entities) < self.MIN_SAMPLES:
                continue
            pattern = self._build_pattern(
                f"hook_reward_{key.replace('×', '_').replace(' ', '_')}",
                key,
                entities,
            )
            patterns.append(pattern)

        return patterns

    def _mine_hook_composition(self) -> list[WinnerPattern]:
        """Mine hook × visual composition patterns."""
        patterns = []
        groups: dict[str, list[CreativeEntity]] = defaultdict(list)

        for e in self.index._entities:
            if not e.performance.roas_d1:
                continue
            if e.dna.hook.type and e.dna.visual.composition:
                key = f"{e.dna.hook.type}×{e.dna.visual.composition}"
                groups[key].append(e)

        for key, entities in groups.items():
            if len(entities) < self.MIN_SAMPLES:
                continue
            pattern = self._build_pattern(
                f"hook_comp_{key.replace('×', '_')}",
                key,
                entities,
            )
            patterns.append(pattern)

        return patterns

    def _mine_hook_color(self) -> list[WinnerPattern]:
        """Mine hook × color palette patterns."""
        patterns = []
        groups: dict[str, list[CreativeEntity]] = defaultdict(list)

        for e in self.index._entities:
            if not e.performance.roas_d1:
                continue
            if e.dna.hook.type and e.dna.visual.color:
                key = f"{e.dna.hook.type}×{e.dna.visual.color}"
                groups[key].append(e)

        for key, entities in groups.items():
            if len(entities) < self.MIN_SAMPLES:
                continue
            pattern = self._build_pattern(
                f"hook_color_{key.replace('×', '_')}",
                key,
                entities,
            )
            patterns.append(pattern)

        return patterns

    def _build_pattern(self, pattern_id: str, name: str,
                       entities: list[CreativeEntity]) -> WinnerPattern:
        roas_vals = [e.performance.roas_d1 for e in entities if e.performance.roas_d1]
        spend_vals = [e.performance.spend for e in entities if e.performance.spend]
        revenue_vals = [e.performance.revenue for e in entities if e.performance.revenue]
        ctr_vals = [e.performance.ctr for e in entities if e.performance.ctr]

        return WinnerPattern(
            pattern_id=pattern_id,
            name=name,
            sample_count=len(entities),
            sample_ids=[e.creative_id for e in entities[:5]],
            avg_roas=sum(roas_vals) / len(roas_vals) if roas_vals else 0,
            avg_spend=sum(spend_vals) / len(spend_vals) if spend_vals else 0,
            avg_revenue=sum(revenue_vals) / len(revenue_vals) if revenue_vals else 0,
            avg_ctr=sum(ctr_vals) / len(ctr_vals) if ctr_vals else 0,
            avg_cvr=0,
            hook_type=entities[0].dna.hook.type,
            reward_type=entities[0].dna.reward.type,
            gameplay_genre=entities[0].dna.gameplay.genre,
            visual_composition=entities[0].dna.visual.composition,
            visual_color=entities[0].dna.visual.color,
        )


# ═══════════════════════════════════════════════════════════
# 3. DNA Performance Correlation
# ═══════════════════════════════════════════════════════════

@dataclass
class DNACorrelation:
    """Correlation between a DNA dimension and performance."""
    dimension: str = ""
    value: str = ""
    sample_count: int = 0
    avg_roas: float = 0.0
    avg_spend: float = 0.0
    avg_revenue: float = 0.0
    winner_rate: float = 0.0  # % of samples that are winners (ROAS > 1)


class DNAPerformanceCorrelation:
    """Analyze which DNA dimensions correlate with performance."""

    MIN_SAMPLES = 3

    def __init__(self, index: CreativeEntityIndex) -> None:
        self.index = index

    def analyze(self) -> dict[str, list[DNACorrelation]]:
        """Run full correlation analysis across all DNA dimensions."""
        return {
            "hook": self._analyze_hook(),
            "reward": self._analyze_reward(),
            "visual_composition": self._analyze_composition(),
            "visual_color": self._analyze_color(),
            "gameplay": self._analyze_gameplay(),
        }

    def _analyze_hook(self) -> list[DNACorrelation]:
        return self._correlate("hook", self.index.by_hook, lambda e: e.dna.hook.type)

    def _analyze_reward(self) -> list[DNACorrelation]:
        return self._correlate("reward", self.index.by_reward, lambda e: e.dna.reward.type)

    def _analyze_composition(self) -> list[DNACorrelation]:
        return self._correlate("composition", self.index.by_visual, lambda e: e.dna.visual.composition)

    def _analyze_color(self) -> list[DNACorrelation]:
        by_color: dict[str, list[CreativeEntity]] = defaultdict(list)
        for e in self.index._entities:
            if e.dna.visual.color:
                by_color[e.dna.visual.color].append(e)
        return self._correlate("color", by_color, lambda e: e.dna.visual.color)

    def _analyze_gameplay(self) -> list[DNACorrelation]:
        return self._correlate("gameplay", self.index.by_gameplay, lambda e: e.dna.gameplay.genre)

    def _correlate(self, dimension: str, groups: dict[str, list[CreativeEntity]],
                   _key_fn) -> list[DNACorrelation]:
        results = []
        for value, entities in groups.items():
            if len(entities) < self.MIN_SAMPLES:
                continue

            has_roas = [e for e in entities if e.performance.roas_d1]
            roas_vals = [e.performance.roas_d1 for e in has_roas]
            spend_vals = [e.performance.spend for e in entities if e.performance.spend]
            revenue_vals = [e.performance.revenue for e in entities if e.performance.revenue]
            winner_count = sum(1 for e in entities if e.is_winner)

            results.append(DNACorrelation(
                dimension=dimension,
                value=value,
                sample_count=len(entities),
                avg_roas=sum(roas_vals) / len(roas_vals) if roas_vals else 0,
                avg_spend=sum(spend_vals) / len(spend_vals) if spend_vals else 0,
                avg_revenue=sum(revenue_vals) / len(revenue_vals) if revenue_vals else 0,
                winner_rate=winner_count / len(entities) if entities else 0,
            ))

        results.sort(key=lambda r: r.avg_roas, reverse=True)
        return results


# ═══════════════════════════════════════════════════════════
# 4. CreativeDecisionScore
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeDecisionScore:
    """Performance-grounded creative score. NOT CLIP-based."""
    creative_id: str = ""
    total_score: float = 0.0
    performance_score: float = 0.0
    hook_score: float = 0.0
    gameplay_score: float = 0.0
    reward_score: float = 0.0
    visual_score: float = 0.0
    reasons: list[str] = field(default_factory=list)


class CreativeDecisionScorer:
    """Score creatives based on performance data, not CLIP."""

    # Weights
    W_PERFORMANCE = 0.35
    W_HOOK = 0.25
    W_GAMEPLAY = 0.20
    W_REWARD = 0.10
    W_VISUAL = 0.10

    def __init__(self, index: CreativeEntityIndex) -> None:
        self.index = index
        self._hook_roas = self._build_dimension_roas(index.by_hook)
        self._reward_roas = self._build_dimension_roas(index.by_reward)
        self._comp_roas = self._build_dimension_roas(index.by_visual)

    def _build_dimension_roas(self, groups: dict[str, list[CreativeEntity]]) -> dict[str, float]:
        result = {}
        for key, entities in groups.items():
            roas_vals = [e.performance.roas_d1 for e in entities if e.performance.roas_d1]
            if roas_vals:
                result[key] = sum(roas_vals) / len(roas_vals)
        return result

    def score(self, entity: CreativeEntity) -> CreativeDecisionScore:
        reasons = []

        # Performance score (0-1)
        perf_score = 0.0
        if entity.performance.roas_d1 is not None:
            perf_score = min(entity.performance.roas_d1 / 3.0, 1.0)
            if entity.performance.roas_d1 > 1.5:
                reasons.append(f"High ROAS ({entity.performance.roas_d1:.2f})")

        # Hook score (0-1)
        hook_score = 0.0
        hook = entity.dna.hook.type
        if hook and hook in self._hook_roas:
            hook_roas = self._hook_roas[hook]
            hook_score = min(hook_roas / 2.0, 1.0)
            if hook_roas > 1.0:
                reasons.append(f"Strong hook pattern: {hook}")

        # Gameplay score (0-1)
        gameplay_score = 0.0
        genre = entity.dna.gameplay.genre
        if genre and genre in self._reward_roas:
            genre_roas = self._reward_roas.get(genre, 0)
            gameplay_score = min(genre_roas / 2.0, 1.0)

        # Reward score (0-1)
        reward_score = 0.0
        reward = entity.dna.reward.type
        if reward and reward in self._reward_roas:
            reward_roas = self._reward_roas[reward]
            reward_score = min(reward_roas / 2.0, 1.0)

        # Visual score (0-1)
        visual_score = 0.0
        comp = entity.dna.visual.composition
        if comp and comp in self._comp_roas:
            comp_roas = self._comp_roas[comp]
            visual_score = min(comp_roas / 2.0, 1.0)

        total = (
            self.W_PERFORMANCE * perf_score +
            self.W_HOOK * hook_score +
            self.W_GAMEPLAY * gameplay_score +
            self.W_REWARD * reward_score +
            self.W_VISUAL * visual_score
        )

        if not reasons:
            reasons.append("Baseline creative")

        return CreativeDecisionScore(
            creative_id=entity.creative_id,
            total_score=round(total, 3),
            performance_score=round(perf_score, 3),
            hook_score=round(hook_score, 3),
            gameplay_score=round(gameplay_score, 3),
            reward_score=round(reward_score, 3),
            visual_score=round(visual_score, 3),
            reasons=reasons,
        )

    def score_all(self) -> list[CreativeDecisionScore]:
        scores = []
        for e in self.index._entities:
            scores.append(self.score(e))
        scores.sort(key=lambda s: s.total_score, reverse=True)
        return scores


# ═══════════════════════════════════════════════════════════
# 5. CreativeBlueprint
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeBlueprint:
    """Generation Input Contract for Phase 2 Gameplay Generator.

    This is the ONLY input the Gameplay Generator should accept.
    It does NOT contain raw images — only structured DNA instructions.
    """

    source_creative_id: str = ""
    hook_pattern: str = ""
    gameplay_pattern: str = ""
    reward_pattern: str = ""
    visual_style: str = ""
    visual_color: str = ""
    target_dimension: str = "1080x1080"
    generation_reason: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_entity(cls, entity: CreativeEntity) -> "CreativeBlueprint":
        return cls(
            source_creative_id=entity.creative_id,
            hook_pattern=entity.dna.hook.type,
            gameplay_pattern=entity.dna.gameplay.genre,
            reward_pattern=entity.dna.reward.type,
            visual_style=entity.dna.visual.composition,
            visual_color=entity.dna.visual.color,
            target_dimension="1080x1080",
            generation_reason=(
                f"Top ROAS={entity.performance.roas_d1:.2f}"
                if entity.performance.roas_d1
                else "Pattern-based generation"
            ),
        )

    @classmethod
    def from_pattern(cls, pattern: WinnerPattern) -> "CreativeBlueprint":
        return cls(
            source_creative_id=pattern.sample_ids[0] if pattern.sample_ids else "",
            hook_pattern=pattern.hook_type,
            gameplay_pattern=pattern.gameplay_genre,
            reward_pattern=pattern.reward_type,
            visual_style=pattern.visual_composition,
            visual_color=pattern.visual_color,
            target_dimension="1080x1080",
            generation_reason=f"Top pattern: {pattern.name} (avg ROAS={pattern.avg_roas:.2f}, n={pattern.sample_count})",
        )