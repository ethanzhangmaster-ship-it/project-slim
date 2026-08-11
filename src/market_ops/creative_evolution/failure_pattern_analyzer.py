"""E9.8: Failure Pattern Analyzer — Identifies DNA patterns that lead to failure.

Analyzes underperforming creatives to identify:
  - DNA dimensions that correlate with low LTV
  - Specific values to avoid (e.g., "unknown" hook, empty reward)
  - Impact magnitude of each failure pattern
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from market_ops.creative_evolution.schemas import FailurePattern, FailureAnalysis


class FailurePatternAnalyzer:
    """Analyzes loser creatives to identify failure DNA patterns.

    Usage:
        analyzer = FailurePatternAnalyzer(ltv_threshold_percentile=20)
        analysis = analyzer.analyze(dna_list, performance_map)
    """

    def __init__(self, ltv_threshold_percentile: float = 20.0) -> None:
        self._threshold_pct = ltv_threshold_percentile

    # ── Main Analysis ─────────────────────────────────────

    def analyze(
        self,
        dna_list: list[dict[str, Any]],
        performance_map: dict[str, dict[str, Any]],
    ) -> FailureAnalysis:
        """Analyze failure DNA patterns.

        Args:
            dna_list: Creative DNA entries
            performance_map: {creative_id: {ltv_d30, ...}}

        Returns:
            FailureAnalysis with identified failure patterns
        """
        ltvs = [p.get("ltv_d30", 0) for p in performance_map.values()]
        if not ltvs:
            return FailureAnalysis()

        ltvs.sort()
        idx = int(len(ltvs) * self._threshold_pct / 100)
        loser_threshold = ltvs[min(idx, len(ltvs) - 1)]

        # Identify losers
        loser_ids = {
            cid for cid, p in performance_map.items()
            if p.get("ltv_d30", 0) <= loser_threshold
        }

        loser_dnas = [d for d in dna_list if d.get("creative_id", "") in loser_ids]
        loser_perfs = [
            performance_map[cid] for cid in loser_ids
            if cid in performance_map
        ]

        if not loser_dnas:
            return FailureAnalysis()

        analysis = FailureAnalysis(
            loser_count=len(loser_dnas),
            total_analyzed=len(dna_list),
            avg_loser_ltv=(
                sum(p.get("ltv_d30", 0) for p in loser_perfs) / len(loser_perfs)
                if loser_perfs else 0.0
            ),
        )

        # Find failure patterns per dimension
        patterns: list[FailurePattern] = []

        # Hook analysis
        patterns.extend(self._analyze_dimension(
            loser_dnas, "hook", "type", loser_perfs, "hook",
        ))

        # Reward analysis
        patterns.extend(self._analyze_dimension(
            loser_dnas, "reward", "type", loser_perfs, "reward",
        ))

        # Visual analysis
        patterns.extend(self._analyze_dimension(
            loser_dnas, "visual", "style", loser_perfs, "visual",
        ))

        # Sort by impact (most negative first)
        patterns.sort(key=lambda p: p.impact)

        analysis.patterns = patterns[:20]

        # Build avoidance lists
        analysis.avoid_hooks = self._build_avoidance_list(patterns, "hook")
        analysis.avoid_rewards = self._build_avoidance_list(patterns, "reward")
        analysis.avoid_visuals = self._build_avoidance_list(patterns, "visual")
        analysis.avoid_fantasies = self._build_avoidance_list(patterns, "fantasy")

        return analysis

    # ── Dimension Analysis ─────────────────────────────────

    def _analyze_dimension(
        self,
        loser_dnas: list[dict[str, Any]],
        dimension: str,
        value_key: str,
        loser_perfs: list[dict[str, Any]],
        dim_name: str,
    ) -> list[FailurePattern]:
        """Analyze a single DNA dimension for failure patterns."""
        # Group losers by dimension value
        value_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for d in loser_dnas:
            dim = d.get(dimension, {}) or {}
            val = dim.get(value_key, "") or "empty"
            value_groups[val].append(d)

        avg_all_ltv = (
            sum(p.get("ltv_d30", 0) for p in loser_perfs) / len(loser_perfs)
            if loser_perfs else 0.0
        )

        patterns = []
        for val, items in value_groups.items():
            # High frequency of a value in losers = potential failure pattern
            freq = len(items)
            pct = freq / len(loser_dnas) if loser_dnas else 0

            # Impact: how much below average
            impact = -pct  # Simple model: frequency = negative impact

            patterns.append(FailurePattern(
                feature=f"{dim_name}_{val}" if val != "empty" else f"empty_{dim_name}",
                dimension=dim_name,
                value=val,
                impact=round(impact, 3),
                frequency=freq,
                loser_avg_ltv=avg_all_ltv,
            ))

        return patterns

    # ── Avoidance Lists ────────────────────────────────────

    @staticmethod
    def _build_avoidance_list(
        patterns: list[FailurePattern],
        dimension: str,
    ) -> list[str]:
        """Build list of values to avoid for a dimension."""
        return [
            p.value for p in patterns
            if p.dimension == dimension and p.impact < -0.05
        ]