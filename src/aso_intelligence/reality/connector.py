"""E16.6.2 — ASO Reality Connector: the unified collection entry point.

``collect(game_id, platform) -> ASOCollectResult``

Pipeline (each step is isolated so one provider's failure can't break the run):

1. Every ``ASODataProvider`` fetches; snapshots are merged (non-None wins).
2. Every ``ReviewProvider`` fetches; reviews are concatenated.
3. The ``CompetitorProvider`` (E16.6.1 ``load_competitors`` contract) fetches.
4. The merged reality is quality-gated (missing / stale / anomaly) — the
   previous snapshot (from the feature store) drives anomaly detection.
5. The raw reality is normalized into the E16.6.1 analysis-ready ASOSnapshot.
6. Optionally persisted to the ASOFeatureStore (snapshots + reviews + keywords).

This mirrors E15.2's ``PlayRealityConnector`` contract exactly (collect /
collect_many with package-level isolation) so ASO reality behaves like the
other Reality Layer feeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from ..models import ASOSnapshot, CompetitorSnapshot  # E16.6.1
from ..collector import NullCompetitorProvider  # E16.6.1 first-version
from .feature_store import ASOFeatureStore
from .models import ASODataQuality, ASORealitySnapshot, Platform, ReviewRecord
from .normalizer import ASONormalizer
from .providers.base import ASODataProvider, ReviewProvider
from .providers.competitor import NullCompetitorProvider as _CompetitorNull


@dataclass
class ASOCollectResult:
    game_id: str
    platform: Platform
    reality: ASORealitySnapshot
    quality: ASODataQuality
    aso_snapshot: ASOSnapshot
    reviews: List[ReviewRecord] = field(default_factory=list)
    competitors: List[CompetitorSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "platform": self.platform.value,
            "reality": self.reality.to_dict(),
            "quality": self.quality.to_dict(),
            "aso_snapshot": self.aso_snapshot.to_dict(),
            "reviews": [r.to_dict() for r in self.reviews],
            "competitors": [c.to_dict() for c in self.competitors],
        }


class ASORealityConnector:
    def __init__(
        self,
        *,
        data_providers: Optional[List[ASODataProvider]] = None,
        review_providers: Optional[List[ReviewProvider]] = None,
        competitor_provider: Any = None,
        feature_store: Optional[ASOFeatureStore] = None,
        normalizer: Optional[ASONormalizer] = None,
        stale_days: int = 30,
    ) -> None:
        self.data_providers = list(data_providers or [])
        self.review_providers = list(review_providers or [])
        self.competitor_provider = competitor_provider or NullCompetitorProvider()
        self.feature_store = feature_store
        self.normalizer = normalizer or ASONormalizer()
        self.stale_days = stale_days

    # ------------------------------------------------------------------ #
    def collect(
        self,
        game_id: str,
        *,
        platform: Platform = Platform.GOOGLE_PLAY,
        persist: bool = True,
    ) -> ASOCollectResult:
        # 1. data providers -> merge
        realities: List[ASORealitySnapshot] = []
        for p in self.data_providers:
            try:
                snap = p.fetch(game_id, platform=platform)
            except Exception:
                continue
            if snap is not None:
                realities.append(snap)
        reality = (
            ASONormalizer.merge(realities)
            if realities
            else ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )
        )

        # 2. reviews
        reviews: List[ReviewRecord] = []
        for rp in self.review_providers:
            try:
                reviews.extend(rp.fetch_reviews(game_id, platform=platform))
            except Exception:
                continue

        # 3. competitors (E16.6.1 CompetitorProvider: load_competitors)
        competitors: List[CompetitorSnapshot] = []
        period = reality.timestamp.date().isoformat()
        try:
            competitors = list(
                self.competitor_provider.load_competitors(game_id, period) or []
            )
        except Exception:
            competitors = []

        # 4. quality gate (needs previous snapshot for anomaly detection)
        previous: Optional[ASORealitySnapshot] = None
        if self.feature_store is not None:
            try:
                previous = self.feature_store.latest(game_id, platform)
            except Exception:
                previous = None
        quality = ASODataQuality.from_snapshot(
            reality, previous=previous, stale_days=self.stale_days
        )

        # 5. normalize
        aso_snapshot = self.normalizer.to_aso_snapshot(reality, reviews)

        # 6. persist
        if persist and self.feature_store is not None:
            try:
                self.feature_store.record_snapshot(reality, quality)
                if reviews:
                    self.feature_store.record_reviews(game_id, platform, reviews)
                if reality.keyword_rankings:
                    self.feature_store.record_keywords(
                        game_id, platform, reality.keyword_rankings
                    )
            except Exception:
                pass  # persistence failure must not break collection

        return ASOCollectResult(
            game_id=game_id,
            platform=platform,
            reality=reality,
            quality=quality,
            aso_snapshot=aso_snapshot,
            reviews=reviews,
            competitors=competitors,
        )

    # ------------------------------------------------------------------ #
    @classmethod
    def build_default(
        cls,
        *,
        client: Optional[Any] = None,
        feature_store: Optional[ASOFeatureStore] = None,
        stale_days: int = 30,
    ) -> "ASORealityConnector":
        """Wire the real providers (Google Play via E15.2 + review bridge).

        App Store / external ASO / competitor remain stubs until their bridges
        land — the connector runs unchanged once they're added.
        """
        from .providers.app_store import AppStoreProvider
        from .providers.google_play import (
            ExternalASOProvider,
            GooglePlayProvider,
        )
        from .providers.reviews import (
            AppStoreReviewProvider,
            GooglePlayReviewProvider,
        )

        return cls(
            data_providers=[
                GooglePlayProvider(client=client),
                AppStoreProvider(client=client),
                ExternalASOProvider(),
            ],
            review_providers=[
                GooglePlayReviewProvider(client=client),
                AppStoreReviewProvider(client=client),
            ],
            competitor_provider=NullCompetitorProvider(),
            feature_store=feature_store,
            stale_days=stale_days,
        )


__all__ = ["ASORealityConnector", "ASOCollectResult"]
