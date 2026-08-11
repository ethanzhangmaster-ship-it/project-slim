"""E17.4 Test2（UA Scale）+ Test3（ASO）模板内容校验。"""
from src.ceo_intelligence.decision_engine.models import DecisionType, GrowthDecision
from src.ceo_intelligence.strategy_planner.agent import GrowthStrategyPlannerAgent


def _dec(game_id, otype, conf=0.9, ev=0.2, risk=0.3, dtype=DecisionType.EXECUTE):
    return GrowthDecision(
        game_id=game_id,
        opportunity_id=f"{game_id}:{otype}",
        action=f"{otype} ({game_id})",
        decision_type=dtype,
        expected_value=ev,
        confidence=conf,
        risk=risk,
        reason="test",
        created_at="2026-07-29",
    )


def test_ua_scale_budget_and_roas():
    """Test2：UA_SCALE 含「预算增加」与「monitor ROAS」。"""
    agent = GrowthStrategyPlannerAgent()
    plan = agent.create_plan(_dec("merge_witch", "ua_scale"))
    actions = " ".join(t.action.lower() for t in plan.tasks)
    assert "budget" in actions and "20%" in actions
    assert "monitor roas" in actions
    # 成功指标含 roas / cpi
    assert "roas" in plan.success_metrics and "cpi" in plan.success_metrics


def test_aso_keyword_listing_experiment():
    """Test3：ASO_OPTIMIZATION 含 keyword / listing / experiment。"""
    agent = GrowthStrategyPlannerAgent()
    plan = agent.create_plan(_dec("puzzle_island", "aso_optimization"))
    actions = " ".join(t.action.lower() for t in plan.tasks)
    assert "keyword" in actions
    assert "listing" in actions
    assert "experiment" in actions
    assert len(plan.tasks) == 4
