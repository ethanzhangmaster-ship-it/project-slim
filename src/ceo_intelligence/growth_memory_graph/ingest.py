"""E17.7 — Ingest 适配器：把 E17.2–E17.6 的产出转成 MemoryEvent。

键的链路一致性（全部来自既有契约，不发明新键）：
- opportunity_id = f"{game_id}:{type}"（E17.3 GrowthDecision.opportunity_id 格式）
- decision 键 = GrowthDecision.audit_id = plan.decision_id
  = ExecutionAction.decision_id = ExecutionExperience.decision_id
- strategy 键 = plan.decision_id（决策与策略 1:1）
- execution 键 = ExecutionReport.execution_id；action / result 键 = action_id

每个适配器允许上游节点缺席（自动补 stub 节点），保证任意摄入顺序都成图。
"""
from __future__ import annotations

from typing import Any, Dict

from .models import EdgeType, GraphEdge, GraphNode, MemoryEvent, NodeType, node_id


def _game_node(game_id: str) -> GraphNode:
    return GraphNode(
        id=node_id(NodeType.GAME, game_id),
        type=NodeType.GAME,
        label=game_id,
        payload={"game_id": game_id},
    )


# --------------------------------------------------------------------------- #
# E17.2 GrowthOpportunity
# --------------------------------------------------------------------------- #
def event_from_opportunity(opp) -> MemoryEvent:
    """GAME --HAS_OPPORTUNITY--> OPPORTUNITY。"""
    opportunity_id = f"{opp.game_id}:{opp.type.value}"
    game = _game_node(opp.game_id)
    node = GraphNode(
        id=node_id(NodeType.OPPORTUNITY, opportunity_id),
        type=NodeType.OPPORTUNITY,
        label=opp.title,
        payload={
            "game_id": opp.game_id,
            "opportunity_type": opp.type.value,
            "priority": opp.priority,
            "expected_impact": opp.expected_impact,
            "confidence": opp.confidence,
            "risk": opp.risk,
            "segment": opp.segment,
        },
    )
    edge = GraphEdge(src=game.id, tgt=node.id, type=EdgeType.HAS_OPPORTUNITY)
    return MemoryEvent(kind="opportunity", nodes=[game, node], edges=[edge])


# --------------------------------------------------------------------------- #
# E17.3 GrowthDecision
# --------------------------------------------------------------------------- #
def event_from_decision(dec) -> MemoryEvent:
    """OPPORTUNITY --LEADS_TO_DECISION--> DECISION（机会节点缺席则补 stub）。"""
    game = _game_node(dec.game_id)
    opp_node = GraphNode(
        id=node_id(NodeType.OPPORTUNITY, dec.opportunity_id),
        type=NodeType.OPPORTUNITY,
        label=dec.opportunity_id,
        payload={"game_id": dec.game_id},
    )
    dec_node = GraphNode(
        id=node_id(NodeType.DECISION, dec.audit_id),
        type=NodeType.DECISION,
        label=dec.action,
        payload={
            "game_id": dec.game_id,
            "decision_id": dec.audit_id,
            "opportunity_id": dec.opportunity_id,
            "decision_type": dec.decision_type.value,
            "expected_value": dec.expected_value,
            "confidence": dec.confidence,
            "risk": dec.risk,
        },
    )
    edges = [
        GraphEdge(src=game.id, tgt=opp_node.id, type=EdgeType.HAS_OPPORTUNITY),
        GraphEdge(src=opp_node.id, tgt=dec_node.id, type=EdgeType.LEADS_TO_DECISION),
    ]
    return MemoryEvent(kind="decision", nodes=[game, opp_node, dec_node], edges=edges)


# --------------------------------------------------------------------------- #
# E17.4 GrowthStrategyPlan
# --------------------------------------------------------------------------- #
def event_from_strategy(plan) -> MemoryEvent:
    """DECISION --PLANS_STRATEGY--> STRATEGY（决策节点缺席则补 stub）。"""
    dec_node = GraphNode(
        id=node_id(NodeType.DECISION, plan.decision_id),
        type=NodeType.DECISION,
        label=plan.decision_id,
        payload={"game_id": plan.game_id, "decision_id": plan.decision_id},
    )
    strat_node = GraphNode(
        id=node_id(NodeType.STRATEGY, plan.decision_id),
        type=NodeType.STRATEGY,
        label=plan.objective,
        payload={
            "game_id": plan.game_id,
            "decision_id": plan.decision_id,
            "strategy_type": plan.strategy_type,
            "expected_value": plan.expected_value,
            "confidence": plan.confidence,
            "task_count": len(plan.tasks),
            "needs_approval": plan.needs_approval,
        },
    )
    edge = GraphEdge(src=dec_node.id, tgt=strat_node.id, type=EdgeType.PLANS_STRATEGY)
    return MemoryEvent(kind="strategy", nodes=[dec_node, strat_node], edges=[edge])


# --------------------------------------------------------------------------- #
# E17.6 ExecutionReport（含全部 action + result）
# --------------------------------------------------------------------------- #
def event_from_execution_report(report) -> MemoryEvent:
    """STRATEGY --EXECUTES--> EXECUTION --INCLUDES_ACTION--> ACTION --PRODUCES_RESULT--> RESULT。"""
    strat_node = GraphNode(
        id=node_id(NodeType.STRATEGY, report.decision_id),
        type=NodeType.STRATEGY,
        label=report.strategy_type,
        payload={
            "game_id": report.game_id,
            "decision_id": report.decision_id,
            "strategy_type": report.strategy_type,
        },
    )
    exec_node = GraphNode(
        id=node_id(NodeType.EXECUTION, report.execution_id),
        type=NodeType.EXECUTION,
        label=f"{report.game_id}:{report.strategy_type}",
        payload={
            "game_id": report.game_id,
            "decision_id": report.decision_id,
            "strategy_type": report.strategy_type,
            "status": report.status,
            "summary": report.summary,
        },
    )
    nodes = [strat_node, exec_node]
    edges = [GraphEdge(src=strat_node.id, tgt=exec_node.id, type=EdgeType.EXECUTES)]

    for item in report.actions:
        a: Dict[str, Any] = item["action"]
        r: Dict[str, Any] = item["result"]
        act_node = GraphNode(
            id=node_id(NodeType.ACTION, a["action_id"]),
            type=NodeType.ACTION,
            label=f"{a['domain']}:{a['action_type']}",
            payload={
                "game_id": a["game_id"],
                "decision_id": a.get("decision_id", ""),
                "execution_id": report.execution_id,
                "strategy_type": a.get("plan_strategy_type", report.strategy_type),
                "domain": a["domain"],
                "action_type": a["action_type"],
                "source_task_order": a.get("source_task_order", 0),
                "risk_level": a.get("risk_level", 0.0),
            },
        )
        res_node = GraphNode(
            id=node_id(NodeType.RESULT, a["action_id"]),
            type=NodeType.RESULT,
            label=r["status"],
            payload={
                "game_id": a["game_id"],
                "execution_id": report.execution_id,
                "strategy_type": a.get("plan_strategy_type", report.strategy_type),
                "domain": a["domain"],
                "action_type": a["action_type"],
                "status": r["status"],
                "success": r["status"] == "success",
                "system": r.get("system", ""),
                "real_api_called": bool(r.get("real_api_called", False)),
                "rolled_back": bool(r.get("rolled_back", False)),
            },
        )
        nodes.extend([act_node, res_node])
        edges.append(GraphEdge(src=exec_node.id, tgt=act_node.id,
                               type=EdgeType.INCLUDES_ACTION))
        edges.append(GraphEdge(src=act_node.id, tgt=res_node.id,
                               type=EdgeType.PRODUCES_RESULT))
    return MemoryEvent(kind="execution", nodes=nodes, edges=edges)


# --------------------------------------------------------------------------- #
# E17.6 ExecutionExperience（单条 → 全链 stub，供离线重建）
# --------------------------------------------------------------------------- #
def event_from_experience(exp) -> MemoryEvent:
    """从一条 ExecutionExperience 重建 game→decision→strategy→execution→action→result 链。

    机会节点无法从经验反推（经验里没有 opportunity_id），故链从 decision 起；
    game 节点仍建立并直连 decision 所属机会缺失时的图仍可按 game 查询（payload.game_id）。
    """
    game = _game_node(exp.game_id)
    dec_node = GraphNode(
        id=node_id(NodeType.DECISION, exp.decision_id),
        type=NodeType.DECISION,
        label=exp.decision_id,
        payload={"game_id": exp.game_id, "decision_id": exp.decision_id},
    )
    strat_node = GraphNode(
        id=node_id(NodeType.STRATEGY, exp.decision_id),
        type=NodeType.STRATEGY,
        label=exp.strategy_type,
        payload={
            "game_id": exp.game_id,
            "decision_id": exp.decision_id,
            "strategy_type": exp.strategy_type,
        },
    )
    exec_node = GraphNode(
        id=node_id(NodeType.EXECUTION, exp.execution_id),
        type=NodeType.EXECUTION,
        label=f"{exp.game_id}:{exp.strategy_type}",
        payload={
            "game_id": exp.game_id,
            "decision_id": exp.decision_id,
            "strategy_type": exp.strategy_type,
        },
    )
    act_node = GraphNode(
        id=node_id(NodeType.ACTION, exp.action_id),
        type=NodeType.ACTION,
        label=f"{exp.domain}:{exp.action_type}",
        payload={
            "game_id": exp.game_id,
            "decision_id": exp.decision_id,
            "execution_id": exp.execution_id,
            "strategy_type": exp.strategy_type,
            "domain": exp.domain,
            "action_type": exp.action_type,
        },
    )
    res_node = GraphNode(
        id=node_id(NodeType.RESULT, exp.action_id),
        type=NodeType.RESULT,
        label=exp.status,
        payload={
            "game_id": exp.game_id,
            "execution_id": exp.execution_id,
            "strategy_type": exp.strategy_type,
            "domain": exp.domain,
            "action_type": exp.action_type,
            "status": exp.status,
            "success": exp.success,
            "real_api_called": exp.real_api_called,
            "rolled_back": exp.rolled_back,
        },
    )
    edges = [
        GraphEdge(src=dec_node.id, tgt=strat_node.id, type=EdgeType.PLANS_STRATEGY),
        GraphEdge(src=strat_node.id, tgt=exec_node.id, type=EdgeType.EXECUTES),
        GraphEdge(src=exec_node.id, tgt=act_node.id, type=EdgeType.INCLUDES_ACTION),
        GraphEdge(src=act_node.id, tgt=res_node.id, type=EdgeType.PRODUCES_RESULT),
    ]
    return MemoryEvent(
        kind="experience",
        nodes=[game, dec_node, strat_node, exec_node, act_node, res_node],
        edges=edges,
    )


__all__ = [
    "event_from_opportunity",
    "event_from_decision",
    "event_from_strategy",
    "event_from_execution_report",
    "event_from_experience",
]
