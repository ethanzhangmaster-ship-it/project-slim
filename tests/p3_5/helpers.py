"""
P3.5 测试夹具：构造 5 个 memory 源的最小可用实例（全部隔离在临时路径），
供 test_knowledge / test_contract_boundary 复用。
"""
from __future__ import annotations

import tempfile

from src.ceo_intelligence.growth_memory_graph.knowledge import GrowthKnowledgeGraph
from src.ceo_intelligence.growth_memory_graph.models import (
    GraphNode,
    NodeType,
    node_id,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.execution.recovery import JsonlRecoveryExperienceStore, RecoveryExperienceRecord
from src.operator.strategy.memory import StrategyMemoryAdapter
from src.operator.portfolio.optimizer_models import (
    OptimizationStatus,
    PortfolioOptimizationResult,
)
from src.operator.portfolio.proposal import (
    PortfolioProposal,
    ProposalGuardVerdict,
    ProposalItem,
)
from src.operator.portfolio.ranking_models import PortfolioVerdict
from src.operator.report.models import ActionState


def _tmp() -> str:
    fd = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    p = fd.name
    fd.close()
    return p


def build_e17_graph() -> GrowthMemoryGraph:
    """构造一个最小的 E17.7 图（含 GAME / EXECUTION / RESULT），供模式与连接推导。"""
    g = GrowthMemoryGraph(path=_tmp())
    for gid in ("game_001", "game_002"):
        g.add_node(
            GraphNode(
                id=node_id(NodeType.GAME, gid),
                type=NodeType.GAME,
                label=gid,
                payload={"game_id": gid},
            )
        )
    # game_001: 两个域均成功
    g.add_node(
        GraphNode(
            id=node_id(NodeType.EXECUTION, "exec_1"),
            type=NodeType.EXECUTION,
            label="game_001:creative_refresh",
            payload={
                "game_id": "game_001",
                "execution_id": "exec_1",
                "strategy_type": "creative_refresh",
            },
        )
    )
    g.add_node(
        GraphNode(
            id=node_id(NodeType.RESULT, "act_1a"),
            type=NodeType.RESULT,
            label="success",
            payload={
                "game_id": "game_001",
                "execution_id": "exec_1",
                "strategy_type": "creative_refresh",
                "domain": "creative",
                "action_type": "analyze_dna",
                "status": "success",
                "success": True,
            },
        )
    )
    g.add_node(
        GraphNode(
            id=node_id(NodeType.RESULT, "act_1b"),
            type=NodeType.RESULT,
            label="success",
            payload={
                "game_id": "game_001",
                "execution_id": "exec_1",
                "strategy_type": "creative_refresh",
                "domain": "ua",
                "action_type": "run_experiment",
                "status": "success",
                "success": True,
            },
        )
    )
    # game_002: creative 成功 / ua 失败（共享 strategy_type 形成相似度）
    g.add_node(
        GraphNode(
            id=node_id(NodeType.EXECUTION, "exec_2"),
            type=NodeType.EXECUTION,
            label="game_002:creative_refresh",
            payload={
                "game_id": "game_002",
                "execution_id": "exec_2",
                "strategy_type": "creative_refresh",
            },
        )
    )
    g.add_node(
        GraphNode(
            id=node_id(NodeType.RESULT, "act_2a"),
            type=NodeType.RESULT,
            label="success",
            payload={
                "game_id": "game_002",
                "execution_id": "exec_2",
                "strategy_type": "creative_refresh",
                "domain": "creative",
                "action_type": "analyze_dna",
                "status": "success",
                "success": True,
            },
        )
    )
    g.add_node(
        GraphNode(
            id=node_id(NodeType.RESULT, "act_2b"),
            type=NodeType.RESULT,
            label="failure",
            payload={
                "game_id": "game_002",
                "execution_id": "exec_2",
                "strategy_type": "creative_refresh",
                "domain": "ua",
                "action_type": "run_experiment",
                "status": "failed",
                "success": False,
            },
        )
    )
    return g


def build_strategy_memory() -> StrategyMemoryAdapter:
    sm = StrategyMemoryAdapter(store_path=None)  # 内存态，不落盘
    # 让 creative_refresh 成为已知策略态，且其维度映射 growth->ua，便于 lifecycle 查询
    sm.ensure("creative_refresh", "ua")
    return sm


def build_execution_memory() -> ExecutionMemory:
    em = ExecutionMemory(path=_tmp())
    rows = [
        ("exec_1", "a1", "d1", "game_001", "creative", "analyze_dna", True, True),
        ("exec_1", "a2", "d1", "game_001", "ua", "run_experiment", True, True),
        ("exec_2", "a3", "d2", "game_002", "creative", "analyze_dna", True, True),
        ("exec_2", "a4", "d2", "game_002", "ua", "run_experiment", False, False),
    ]
    for (eid, aid, did, gid, dom, at, succ, rb) in rows:
        em.record(
            _experience(eid, aid, did, gid, dom, at, succ, rb)
        )
    return em


def _experience(eid, aid, did, gid, dom, at, succ, rb):
    # 延迟导入避免循环；ExecutionExperience 字段与 memory.py 一致
    from src.ceo_intelligence.execution_router.models import ExecutionExperience

    return ExecutionExperience(
        execution_id=eid,
        action_id=aid,
        decision_id=did,
        game_id=gid,
        strategy_type="creative_refresh",
        domain=dom,
        action_type=at,
        status="success" if succ else "failed",
        success=succ,
        real_api_called=False,
        rolled_back=rb,
        detail="fixture",
    )


def build_recovery_store() -> JsonlRecoveryExperienceStore:
    rs = JsonlRecoveryExperienceStore(path=_tmp())
    rec = RecoveryExperienceRecord(
        failure="timeout",
        action="run_experiment",
        recovery="retry",
        result="success",
        reward=0.8,
        provider="meta",
        incident_id="inc_001",
        attempts=2,
        metadata={"severity": "low", "execution_id": "exec_1"},
    )
    rs.add(rec)
    return rs


def build_portfolio_result() -> PortfolioOptimizationResult:
    item = ProposalItem(
        game_id="game_001",
        rank=1,
        recommended_action=PortfolioVerdict.SCALE,
        budget_delta=10.0,
        current_spend=100.0,
        proposed_spend=110.0,
        action_state=ActionState.AUTO,
        confidence=0.8,
        priority=80.0,
        rationale="creative_refresh SCALE: high portfolio score",
    )
    prop = PortfolioProposal(
        proposal_id="prop_1",
        items=[item],
        summary="scale game_001",
        recommendation="scale game_001",
        confidence=0.8,
        guard_verdict=ProposalGuardVerdict.PROPOSABLE,
        auto_count=1,
        approval_count=0,
        blocked_count=0,
    )
    return PortfolioOptimizationResult(
        optimization_id="opt_1",
        proposal=prop,
        simulation=None,
        ranked_games=[],
        evidence=["fixture evidence"],
        status=OptimizationStatus.COMPLETED,
        real_api_called=False,
    )


def build_knowledge_graph() -> GrowthKnowledgeGraph:
    g = build_e17_graph()
    kg = GrowthKnowledgeGraph(graph=g)
    kg.consolidate(
        strategy_memory=build_strategy_memory(),
        execution_memory=build_execution_memory(),
        recovery_store=build_recovery_store(),
        portfolio_results=[build_portfolio_result()],
    )
    return kg
