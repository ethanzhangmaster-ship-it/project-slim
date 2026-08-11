"""E17.7 — ingest 适配器 + 模式提炼 + 学习反馈闭环。"""
from src.ceo_intelligence.decision_engine.models import (
    DecisionType,
    GrowthDecision,
    SimulationResult,
)
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.models import ExecutionExperience
from src.ceo_intelligence.growth_memory_graph.ingest import (
    event_from_decision,
    event_from_opportunity,
    event_from_strategy,
)
from src.ceo_intelligence.growth_memory_graph.models import EdgeType, NodeType
from src.ceo_intelligence.growth_memory_graph.patterns import (
    confidence_boost_for,
    extract_patterns,
    record_outcome,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.ceo_intelligence.opportunity_engine.models import (
    GrowthOpportunity,
    OpportunityType,
)
from src.ceo_intelligence.strategy_planner.models import GrowthStrategyPlan


def _graph(tmp_path) -> GrowthMemoryGraph:
    return GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))


def _exp(action_id, success=True, strategy_type="creative_refresh",
         domain="creative", action_type="generate_creatives",
         execution_id="exec_1") -> ExecutionExperience:
    return ExecutionExperience(
        execution_id=execution_id, action_id=action_id, decision_id="dec_1",
        game_id="merge_witch", strategy_type=strategy_type, domain=domain,
        action_type=action_type, status="success" if success else "failed",
        success=success,
    )


# --------------------------------------------------------------------------- #
# ingest 适配器
# --------------------------------------------------------------------------- #
def test_event_from_opportunity(tmp_path):
    g = _graph(tmp_path)
    opp = GrowthOpportunity(
        game_id="merge_witch", type=OpportunityType.CREATIVE_REFRESH,
        title="创意疲劳", problem="CTR -27%", expected_impact=0.15,
        confidence=0.8, risk=0.3, priority=0.4,
    )
    g.ingest_event(event_from_opportunity(opp))
    node = g.get_node("opportunity:merge_witch:creative_refresh")
    assert node is not None
    assert abs(node.payload["expected_impact"] - 0.15) < 1e-6
    assert g.neighbors("game:merge_witch", EdgeType.HAS_OPPORTUNITY)[0].id == node.id


def test_event_from_decision_and_strategy_link(tmp_path):
    """decision.audit_id = plan.decision_id → 图上 DECISION 与 STRATEGY 相连。"""
    g = _graph(tmp_path)
    dec = GrowthDecision(
        game_id="merge_witch", opportunity_id="merge_witch:creative_refresh",
        action="刷新创意素材（merge_witch）", decision_type=DecisionType.EXECUTE,
        expected_value=0.15, confidence=0.9, risk=0.2, reason="记忆加成",
        simulation=SimulationResult(0.12, 0.05, 0.9, 0.2),
    )
    g.ingest_event(event_from_decision(dec))
    plan = GrowthStrategyPlan(
        game_id="merge_witch", decision_id=dec.audit_id, objective="恢复创意效率",
        strategy_type="creative_refresh", confidence=0.9, expected_value=0.15,
    )
    g.ingest_event(event_from_strategy(plan))

    dec_node = g.get_node(f"decision:{dec.audit_id}")
    assert dec_node.payload["decision_type"] == "execute"
    # opportunity → decision → strategy 全通
    assert g.neighbors("opportunity:merge_witch:creative_refresh",
                       EdgeType.LEADS_TO_DECISION)[0].id == dec_node.id
    strat = g.neighbors(dec_node.id, EdgeType.PLANS_STRATEGY)
    assert strat[0].payload["strategy_type"] == "creative_refresh"


# --------------------------------------------------------------------------- #
# 模式提炼 + 反馈
# --------------------------------------------------------------------------- #
def _seed(g, tmp_path):
    mem = ExecutionMemory(str(tmp_path / "mem.jsonl"))
    mem.record(_exp("a1", True))
    mem.record(_exp("a2", True, execution_id="exec_2"))
    mem.record(_exp("a3", False, strategy_type="aso_optimization",
                    domain="aso", action_type="update_listing",
                    execution_id="exec_3"))
    g.build_from_execution_memory(mem)


def test_extract_patterns_and_ordering(tmp_path):
    g = _graph(tmp_path)
    _seed(g, tmp_path)
    patterns = extract_patterns(g)
    assert len(patterns) == 2
    top = patterns[0]  # 成功率降序：creative 1.0 在前
    assert top.strategy_type == "creative_refresh"
    assert top.samples == 2 and top.successes == 2
    assert abs(top.success_rate - 1.0) < 1e-6
    assert abs(top.confidence_boost - 0.15) < 1e-6  # min(0.20, 1.0*0.15)
    aso = patterns[1]
    assert aso.samples == 1
    assert abs(aso.confidence_boost - 0.0) < 1e-6   # <2 样本无加成


def test_confidence_boost_for(tmp_path):
    g = _graph(tmp_path)
    _seed(g, tmp_path)
    assert abs(confidence_boost_for(g, "creative_refresh") - 0.15) < 1e-6
    assert abs(confidence_boost_for(g, "creative_refresh",
                                    domain="creative",
                                    action_type="generate_creatives") - 0.15) < 1e-6
    assert abs(confidence_boost_for(g, "aso_optimization") - 0.0) < 1e-6
    assert abs(confidence_boost_for(g, "nonexistent") - 0.0) < 1e-6


def test_record_outcome_feeds_avg_revenue_delta(tmp_path):
    g = _graph(tmp_path)
    _seed(g, tmp_path)
    assert record_outcome(g, "exec_1", 0.18, "创意刷新后 7 日收入 +18%") is True
    assert record_outcome(g, "exec_2", 0.10) is True
    assert record_outcome(g, "exec_missing", 0.5) is False

    node = g.get_node("execution:exec_1")
    assert abs(node.payload["revenue_delta"] - 0.18) < 1e-6

    top = extract_patterns(g)[0]
    assert abs(top.avg_revenue_delta - 0.14) < 1e-6  # (0.18+0.10)/2

    # 持久化：重载后 outcome 仍在
    g2 = GrowthMemoryGraph(path=str(g.path))
    assert abs(g2.get_node("execution:exec_1").payload["revenue_delta"] - 0.18) < 1e-6
