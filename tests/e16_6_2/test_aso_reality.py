"""
E16.6.2 — ASO Data Reality Layer tests.

Five scenarios per spec:

  1. Google Play data conversion — Mock Play response -> ASORealitySnapshot
     (reuses E15.2 PlayRealityConnector shape; verifies field mapping +
      external-ASO seam merge).
  2. Review collection — 100 raw reviews -> List[ReviewRecord].
  3. Multi-platform isolation — game_a (Android) / game_b (iOS) data never
     cross-contaminate, at both feature-store and connector level.
  4. Feature Store — record / latest / history round-trip (+ quality attached).
  5. Agent closed loop — Reality -> ASOSnapshot -> ASOInsight -> GrowthAction
     -> Memory (the E16.6.1 -> E16.6.2 upgrade: agent fetches its own data).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from operation.publishing_factory.play_runtime.reality.models import (
    PlayRealitySnapshot,
)

from src.aso_intelligence.agent import ASOAgentRunResult, ASOIntelligenceAgent
from src.aso_intelligence.collector import NullCompetitorProvider
from src.aso_intelligence.memory import ASOMemory
from src.aso_intelligence.models import ASOAction, ASOSnapshot
from src.aso_intelligence.reality.connector import (
    ASOCollectResult,
    ASORealityConnector,
)
from src.aso_intelligence.reality.feature_store import ASOFeatureStore
from src.aso_intelligence.reality.models import (
    ASODataQualityFlag,
    ASORealitySnapshot,
    Platform,
    ReviewRecord,
)
from src.aso_intelligence.reality.normalizer import ASONormalizer
from src.aso_intelligence.reality.providers.google_play import (
    ExternalASOProvider,
    GooglePlayProvider,
)
from src.aso_intelligence.reality.providers.reviews import GooglePlayReviewProvider
from src.revenue_intelligence.models import GrowthAction


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
class FakePlayConnector:
    """Stand-in for E15.2 PlayRealityConnector.collect()."""

    def __init__(self, prs: PlayRealitySnapshot):
        self._prs = prs

    def collect(self, package_name: str) -> PlayRealitySnapshot:
        return self._prs


class FakeReviewClient:
    """Stand-in for GooglePlayRealClient.get_reviews()."""

    def __init__(self, reviews):
        self._reviews = reviews

    def get_reviews(self, package_name: str, max_results: int = 200):
        return {
            "reviews": self._reviews[:max_results],
            "count": len(self._reviews),
        }


class FakeDataProvider:
    """Returns its snapshot only for its platform; fallback otherwise."""

    def __init__(self, platform: Platform, snap: ASORealitySnapshot):
        self._platform = platform
        self._snap = snap

    def fetch(self, game_id: str, *, platform: Platform) -> ASORealitySnapshot:
        if platform != self._platform:
            return ASORealitySnapshot(
                game_id=game_id, platform=platform, source="fallback"
            )
        return self._snap


class RecordingSink:
    def __init__(self):
        self.submitted: list[GrowthAction] = []

    def submit(self, action: GrowthAction) -> bool:
        self.submitted.append(action)
        return True


# --------------------------------------------------------------------------- #
# 1. Google Play data conversion
# --------------------------------------------------------------------------- #
class TestGooglePlayConversion:
    def _prs(self) -> PlayRealitySnapshot:
        return PlayRealitySnapshot(
            package_name="com.born2play.mergewitch",
            installs=5000,
            rating_average=4.3,
            review_count=1200,
            negative_review_ratio=0.12,
            sources={"store": "live"},
            collected_at=datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc),
        )

    def test_play_reality_maps_to_aso_reality(self):
        provider = GooglePlayProvider(play_connector=FakePlayConnector(self._prs()))
        snap = provider.fetch(
            "com.born2play.mergewitch", platform=Platform.GOOGLE_PLAY
        )
        assert snap.installs == 5000
        assert abs(snap.rating - 4.3) < 1e-6
        assert snap.review_count == 1200
        assert snap.platform == Platform.GOOGLE_PLAY
        assert snap.source == "google_play:live"
        assert snap.extra.get("negative_review_ratio") == 0.12

    def test_non_google_platform_returns_fallback(self):
        provider = GooglePlayProvider(play_connector=FakePlayConnector(self._prs()))
        snap = provider.fetch("some.ios.game", platform=Platform.APP_STORE)
        assert snap.is_empty()
        assert snap.source == "fallback"

    def test_external_aso_provider_is_stub(self):
        ext = ExternalASOProvider()
        snap = ext.fetch("com.x", platform=Platform.GOOGLE_PLAY)
        assert snap.source == "unavailable"
        assert snap.is_empty()

    def test_connector_merges_google_and_external(self):
        gp = GooglePlayProvider(play_connector=FakePlayConnector(self._prs()))
        with TemporaryDirectory() as td:
            store = ASOFeatureStore(Path(td) / "aso")
            conn = ASORealityConnector(
                data_providers=[gp, ExternalASOProvider()],
                review_providers=[],
                feature_store=store,
            )
            res = conn.collect(
                "com.born2play.mergewitch",
                platform=Platform.GOOGLE_PLAY,
                persist=False,
            )
            assert isinstance(res, ASOCollectResult)
            # GP data survived the merge; external contributed nothing
            assert res.reality.installs == 5000
            assert res.quality.status == ASODataQualityFlag.OK
            # normalized ASOSnapshot carries installs + rating
            assert res.aso_snapshot.installs == 5000
            assert abs(res.aso_snapshot.rating - 4.3) < 1e-6


# --------------------------------------------------------------------------- #
# 2. Review collection
# --------------------------------------------------------------------------- #
class TestReviewCollection:
    def _reviews(self, n: int = 100):
        out = []
        for i in range(n):
            star = 5 if i % 4 else 2
            out.append(
                {
                    "star_rating": star,
                    "text": "love this merge game so much magic" if i % 3 else "ok",
                    "author": f"user_{i}",
                }
            )
        return out

    def test_hundred_reviews_to_records(self):
        client = FakeReviewClient(self._reviews(100))
        provider = GooglePlayReviewProvider(client=client)
        recs = provider.fetch_reviews(
            "com.born2play.mergewitch", platform=Platform.GOOGLE_PLAY
        )
        assert len(recs) == 100
        assert all(isinstance(r, ReviewRecord) for r in recs)
        # star ratings preserved (including the 2-star cases)
        assert any(abs(r.rating - 2.0) < 1e-6 for r in recs)
        assert any(abs(r.rating - 5.0) < 1e-6 for r in recs)

    def test_non_google_platform_no_reviews(self):
        client = FakeReviewClient(self._reviews(50))
        provider = GooglePlayReviewProvider(client=client)
        assert provider.fetch_reviews("ios.game", platform=Platform.APP_STORE) == []

    def test_review_provider_failure_is_safe(self):
        class BoomClient:
            def get_reviews(self, *a, **k):
                raise RuntimeError("network down")

        provider = GooglePlayReviewProvider(client=BoomClient())
        assert (
            provider.fetch_reviews("x", platform=Platform.GOOGLE_PLAY) == []
        )


# --------------------------------------------------------------------------- #
# 3. Multi-platform isolation
# --------------------------------------------------------------------------- #
class TestMultiPlatformIsolation:
    def test_connector_isolates_platforms(self):
        gp_snap = ASORealitySnapshot(
            game_id="game_a",
            platform=Platform.GOOGLE_PLAY,
            installs=1000,
            rating=4.0,
            review_count=50,
            source="google_play:live",
        )
        ios_snap = ASORealitySnapshot(
            game_id="game_b",
            platform=Platform.APP_STORE,
            installs=2000,
            rating=4.5,
            review_count=80,
            source="app_store:live",
        )
        gp = FakeDataProvider(Platform.GOOGLE_PLAY, gp_snap)
        ios = FakeDataProvider(Platform.APP_STORE, ios_snap)

        with TemporaryDirectory() as td:
            store = ASOFeatureStore(Path(td) / "aso")
            conn = ASORealityConnector(
                data_providers=[gp, ios],
                review_providers=[],
                feature_store=store,
            )
            ra = conn.collect("game_a", platform=Platform.GOOGLE_PLAY)
            rb = conn.collect("game_b", platform=Platform.APP_STORE)

            # correct platforms, no leakage
            assert ra.reality.platform == Platform.GOOGLE_PLAY
            assert ra.reality.installs == 1000
            assert rb.reality.platform == Platform.APP_STORE
            assert rb.reality.installs == 2000

            # feature store isolation
            assert store.latest("game_a", Platform.GOOGLE_PLAY).installs == 1000
            assert store.latest("game_b", Platform.APP_STORE).installs == 2000
            assert store.latest("game_a", Platform.APP_STORE) is None
            assert store.latest("game_b", Platform.GOOGLE_PLAY) is None


# --------------------------------------------------------------------------- #
# 4. Feature Store round-trip
# --------------------------------------------------------------------------- #
class TestFeatureStore:
    def test_record_latest_history(self):
        with TemporaryDirectory() as td:
            store = ASOFeatureStore(Path(td) / "aso")
            base = datetime(2026, 7, 1, tzinfo=timezone.utc)
            for day in (1, 5, 10):
                snap = ASORealitySnapshot(
                    game_id="game_a",
                    platform=Platform.GOOGLE_PLAY,
                    timestamp=base + timedelta(days=day),
                    installs=1000 + day,
                    rating=4.0,
                    review_count=50,
                    source="google_play:live",
                )
                store.record_snapshot(snap, quality=None)

            hist = store.history("game_a", Platform.GOOGLE_PLAY)
            assert len(hist) == 3
            assert hist[0].installs == 1001
            assert hist[-1].installs == 1010

            latest = store.latest("game_a", Platform.GOOGLE_PLAY)
            assert latest.installs == 1010

    def test_history_days_filter(self):
        with TemporaryDirectory() as td:
            store = ASOFeatureStore(Path(td) / "aso")
            now = datetime.now(timezone.utc)
            store.record_snapshot(
                ASORealitySnapshot(
                    game_id="g",
                    platform=Platform.GOOGLE_PLAY,
                    timestamp=now - timedelta(days=40),
                    installs=1,
                    rating=3.0,
                    review_count=1,
                    source="google_play:live",
                )
            )
            store.record_snapshot(
                ASORealitySnapshot(
                    game_id="g",
                    platform=Platform.GOOGLE_PLAY,
                    timestamp=now - timedelta(days=2),
                    installs=2,
                    rating=3.0,
                    review_count=1,
                    source="google_play:live",
                )
            )
            assert len(store.history("g", Platform.GOOGLE_PLAY, days=30)) == 1
            assert len(store.history("g", Platform.GOOGLE_PLAY)) == 2

    def test_reviews_round_trip(self):
        with TemporaryDirectory() as td:
            store = ASOFeatureStore(Path(td) / "aso")
            recs = [
                ReviewRecord(
                    game_id="g",
                    platform=Platform.GOOGLE_PLAY,
                    rating=5.0,
                    text="great",
                    source="google_play",
                ),
                ReviewRecord(
                    game_id="g",
                    platform=Platform.GOOGLE_PLAY,
                    rating=1.0,
                    text="bad",
                    source="google_play",
                ),
            ]
            store.record_reviews("g", Platform.GOOGLE_PLAY, recs)
            got = store.latest_reviews("g", Platform.GOOGLE_PLAY)
            assert len(got) == 2
            assert {r.text for r in got} == {"great", "bad"}

    def test_quality_attached_to_snapshot(self):
        with TemporaryDirectory() as td:
            store = ASOFeatureStore(Path(td) / "aso")
            snap = ASORealitySnapshot(
                game_id="g",
                platform=Platform.GOOGLE_PLAY,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),  # stale
                installs=None,  # missing
                rating=None,
                review_count=None,
                source="fallback",
            )
            store.record_snapshot(snap, quality=None)
            # re-read and re-gate manually to confirm stale+missing detection
            latest = store.latest("g", Platform.GOOGLE_PLAY)
            from src.aso_intelligence.reality.models import ASODataQuality

            q = ASODataQuality.from_snapshot(latest)
            assert q.is_stale
            # both flags present; status surfaces the highest-priority one
            assert ASODataQualityFlag.MISSING_FIELDS in q.flags
            assert q.status == ASODataQualityFlag.STALE_DATA


# --------------------------------------------------------------------------- #
# 5. Agent closed loop: Reality -> ASOSnapshot -> Insight -> Action -> Memory
# --------------------------------------------------------------------------- #
class TestAgentClosedLoop:
    def _build_connector(self, td: str):
        prs = PlayRealitySnapshot(
            package_name="com.born2play.mergewitch",
            installs=1500,
            rating_average=4.5,
            review_count=1200,
            negative_review_ratio=0.1,
            sources={"store": "live"},
            collected_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )
        reviews = [
            {"star_rating": 5, "text": "love the magic merge", "author": f"u{i}"}
            for i in range(10)
        ] + [
            {"star_rating": 4, "text": "good puzzle", "author": f"v{i}"}
            for i in range(10)
        ]
        store = ASOFeatureStore(Path(td) / "aso")
        return ASORealityConnector(
            data_providers=[GooglePlayProvider(play_connector=FakePlayConnector(prs))],
            review_providers=[GooglePlayReviewProvider(client=FakeReviewClient(reviews))],
            competitor_provider=NullCompetitorProvider(),
            feature_store=store,
        )

    def test_run_produces_insights_and_actions(self):
        with TemporaryDirectory() as td:
            agent = ASOIntelligenceAgent()
            conn = self._build_connector(td)
            result = agent.run(
                "com.born2play.mergewitch",
                conn,
                intent_keywords=["merge", "witch", "magic", "puzzle"],
            )
            assert isinstance(result, ASOAgentRunResult)
            # reality was collected + normalized
            assert result.reality.installs == 1500
            assert result.aso_snapshot.installs == 1500
            # quality healthy (all required fields present, fresh)
            assert result.quality.status == ASODataQualityFlag.OK
            # analyzers produced insights + gated actions
            assert result.report.insights
            assert result.report.actions
            assert all(a.action in ASOAction for a in result.report.actions)
            # "magic" appears in reviews -> keyword opportunity action
            action_values = {a.action for a in result.report.actions}
            assert ASOAction.ADD_KEYWORD in action_values

    def test_run_persists_and_records_outcome(self):
        with TemporaryDirectory() as td:
            mem = ASOMemory(
                str(Path(td) / "exp.jsonl"), str(Path(td) / "pat.jsonl")
            )
            sink = RecordingSink()
            agent = ASOIntelligenceAgent(memory=mem, action_sink=sink)
            conn = self._build_connector(td)

            result = agent.run(
                "com.born2play.mergewitch",
                conn,
                intent_keywords=["merge", "witch", "magic", "puzzle"],
            )
            assert result.report.actions

            # close the loop: record a real outcome into memory
            exp = agent.record_outcome(
                "com.born2play.mergewitch",
                ASOAction.ADD_KEYWORD,
                "added magic keyword",
                before_revenue=1000.0,
                after_revenue=1180.0,
                before_cvr=0.15,
                after_cvr=0.18,
            )
            assert exp is not None and exp.success is True
            stats = mem.stats("com.born2play.mergewitch", ASOAction.ADD_KEYWORD)
            assert stats["n"] == 1

            # reality was persisted to the feature store
            assert (
                conn.feature_store.latest(
                    "com.born2play.mergewitch", Platform.GOOGLE_PLAY
                )
                is not None
            )


# --------------------------------------------------------------------------- #
# 6. Normalizer cross-platform unification (installs == downloads)
# --------------------------------------------------------------------------- #
class TestNormalizerUnification:
    def test_apple_downloads_normalized_to_installs(self):
        # An App Store reality where the field would be "downloads" upstream;
        # the provider maps it to `installs` and the normalizer is agnostic.
        reality = ASORealitySnapshot(
            game_id="ios_game",
            platform=Platform.APP_STORE,
            installs=9000,
            product_page_views=30000,
            rating=4.7,
            review_count=400,
            title="iOS Game",
            source="app_store:live",
        )
        snap = ASONormalizer.to_aso_snapshot(reality, reviews=[])
        assert snap.installs == 9000
        # product_page_views -> store_visits
        assert snap.store_visits == 30000
        # raw creative assets preserved for E16.6.3, not synthesized
        assert snap.screenshots == []
        assert snap.extra["source"] == "app_store:live"

    def test_merge_prefers_non_null(self):
        a = ASORealitySnapshot(
            game_id="g",
            platform=Platform.GOOGLE_PLAY,
            installs=100,
            source="google_play:live",
        )
        b = ASORealitySnapshot(
            game_id="g",
            platform=Platform.GOOGLE_PLAY,
            rating=4.2,
            review_count=10,
            source="external:live",
        )
        merged = ASONormalizer.merge([a, b])
        assert merged.installs == 100
        assert merged.rating == 4.2
        assert merged.review_count == 10
        # source preference: last non-null wins
        assert merged.source == "external:live"
