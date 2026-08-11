"""V4.1 Pattern Mining — automatic discovery of creative patterns.

Discovers:
  - Winner patterns (high ROAS combinations)
  - Loser patterns (low ROAS combinations)
  - Country patterns (geo-specific preferences)
  - Trend patterns (temporal shifts)
  - Hook patterns
  - Reward patterns
  - Character patterns
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternResult:
    pattern_type: str = ""
    dimension: str = ""
    values: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sample_count: int = 0
    performance_lift: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "dimension": self.dimension,
            "values": self.values,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "performance_lift": self.performance_lift,
            "metadata": self.metadata,
        }


class BasePatternMiner:
    """Base class for pattern miners."""

    def _count_values(self, items: list[dict[str, Any]],
                      dimension: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            value = item.get(dimension, "")
            if value:
                counts[value] = counts.get(value, 0) + 1
        return counts

    def _top_n(self, counts: dict[str, int], n: int = 5) -> list[tuple[str, int]]:
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]


class WinnerPatternMiner(BasePatternMiner):
    """Mines patterns from winning creatives (high ROAS)."""

    def mine(self, creatives: list[dict[str, Any]],
             dimensions: list[str] | None = None) -> list[PatternResult]:
        dimensions = dimensions or ["character", "reward", "hook", "gameplay", "camera", "lighting"]
        winners = [c for c in creatives if c.get("performance", {}).get("roas_d7", 0) >= 0.5]
        if not winners:
            return []

        results = []
        total = len(winners)
        for dim in dimensions:
            counts = self._count_values(winners, dim)
            for value, count in self._top_n(counts):
                results.append(PatternResult(
                    pattern_type="winner",
                    dimension=dim,
                    values=[value],
                    confidence=count / max(total, 1),
                    sample_count=count,
                    performance_lift=0.0,
                    metadata={"total_winners": total},
                ))
        return results


class LoserPatternMiner(BasePatternMiner):
    """Mines patterns from losing creatives (low ROAS)."""

    def mine(self, creatives: list[dict[str, Any]],
             dimensions: list[str] | None = None) -> list[PatternResult]:
        dimensions = dimensions or ["character", "reward", "hook", "gameplay"]
        losers = [c for c in creatives if c.get("performance", {}).get("roas_d7", 0) < 0.3]
        if not losers:
            return []

        results = []
        total = len(losers)
        for dim in dimensions:
            counts = self._count_values(losers, dim)
            for value, count in self._top_n(counts):
                results.append(PatternResult(
                    pattern_type="loser",
                    dimension=dim,
                    values=[value],
                    confidence=count / max(total, 1),
                    sample_count=count,
                    performance_lift=0.0,
                    metadata={"total_losers": total},
                ))
        return results


class TrendPatternMiner(BasePatternMiner):
    """Mines temporal trend patterns."""

    def mine(self, creatives: list[dict[str, Any]],
             dimensions: list[str] | None = None) -> list[PatternResult]:
        dimensions = dimensions or ["character", "hook", "reward"]
        if not creatives:
            return []

        results = []
        for dim in dimensions:
            counts = self._count_values(creatives, dim)
            total = sum(counts.values())
            for value, count in self._top_n(counts):
                results.append(PatternResult(
                    pattern_type="trend",
                    dimension=dim,
                    values=[value],
                    confidence=count / max(total, 1),
                    sample_count=count,
                    performance_lift=0.0,
                ))
        return results


class CountryPatternMiner(BasePatternMiner):
    """Mines country-specific patterns."""

    def mine(self, creatives: list[dict[str, Any]],
             dimensions: list[str] | None = None) -> list[PatternResult]:
        dimensions = dimensions or ["character", "hook", "reward", "gameplay"]
        country_groups: dict[str, list[dict[str, Any]]] = {}
        for c in creatives:
            country = c.get("country", "unknown")
            country_groups.setdefault(country, []).append(c)

        results = []
        for country, items in country_groups.items():
            for dim in dimensions:
                counts = self._count_values(items, dim)
                for value, count in self._top_n(counts, n=3):
                    results.append(PatternResult(
                        pattern_type="country",
                        dimension=dim,
                        values=[value],
                        confidence=count / max(len(items), 1),
                        sample_count=count,
                        metadata={"country": country},
                ))
        return results


class PatternRanker:
    """Unified pattern ranking and analysis.

    Ranks patterns from multiple miners by confidence and sample count.
    """

    def __init__(self) -> None:
        self._winner = WinnerPatternMiner()
        self._loser = LoserPatternMiner()
        self._trend = TrendPatternMiner()
        self._country = CountryPatternMiner()

    def mine_all(self, creatives: list[dict[str, Any]]) -> dict[str, list[PatternResult]]:
        return {
            "winner": self._winner.mine(creatives),
            "loser": self._loser.mine(creatives),
            "trend": self._trend.mine(creatives),
            "country": self._country.mine(creatives),
        }

    def rank(self, patterns: list[PatternResult]) -> list[PatternResult]:
        return sorted(patterns, key=lambda p: (p.confidence, p.sample_count), reverse=True)

    def top_patterns(self, creatives: list[dict[str, Any]], top_n: int = 10) -> list[PatternResult]:
        all_patterns = []
        for miner in [self._winner, self._loser, self._trend, self._country]:
            all_patterns.extend(miner.mine(creatives))
        return self.rank(all_patterns)[:top_n]