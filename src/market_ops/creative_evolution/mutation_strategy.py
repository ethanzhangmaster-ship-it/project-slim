"""E9.8: Mutation Strategy Engine — Decides what and how to mutate.

Generates mutation strategies based on:
  - Winner DNA patterns (emulate winners)
  - Failure DNA patterns (avoid losers)
  - Exploration (try new combinations)

5 mutation categories:
  1. Hook Mutation: change hook type
  2. Reward Mutation: change reward type
  3. Visual Mutation: change visual style
  4. Fantasy Mutation: change fantasy drive
  5. Archetype Mutation: target different player archetype
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_evolution.schemas import (
    WinnerPattern, FailureAnalysis, MutationStrategy,
)


# ═══════════════════════════════════════════════════════════
# Value Spaces (what each dimension can mutate to)
# ═══════════════════════════════════════════════════════════

HOOK_VALUES = [
    "emotional", "challenge", "secret", "curiosity",
    "collection", "progression", "competition",
]

REWARD_VALUES = [
    "discovery", "unlock", "collection", "upgrade",
    "rare", "power_up", "progression",
]

VISUAL_VALUES = [
    "2d_flat", "3d_cartoon", "3d_realistic",
    "pixel_art", "minimalist",
]

FANTASY_VALUES = [
    "become_powerful", "discovery_world", "collect_dragons",
    "build_kingdom", "rescue_princess", "solve_mystery",
]

ARCHETYPE_VALUES = [
    "power", "collector", "explorer", "progression", "casual",
]


# ═══════════════════════════════════════════════════════════
# Strategy Engine
# ═══════════════════════════════════════════════════════════

class MutationStrategyEngine:
    """Generates mutation strategies based on winner/failure analysis.

    Usage:
        engine = MutationStrategyEngine()
        strategies = engine.generate(winner_pattern, failure_analysis)
    """

    def generate(
        self,
        winner_pattern: WinnerPattern,
        failure_analysis: FailureAnalysis,
        existing_dna_values: dict[str, set[str]] | None = None,
    ) -> list[MutationStrategy]:
        """Generate all mutation strategies.

        Args:
            winner_pattern: Aggregated winner DNA patterns
            failure_analysis: Identified failure patterns
            existing_dna_values: {dimension: {existing_values}} for novelty

        Returns:
            List of MutationStrategy objects
        """
        strategies: list[MutationStrategy] = []

        # ── Strategy 1: Winner Emulation ──────────────────
        strategies.extend(self._winner_emulation(winner_pattern))

        # ── Strategy 2: Failure Avoidance ─────────────────
        strategies.extend(self._failure_avoidance(failure_analysis))

        # ── Strategy 3: Exploration ───────────────────────
        strategies.extend(self._exploration(existing_dna_values or {}))

        # ── Strategy 4: Archetype Targeting ───────────────
        strategies.extend(self._archetype_targeting(winner_pattern))

        return strategies

    # ── Winner Emulation ──────────────────────────────────

    def _winner_emulation(self, wp: WinnerPattern) -> list[MutationStrategy]:
        """Generate strategies to emulate winner DNA patterns."""
        strategies = []

        # Hook: push towards winner hooks
        for hook_entry in wp.top_hooks[:3]:
            winner_val = hook_entry["value"]
            for other_val in HOOK_VALUES:
                if other_val != winner_val:
                    strategies.append(MutationStrategy(
                        strategy_type="winner_emulation",
                        dimension="hook",
                        from_value=other_val,
                        to_values=[winner_val],
                        weight=hook_entry["pct"] / 100 * 0.8,
                        reason=f"Top winner hook '{winner_val}' ({hook_entry['pct']}% of winners)",
                    ))

        # Reward: push towards winner rewards
        for reward_entry in wp.top_rewards[:3]:
            winner_val = reward_entry["value"]
            for other_val in REWARD_VALUES:
                if other_val != winner_val:
                    strategies.append(MutationStrategy(
                        strategy_type="winner_emulation",
                        dimension="reward",
                        from_value=other_val,
                        to_values=[winner_val],
                        weight=reward_entry["pct"] / 100 * 0.8,
                        reason=f"Top winner reward '{winner_val}' ({reward_entry['pct']}% of winners)",
                    ))

        # Fantasy: push towards winner fantasies
        for fantasy_entry in wp.top_fantasies[:3]:
            winner_val = fantasy_entry["value"]
            for other_val in FANTASY_VALUES:
                if other_val != winner_val:
                    strategies.append(MutationStrategy(
                        strategy_type="winner_emulation",
                        dimension="fantasy",
                        from_value=other_val,
                        to_values=[winner_val],
                        weight=fantasy_entry["pct"] / 100 * 0.7,
                        reason=f"Top winner fantasy '{winner_val}' ({fantasy_entry['pct']}% of winners)",
                    ))

        return strategies

    # ── Failure Avoidance ─────────────────────────────────

    def _failure_avoidance(self, fa: FailureAnalysis) -> list[MutationStrategy]:
        """Generate strategies to avoid failure patterns."""
        strategies = []

        for pattern in fa.patterns[:10]:
            # For each failure value, suggest migrating to any non-failure alternative
            alternatives = self._get_alternatives(pattern.dimension, pattern.value)

            if alternatives:
                strategies.append(MutationStrategy(
                    strategy_type="failure_avoidance",
                    dimension=pattern.dimension,
                    from_value=pattern.value,
                    to_values=alternatives[:3],
                    weight=abs(pattern.impact) * 0.6,
                    reason=f"Avoid '{pattern.value}' (impact={pattern.impact}, freq={pattern.frequency})",
                ))

        return strategies

    # ── Exploration ───────────────────────────────────────

    def _exploration(
        self,
        existing_values: dict[str, set[str]],
    ) -> list[MutationStrategy]:
        """Generate exploration strategies for under-explored values."""
        strategies = []

        dim_spaces = {
            "hook": HOOK_VALUES,
            "reward": REWARD_VALUES,
            "visual": VISUAL_VALUES,
            "fantasy": FANTASY_VALUES,
        }

        for dim, all_values in dim_spaces.items():
            existing = existing_values.get(dim, set())
            unexplored = [v for v in all_values if v not in existing]

            if unexplored:
                for from_val in list(existing)[:2] if existing else ["unknown"]:
                    strategies.append(MutationStrategy(
                        strategy_type="exploration",
                        dimension=dim,
                        from_value=from_val,
                        to_values=unexplored[:3],
                        weight=0.3,
                        reason=f"Explore {dim} values: {', '.join(unexplored[:3])}",
                    ))

        return strategies

    # ── Archetype Targeting ────────────────────────────────

    def _archetype_targeting(self, wp: WinnerPattern) -> list[MutationStrategy]:
        """Generate strategies targeting specific archetypes."""
        strategies = []

        # Find under-represented archetypes in winners
        arch_affinity = wp.archetype_affinity
        if not arch_affinity:
            return strategies

        max_arch = max(arch_affinity, key=arch_affinity.get)
        min_arch = min(arch_affinity, key=arch_affinity.get)

        # Target under-represented archetypes
        if arch_affinity.get(min_arch, 0) < 0.15:
            strategies.append(MutationStrategy(
                strategy_type="archetype_targeting",
                dimension="hook",
                from_value="",
                to_values=HOOK_VALUES[:3],
                weight=0.5,
                reason=f"Target under-represented archetype '{min_arch}' (only {arch_affinity[min_arch]:.1%})",
            ))

        return strategies

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _get_alternatives(dimension: str, current: str) -> list[str]:
        """Get alternative values for a dimension excluding current."""
        dim_map = {
            "hook": HOOK_VALUES,
            "reward": REWARD_VALUES,
            "visual": VISUAL_VALUES,
            "fantasy": FANTASY_VALUES,
        }
        values = dim_map.get(dimension, [])
        return [v for v in values if v != current]

    @staticmethod
    def get_strategy_summary(
        strategies: list[MutationStrategy],
    ) -> dict[str, Any]:
        """Get summary of generated strategies."""
        by_type: dict[str, int] = {}
        by_dim: dict[str, int] = {}
        for s in strategies:
            by_type[s.strategy_type] = by_type.get(s.strategy_type, 0) + 1
            by_dim[s.dimension] = by_dim.get(s.dimension, 0) + 1

        return {
            "total_strategies": len(strategies),
            "by_type": by_type,
            "by_dimension": by_dim,
        }