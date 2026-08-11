"""E17.4 Test6：策略记忆（历史成功策略 → 置信度加成）。"""
from src.ceo_intelligence.decision_engine.models import DecisionType, GrowthDecision
from src.ceo_intelligence.strategy_planner.agent import GrowthStrategyPlannerAgent
from src.ceo_intelligence.strategy_planner.memory import StrategyMemory


def _dec(game_id, otype, conf=0.85, ev=0.2, risk=0.3, dtype=DecisionType.EXECUTE):
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


def test_memory_boosts_confidence(tmp_path):
    """Test6：≥2 条成功历史 → 新计划置信度提升。"""
    mem = StrategyMemory(path=str(tmp_path / "strategy_memory.jsonl"))
    # 历史：Merge 类 / Creative Refresh / UGC+真人开场 → ROAS +23% / +18%
    mem.record_outcome(
        game_id="merge_witch", strategy_type="creative_refresh",
        objective="UGC + 真人开场", outcome_impact=0.23, notes="roas +23%",
    )
    mem.record_outcome(
        game_id="merge_witch", strategy_type="creative_refresh",
        objective="UGC + 真人开场", outcome_impact=0.18, notes="roas +18%",
    )

    agent = GrowthStrategyPlannerAgent(memory=mem)
    plan = agent.create_plan(_dec("merge_witch", "creative_refresh", conf=0.85))
    # 基线 0.85 → 加成（rate=1.0 → +0.15，封顶 0.99）
    assert plan.confidence > 0.85
    assert plan.confidence == 0.99

    # 无记忆的同类型不同游戏不加成
    agent2 = GrowthStrategyPlannerAgent()  # 无 memory
    plan2 = agent2.create_plan(_dec("puzzle_island", "creative_refresh", conf=0.85))
    assert plan2.confidence == 0.85
