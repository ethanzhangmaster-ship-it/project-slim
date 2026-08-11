"""E9.8: Winner DNA Analyzer — Extracts common DNA patterns from top performers.

Analyzes historical winning creatives to identify:
  - Most common hook, reward, visual, fantasy, mechanism types
  - Archetype affinity of winners
  - Average performance metrics of winner group
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from market_ops.creative_evolution.schemas import WinnerPattern


class WinnerDNAAnalyzer:
    """Analyzes winner creatives to extract common DNA patterns.

    Usage:
        analyzer = WinnerDNAAnalyzer(ltv_threshold_percentile=80)
        pattern = analyzer.analyze(dna_list, performance_map)
    """

    def __init__(self, ltv_threshold_percentile: float = 80.0) -> None:
        self._threshold_pct = ltv_threshold_percentile
        self._ltv_threshold: float = 0.0

    # ── Main Analysis ─────────────────────────────────────

    def analyze(
        self,
        dna_list: list[dict[str, Any]],
        performance_map: dict[str, dict[str, Any]],
    ) -> WinnerPattern:
        """Analyze winner DNA patterns.

        Args:
            dna_list: Creative DNA entries from creative_dna_master.json
            performance_map: {creative_id: {ltv_d30, payer_rate, ...}}

        Returns:
            WinnerPattern with aggregated winner DNA patterns
        """
        # Compute LTV threshold
        ltvs = [p.get("ltv_d30", 0) for p in performance_map.values()]
        if not ltvs:
            return WinnerPattern()

        ltvs.sort()
        idx = int(len(ltvs) * self._threshold_pct / 100)
        self._ltv_threshold = ltvs[min(idx, len(ltvs) - 1)]

        # Identify winners
        winner_ids = {
            cid for cid, p in performance_map.items()
            if p.get("ltv_d30", 0) >= self._ltv_threshold
        }

        # Filter DNA to winners only
        winner_dnas = [d for d in dna_list if d.get("creative_id", "") in winner_ids]

        if not winner_dnas:
            return WinnerPattern()

        pattern = WinnerPattern(
            winner_count=len(winner_dnas),
            total_analyzed=len(dna_list),
        )

        # Extract patterns
        pattern.top_hooks = self._extract_dimension(winner_dnas, "hook", "type")
        pattern.top_rewards = self._extract_dimension(winner_dnas, "reward", "type")
        pattern.top_visuals = self._extract_dimension(winner_dnas, "visual", "style")
        pattern.top_fantasies = self._extract_fantasy(winner_dnas)
        pattern.top_mechanisms = self._extract_dimension(winner_dnas, "mechanism", "type")

        # Archetype affinity
        pattern.archetype_affinity = self._compute_archetype_affinity(
            winner_ids, performance_map,
        )

        # Performance
        winner_perfs = [
            performance_map[cid] for cid in winner_ids
            if cid in performance_map
        ]
        pattern.avg_ltv = (
            sum(p.get("ltv_d30", 0) for p in winner_perfs) / len(winner_perfs)
            if winner_perfs else 0.0
        )
        pattern.avg_payer_rate = (
            sum(p.get("payer_rate", 0) for p in winner_perfs) / len(winner_perfs)
            if winner_perfs else 0.0
        )
        pattern.avg_retention = (
            sum(p.get("d30_retention", 0) for p in winner_perfs) / len(winner_perfs)
            if winner_perfs else 0.0
        )

        return pattern

    # ── Dimension Extraction ───────────────────────────────

    @staticmethod
    def _extract_dimension(
        dna_list: list[dict[str, Any]],
        dimension: str,
        value_key: str,
    ) -> list[dict[str, Any]]:
        """Extract top values for a DNA dimension."""
        counter: Counter = Counter()
        for d in dna_list:
            dim = d.get(dimension, {}) or {}
            val = dim.get(value_key, "") or ""
            if val and val != "unknown":
                counter[val] += 1

        total = len(dna_list)
        return [
            {"value": v, "count": c, "pct": round(c / total * 100, 1)}
            for v, c in counter.most_common(10)
        ]

    @staticmethod
    def _extract_fantasy(
        dna_list: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract top fantasy drives (multi-value)."""
        counter: Counter = Counter()
        for d in dna_list:
            drives = d.get("fantasy", {}).get("drives", []) or []
            for drive in drives:
                counter[drive] += 1

        total = len(dna_list)
        return [
            {"value": v, "count": c, "pct": round(c / total * 100, 1)}
            for v, c in counter.most_common(10)
        ]

    # ── Archetype Affinity ─────────────────────────────────

    @staticmethod
    def _compute_archetype_affinity(
        winner_ids: set[str],
        performance_map: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        """Compute average archetype distribution across winners."""
        arch_sums: dict[str, float] = defaultdict(float)
        count = 0

        for cid in winner_ids:
            perf = performance_map.get(cid, {})
            arch_dist = perf.get("archetype_distribution", {})
            if arch_dist:
                for arch, val in arch_dist.items():
                    arch_sums[arch] += val
                count += 1

        if count == 0:
            return {}

        return {
            arch: round(val / count, 3)
            for arch, val in arch_sums.items()
        }

    # ── Winner DNA Extraction ──────────────────────────────

    def extract_winner_dna(
        self,
        dna_list: list[dict[str, Any]],
        performance_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract full DNA entries for winners only."""
        ltvs = [p.get("ltv_d30", 0) for p in performance_map.values()]
        if not ltvs:
            return []

        ltvs.sort()
        idx = int(len(ltvs) * self._threshold_pct / 100)
        threshold = ltvs[min(idx, len(ltvs) - 1)]

        winner_ids = {
            cid for cid, p in performance_map.items()
            if p.get("ltv_d30", 0) >= threshold
        }

        return [d for d in dna_list if d.get("creative_id", "") in winner_ids]