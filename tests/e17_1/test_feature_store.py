"""E17.1 特征存储测试：追加 / 历史 / 最新 / 全舰队。"""
import pytest

from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import GrowthRealitySnapshot, ProductFact, RevenueFact


def _snap(game_id, ts, rev=10.0, dau=100):
    return GrowthRealitySnapshot(
        game_id=game_id,
        timestamp=ts,
        revenue=RevenueFact(daily_revenue=rev, payer_count=1),
        product=ProductFact(dau=dau),
    )


def test_append_and_latest(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    store.append(_snap("g1", "2026-07-28"))
    store.append(_snap("g1", "2026-07-29"))
    assert store.latest("g1").timestamp == "2026-07-29"
    assert len(store.history("g1")) == 2
    assert len(store.history("g1", limit=1)) == 1


def test_history_absent_game(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    assert store.latest("ghost") is None
    assert store.history("ghost") == []


def test_all_latest_multi_game(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    store.append(_snap("g1", "t"))
    store.append(_snap("g2", "t"))
    all_latest = store.all_latest()
    assert set(all_latest.keys()) == {"g1", "g2"}
    assert isinstance(all_latest["g1"], GrowthRealitySnapshot)


def test_persistence_survives_reopen(tmp_path):
    p = str(tmp_path / "gr")
    s1 = GrowthFeatureStore(root=p)
    s1.append(_snap("g1", "t"))
    s2 = GrowthFeatureStore(root=p)  # 重新打开同目录
    assert s2.latest("g1").timestamp == "t"
