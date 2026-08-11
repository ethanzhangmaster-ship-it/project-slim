"""E17.7 — 模式提炼与反馈闭环。

从图谱 RESULT 节点提炼「策略 × 域 × 动作」模式：
- extract_patterns：成功率 + 实得收入变化均值 + 置信度加成
- confidence_boost_for：给 E17.2 OpportunityMemory 同款加成公式
  （≥2 样本：min(0.20, success_rate * 0.15)，公式与 E17.2/E17.3 记忆层完全对齐）
- record_outcome：把真实收入变化挂回 EXECUTION 节点（学习闭环的最后一步——
  "哪条执行链路真的赚了钱"）

确定性规则，无 LLM。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import GraphPattern, NodeType, node_id
from .store import GrowthMemoryGraph

_MIN_SAMPLES = 2
_BOOST_CAP = 0.20
_BOOST_FACTOR = 0.15


def _boost(samples: int, rate: float) -> float:
    if samples < _MIN_SAMPLES:
        return 0.0
    return min(_BOOST_CAP, rate * _BOOST_FACTOR)


def extract_patterns(graph: GrowthMemoryGraph) -> List[GraphPattern]:
    """按 (strategy_type, domain, action_type) 聚合 RESULT 节点。

    avg_revenue_delta 来自 record_outcome 挂在 EXECUTION 节点上的
    revenue_delta，按该 execution 下所有 result 均摊归属。
    输出按 (success_rate desc, samples desc, key asc) 确定性排序。
    """
    # execution_id -> revenue_delta（record_outcome 写入）
    outcome: Dict[str, float] = {}
    for n in graph.query(NodeType.EXECUTION):
        if "revenue_delta" in n.payload:
            outcome[n.payload.get("execution_id", n.id.split(":", 1)[1])] = float(
                n.payload["revenue_delta"]
            )

    buckets: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for n in graph.query(NodeType.RESULT):
        key = (
            str(n.payload.get("strategy_type", "")),
            str(n.payload.get("domain", "")),
            str(n.payload.get("action_type", "")),
        )
        b = buckets.setdefault(
            key, {"samples": 0, "successes": 0, "delta_sum": 0.0, "delta_n": 0}
        )
        b["samples"] += 1
        if n.payload.get("success"):
            b["successes"] += 1
        exec_id = str(n.payload.get("execution_id", ""))
        if exec_id in outcome:
            b["delta_sum"] += outcome[exec_id]
            b["delta_n"] += 1

    patterns: List[GraphPattern] = []
    for (stype, domain, atype), b in buckets.items():
        samples = int(b["samples"])
        successes = int(b["successes"])
        rate = successes / samples if samples else 0.0
        avg_delta = b["delta_sum"] / b["delta_n"] if b["delta_n"] else 0.0
        patterns.append(GraphPattern(
            strategy_type=stype,
            domain=domain,
            action_type=atype,
            samples=samples,
            successes=successes,
            success_rate=round(rate, 6),
            avg_revenue_delta=round(avg_delta, 6),
            confidence_boost=round(_boost(samples, rate), 6),
        ))
    patterns.sort(
        key=lambda p: (-p.success_rate, -p.samples,
                       p.strategy_type, p.domain, p.action_type)
    )
    return patterns


def confidence_boost_for(
    graph: GrowthMemoryGraph,
    strategy_type: str,
    domain: Optional[str] = None,
    action_type: Optional[str] = None,
) -> float:
    """相似链路历史成功率 → 置信度加成（回馈 E17.2/E17.3 的记忆公式）。"""
    rows = [
        n for n in graph.query(NodeType.RESULT)
        if n.payload.get("strategy_type") == strategy_type
        and (domain is None or n.payload.get("domain") == domain)
        and (action_type is None or n.payload.get("action_type") == action_type)
    ]
    if not rows:
        return 0.0
    rate = sum(1 for n in rows if n.payload.get("success")) / len(rows)
    return round(_boost(len(rows), rate), 6)


def record_outcome(
    graph: GrowthMemoryGraph,
    execution_id: str,
    revenue_delta: float,
    detail: str = "",
) -> bool:
    """把真实收入变化挂回 EXECUTION 节点（payload 合并 + 持久化）。

    返回 False 表示图中无该 execution。
    """
    from .models import GraphNode

    nid = node_id(NodeType.EXECUTION, execution_id)
    existing = graph.get_node(nid)
    if existing is None:
        return False
    graph.add_node(GraphNode(
        id=nid,
        type=NodeType.EXECUTION,
        label=existing.label,
        payload={
            "execution_id": execution_id,
            "revenue_delta": float(revenue_delta),
            "outcome_detail": detail,
        },
    ))
    return True


__all__ = ["extract_patterns", "confidence_boost_for", "record_outcome"]
