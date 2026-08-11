"""E17.4 Test7：端到端 Reality → Opportunity → Decision → Strategy Plan。"""
from src.ceo_intelligence.decision_engine.models import DecisionType
from src.ceo_intelligence.strategy_planner.agent import (
    GrowthStrategyPlannerAgent,
    run_pipeline,
)
from src.ceo_intelligence.strategy_planner.planner import StrategyGraph
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import AsoFact, CreativeFact, GrowthRealitySnapshot, RevenueFact
from src.growth_reality.snapshot import build_company_snapshot


def _build_company(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    # merge_witch：收入 -30% + 创意疲劳 → CREATIVE_REFRESH
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d0",
        revenue=RevenueFact(5000, 50), creative=CreativeFact(0.03, 0.2, 80),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d1",
        revenue=RevenueFact(3500, 35), creative=CreativeFact(0.022, 0.85, 55),
        confidence=1.0,
    ))
    # puzzle_island：商店 CVR -20%，评分高 → ASO_OPTIMIZATION
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d0", aso=AsoFact(12, 0.05, 4.6, 4), confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d1", aso=AsoFact(12, 0.04, 4.6, 4), confidence=1.0,
    ))
    company = build_company_snapshot(
        [store.latest("merge_witch"), store.latest("puzzle_island")], "2026-07-29"
    )
    return store, company


def test_e2e_reality_to_strategy_plan(tmp_path):
    """Test7：完整链路产出可执行的作战计划组合。"""
    store, company = _build_company(tmp_path)

    dec_report, portfolio = run_pipeline(
        company, store=store,
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )

    # 决策已产出
    assert dec_report.total_decisions >= 2

    # 作战计划组合已生成
    assert portfolio.summary["planned"] >= 2
    assert portfolio.summary["rejected"] == 0

    # 至少有一条 creative_refresh 计划含 5 步且依赖图合法
    cr = next(
        (p for p in portfolio.plans if p.strategy_type == "creative_refresh"), None
    )
    assert cr is not None
    assert len(cr.tasks) == 5
    assert StrategyGraph(cr.tasks).is_valid() is True

    # 组合可渲染为 CEO 周计划 markdown
    md = portfolio.to_markdown()
    assert "每周经营作战计划" in md
    assert "merge_witch" in md


def test_portfolio_plan_from_decision_report(tmp_path):
    """批量入口：DecisionReport → PortfolioStrategyPlan。"""
    store, company = _build_company(tmp_path)
    # 复用 E17.3 的 run_pipeline 拿 DecisionReport
    from src.ceo_intelligence.decision_engine.agent import run_pipeline as dec_pipe
    _, dec_report = dec_pipe(
        company, store=store,
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )
    agent = GrowthStrategyPlannerAgent()
    portfolio = agent.create_portfolio_plan(dec_report)
    assert portfolio.summary["planned"] >= 2
    # 每条计划都通过质量门禁
    for p in portfolio.plans:
        assert p.quality_gate_passed is True
        assert p.needs_approval in (True, False)
