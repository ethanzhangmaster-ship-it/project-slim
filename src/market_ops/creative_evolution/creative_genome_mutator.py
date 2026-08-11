"""E9.8: Creative Genome Mutator — Core mutation engine.

Applies mutation strategies to winner DNA to generate new CreativeGenome candidates.

Input:  Winner DNA + Mutation Strategies + Failure Avoidance
Output: Multiple CreativeGenome candidates with mutation records
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from itertools import product
from typing import Any

from market_ops.creative_evolution.schemas import (
    CreativeGenome, MutationRecord, MutationStrategy,
    WinnerPattern, FailureAnalysis,
)


class CreativeGenomeMutator:
    """Core mutation engine that generates new CreativeGenome candidates.

    Usage:
        mutator = CreativeGenomeMutator()
        candidates = mutator.mutate(
            winner_dnas, strategies, failure_analysis,
        )
    """

    # All possible values for each dimension
    HOOK_SPACE = [
        "emotional", "challenge", "secret", "curiosity",
        "collection", "progression", "competition",
    ]
    REWARD_SPACE = [
        "discovery", "unlock", "collection", "upgrade",
        "rare", "power_up", "progression",
    ]
    VISUAL_SPACE = ["2d_flat", "3d_cartoon", "3d_realistic", "pixel_art", "minimalist"]
    FANTASY_SPACE = [
        "become_powerful", "discovery_world", "collect_dragons",
        "build_kingdom", "rescue_princess", "solve_mystery",
    ]
    ARCHETYPE_SPACE = ["power", "collector", "explorer", "progression", "casual"]

    def __init__(self) -> None:
        self._generation_counter = 0

    # ── Main Mutation ─────────────────────────────────────

    def mutate(
        self,
        winner_dnas: list[dict[str, Any]],
        strategies: list[MutationStrategy],
        failure_analysis: FailureAnalysis,
        max_candidates: int = 2000,
    ) -> list[tuple[CreativeGenome, list[MutationRecord]]]:
        """Generate new CreativeGenome candidates via mutation.

        Args:
            winner_dnas: Winner DNA entries (templates)
            strategies: Mutation strategies to apply
            failure_analysis: What to avoid
            max_candidates: Maximum number of candidates

        Returns:
            List of (genome, mutations) tuples
        """
        self._generation_counter += 1
        candidates: list[tuple[CreativeGenome, list[MutationRecord]]] = []
        now = datetime.now(timezone.utc).isoformat()

        # Build avoidance set
        avoid_hooks = set(failure_analysis.avoid_hooks)
        avoid_rewards = set(failure_analysis.avoid_rewards)
        avoid_visuals = set(failure_analysis.avoid_visuals)

        # Group strategies by dimension
        strategies_by_dim: dict[str, list[MutationStrategy]] = {}
        for s in strategies:
            strategies_by_dim.setdefault(s.dimension, []).append(s)

        # For each winner DNA as template
        for parent_dna in winner_dnas[:50]:  # Cap at 50 templates
            parent_id = parent_dna.get("creative_id", "unknown")

            # Extract current values
            current = {
                "hook": (parent_dna.get("hook", {}) or {}).get("type", "emotional"),
                "reward": (parent_dna.get("reward", {}) or {}).get("type", "discovery"),
                "visual": (parent_dna.get("visual", {}) or {}).get("style", "2d_flat"),
                "fantasy": (parent_dna.get("fantasy", {}) or {}).get("drives", ["become_powerful"]) or ["become_powerful"],
                "mechanism": (parent_dna.get("mechanism", {}) or {}).get("type", "merge"),
            }

            # ── Hook mutations: try ALL alternative hook values ──
            for alt_hook in self.HOOK_SPACE:
                if alt_hook == current["hook"]:
                    continue
                if alt_hook in avoid_hooks:
                    continue
                s = self._find_strategy(strategies_by_dim, "hook", alt_hook)
                genome = self._create_genome(parent_id, current, "hook", current["hook"], alt_hook, s, now)
                genome.hook = alt_hook
                mutation = MutationRecord(
                    parent_genome_id=parent_id, mutation_type="hook", dimension="hook",
                    before=current["hook"], after=alt_hook,
                    strategy=s.strategy_type if s else "exploration",
                    confidence=s.weight if s else 0.3,
                )
                candidates.append((genome, [mutation]))

            # ── Reward mutations: try ALL alternative reward values ──
            for alt_reward in self.REWARD_SPACE:
                if alt_reward == current["reward"]:
                    continue
                if alt_reward in avoid_rewards:
                    continue
                s = self._find_strategy(strategies_by_dim, "reward", alt_reward)
                genome = self._create_genome(parent_id, current, "reward", current["reward"], alt_reward, s, now)
                genome.reward = alt_reward
                mutation = MutationRecord(
                    parent_genome_id=parent_id, mutation_type="reward", dimension="reward",
                    before=current["reward"], after=alt_reward,
                    strategy=s.strategy_type if s else "exploration",
                    confidence=s.weight if s else 0.3,
                )
                candidates.append((genome, [mutation]))

            # ── Visual mutations: try ALL alternative visual values ──
            for alt_visual in self.VISUAL_SPACE:
                if alt_visual == current["visual"]:
                    continue
                if alt_visual in avoid_visuals:
                    continue
                s = self._find_strategy(strategies_by_dim, "visual", alt_visual)
                genome = self._create_genome(parent_id, current, "visual", current["visual"], alt_visual, s, now)
                genome.visual_style = alt_visual
                mutation = MutationRecord(
                    parent_genome_id=parent_id, mutation_type="visual", dimension="visual",
                    before=current["visual"], after=alt_visual,
                    strategy=s.strategy_type if s else "exploration",
                    confidence=s.weight if s else 0.3,
                )
                candidates.append((genome, [mutation]))

            # ── Fantasy mutations: try ALL alternative fantasy values ──
            cur_fantasy = current["fantasy"][0] if current["fantasy"] else ""
            for alt_fantasy in self.FANTASY_SPACE:
                if alt_fantasy in current["fantasy"]:
                    continue
                s = self._find_strategy(strategies_by_dim, "fantasy", alt_fantasy)
                genome = self._create_genome(parent_id, current, "fantasy", cur_fantasy, alt_fantasy, s, now)
                genome.fantasy = alt_fantasy
                mutation = MutationRecord(
                    parent_genome_id=parent_id, mutation_type="fantasy", dimension="fantasy",
                    before=cur_fantasy, after=alt_fantasy,
                    strategy=s.strategy_type if s else "exploration",
                    confidence=s.weight if s else 0.3,
                )
                candidates.append((genome, [mutation]))

            # ── Multi-dimension mutations (hook + reward combos) ──
            for h_val in self.HOOK_SPACE[1:4]:  # Skip emotional, try challenge/secret/curiosity
                if h_val in avoid_hooks:
                    continue
                for r_val in self.REWARD_SPACE[1:4]:  # Skip discovery, try unlock/collection/upgrade
                    if r_val in avoid_rewards:
                        continue
                    if h_val == current["hook"] and r_val == current["reward"]:
                        continue

                    hs = self._find_strategy(strategies_by_dim, "hook", h_val)
                    rs = self._find_strategy(strategies_by_dim, "reward", r_val)
                    genome = self._create_genome(parent_id, current, "hook+reward",
                        f"{current['hook']}+{current['reward']}", f"{h_val}+{r_val}", hs, now)
                    genome.hook = h_val
                    genome.reward = r_val
                    mutations = [
                        MutationRecord(parent_genome_id=parent_id, mutation_type="hook",
                            dimension="hook", before=current["hook"], after=h_val,
                            strategy=hs.strategy_type if hs else "exploration",
                            confidence=hs.weight if hs else 0.3),
                        MutationRecord(parent_genome_id=parent_id, mutation_type="reward",
                            dimension="reward", before=current["reward"], after=r_val,
                            strategy=rs.strategy_type if rs else "exploration",
                            confidence=rs.weight if rs else 0.3),
                    ]
                    candidates.append((genome, mutations))

            # ── Archetype targeting mutations ──
            for target_arch in self.ARCHETYPE_SPACE:
                if target_arch == "collector":  # Already predicting collector mostly
                    continue
                s = self._find_strategy(strategies_by_dim, "archetype", target_arch)
                genome = self._create_genome(parent_id, current, "archetype",
                    "collector", target_arch, s, now)
                genome.target_archetype = target_arch
                mutation = MutationRecord(
                    parent_genome_id=parent_id, mutation_type="archetype",
                    dimension="archetype",
                    before="collector", after=target_arch,
                    strategy=s.strategy_type if s else "exploration",
                    confidence=s.weight if s else 0.25,
                )
                candidates.append((genome, [mutation]))

            if len(candidates) >= max_candidates:
                break

        return candidates[:max_candidates]

    # ── Genome Factory ─────────────────────────────────────

    def _create_genome(
        self,
        parent_id: str,
        current: dict[str, Any],
        mutation_type: str,
        before: str,
        after: str,
        strategy: MutationStrategy,
        timestamp: str,
    ) -> CreativeGenome:
        """Create a new CreativeGenome with deterministic ID."""
        genome_id = self._generate_genome_id(
            parent_id, mutation_type, before, after,
            self._generation_counter,
        )

        return CreativeGenome(
            genome_id=genome_id,
            generation=self._generation_counter,
            hook=current["hook"],
            mechanism=current.get("mechanism", "merge"),
            reward=current["reward"],
            fantasy=current["fantasy"][0] if isinstance(current.get("fantasy"), list) and current["fantasy"] else str(current.get("fantasy", "")),
            visual_style=current["visual"],
            parent_genome_id=parent_id,
            mutation_type=mutation_type,
            created_at=timestamp,
            mutation_round=self._generation_counter,
        )

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _find_strategy(
        strategies_by_dim: dict[str, list[MutationStrategy]],
        dimension: str,
        target_value: str,
    ) -> MutationStrategy | None:
        """Find a strategy that targets the given dimension+value."""
        for s in strategies_by_dim.get(dimension, []):
            if target_value in s.to_values:
                return s
        return None

    # ── ID Generation ──────────────────────────────────────

    @staticmethod
    def _generate_genome_id(
        parent_id: str,
        mutation_type: str,
        before: str,
        after: str,
        generation: int,
    ) -> str:
        """Generate deterministic genome ID using SHA256."""
        seed = f"{parent_id}|{mutation_type}|{before}|{after}|gen{generation}"
        hash_val = hashlib.sha256(seed.encode()).hexdigest()[:12]
        return f"G{generation:03d}_{hash_val}"