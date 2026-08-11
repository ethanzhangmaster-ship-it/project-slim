"""E17.1 Hub 端到端测试：采集→归一→持久化→聚合；SIM 纪律。"""
import pytest

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.collector import CatalogRealitySource, DemoRealitySource
from src.growth_reality.feature_store import GrowthFeatureStore


def test_refresh_fuses_demo_and_catalog(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    hub = GrowthRealityHub(
        sources=[DemoRealitySource(), CatalogRealitySource()], store=store
    )
    game_ids = ["merge_game_a", "2022fruit_veg_quiz"]
    cs = hub.refresh(game_ids, "2026-07-29")
    assert cs.game_count == 2
    # demo 对任意 game_id 都给五域；catalog 桥接对已知游戏生效（sources 中出现）
    assert cs.per_game["merge_game_a"].confidence == 1.0
    assert "catalog" in cs.per_game["2022fruit_veg_quiz"].sources
    assert cs.per_game["2022fruit_veg_quiz"].confidence == 1.0  # demo 覆盖
    # SIM 纪律：无真实 API 调用
    assert hub.last_real_api_called is False


def test_catalog_source_alone_yields_low_confidence(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    # 仅 catalog 源：已知游戏只有 product 域（且 dau=0）→ 低置信度
    hub = GrowthRealityHub(sources=[CatalogRealitySource()], store=store)
    cs = hub.refresh(["2022fruit_veg_quiz"], "2026-07-29")
    snap = cs.per_game["2022fruit_veg_quiz"]
    assert snap.confidence == 0.2  # 仅 product 域
    assert snap.product.dau == 0  # catalog 无 metrics → 覆盖盲区暴露


def test_refresh_persists_to_store(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    hub = GrowthRealityHub(sources=[DemoRealitySource()], store=store)
    hub.refresh(["g_x"], "2026-07-29")
    # 可从 store 重新取回
    snap = hub.query_game("g_x")
    assert snap is not None
    assert snap.game_id == "g_x"
    assert snap.domain_coverage() == 5


def test_query_fleet_rebuilds_company_snapshot(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    hub = GrowthRealityHub(sources=[DemoRealitySource()], store=store)
    hub.refresh(["a", "b", "c"], "2026-07-29")
    cs = hub.query_fleet()
    assert cs.game_count == 3
    assert cs.total_revenue > 0


def test_to_markdown_ceo_view(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    hub = GrowthRealityHub(sources=[DemoRealitySource()], store=store)
    cs = hub.refresh(["g1", "g2"], "2026-07-29")
    md = hub.to_markdown(cs)
    assert "公司增长现实快照" in md
    assert "g1" in md and "g2" in md
