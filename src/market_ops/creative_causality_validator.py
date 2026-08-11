"""Phase 1.4: Creative Causality Validation Layer.

Validates that discovered patterns have genuine production value,
not just survivorship bias or sample-size artifacts.

Answers:
  1. Is high ROAS really from DNA, or just small sample size?
  2. Which factors should enter AI Creative Generator?
  3. Which factors are only surface correlations?
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from typing import Any, Optional

from .creative_entity_v2 import CreativeEntity
from .creative_validation_layer import (
    CreativeEntityIndex, WinnerPatternMiner, WinnerPattern,
    DNAPerformanceCorrelation, DNACorrelation,
)


# ═══════════════════════════════════════════════════════════
# 1. PatternConfidenceAnalyzer
# ═══════════════════════════════════════════════════════════

@dataclass
class PatternConfidence:
    """Confidence score for a pattern's production value."""
    pattern_name: str = ""
    sample_size: int = 0
    avg_roas: float = 0.0
    confidence: float = 0.0  # 0-1
    lift_vs_global: float = 0.0  # pattern_roas / global_roas
    variance: float = 0.0
    recommendation: str = ""  # USE / TEST / SKIP
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PatternConfidenceAnalyzer:
    """Analyzes pattern confidence using sample size, lift, and variance.

    Confidence = f(sample_size, lift, variance)
    - Small samples with high ROAS → low confidence (could be luck)
    - Large samples with moderate ROAS → high confidence (proven)
    """

    MIN_SAMPLE_SIZE = 5
    MIN_LIFT = 1.02  # 2% above global average

    def __init__(self, global_avg_roas: float, global_roas_std: float) -> None:
        self.global_avg_roas = global_avg_roas
        self.global_roas_std = global_roas_std

    def analyze(self, patterns: list[WinnerPattern]) -> list[PatternConfidence]:
        results = []
        for p in patterns:
            if p.sample_count < 3:
                continue
            results.append(self._analyze_one(p))
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def _analyze_one(self, p: WinnerPattern) -> PatternConfidence:
        # 1. Sample size weight (0-1)
        sample_weight = min(p.sample_count / max(self.MIN_SAMPLE_SIZE, 1), 1.0)
        sample_weight = 1.0 / (1.0 + math.exp(-3 * (sample_weight - 0.5)))  # sigmoid

        # 2. ROAS lift
        lift = p.avg_roas / self.global_avg_roas if self.global_avg_roas > 0 else 1.0
        lift_weight = min(lift / 2.0, 1.0)

        # 3. Variance penalty
        # Small samples with high ROAS = high variance = low confidence
        variance_factor = 1.0 / (1.0 + 2.0 / max(p.sample_count, 1))

        # Composite confidence
        confidence = 0.4 * sample_weight + 0.40 * lift_weight + 0.20 * variance_factor

        # Recommendation
        reasons = []
        if p.sample_count < self.MIN_SAMPLE_SIZE:
            reasons.append(f"Small sample (n={p.sample_count})")
        if lift < self.MIN_LIFT:
            reasons.append(f"Low lift ({lift:.2f}x)")
        if lift > 1.5:
            reasons.append(f"Strong lift ({lift:.2f}x)")
        if p.sample_count >= 10:
            reasons.append(f"Large sample (n={p.sample_count})")

        if confidence >= 0.7:
            recommendation = "USE"
        elif confidence >= 0.5:
            recommendation = "TEST"
        else:
            recommendation = "SKIP"
            reasons.append("Insufficient evidence")

        if not reasons:
            reasons.append(f"Moderate confidence ({confidence:.2f})")

        return PatternConfidence(
            pattern_name=p.name,
            sample_size=p.sample_count,
            avg_roas=p.avg_roas,
            confidence=round(confidence, 3),
            lift_vs_global=round(lift, 2),
            variance=round(1.0 - variance_factor, 3),
            recommendation=recommendation,
            reasons=reasons,
        )


# ═══════════════════════════════════════════════════════════
# 2. Winner vs Loser Contrast
# ═══════════════════════════════════════════════════════════

@dataclass
class DNAContrast:
    """Winner vs Loser contrast for a DNA dimension value."""
    dimension: str = ""
    value: str = ""
    winner_count: int = 0
    loser_count: int = 0
    winner_rate: float = 0.0  # % of winners that have this value
    loser_rate: float = 0.0   # % of losers that have this value
    odds_ratio: float = 0.0   # winner_rate / loser_rate
    is_significant: bool = False
    verdict: str = ""  # EFFECTIVE / NEUTRAL / NEGATIVE


class WinnerVsLoserContrast:
    """Compare DNA distributions between winners and losers.

    A DNA dimension is "effective" if winners have it significantly
    more often than losers — not just because it's common overall.
    """

    SIGNIFICANCE_THRESHOLD = 1.2  # odds_ratio > 1.2 = significant

    def __init__(self, index: CreativeEntityIndex) -> None:
        self.index = index
        self.total_winners = index.winner_count
        self.total_losers = index.loser_count

    def analyze(self) -> dict[str, list[DNAContrast]]:
        """Run contrast analysis across all DNA dimensions."""
        return {
            "hook": self._contrast_hook(),
            "composition": self._contrast_composition(),
            "color": self._contrast_color(),
        }

    def _contrast_hook(self) -> list[DNAContrast]:
        return self._contrast_dimension(
            "hook", self.index.by_hook,
            lambda e: e.dna.hook.type,
        )

    def _contrast_composition(self) -> list[DNAContrast]:
        return self._contrast_dimension(
            "composition", self.index.by_visual,
            lambda e: e.dna.visual.composition,
        )

    def _contrast_color(self) -> list[DNAContrast]:
        by_color: dict[str, list[CreativeEntity]] = defaultdict(list)
        for e in self.index._entities:
            if e.dna.visual.color:
                by_color[e.dna.visual.color].append(e)
        return self._contrast_dimension(
            "color", by_color,
            lambda e: e.dna.visual.color,
        )

    def _contrast_dimension(self, dim: str,
                            groups: dict[str, list[CreativeEntity]],
                            _key_fn) -> list[DNAContrast]:
        results = []
        for value, entities in groups.items():
            if len(entities) < 3:
                continue

            winner_count = sum(1 for e in entities if e.is_winner)
            loser_count = sum(1 for e in entities if not e.is_winner and e.performance.roas_d1 is not None and e.performance.roas_d1 > 0)

            winner_rate = winner_count / max(self.total_winners, 1)
            loser_rate = loser_count / max(self.total_losers, 1)
            odds_ratio = winner_rate / max(loser_rate, 0.001)

            is_sig = odds_ratio > self.SIGNIFICANCE_THRESHOLD

            if is_sig:
                verdict = "EFFECTIVE"
            elif odds_ratio > 0.8:
                verdict = "NEUTRAL"
            else:
                verdict = "NEGATIVE"

            results.append(DNAContrast(
                dimension=dim,
                value=value,
                winner_count=winner_count,
                loser_count=loser_count,
                winner_rate=round(winner_rate, 3),
                loser_rate=round(loser_rate, 3),
                odds_ratio=round(odds_ratio, 2),
                is_significant=is_sig,
                verdict=verdict,
            ))

        results.sort(key=lambda r: r.odds_ratio, reverse=True)
        return results


# ═══════════════════════════════════════════════════════════
# 3. DNAImpactScore
# ═══════════════════════════════════════════════════════════

@dataclass
class DNAImpactScore:
    """Combined impact score for a DNA dimension value."""
    dna_dimension: str = ""
    dna_value: str = ""
    impact_score: float = 0.0  # 0-1
    roas_lift: float = 0.0
    confidence: float = 0.0
    sample_weight: float = 0.0
    contrast_odds: float = 0.0
    decision: str = ""  # GENERATE / TEST / SKIP


class DNAImpactScorer:
    """Combine lift, confidence, sample size, and contrast into one impact score.

    Impact = 0.35 * ROAS_Lift + 0.25 * Confidence + 0.20 * Sample_Weight + 0.20 * Contrast_Odds
    """

    def __init__(self, global_avg_roas: float) -> None:
        self.global_avg_roas = global_avg_roas

    def score(self, confidences: list[PatternConfidence],
              contrasts: dict[str, list[DNAContrast]]) -> list[DNAImpactScore]:
        scores = []

        # Build contrast lookup
        contrast_map: dict[str, DNAContrast] = {}
        for dim_contrasts in contrasts.values():
            for c in dim_contrasts:
                contrast_map[f"{c.dimension}:{c.value}"] = c

        for pc in confidences:
            # Extract dimension and value from pattern name
            # Pattern names like "character_showcase×center" or "character_showcase"
            parts = pc.pattern_name.split("×")

            for part in parts:
                # Find matching contrast
                contrast = None
                for key, c in contrast_map.items():
                    if c.value == part:
                        contrast = c
                        break

                odds = contrast.odds_ratio if contrast else 1.0
                odds_norm = min(odds / 2.0, 1.0)

                lift_norm = min(pc.lift_vs_global / 2.0, 1.0)
                sample_norm = min(pc.sample_size / 20.0, 1.0)

                impact = (
                    0.35 * lift_norm +
                    0.25 * pc.confidence +
                    0.20 * sample_norm +
                    0.20 * odds_norm
                )

                if impact >= 0.7:
                    decision = "GENERATE"
                elif impact >= 0.5:
                    decision = "TEST"
                else:
                    decision = "SKIP"

                scores.append(DNAImpactScore(
                    dna_dimension=contrast.dimension if contrast else "unknown",
                    dna_value=part,
                    impact_score=round(impact, 3),
                    roas_lift=round(lift_norm, 3),
                    confidence=round(pc.confidence, 3),
                    sample_weight=round(sample_norm, 3),
                    contrast_odds=round(odds_norm, 3),
                    decision=decision,
                ))

        # Deduplicate by dna_value, keep highest impact
        seen = {}
        for s in scores:
            if s.dna_value not in seen or s.impact_score > seen[s.dna_value].impact_score:
                seen[s.dna_value] = s

        scores = list(seen.values())
        scores.sort(key=lambda s: s.impact_score, reverse=True)
        return scores


# ═══════════════════════════════════════════════════════════
# 4. CreativeBlueprintV2
# ═══════════════════════════════════════════════════════════

@dataclass
class GameplayRequirement:
    need_character: bool = False
    need_progression: bool = False
    need_reward_visible: bool = False
    need_merge_board: bool = False
    need_ui_elements: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class VisualRequirement:
    composition: str = ""
    color: str = ""
    brightness: str = ""
    contrast: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class CreativeBlueprintV2:
    """Upgraded generation input contract with confidence scores.

    AI Creative Generator should ONLY accept this, not raw images.
    """

    source_pattern: str = ""
    confidence: float = 0.0
    impact_score: float = 0.0
    gameplay_requirement: GameplayRequirement = field(default_factory=GameplayRequirement)
    visual_requirement: VisualRequirement = field(default_factory=VisualRequirement)
    generation_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_pattern": self.source_pattern,
            "confidence": self.confidence,
            "impact_score": self.impact_score,
            "gameplay_requirement": self.gameplay_requirement.to_dict(),
            "visual_requirement": self.visual_requirement.to_dict(),
            "generation_reason": self.generation_reason,
        }


# ═══════════════════════════════════════════════════════════
# 5. ProductionRules
# ═══════════════════════════════════════════════════════════

@dataclass
class ProductionRules:
    """Validated production rules for a game project."""
    project: str = ""
    preferred_hooks: list[str] = field(default_factory=list)
    preferred_layouts: list[str] = field(default_factory=list)
    preferred_colors: list[str] = field(default_factory=list)
    preferred_rewards: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_impact_scores(cls, project: str,
                           scores: list[DNAImpactScore],
                           contrasts: dict[str, list[DNAContrast]]) -> "ProductionRules":
        rules = cls(project=project)

        for s in scores:
            if s.decision == "GENERATE":
                if s.dna_dimension == "hook":
                    rules.preferred_hooks.append(s.dna_value)
                elif s.dna_dimension == "composition":
                    rules.preferred_layouts.append(s.dna_value)
                elif s.dna_dimension == "color":
                    rules.preferred_colors.append(s.dna_value)

            if s.decision == "GENERATE":
                rules.rules.append({
                    "rule_id": f"RULE_{len(rules.rules)+1:03d}",
                    "dimension": s.dna_dimension,
                    "value": s.dna_value,
                    "impact_score": s.impact_score,
                    "confidence": s.confidence,
                    "decision": s.decision,
                })

        # Find patterns to avoid
        for dim_contrasts in contrasts.values():
            for c in dim_contrasts:
                if c.verdict == "NEGATIVE" and c.value not in rules.avoid:
                    rules.avoid.append(c.value)

        return rules

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionRules":
        """Reconstruct from a JSON dict (e.g., creative_rules.json)."""
        return cls(
            project=data.get("project", ""),
            preferred_hooks=data.get("preferred_hooks", []),
            preferred_layouts=data.get("preferred_layouts", []),
            preferred_colors=data.get("preferred_colors", []),
            preferred_rewards=data.get("preferred_rewards", []),
            avoid=data.get("avoid", []),
            rules=data.get("rules", []),
        )