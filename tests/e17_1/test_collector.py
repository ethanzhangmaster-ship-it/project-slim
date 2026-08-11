"""E17.1 采集层测试：多域打包源 / 单域源 / SIM 确定性。"""
from src.growth_reality.collector import (
    CatalogRealitySource,
    DemoRealitySource,
    RealityCollector,
)


class _SingleDomainSource:
    domain = "revenue"
    source_id = "fake_rev"

    def __init__(self, data):
        self._data = data

    def collect(self, game_id, as_of):
        return self._data


def test_demo_source_deterministic_and_full_domain():
    s = DemoRealitySource()
    a = s.collect("merge_game", "2026-07-29")
    b = s.collect("merge_game", "2026-07-29")
    assert a == b  # 确定性
    for dom in ("revenue", "acquisition", "aso", "creative", "product"):
        assert dom in a, f"missing domain {dom}"
    # 数值合理性
    assert 0 < a["revenue"]["daily_revenue"]
    assert 0 <= a["aso"]["rating"] <= 5


def test_collector_spreads_multi_domain_bundle():
    col = RealityCollector([DemoRealitySource()])
    raw = col.collect_game("g1", "2026-07-29")
    domains = raw["domains"]
    assert "revenue" in domains and "product" in domains
    assert raw["sources"] == ["demo_sim"]


def test_collector_single_domain_source_under_its_domain():
    src = _SingleDomainSource({"daily_revenue": 99.0})
    col = RealityCollector([src])
    raw = col.collect_game("g2", "2026-07-29")
    assert raw["domains"]["revenue"] == {"daily_revenue": 99.0}
    assert raw["sources"] == ["fake_rev"]


def test_catalog_source_known_game():
    src = CatalogRealitySource()
    out = src.collect("2022fruit_veg_quiz", "2026-07-29")
    # 该游戏在 catalog 中存在，status 字段应出现
    assert "release_status" in out
    # catalog 无 metrics → dau 为 0（覆盖盲区）
    assert out["dau"] == 0


def test_catalog_source_unknown_game_empty():
    src = CatalogRealitySource()
    assert src.collect("ghost_game", "2026-07-29") == {}
