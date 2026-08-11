"""E6.1: Collector layer — real market signal ingestion.

Abstract collectors for each signal source. Mock implementations
simulate real data collection with realistic patterns.

Sources:
  - Google Play: ranking changes, new releases, review sentiment
  - App Store: category shifts, keyword trends
  - Facebook Ads: creative volume, CTR benchmarks, format changes
  - TikTok: hashtag trends, UGC format adoption
  - YouTube: gameplay video trends, comment sentiment
  - Reddit: community sentiment, pain points

Each collector → market knowledge graph node.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CollectedSignal:
    """A raw signal from an external source."""
    source: str
    entity: str           # game name, category, or keyword
    metric: str           # "ranking", "downloads", "ad_volume", "sentiment"
    value: float
    change_pct: float      # percentage change
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_preview: str = ""  # For audit


class SignalCollector(ABC):
    """Base collector with source identity."""

    source_name: str = "unknown"

    @abstractmethod
    def collect(self) -> list[CollectedSignal]:
        raise NotImplementedError

    def collect_and_enrich(self, graph) -> None:
        """Collect signals and feed into knowledge graph."""
        signals = self.collect()
        for s in signals:
            # Feed as trend-like signal to knowledge graph
            from market_ops.market_intelligence.trend_detector import TrendSignal, TrendDirection, TrendConfidence
            trend_sig = TrendSignal(
                signal_id=f"{s.source}_{s.entity}_{s.metric}",
                category=s.entity,
                subcategory=s.metric,
                direction=TrendDirection.RISING if s.change_pct > 50 else TrendDirection.STABLE,
                growth_pct=s.change_pct,
                velocity_score=min(100, abs(s.change_pct) / 3 + s.confidence * 20),
                confidence=TrendConfidence.MEDIUM if s.confidence > 0.7 else TrendConfidence.LOW,
                data_points=1,
                sources=[s.source],
                evidence=[s.raw_preview],
            )
            graph.ingest_signal(trend_sig, s.entity)


class GooglePlayCollector(SignalCollector):
    """Collects from Google Play: rankings, new releases, review sentiment.

    Mock: simulates chart movements and review patterns.
    Production: Play Store scraping API or SensorTower integration.
    """
    source_name = "google_play"

    def collect(self) -> list[CollectedSignal]:
        return [
            CollectedSignal(source="google_play", entity="sort",
                            metric="ranking_jump", value=35, change_pct=45,
                            confidence=0.85,
                            raw_preview="Stack Sort ranked #12 → #3 in Puzzle category"),
            CollectedSignal(source="google_play", entity="merge",
                            metric="new_releases", value=8, change_pct=15,
                            confidence=0.78,
                            raw_preview="8 new merge games launched this month"),
            CollectedSignal(source="google_play", entity="simulation",
                            metric="download_growth", value=240, change_pct=240,
                            confidence=0.92,
                            raw_preview="Simulation category downloads +240% MoM"),
            CollectedSignal(source="google_play", entity="puzzle",
                            metric="review_volume", value=5000, change_pct=30,
                            confidence=0.72,
                            raw_preview="Puzzle reviews +30%, players want more depth"),
            CollectedSignal(source="google_play", entity="decorate",
                            metric="retention", value=68, change_pct=12,
                            confidence=0.65,
                            raw_preview="Decorate games D30 retention improving"),
        ]


class FacebookAdCollector(SignalCollector):
    """Collects from Facebook Ads Library: creative volume, format shifts.

    Mock: simulates ad volume trends and creative format adoption.
    Production: Meta Ad Library API or third-party data providers.
    """
    source_name = "meta_ads"

    def collect(self) -> list[CollectedSignal]:
        return [
            CollectedSignal(source="meta_ads", entity="sort",
                            metric="ad_volume", value=3200, change_pct=180,
                            confidence=0.88,
                            raw_preview="Sort genre ad volume +180%, rescue hook dominant"),
            CollectedSignal(source="meta_ads", entity="merge",
                            metric="ad_volume", value=1800, change_pct=25,
                            confidence=0.82,
                            raw_preview="Merge ads shifting from gameplay → UGC format"),
            CollectedSignal(source="meta_ads", entity="rescue_hook",
                            metric="ctr_benchmark", value=4.8, change_pct=45,
                            confidence=0.90,
                            raw_preview="Rescue hook CTR +45% across all genres"),
            CollectedSignal(source="meta_ads", entity="ugc_format",
                            metric="adoption_rate", value=65, change_pct=60,
                            confidence=0.85,
                            raw_preview="UGC format adoption +60%, CPI 30% lower than gameplay"),
            CollectedSignal(source="meta_ads", entity="3d_visual",
                            metric="a_b_test_wins", value=72, change_pct=15,
                            confidence=0.80,
                            raw_preview="3D cartoon visual beats 2D in 72% of A/B tests"),
        ]


class TikTokCollector(SignalCollector):
    """Collects from TikTok Creative Center: hashtag trends, format shifts.

    Mock: simulates TikTok creative trends.
    Production: TikTok Creative Center API or scraping.
    """
    source_name = "tiktok"

    def collect(self) -> list[CollectedSignal]:
        return [
            CollectedSignal(source="tiktok", entity="rescue_hook",
                            metric="hashtag_growth", value=320, change_pct=320,
                            confidence=0.68,
                            raw_preview="#rescuedragonchallenge +320%, 50M+ views"),
            CollectedSignal(source="tiktok", entity="sort_satisfaction",
                            metric="video_volume", value=8500, change_pct=220,
                            confidence=0.70,
                            raw_preview="Sort satisfaction videos +220%, satisfying cleanup format"),
            CollectedSignal(source="tiktok", entity="ugc_creative",
                            metric="spark_ads", value=180, change_pct=180,
                            confidence=0.75,
                            raw_preview="TikTok Spark Ads for UGC creatives +180%"),
            CollectedSignal(source="tiktok", entity="collection",
                            metric="engagement", value=45, change_pct=85,
                            confidence=0.62,
                            raw_preview="Collection reveal videos high engagement"),
        ]


class RedditCollector(SignalCollector):
    """Collects from Reddit: community pain points, game discussions.

    Mock: simulates community signals.
    Production: Reddit API.
    """
    source_name = "reddit"

    def collect(self) -> list[CollectedSignal]:
        return [
            CollectedSignal(source="reddit", entity="merge_games",
                            metric="sentiment_negative", value=15, change_pct=-5,
                            confidence=0.55,
                            raw_preview="Players complaining about merge game grind — want evolution"),
            CollectedSignal(source="reddit", entity="sort_games",
                            metric="pain_point", value=28, change_pct=10,
                            confidence=0.50,
                            raw_preview="'Sort games need meta-layer' — top voted comment"),
            CollectedSignal(source="reddit", entity="mobile_gaming",
                            metric="demand", value=42, change_pct=20,
                            confidence=0.48,
                            raw_preview="Players asking for 'sort + collect' hybrid"),
        ]


class YouTubeCollector(SignalCollector):
    """Collects from YouTube: gameplay trends, creator sentiment.

    Mock: simulates YouTube video trends.
    """
    source_name = "youtube"

    def collect(self) -> list[CollectedSignal]:
        return [
            CollectedSignal(source="youtube", entity="sort_3d",
                            metric="video_views", value=25000000, change_pct=180,
                            confidence=0.75,
                            raw_preview="3D Sort gameplay compilations 25M+ views"),
            CollectedSignal(source="youtube", entity="merge_evolution",
                            metric="creator_count", value=45, change_pct=55,
                            confidence=0.65,
                            raw_preview="45 new creators making merge evolution content"),
        ]


# ═══════════════════════════════════════════════════════════
# Collector Pipeline
# ═══════════════════════════════════════════════════════════

class SignalCollectionPipeline:
    """Orchestrates all collectors and feeds into knowledge graph."""

    COLLECTORS: list[SignalCollector] = [
        GooglePlayCollector(),
        FacebookAdCollector(),
        TikTokCollector(),
        RedditCollector(),
        YouTubeCollector(),
    ]

    @classmethod
    def collect_all(cls) -> list[CollectedSignal]:
        """Run all collectors. Returns flattened signal list."""
        all_signals = []
        for collector in cls.COLLECTORS:
            try:
                signals = collector.collect()
                all_signals.extend(signals)
            except Exception:
                pass
        return all_signals

    @classmethod
    def feed_graph(cls, graph) -> int:
        """Collect + feed into MarketKnowledgeGraph. Returns signal count."""
        signals = cls.collect_all()
        for s in signals:
            graph.ingest_signal(s, s.entity)
        return len(signals)

    @classmethod
    def get_source_breakdown(cls) -> dict[str, int]:
        """How many signals from each source."""
        counts: dict[str, int] = {}
        for collector in cls.COLLECTORS:
            counts[collector.source_name] = len(collector.collect())
        return counts
