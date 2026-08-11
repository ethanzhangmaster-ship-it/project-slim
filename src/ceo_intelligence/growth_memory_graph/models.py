"""E17.7 Growth Memory Graph — 模型层。

把 E17.1→E17.6 全链路「机会 → 决策 → 策略 → 执行 → 结果」沉淀为可查询的
增长记忆图谱，让系统从「推荐器」升级为「学习者」。

约定（与 E17.1–E17.6 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- 枚举为 str Enum，便于 JSON 序列化与图键
- 节点 ID 规范：f"{NodeType.value}:{natural_key}"，天然幂等（重复摄入去重）
    game:merge_witch
    opportunity:merge_witch:creative_refresh   （= opportunity_id）
    decision:dec_ab12cd34ef56                  （= GrowthDecision.audit_id）
    strategy:dec_ab12cd34ef56                  （= plan.decision_id，与决策 1:1）
    execution:exec_1a2b3c4d5e6f                （= ExecutionReport.execution_id）
    action:act_9f8e7d6c5b4a                    （= ExecutionAction.action_id）
    result:act_9f8e7d6c5b4a                    （与 action 1:1）
- 边方向固定为链路顺序：
    GAME --HAS_OPPORTUNITY--> OPPORTUNITY --LEADS_TO_DECISION--> DECISION
    --PLANS_STRATEGY--> STRATEGY --EXECUTES--> EXECUTION
    --INCLUDES_ACTION--> ACTION --PRODUCES_RESULT--> RESULT
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Tuple


class NodeType(str, Enum):
    GAME = "game"
    OPPORTUNITY = "opportunity"
    DECISION = "decision"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    ACTION = "action"
    RESULT = "result"
    # ---- P3.5 Growth Knowledge Graph（跨源 consolidated 高层节点）----
    CREATIVE_PATTERN = "creative_pattern"
    UA_PATTERN = "ua_pattern"
    MONETIZATION_PATTERN = "monetization_pattern"
    STRATEGY_RESULT = "strategy_result"
    EXECUTION_OUTCOME = "execution_outcome"
    RECOVERY_HISTORY = "recovery_history"
    PORTFOLIO_DECISION = "portfolio_decision"
    # ---- P3.5.2 Knowledge Feedback Loop（决策学习节点）----
    CEO_DECISION = "ceo_decision"
    # ---- P3.6.2 Strategic Summary Memory（长期战略规律节点）----
    STRATEGIC_INSIGHT = "strategic_insight"
    # ---- P3.6.3 Memory Reflection Loop（认知复盘节点，每天一条，幂等键=period）----
    CEO_REFLECTION = "ceo_reflection"
    # ---- P3.6.4 Memory Governance ----
    GOVERNANCE_RECORD = "governance_record"


class EdgeType(str, Enum):
    HAS_OPPORTUNITY = "has_opportunity"        # GAME -> OPPORTUNITY
    LEADS_TO_DECISION = "leads_to_decision"    # OPPORTUNITY -> DECISION
    PLANS_STRATEGY = "plans_strategy"          # DECISION -> STRATEGY
    EXECUTES = "executes"                      # STRATEGY -> EXECUTION
    INCLUDES_ACTION = "includes_action"        # EXECUTION -> ACTION
    PRODUCES_RESULT = "produces_result"        # ACTION -> RESULT
    # ---- P3.5 Growth Knowledge Graph（高层节点连边）----
    HAS_CREATIVE_PATTERN = "has_creative_pattern"        # GAME -> CREATIVE_PATTERN
    HAS_UA_PATTERN = "has_ua_pattern"                    # GAME -> UA_PATTERN
    HAS_MONETIZATION_PATTERN = "has_monetization_pattern"  # GAME -> MONETIZATION_PATTERN
    HAS_STRATEGY_RESULT = "has_strategy_result"          # GAME -> STRATEGY_RESULT
    HAS_EXECUTION_OUTCOME = "has_execution_outcome"      # GAME -> EXECUTION_OUTCOME
    HAS_RECOVERY_HISTORY = "has_recovery_history"        # GAME -> RECOVERY_HISTORY
    HAS_PORTFOLIO_DECISION = "has_portfolio_decision"    # GAME -> PORTFOLIO_DECISION
    PATTERN_SIMILAR_TO = "pattern_similar_to"          # pattern -> pattern
    # ---- P3.5.2 Knowledge Feedback Loop ----
    HAS_CEO_DECISION = "has_ceo_decision"              # GAME -> CEO_DECISION（决策归属）
    USED_KNOWLEDGE_SIGNAL = "used_knowledge_signal"    # CEO_DECISION -> GAME（决策使用了什么知识）
    PRODUCED_OUTCOME = "produced_outcome"              # CEO_DECISION -> GAME（决策产出什么结果）
    # ---- P3.6.2 Strategic Summary Memory ----
    INSIGHT_DERIVED_FROM_MEMORY = "insight_derived_from_memory"  # STRATEGIC_INSIGHT -> 支撑记忆节点
    # ---- P3.6.3 Memory Reflection Loop ----
    REFLECTION_DERIVED_FROM_DECISION = "reflection_derived_from_decision"  # CEO_REFLECTION -> CEO_DECISION（审计链）
    # ---- P3.6.4 Memory Governance ----
    GOVERNANCE_APPLIED_TO = "governance_applied_to"
    MERGE_SOURCE = "merge_source"


def node_id(node_type: NodeType, natural_key: str) -> str:
    """节点 ID 规范化（幂等键）。"""
    return f"{node_type.value}:{natural_key}"


@dataclass
class GraphNode:
    """图节点：id 幂等，payload 承载该层的业务快照（last-write-wins 合并）。"""
    id: str
    type: NodeType
    label: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "payload": self.payload,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphNode":
        return cls(
            id=d["id"],
            type=NodeType(d["type"]),
            label=d.get("label", ""),
            payload=dict(d.get("payload", {})),
            created_at=d.get("created_at", ""),
        )


@dataclass
class GraphEdge:
    """图边：(src, tgt, type) 为唯一键。"""
    src: str
    tgt: str
    type: EdgeType
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.src, self.tgt, self.type.value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "src": self.src,
            "tgt": self.tgt,
            "type": self.type.value,
            "payload": self.payload,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphEdge":
        return cls(
            src=d["src"],
            tgt=d["tgt"],
            type=EdgeType(d["type"]),
            payload=dict(d.get("payload", {})),
            created_at=d.get("created_at", ""),
        )


@dataclass
class MemoryEvent:
    """一次可摄入的记忆事件（ingest 适配器的统一产出）。"""
    kind: str                                   # opportunity / decision / strategy / execution / experience
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    event_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryEvent":
        return cls(
            kind=d.get("kind", ""),
            nodes=[GraphNode.from_dict(n) for n in d.get("nodes", [])],
            edges=[GraphEdge.from_dict(e) for e in d.get("edges", [])],
            event_id=d.get("event_id", ""),
            created_at=d.get("created_at", ""),
        )


@dataclass
class GraphPattern:
    """从 RESULT 节点提炼的可复用模式（键：strategy_type × domain × action_type）。"""
    strategy_type: str
    domain: str
    action_type: str
    samples: int = 0
    successes: int = 0
    success_rate: float = 0.0
    avg_revenue_delta: float = 0.0     # record_outcome 挂上的实得收入变化均值
    confidence_boost: float = 0.0      # ≥2 样本：min(0.20, rate * 0.15)，与 E17.2 对齐

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "domain": self.domain,
            "action_type": self.action_type,
            "samples": self.samples,
            "successes": self.successes,
            "success_rate": self.success_rate,
            "avg_revenue_delta": self.avg_revenue_delta,
            "confidence_boost": self.confidence_boost,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphPattern":
        return cls(
            strategy_type=d.get("strategy_type", ""),
            domain=d.get("domain", ""),
            action_type=d.get("action_type", ""),
            samples=int(d.get("samples", 0)),
            successes=int(d.get("successes", 0)),
            success_rate=float(d.get("success_rate", 0.0)),
            avg_revenue_delta=float(d.get("avg_revenue_delta", 0.0)),
            confidence_boost=float(d.get("confidence_boost", 0.0)),
        )


@dataclass
class ExecutionChain:
    """trace_execution 的产出：一条 execution 的完整因果链。"""
    execution_id: str
    game_id: str = ""
    decision_id: str = ""
    strategy_type: str = ""
    node_ids: List[str] = field(default_factory=list)   # 链路顺序排列
    success_actions: int = 0
    total_actions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "game_id": self.game_id,
            "decision_id": self.decision_id,
            "strategy_type": self.strategy_type,
            "node_ids": self.node_ids,
            "success_actions": self.success_actions,
            "total_actions": self.total_actions,
        }


@dataclass
class MemoryGraphReport:
    """E17.7 主输出：图谱规模 + 链路 + 模式 + CEO 摘要。"""
    total_nodes: int = 0
    total_edges: int = 0
    games: List[str] = field(default_factory=list)
    chains: List[ExecutionChain] = field(default_factory=list)
    patterns: List[GraphPattern] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "games": self.games,
            "chains": [c.to_dict() for c in self.chains],
            "patterns": [p.to_dict() for p in self.patterns],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines: List[str] = ["# 增长记忆图谱（Growth Memory Graph · CEO Brain）", ""]
        lines.append(
            f"- 节点 **{self.total_nodes}** ｜ 边 **{self.total_edges}** "
            f"｜ 覆盖游戏 **{len(self.games)}**"
        )
        s = self.summary
        lines.append(
            f"- 执行链 {s.get('chains', 0)} 条 ｜ 动作成功率 "
            f"{s.get('action_success_rate', 0.0):.0%} ｜ 真实 API："
            f"{'是' if s.get('real_api_called') else '否（SIM）'}"
        )
        lines.append("")
        if self.patterns:
            lines.append("## 已学到的模式（策略 × 域 × 动作）")
            lines.append("")
            lines.append("| 策略 | 域 | 动作 | 样本 | 成功率 | 置信加成 |")
            lines.append("|---|---|---|---|---|---|")
            for p in self.patterns[:10]:
                lines.append(
                    f"| {p.strategy_type} | {p.domain} | {p.action_type} "
                    f"| {p.samples} | {p.success_rate:.0%} | +{p.confidence_boost:.2f} |"
                )
            lines.append("")
        if self.chains:
            lines.append("## 执行链路")
            for c in self.chains[:10]:
                lines.append(
                    f"- `{c.execution_id}` {c.game_id} — {c.strategy_type}"
                    f"（{c.success_actions}/{c.total_actions} 动作成功）"
                )
        return "\n".join(lines)


__all__ = [
    "NodeType",
    "EdgeType",
    "node_id",
    "GraphNode",
    "GraphEdge",
    "MemoryEvent",
    "GraphPattern",
    "ExecutionChain",
    "MemoryGraphReport",
    # P3.5 consolidated node/edge types（复用 E17.7 图模型）
    "CREATIVE_PATTERN",
    "UA_PATTERN",
    "MONETIZATION_PATTERN",
    "STRATEGY_RESULT",
    "EXECUTION_OUTCOME",
    "RECOVERY_HISTORY",
    "PORTFOLIO_DECISION",
    "HAS_CREATIVE_PATTERN",
    "HAS_UA_PATTERN",
    "HAS_MONETIZATION_PATTERN",
    "HAS_STRATEGY_RESULT",
    "HAS_EXECUTION_OUTCOME",
    "HAS_RECOVERY_HISTORY",
    "HAS_PORTFOLIO_DECISION",
    "PATTERN_SIMILAR_TO",
    # P3.5.2 Knowledge Feedback Loop
    "CEO_DECISION",
    "HAS_CEO_DECISION",
    "USED_KNOWLEDGE_SIGNAL",
    "PRODUCED_OUTCOME",
    # P3.6.2 Strategic Summary Memory
    "STRATEGIC_INSIGHT",
    "INSIGHT_DERIVED_FROM_MEMORY",
    # P3.6.3 Memory Reflection Loop
    "CEO_REFLECTION",
    "REFLECTION_DERIVED_FROM_DECISION",
    # P3.6.4 Memory Governance
    "GOVERNANCE_RECORD",
    "GOVERNANCE_APPLIED_TO",
    "MERGE_SOURCE",
]
