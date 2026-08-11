"""
P3.5.1 测试夹具：构造带历史经验的 GrowthKnowledgeGraph（不依赖 5 源 consolidate）。

直接往 E17.7 图里种高层节点（StrategyResult / ExecutionOutcome / PortfolioDecision），
让 advisor 的 similar_games / why_game_succeeded / strategy_results_by_success 有料可查。
"""
from __future__ import annotations

import tempfile

from src.ceo_intelligence.growth_memory_graph.knowledge import GrowthKnowledgeGraph
from src.ceo_intelligence.growth_memory_graph.knowledge_models import (
    ExecutionOutcome,
    PortfolioDecision,
    StrategyResult,
)
from src.ceo_intelligence.growth_memory_graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    node_id,
)


def _tmp_path() -> str:
    fd = tempfile.NamedTemporaryFile(prefix="p3_5_1_", suffix=".jsonl", delete=False)
    p = fd.name
    fd.close()
    return p


def _add_game(kg: GrowthKnowledgeGraph, gid: str) -> None:
    kg.graph.add_node(
        GraphNode(
            id=node_id(NodeType.GAME, gid),
            type=NodeType.GAME,
            label=gid,
            payload={"game_id": gid},
        )
    )


def _link_strategy(kg, sid, dim, sr, samples, games):
    node = StrategyResult(
        strategy_id=sid,
        dimension=dim,
        success_rate=sr,
        samples=samples,
        games=list(games),
    ).to_node()
    kg.graph.add_node(node)
    for g in games:
        kg.graph.add_edge(
            GraphEdge(
                src=node_id(NodeType.GAME, g),
                tgt=node.id,
                type=EdgeType.HAS_STRATEGY_RESULT,
            )
        )


def _link_execution(kg, gid, domain, sr):
    node = ExecutionOutcome(
        game_id=gid, domain=domain, success_rate=sr, samples=1, rolled_back_rate=0.0
    ).to_node()
    kg.graph.add_node(node)
    kg.graph.add_edge(
        GraphEdge(
            src=node_id(NodeType.GAME, gid),
            tgt=node.id,
            type=EdgeType.HAS_EXECUTION_OUTCOME,
        )
    )


def _link_portfolio(kg, gid, recommendation):
    node = PortfolioDecision(
        game_id=gid,
        recommendation=recommendation,
        confidence=0.8,
        priority=80.0,
        guard="auto",
        status="completed",
        rank=1,
    ).to_node()
    kg.graph.add_node(node)
    kg.graph.add_edge(
        GraphEdge(
            src=node_id(NodeType.GAME, gid),
            tgt=node.id,
            type=EdgeType.HAS_PORTFOLIO_DECISION,
        )
    )


def build_kg_success() -> GrowthKnowledgeGraph:
    """game_a 与两个高成功历史的相似游戏共享经验（Case2 正向）。"""
    kg = GrowthKnowledgeGraph(graph_path=_tmp_path())
    for g in ("game_a", "game_x", "game_z"):
        _add_game(kg, g)
    _link_strategy(kg, "ua_ios", "ua", 0.92, 6, ["game_a", "game_x"])
    _link_strategy(kg, "creative_refresh", "creative", 0.90, 5, ["game_a", "game_z"])
    _link_execution(kg, "game_x", "ua", 0.95)
    _link_execution(kg, "game_z", "creative", 0.90)
    _link_portfolio(kg, "game_x", "scale")
    _link_portfolio(kg, "game_z", "scale")
    return kg


def build_kg_failure() -> GrowthKnowledgeGraph:
    """game_a 与两个低成功/负面历史的相似游戏共享经验（Case3 风险）。"""
    kg = GrowthKnowledgeGraph(graph_path=_tmp_path())
    for g in ("game_a", "game_y", "game_w"):
        _add_game(kg, g)
    _link_strategy(kg, "ua_ios", "ua", 0.18, 6, ["game_a", "game_y"])
    _link_strategy(kg, "monetization_m", "monetization", 0.10, 5, ["game_a", "game_w"])
    _link_execution(kg, "game_y", "ua", 0.15)
    _link_execution(kg, "game_w", "monetization", 0.10)
    _link_portfolio(kg, "game_y", "reduce")
    _link_portfolio(kg, "game_w", "sunset")
    return kg


def build_kg_empty() -> GrowthKnowledgeGraph:
    """game_a 无任何相似经验（Case1 空信号）。"""
    kg = GrowthKnowledgeGraph(graph_path=_tmp_path())
    _add_game(kg, "game_a")
    return kg


def build_kg_strategy_failure() -> GrowthKnowledgeGraph:
    """含一个历史失败策略 aggressive_scale（供 advise_strategy 匹配；该策略属
    SAFER_VARIANT，StrategyLoop 会对其产出 gated 提案，便于端到端验证）。"""
    kg = GrowthKnowledgeGraph(graph_path=_tmp_path())
    node = StrategyResult(
        strategy_id="aggressive_scale",
        dimension="ua",
        success_rate=0.15,
        samples=4,
        rationale="increase budget 30% retention drop after day14",
        recommendation="reduce",
    ).to_node()
    kg.graph.add_node(node)
    return kg


def build_advisor(kg=None):
    from src.ceo_intelligence.growth_memory_graph.advisor import GrowthKnowledgeAdvisor

    return GrowthKnowledgeAdvisor(graph=kg)
