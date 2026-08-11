"""E17.4 模型 + Test1：Creative Refresh 生成 5 个步骤。"""
from src.ceo_intelligence.decision_engine.models import DecisionType, GrowthDecision
from src.ceo_intelligence.strategy_planner.agent import GrowthStrategyPlannerAgent
from src.ceo_intelligence.strategy_planner.models import GrowthStrategyPlan


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


def test_creative_refresh_five_steps():
    """Test1：CREATIVE_REFRESH 生成 5 步。"""
    agent = GrowthStrategyPlannerAgent()
    plan = agent.create_plan(_dec("merge_witch", "creative_refresh"))

    assert isinstance(plan, GrowthStrategyPlan)
    assert plan.strategy_type == "creative_refresh"
    assert plan.objective == "Recover creative fatigue"
    assert len(plan.tasks) == 5
    assert plan.estimated_duration_days == 14
    # 5 个 owner 角色齐备
    owners = {t.owner for t in plan.tasks}
    assert "Creative Agent" in owners and "UA Agent" in owners and "Analytics" in owners
    # 成功指标可量化
    assert plan.success_metrics.get("ctr") == "+15%"
    assert plan.success_metrics.get("roas") == "+10%"


def test_plan_roundtrip():
    """模型 to_dict / from_dict 往返一致。"""
    agent = GrowthStrategyPlannerAgent()
    plan = agent.create_plan(_dec("merge_witch", "creative_refresh"))
    d = plan.to_dict()
    back = GrowthStrategyPlan.from_dict(d)
    assert back.strategy_type == plan.strategy_type
    assert len(back.tasks) == len(plan.tasks)
    assert back.tasks[1].dependency == plan.tasks[1].dependency
    assert back.success_metrics == plan.success_metrics
