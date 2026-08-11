"""E5.1 Market Brain — Trend Detector.

Detects market trends from multi-source signals:
  - Download velocity changes
  - Ad volume surges
  - Category ranking movements
  - Social media signal spikes

Output: TrendSignal objects that feed OpportunityGenerator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TrendDirection(Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    EXPLODING = "exploding"


class TrendConfidence(Enum):
    LOW = "low"        # < 3 data points
    MEDIUM = "medium"   # 3-10 data points
    HIGH = "high"       # 10+ data points


@dataclass
class TrendSignal:
    """A detected market trend."""
    signal_id: str = ""
    category: str = ""          # e.g. "sort", "merge", "puzzle"
    subcategory: str = ""        # e.g. "3d_sort", "merge_simulation"
    direction: TrendDirection = TrendDirection.STABLE
    growth_pct: float = 0.0     # e.g. 240.0 = +240%
    velocity_score: float = 0.0  # 0-100
    confidence: TrendConfidence = TrendConfidence.LOW
    data_points: int = 0
    sources: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "direction": self.direction.value,
            "growth_pct": round(self.growth_pct, 1),
            "velocity_score": round(self.velocity_score, 1),
            "confidence": self.confidence.value,
            "data_points": self.data_points,
            "sources": self.sources,
            "evidence": self.evidence,
            "detected_at": self.detected_at,
        }


class TrendDetector:
    """Detect trends from aggregated market signals.

    Combines signals from multiple sources to produce trend assessment.

    Real sources (future): Google Play rankings, SensorTower downloads,
      Facebook Ad Library volume, TikTok hashtag data, AppMagic revenue.
    """

    # Trend detection thresholds
    EXPLODING_THRESHOLD = 200.0   # +200% growth → exploding
    RISING_THRESHOLD = 50.0       # +50% growth → rising
    FALLING_THRESHOLD = -20.0     # -20% growth → falling

    def __init__(self) -> None:
        self._signal_history: list[dict[str, Any]] = []

    def detect_from_signals(self, signals: list[dict[str, Any]]) -> list[TrendSignal]:
        """Process raw market signals into trend signals.

        Args:
            signals: Raw signals from market_scanner, each with:
                     {category, source, metric_type, value, timestamp}
        """
        # Group by category
        by_category: dict[str, list[dict[str, Any]]] = {}
        for s in signals:
            cat = s.get("category", "unknown")
            by_category.setdefault(cat, []).append(s)

        trends = []
        for category, group in by_category.items():
            trend = self._analyze_category_trend(category, group)
            if trend:
                trends.append(trend)

        # Sort by velocity_score descending
        trends.sort(key=lambda t: t.velocity_score, reverse=True)
        return trends

    def detect_from_mock_data(self) -> list[TrendSignal]:
        """Generate realistic mock trends based on current market patterns.

        Simulates data from: Google Play, Meta Ads, TikTok, SensorTower.
        """
        mock_trends = [
            self._make_trend(
                "sort", "3d_sort_physics",
                TrendDirection.EXPLODING, 240, 92,
                TrendConfidence.MEDIUM, 8,
                ["google_play", "meta_ads", "tiktok"],
                ["Downloads +240% in 30 days", "Ad volume +180%", "3D physics in sort genre growing"],
            ),
            self._make_trend(
                "merge", "merge_simulation",
                TrendDirection.RISING, 180, 78,
                TrendConfidence.HIGH, 15,
                ["all_sources"],
                ["Merge + Sim hybrid gaining traction", "Top 10 merge games adding sim layer"],
            ),
            self._make_trend(
                "rescue", "rescue_hook_ads",
                TrendDirection.EXPLODING, 320, 96,
                TrendConfidence.HIGH, 12,
                ["tiktok", "meta_ads"],
                ["Rescue hook CTR +45% across genres", "Viral TikTok rescue format"],
            ),
            self._make_trend(
                "visual", "3d_cartoon_style",
                TrendDirection.RISING, 90, 68,
                TrendConfidence.HIGH, 20,
                ["meta_ads", "tiktok"],
                ["3D cartoon outperforming 2D in A/B tests", "Unity asset store 3D pack downloads up"],
            ),
            self._make_trend(
                "monetization", "hybrid_iaa_iap",
                TrendDirection.RISING, 65, 60,
                TrendConfidence.MEDIUM, 6,
                ["sensortower", "appmagic"],
                ["Hybrid monetization ARPU +30%", "IAA + battle pass combo trending"],
            ),
            self._make_trend(
                "puzzle", "puzzle_simulation",
                TrendDirection.RISING, 55, 55,
                TrendConfidence.MEDIUM, 5,
                ["google_play"],
                ["Puzzle + Sim crossover category growing"],
            ),
            self._make_trend(
                "ua_channel", "ugc_creative_format",
                TrendDirection.EXPLODING, 280, 88,
                TrendConfidence.HIGH, 18,
                ["tiktok", "meta_ads"],
                ["UGC format CPI 30% lower", "TikTok Spark Ads driving UGC adoption"],
            ),
            self._make_trend(
                "gameplay", "collection_meta",
                TrendDirection.RISING, 75, 62,
                TrendConfidence.HIGH, 10,
                ["all_sources"],
                ["Collection meta-layer boosts D7 retention +15%"],
            ),
        ]
        return [t for t in mock_trends if t is not None]

    def get_top_trends(self, n: int = 10) -> list[TrendSignal]:
        """Get top N trending categories by velocity."""
        trends = self.detect_from_mock_data()
        return sorted(trends, key=lambda t: t.velocity_score, reverse=True)[:n]

    def get_exploding_trends(self) -> list[TrendSignal]:
        """Get only exploding trends."""
        return [t for t in self.detect_from_mock_data()
                if t.direction == TrendDirection.EXPLODING]

    # ── Internal ────────────────────────────────────────────

    def _analyze_category_trend(
        self, category: str, signals: list[dict[str, Any]]
    ) -> TrendSignal | None:
        """Analyze signals for a single category."""
        if not signals:
            return None

        velocities = [s.get("value", 0) for s in signals]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0
        sources = list(set(s.get("source", "") for s in signals))

        direction = self._classify_direction(avg_velocity)
        confidence = self._classify_confidence(len(signals))
        velocity_score = self._calculate_velocity_score(avg_velocity, len(signals), len(sources))

        return TrendSignal(
            signal_id=f"trend_{category}_{datetime.now().strftime('%Y%m%d')}",
            category=category,
            direction=direction,
            growth_pct=round(avg_velocity, 1),
            velocity_score=velocity_score,
            confidence=confidence,
            data_points=len(signals),
            sources=sources,
            evidence=[f"{s['source']}: {s.get('metric_type', 'unknown')}" for s in signals[:3]],
        )

    def _classify_direction(self, growth_pct: float) -> TrendDirection:
        if growth_pct >= self.EXPLODING_THRESHOLD:
            return TrendDirection.EXPLODING
        if growth_pct >= self.RISING_THRESHOLD:
            return TrendDirection.RISING
        if growth_pct <= self.FALLING_THRESHOLD:
            return TrendDirection.FALLING
        return TrendDirection.STABLE

    @staticmethod
    def _classify_confidence(data_points: int) -> TrendConfidence:
        if data_points >= 10:
            return TrendConfidence.HIGH
        if data_points >= 3:
            return TrendConfidence.MEDIUM
        return TrendConfidence.LOW

    @staticmethod
    def _calculate_velocity_score(growth: float, data_points: int, source_count: int) -> float:
        """Score 0-100 combining growth magnitude + data quality."""
        base = min(80, abs(growth) / 3)  # growth contribution
        quality_bonus = min(20, data_points * 2 + source_count * 3)
        return round(base + quality_bonus, 1)

    @staticmethod
    def _make_trend(
        category: str, subcat: str, direction: TrendDirection,
        growth: float, velocity: float, confidence: TrendConfidence,
        data_points: int, sources: list[str], evidence: list[str],
    ) -> TrendSignal:
        return TrendSignal(
            signal_id=f"trend_{category}_{subcat}",
            category=category,
            subcategory=subcat,
            direction=direction,
            growth_pct=growth,
            velocity_score=velocity,
            confidence=confidence,
            data_points=data_points,
            sources=sources,
            evidence=evidence,
        )
