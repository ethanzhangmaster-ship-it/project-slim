"""V4.1.1 Combinatorial Pattern Mining — discover real performance patterns.

NOT frequency counting. This finds actual combinatorial patterns that
drive performance metrics (CTR, IPM, ROAS).

Example:
  Input: 5000 creatives with DNA + performance
  Output:
    Top1: Baby Dragon + Blue + Explosion → CTR +19% (n=127, confidence=0.92)
    Top2: Witch + Purple + Zoom → IPM +15% (n=89, confidence=0.88)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CombinatorialPattern:
    """A discovered combinatorial pattern with performance impact."""
    dimensions: dict[str, str] = field(default_factory=dict)
    metric: str = ""          # "ctr", "ipm", "roas_d7"
    baseline: float = 0.0     # global average
    pattern_value: float = 0.0 # pattern average
    lift_pct: float = 0.0     # (pattern - baseline) / baseline * 100
    sample_count: int = 0
    confidence: float = 0.0   # statistical confidence
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "metric": self.metric,
            "baseline": round(self.baseline, 4),
            "pattern_value": round(self.pattern_value, 4),
            "lift_pct": round(self.lift_pct, 1),
            "sample_count": self.sample_count,
            "confidence": round(self.confidence, 3),
            "rank": self.rank,
        }

    def describe(self) -> str:
        dims = " + ".join(
            f"{k}={v}" for k, v in self.dimensions.items()
        )
        return (
            f"[{self.metric}] {dims} → "
            f"{self.lift_pct:+.1f}% "
            f"(n={self.sample_count}, conf={self.confidence:.2f})"
        )


class CombinatorialPatternMiner:
    """Discovers combinatorial patterns that drive real performance.

    Algorithm:
      1. For each metric (CTR, IPM, ROAS), compute global baseline
      2. For each DNA dimension combination (2-3 dims), compute pattern average
      3. Filter by lift threshold and minimum sample count
      4. Rank by (lift * confidence * log(sample_count))
    """

    DIMENSIONS = ["character", "reward", "hook", "gameplay", "camera",
                  "lighting", "palette", "style", "emotion", "country"]

    METRICS = ["ctr", "ipm", "roas_d7"]

    def __init__(self, min_samples: int = 5, min_lift_pct: float = 5.0,
                 max_dims: int = 3) -> None:
        self._min_samples = min_samples
        self._min_lift_pct = min_lift_pct
        self._max_dims = max_dims

    def mine(self, creatives: list[dict[str, Any]],
             dimensions: list[str] | None = None,
             metrics: list[str] | None = None) -> list[CombinatorialPattern]:
        """Mine combinatorial patterns from creatives.

        Each creative: {"dna": {"character": "witch", ...}, "performance": {"ctr": 4.2, ...}}
        """
        dimensions = dimensions or self.DIMENSIONS[:6]
        metrics = metrics or self.METRICS
        patterns = []

        for metric in metrics:
            baseline = self._compute_baseline(creatives, metric)
            if baseline <= 0:
                continue

            # Single dimension patterns
            for dim in dimensions:
                patterns.extend(
                    self._mine_single_dim(creatives, dim, metric, baseline)
                )

            # Two-dimension combinations
            for i, d1 in enumerate(dimensions):
                for d2 in dimensions[i+1:]:
                    patterns.extend(
                        self._mine_double_dim(creatives, d1, d2, metric, baseline)
                    )

            # Three-dimension combinations (only for top dimensions)
            top_dims = self._select_top_dims(patterns, n=4)
            for i, d1 in enumerate(top_dims):
                for j, d2 in enumerate(top_dims[i+1:], i+1):
                    for d3 in top_dims[j+1:]:
                        patterns.extend(
                            self._mine_triple_dim(creatives, d1, d2, d3, metric, baseline)
                        )

        # Rank all patterns
        return self._rank_patterns(patterns)

    def _compute_baseline(self, creatives: list[dict[str, Any]],
                          metric: str) -> float:
        values = []
        for c in creatives:
            v = c.get("performance", {}).get(metric, 0)
            if v > 0:
                values.append(v)
        return sum(values) / max(len(values), 1)

    def _mine_single_dim(self, creatives: list[dict[str, Any]],
                         dim: str, metric: str, baseline: float) -> list[CombinatorialPattern]:
        patterns = []
        groups: dict[str, list[float]] = {}
        for c in creatives:
            value = c.get("dna", {}).get(dim, "")
            perf = c.get("performance", {}).get(metric, 0)
            if value and perf > 0:
                groups.setdefault(value, []).append(perf)

        for value, perfs in groups.items():
            if len(perfs) < self._min_samples:
                continue
            avg = sum(perfs) / len(perfs)
            lift = (avg - baseline) / baseline * 100

            if abs(lift) >= self._min_lift_pct:
                patterns.append(CombinatorialPattern(
                    dimensions={dim: value},
                    metric=metric,
                    baseline=baseline,
                    pattern_value=avg,
                    lift_pct=lift,
                    sample_count=len(perfs),
                    confidence=min(1.0, len(perfs) / 30),
                ))
        return patterns

    def _mine_double_dim(self, creatives: list[dict[str, Any]],
                         d1: str, d2: str, metric: str,
                         baseline: float) -> list[CombinatorialPattern]:
        patterns = []
        groups: dict[tuple[str, str], list[float]] = {}
        for c in creatives:
            v1 = c.get("dna", {}).get(d1, "")
            v2 = c.get("dna", {}).get(d2, "")
            perf = c.get("performance", {}).get(metric, 0)
            if v1 and v2 and perf > 0:
                groups.setdefault((v1, v2), []).append(perf)

        for (v1, v2), perfs in groups.items():
            if len(perfs) < self._min_samples:
                continue
            avg = sum(perfs) / len(perfs)
            lift = (avg - baseline) / baseline * 100

            if abs(lift) >= self._min_lift_pct:
                patterns.append(CombinatorialPattern(
                    dimensions={d1: v1, d2: v2},
                    metric=metric,
                    baseline=baseline,
                    pattern_value=avg,
                    lift_pct=lift,
                    sample_count=len(perfs),
                    confidence=min(1.0, len(perfs) / 50),
                ))
        return patterns

    def _mine_triple_dim(self, creatives: list[dict[str, Any]],
                         d1: str, d2: str, d3: str, metric: str,
                         baseline: float) -> list[CombinatorialPattern]:
        patterns = []
        groups: dict[tuple[str, str, str], list[float]] = {}
        for c in creatives:
            v1 = c.get("dna", {}).get(d1, "")
            v2 = c.get("dna", {}).get(d2, "")
            v3 = c.get("dna", {}).get(d3, "")
            perf = c.get("performance", {}).get(metric, 0)
            if v1 and v2 and v3 and perf > 0:
                groups.setdefault((v1, v2, v3), []).append(perf)

        for (v1, v2, v3), perfs in groups.items():
            if len(perfs) < self._min_samples:
                continue
            avg = sum(perfs) / len(perfs)
            lift = (avg - baseline) / baseline * 100

            if abs(lift) >= self._min_lift_pct:
                patterns.append(CombinatorialPattern(
                    dimensions={d1: v1, d2: v2, d3: v3},
                    metric=metric,
                    baseline=baseline,
                    pattern_value=avg,
                    lift_pct=lift,
                    sample_count=len(perfs),
                    confidence=min(1.0, len(perfs) / 60),
                ))
        return patterns

    def _select_top_dims(self, patterns: list[CombinatorialPattern],
                         n: int = 4) -> list[str]:
        """Select top dimensions by pattern count."""
        dim_counts: dict[str, int] = {}
        for p in patterns:
            for dim in p.dimensions:
                dim_counts[dim] = dim_counts.get(dim, 0) + 1
        return sorted(dim_counts, key=dim_counts.get, reverse=True)[:n]

    def _rank_patterns(self, patterns: list[CombinatorialPattern]) -> list[CombinatorialPattern]:
        """Rank by composite score: lift * confidence * log(sample_count)."""
        import math
        ranked = sorted(
            patterns,
            key=lambda p: abs(p.lift_pct) * p.confidence * math.log(p.sample_count + 1),
            reverse=True,
        )
        for i, p in enumerate(ranked):
            p.rank = i + 1
        return ranked