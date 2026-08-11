"""E15.2 — Play Reality Connector 测试.

覆盖: 正常采集 / API 失败 fallback / package 级隔离 / feature_store 自动落库.
"""

import pytest

from operation.publishing_factory.play_runtime.memory.feature_store import (
    PlayFeatureRecord,
    PlayFeatureStore,
)
from operation.publishing_factory.play_runtime.reality.connector import (
    PlayRealityConnector,
)
from operation.publishing_factory.play_runtime.reality.models import (
    PlayRealitySnapshot,
)


class FakeClient:
    """成功路径的假 GooglePlayRealClient."""

    def get_track_status(self, package_name, track="production"):
        return {
            "status": "inProgress",
            "user_fraction": 0.05,
            "version_code": 42,
            "version_name": "1.4.2",
        }

    def get_vitals(self, package_name, window_days=7):
        return {"crash_rate": 0.1, "anr_rate": 0.05, "d1_retention": 32.0}

    def get_reviews(self, package_name, max_results=50):
        return {
            "reviews": [
                {"star_rating": 5},
                {"star_rating": 4},
                {"star_rating": 1},
            ],
            "count": 3,
        }


class ExplodingClient:
    """所有 API 都炸的客户端."""

    def get_track_status(self, package_name, track="production"):
        raise RuntimeError("boom")

    def get_vitals(self, package_name, window_days=7):
        raise RuntimeError("boom")

    def get_reviews(self, package_name, max_results=50):
        raise RuntimeError("boom")


class PartialClient:
    """只有 com.game.bad 会炸, 其他包正常 — 验证 package 隔离."""

    def _guard(self, package_name):
        if package_name == "com.game.bad":
            raise RuntimeError("bad package")

    def get_track_status(self, package_name, track="production"):
        self._guard(package_name)
        return {"status": "inProgress", "user_fraction": 0.2,
                "version_code": 7, "version_name": "0.7"}

    def get_vitals(self, package_name, window_days=7):
        self._guard(package_name)
        return {"crash_rate": 0.2, "anr_rate": 0.1, "d1_retention": None}

    def get_reviews(self, package_name, max_results=50):
        self._guard(package_name)
        return {"reviews": [{"star_rating": 4}], "count": 1}


def test_collect_normal_snapshot():
    conn = PlayRealityConnector(FakeClient())
    snap = conn.collect("com.game.a", persist=False)
    assert isinstance(snap, PlayRealitySnapshot)
    assert snap.package_name == "com.game.a"
    assert snap.version_code == 42
    assert snap.release_state == "inProgress"
    assert snap.rollout_percentage == pytest.approx(5.0)
    assert snap.crash_rate == pytest.approx(0.1)
    assert snap.anr_rate == pytest.approx(0.05)
    assert snap.rating_average == pytest.approx(3.33, abs=0.01)
    assert snap.review_count == 3
    assert snap.negative_review_ratio == pytest.approx(1 / 3, abs=0.001)
    assert snap.sources == {"release": "live", "stability": "live", "store": "live"}
    assert snap.collected_at is not None


def test_collect_api_failure_falls_back():
    conn = PlayRealityConnector(ExplodingClient())
    snap = conn.collect("com.game.a", persist=False)
    # 不抛出, 返回空壳快照
    assert snap.package_name == "com.game.a"
    assert snap.crash_rate is None
    assert snap.rollout_percentage is None
    assert snap.rating_average is None
    assert snap.sources == {
        "release": "fallback", "stability": "fallback", "store": "fallback",
    }


def test_collect_without_client_is_fallback():
    conn = PlayRealityConnector(None)
    snap = conn.collect("com.game.a", persist=False)
    assert snap.sources["release"] == "fallback"
    assert snap.crash_rate is None


def test_collect_many_package_isolation():
    conn = PlayRealityConnector(PartialClient())
    result = conn.collect_many(
        ["com.game.good", "com.game.bad", "com.game.also_good"], persist=False)
    # bad 包不打断整批; Provider 内部 fallback 保证不为 None
    assert set(result) == {"com.game.good", "com.game.bad", "com.game.also_good"}
    good = result["com.game.good"]
    bad = result["com.game.bad"]
    assert good is not None and good.crash_rate == pytest.approx(0.2)
    assert good.sources["release"] == "live"
    assert bad is not None and bad.crash_rate is None
    assert bad.sources["release"] == "fallback"
    # 隔离: good 数据不会串到 bad
    assert bad.version_code is None
    assert good.version_code == 7


def test_collect_persists_to_feature_store(tmp_path):
    store = PlayFeatureStore(path=tmp_path / "features.jsonl")
    conn = PlayRealityConnector(FakeClient(), feature_store=store)
    conn.collect("com.game.a")
    latest = store.latest("com.game.a", "crash_rate")
    assert latest is not None
    assert latest.value == pytest.approx(0.1)
    assert latest.version_code == 42
    # package 隔离查询
    assert store.latest("com.game.b", "crash_rate") is None


def test_feature_store_history_ordering(tmp_path):
    store = PlayFeatureStore(path=tmp_path / "features.jsonl")
    for v in (0.1, 0.2, 0.3):
        store.record(PlayFeatureRecord(
            package_name="com.game.a", feature_name="crash_rate", value=v))
    hist = store.history("com.game.a", "crash_rate")
    assert [r.value for r in hist] == [0.1, 0.2, 0.3]
    assert store.latest("com.game.a", "crash_rate").value == 0.3
    hist2 = store.history("com.game.a", "crash_rate", limit=2)
    assert [r.value for r in hist2] == [0.2, 0.3]
