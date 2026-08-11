"""
P3.5.2 测试夹具：构造含 CEO_DECISION 学习记录的 GrowthKnowledgeGraph。

直接往 E17.7 图里种高层节点（StrategyResult / ExecutionOutcome）+ 用
KnowledgeFeedbackRecorder 写入 CEO_DECISION 记录，让 advisor 的加权消费有料可查。
"""
from __future__ import annotations

import tempfile

from src.ceo_intelligence.growth_memory_graph.feedback import (
    DecisionKnowledgeRecord,
    KnowledgeFeedbackRecorder,
)
from src.ceo_intelligence.growth_memory_graph.knowledge import GrowthKnowledgeGraph
from src.ceo_intelligence.growth_memory_graph.knowledge_models import ExecutionOutcome, StrategyResult
from src.ceo_intelligence.growth_memory_graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    node_id,
)


def _tmp_path() -> str:
    fd = tempfile.NamedTemporaryFile(prefix="p3_5_2_", suffix=".jsonl", delete=False)
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


def _link_execution_n(kg, gid, n, sr):
    """n 条同 sr 的 ExecutionOutcome（不同 domain 保证节点独立，模拟 n 次执行）。"""
    for i in range(n):
        _link_execution(kg, gid, f"ua_d{i}", sr)


def _add_ceo(
    kg,
    gid,
    success_rate,
    *,
    simulated=False,
    risk_flags=None,
    decision_type="portfolio",
    record_id="",
    success=None,
):
    """经 KnowledgeFeedbackRecorder 写入一条 CEO_DECISION（走唯一写入口）。"""
    oc = {"success_rate": float(success_rate), "simulated": bool(simulated)}
    if success is not None:
        oc["success"] = bool(success)
    ks = {}
    if risk_flags:
        ks["risk_flags"] = list(risk_flags)
    rec = DecisionKnowledgeRecord(
        record_id=record_id,
        game_id=gid,
        decision_type=decision_type,
        source=decision_type.upper(),
        decision_payload={"action": "scale" if success_rate >= 0.5 else "reduce"},
        knowledge_signal=ks,
        outcome=oc,
    )
    KnowledgeFeedbackRecorder(kg).record(rec)
    return rec


def build_kg_shared(kg=None) -> GrowthKnowledgeGraph:
    """game_a 与 game_x 共享 ua_ios 策略（中性 sr=0.5），保证 similar_games 命中。"""
    kg = kg or GrowthKnowledgeGraph(graph_path=_tmp_path())
    for g in ("game_a", "game_x"):
        _add_game(kg, g)
    _link_strategy(kg, "ua_ios", "ua", 0.5, 2, ["game_a", "game_x"])
    return kg


def build_kg_external_success() -> GrowthKnowledgeGraph:
    """game_x 只有外部成功证据（10 次执行成功，w=1.0）。"""
    kg = build_kg_shared()
    _link_execution_n(kg, "game_x", 10, 1.0)
    return kg


def build_kg_ceo_success() -> GrowthKnowledgeGraph:
    """game_x 有 10 条 CEO 自报成功（w=0.5）——验证自生成经验被折半。"""
    kg = build_kg_shared()
    for i in range(10):
        _add_ceo(kg, "game_x", 1.0, record_id=f"ceo_ok_{i}")
    return kg


def build_kg_isolation() -> GrowthKnowledgeGraph:
    """Knowledge Source Isolation：10 执行失败 + 10 CEO 自报成功。

    weighted_sr = (0.5*1 + 0*10*1 + 1*10*0.5) / (1 + 10 + 5) = 5.5/16 ≈ 0.344，
    绝不能认为历史成功率=1.0（防自嗨）。
    """
    kg = build_kg_shared()
    _link_execution_n(kg, "game_x", 10, 0.0)
    for i in range(10):
        _add_ceo(kg, "game_x", 1.0, record_id=f"ceo_iso_{i}")
    return kg


def build_kg_ceo_simulated() -> GrowthKnowledgeGraph:
    """10 执行失败 + 10 CEO 模拟成功（w=0.2）——模拟证据最弱。"""
    kg = build_kg_shared()
    _link_execution_n(kg, "game_x", 10, 0.0)
    for i in range(10):
        _add_ceo(kg, "game_x", 1.0, simulated=True, record_id=f"ceo_sim_{i}")
    return kg


def build_kg_strategy_ceo_failed() -> GrowthKnowledgeGraph:
    """game_a 有一条「带风险知识 + 失败结果」的策略型 CEO 决策（知识建议被证伪）。"""
    kg = GrowthKnowledgeGraph(graph_path=_tmp_path())
    _add_game(kg, "game_a")
    _add_ceo(
        kg,
        "game_a",
        0.1,
        simulated=True,
        risk_flags=["historical_failure_pattern"],
        decision_type="strategy",
        record_id="ceo_strategy_fail_1",
        success=False,
    )
    return kg


def build_advisor(kg=None):
    from src.ceo_intelligence.growth_memory_graph.advisor import GrowthKnowledgeAdvisor

    return GrowthKnowledgeAdvisor(graph=kg)
