"""E17.4 Test4：依赖图（generate → test → evaluate 顺序与 blockers）。"""
from src.ceo_intelligence.decision_engine.models import DecisionType, GrowthDecision
from src.ceo_intelligence.strategy_planner.agent import GrowthStrategyPlannerAgent
from src.ceo_intelligence.strategy_planner.planner import StrategyGraph


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


def test_dependency_order_generate_test_evaluate():
    """Test4：Creative Refresh 依赖链 generate(2) → test(4) → evaluate(5)。"""
    agent = GrowthStrategyPlannerAgent()
    plan = agent.create_plan(_dec("merge_witch", "creative_refresh"))
    graph = StrategyGraph(plan.tasks)

    # 无环且引用合法
    assert graph.is_valid() is True
    assert graph.has_cycle() is False

    # 拓扑顺序：分析(1)→生成(2)→筛选(3)→测试(4)→评估(5)
    order = graph.execution_order()
    assert order.index(1) < order.index(2) < order.index(3) < order.index(4) < order.index(5)

    # blockers 链：评估(5)←测试(4)←筛选(3)←生成(2)←分析(1)
    assert graph.blockers(5) == [4]
    assert graph.blockers(4) == [3]
    assert graph.blockers(3) == [2]
    assert graph.blockers(2) == [1]

    # 步骤 1（分析）无前置
    assert graph.blockers(1) == []
    assert order[0] == 1
