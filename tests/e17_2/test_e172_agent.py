"""E17.2 端到端测试（Test7）：Reality Hub → Opportunity Engine → Report。

用 GrowthFeatureStore 写入 prev/cur 快照造出环比信号，
驱动 GrowthOpportunityAgent 产出 OpportunityReport。
"""
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AsoFact,
    GrowthRealitySnapshot,
    ProductFact,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot

from src.ceo_intelligence.opportunity_engine.agent import GrowthOpportunityAgent
from src.ceo_intelligence.opportunity_engine.models import OpportunityType


def _seed_store(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    # 游戏 A：收入从 2000 跌到 1400（-30%）→ REVENUE_RECOVERY
    store.append(GrowthRealitySnapshot(
        game_id="A", timestamp="2026-07-28",
        revenue=RevenueFact(daily_revenue=2000, payer_count=10),
        product=ProductFact(dau=1000), confidence=1.0))
    store.append(GrowthRealitySnapshot(
        game_id="A", timestamp="2026-07-29",
        revenue=RevenueFact(daily_revenue=1400, payer_count=7),
        product=ProductFact(dau=1000), confidence=1.0))
    # 游戏 B：商店 CVR 从 0.05 跌到 0.04（-20%），评分 4.6 → ASO_OPTIMIZATION
    store.append(GrowthRealitySnapshot(
        game_id="B", timestamp="2026-07-28",
        aso=AsoFact(ranking=10, store_cvr=0.05, rating=4.6, review_velocity=3), confidence=1.0))
    store.append(GrowthRealitySnapshot(
        game_id="B", timestamp="2026-07-29",
        aso=AsoFact(ranking=10, store_cvr=0.04, rating=4.6, review_velocity=3), confidence=1.0))
    return store


def test_e2e_hub_to_opportunity_report(tmp_path):
    store = _seed_store(tmp_path)
    cur_A = store.latest("A")
    cur_B = store.latest("B")
    company = build_company_snapshot([cur_A, cur_B], "2026-07-29")

    agent = GrowthOpportunityAgent()
    report = agent.analyze(company, store=store)

    # 两类机会均被发现
    assert report.total_opportunities == 2
    types = {o.type for o in report.top_priority}
    assert OpportunityType.REVENUE_RECOVERY in types
    assert OpportunityType.ASO_OPTIMIZATION in types

    # 组合排序每游戏一条
    assert len(report.portfolio_ranking) == 2

    # 风险摘要计数齐全
    rs = report.risk_summary
    assert rs["high"] + rs["medium"] + rs["low"] == 2

    # 优先级最高的是收入下滑（score 更大）
    assert report.top_priority[0].game_id == "A"

    # 中文报告可渲染
    md = report.to_markdown()
    assert "增长机会报告" in md
    assert "A" in md and "B" in md


def test_e2e_empty_company_no_opportunities(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    company = build_company_snapshot([], "2026-07-29")
    report = GrowthOpportunityAgent().analyze(company, store=store)
    assert report.total_opportunities == 0
    assert report.portfolio_ranking == []
