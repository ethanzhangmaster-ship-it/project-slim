"""E17.3 Agent 测试：Test1 多机会排序 + Test6 端到端流水线。"""
from src.ceo_intelligence.decision_engine.agent import (
    GrowthDecisionEngine,
    run_pipeline,
)
from src.ceo_intelligence.decision_engine.models import DecisionType
from src.ceo_intelligence.decision_engine.validator import DecisionValidator
from src.ceo_intelligence.opportunity_engine.models import (
    GrowthOpportunity,
    OpportunityType,
)
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot


def _opp(game_id, otype, **kw):
    return GrowthOpportunity(
        game_id=game_id,
        type=otype,
        title="t",
        problem="p",
        expected_impact=kw.get("ei", 0.2),
        confidence=kw.get("conf", 0.9),
        urgency=kw.get("urg", 0.8),
        risk=kw.get("risk", 0.3),
        suggested_actions=["a"],
        created_at="2026-07-29",
    )


def test_ranking_highest_first(tmp_path):
    """Test1：多机会 → 最高价值排第一。"""
    v = DecisionValidator(
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
    )
    engine = GrowthDecisionEngine(v)
    opps = [
        _opp("gameA", OpportunityType.CREATIVE_REFRESH, ei=0.30, conf=0.9, urg=0.8),
        _opp("gameB", OpportunityType.UA_SCALE, ei=0.15, conf=0.9, urg=0.8),
        _opp("gameC", OpportunityType.ASO_OPTIMIZATION, ei=0.10, conf=0.9, urg=0.5),
    ]
    report = engine.analyze_opportunities(opps)
    assert report.ceo_priority_list[0].game_id == "gameA"
    ranks = [it.rank for it in report.ceo_priority_list]
    assert ranks == [1, 2, 3]
    # 摘要计数一致
    s = report.summary
    assert s["execute"] + s["approve"] + s["observe"] + s["reject"] == report.total_decisions


def test_e2e_pipeline_reality_to_decision(tmp_path):
    """Test6：Reality Hub → Opportunity Engine → Decision Engine → Approval。"""
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    # merge_witch：收入 -30% + 创意疲劳
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
    # puzzle_island：商店 CVR -20%，评分高
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d0", aso=AsoFact(12, 0.05, 4.6, 4), confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d1", aso=AsoFact(12, 0.04, 4.6, 4), confidence=1.0,
    ))
    company = build_company_snapshot(
        [store.latest("merge_witch"), store.latest("puzzle_island")], "2026-07-29"
    )

    opp_report, dec_report = run_pipeline(
        company, store=store,
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )

    # 决策已产出
    assert dec_report.total_decisions >= 2
    # 摘要计数自洽
    s = dec_report.summary
    assert s["execute"] + s["approve"] + s["observe"] + s["reject"] == dec_report.total_decisions
    # 至少有一条可行动决策（EXECUTE 或 APPROVE）
    assert s["execute"] + s["approve"] >= 1

    # Approval 环节：把一条 APPROVE 决策走完人工审批闭环
    engine = GrowthDecisionEngine(DecisionValidator(
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
    ))
    approve_dec = next(
        (d for d in dec_report.decisions if d.decision_type == DecisionType.APPROVE), None
    )
    if approve_dec is not None:
        before = len(engine.pending_approvals)
        assert engine.approve(approve_dec.audit_id) is True
        assert len(engine.pending_approvals) == before - 1
