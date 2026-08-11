"""
P3.5.2 — Knowledge Feedback Loop（决策学习写入器，只写 Graph，不碰 5 源）。

把每次 CEO Decision 收敛成一条可生长的「经验边」：

    Decision Context
        + Knowledge Signal（来自 P3.5.1 KnowledgeSignal）
        + Outcome（已知则带，否则后续 attach）
        ↓
    CEO_DECISION 节点 + 3 条边（HAS_CEO_DECISION / USED_KNOWLEDGE_SIGNAL /
    PRODUCED_OUTCOME）

让 P3.5 的 Knowledge Graph 从「查询系统」升级为「学习系统」：
P3.5.1 的 Advisor 在查询时会把相似游戏的 CEO_DECISION 结果（**带权重**，见 advisor.py
防自我强化规则）并入经验，形成 Experience → Pattern → Advice → Decision → Outcome →
New Pattern 闭环。

纪律（P3.5.2 契约冻结点）：

- ✅ **Graph Writer 唯一入口**：所有新增图写入必须经过本模块
  ``KnowledgeFeedbackRecorder.record()``（或 ``attach_outcome()`` 结果回流）；
  其他组件一律只读 Graph。
- ❌ 绝不写回 5 个源（不调 strategy_memory.save / execution_memory.record /
  recovery_store.add / graph.record_outcome / consolidate）。
- ❌ 不决策、不执行、不调 Provider / SafeExecutor / DecisionEngine。
- ✅ ``real_api_called`` 恒 False。
- ✅ fail-open：图不可用 / 异常 → 静默跳过，不中断主链（与 P3.5.1 Advisor 对称）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    node_id,
)


def _new_id() -> str:
    return f"ceo_{uuid.uuid4().hex[:12]}"


@dataclass
class DecisionKnowledgeRecord:
    """一次 CEO Decision 的学习记录（字段已冻结，P3.5.2 契约）。

    ``record_id`` 是幂等键（图节点 id = ``ceo_decision:{record_id}``）。
    ``decision_payload`` 承载完整决策上下文（action / confidence / priority ...），
    ``knowledge_signal`` 即 P3.5.1 ``KnowledgeSignal.to_dict()``，
    ``outcome`` 结构为 ``{success, reward, metrics, success_rate, ...}``（可空）。
    ``created_at`` 保留（不参与排序）——未来可做经验衰减 / 时间窗口 / 策略版本。
    """

    record_id: str = ""                              # 幂等键（ceo_decision:{record_id}）
    game_id: str = ""                                # 决策所属游戏
    decision_type: str = "portfolio"                 # "portfolio" | "strategy"
    decision_payload: Dict[str, Any] = field(default_factory=dict)  # 决策上下文
    knowledge_signal: Optional[Dict[str, Any]] = None  # KnowledgeSignal.to_dict()
    outcome: Optional[Dict[str, Any]] = None         # {success, reward, metrics, ...}
    source: str = ""                                 # "PORTFOLIO" | "STRATEGY"（来源层）
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = _new_id()

    # ------------------------------------------------------------------ #
    # 图节点互转
    # ------------------------------------------------------------------ #
    def node_id(self) -> str:
        return node_id(NodeType.CEO_DECISION, self.record_id)

    def to_node(self) -> GraphNode:
        return GraphNode(
            id=self.node_id(),
            type=NodeType.CEO_DECISION,
            label=f"{self.game_id}:{self.decision_type}:"
                  f"{self.decision_payload.get('action', '')}",
            payload={
                "record_id": self.record_id,
                "game_id": self.game_id,
                "decision_type": self.decision_type,
                "decision_payload": dict(self.decision_payload),
                "knowledge_signal": dict(self.knowledge_signal or {}),
                "outcome": dict(self.outcome or {}),
                "source": self.source,
                "created_at": self.created_at,
            },
        )

    @classmethod
    def from_node(cls, n: GraphNode) -> "DecisionKnowledgeRecord":
        p = n.payload
        return cls(
            record_id=str(p.get("record_id", "")),
            game_id=str(p.get("game_id", "")),
            decision_type=str(p.get("decision_type", "portfolio")),
            decision_payload=dict(p.get("decision_payload", {}) or {}),
            knowledge_signal=dict(p.get("knowledge_signal", {}) or {}),
            outcome=dict(p.get("outcome", {}) or {}),
            source=str(p.get("source", "")),
            created_at=str(p.get("created_at", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "game_id": self.game_id,
            "decision_type": self.decision_type,
            "decision_payload": dict(self.decision_payload),
            "knowledge_signal": dict(self.knowledge_signal or {}),
            "outcome": dict(self.outcome or {}),
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecisionKnowledgeRecord":
        return cls(
            record_id=str(d.get("record_id", "")),
            game_id=str(d.get("game_id", "")),
            decision_type=str(d.get("decision_type", "portfolio")),
            decision_payload=dict(d.get("decision_payload", {}) or {}),
            knowledge_signal=dict(d.get("knowledge_signal", {}) or {}),
            outcome=dict(d.get("outcome", {}) or {}),
            source=str(d.get("source", "")),
            created_at=str(d.get("created_at", "")),
        )


class KnowledgeFeedbackRecorder:
    """决策学习写入器（唯一 Graph 写入口，fail-open）。

    典型用法::

        rec = KnowledgeFeedbackRecorder(kg)            # kg: GrowthKnowledgeGraph
        rec.record(DecisionKnowledgeRecord(
            game_id="game_001", decision_type="strategy",
            source="STRATEGY",
            decision_payload={"action": "aggressive_scale"},
            knowledge_signal=advisor_signal.to_dict(),
            outcome={"success": False, "success_rate": 0.1, "simulated": True},
        ))
        # 结果已知后（如执行/监控回流）补充：
        rec.attach_outcome(record_id, {"success": True, "success_rate": 0.8})
    """

    def __init__(self, graph: Optional[Any] = None) -> None:
        self.graph = graph

    # ------------------------------------------------------------------ #
    # 纪律：real_api_called 锁死 False（纯写入图，无外部调用）
    # ------------------------------------------------------------------ #
    @property
    def real_api_called(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    # 写入（唯一 mutation boundary）
    # ------------------------------------------------------------------ #
    def record(
        self, rec: DecisionKnowledgeRecord
    ) -> Dict[str, int]:
        """把一次 CEO Decision 写入 Graph（CEO_DECISION 节点 + 3 边）。

        返回 {"nodes_added", "edges_added"}；图不可用 / 异常 → 空计数（fail-open）。
        """
        if self.graph is None:
            return {"nodes_added": 0, "edges_added": 0}
        try:
            return self._record(rec)
        except Exception:
            return {"nodes_added": 0, "edges_added": 0}

    def _record(self, rec: DecisionKnowledgeRecord) -> Dict[str, int]:
        counts: Dict[str, int] = {"nodes_added": 0, "edges_added": 0}
        store = self.graph.graph  # GrowthKnowledgeGraph.graph -> GrowthMemoryGraph store
        gid = rec.game_id
        game_node = node_id(NodeType.GAME, gid)
        ceo_node = rec.to_node()

        if store.add_node(ceo_node):
            counts["nodes_added"] += 1

        # GAME -> CEO_DECISION（主链路，供 why_game_succeeded 聚合）
        if store.add_edge(GraphEdge(
            src=game_node, tgt=ceo_node.id, type=EdgeType.HAS_CEO_DECISION
        )):
            counts["edges_added"] += 1

        # CEO_DECISION -> GAME：USED_KNOWLEDGE_SIGNAL（决策使用了什么知识）
        ks = rec.knowledge_signal or {}
        if store.add_edge(GraphEdge(
            src=ceo_node.id, tgt=game_node, type=EdgeType.USED_KNOWLEDGE_SIGNAL,
            payload={
                "risk_flags": list(ks.get("risk_flags", []) or []),
                "historical_success_rate": float(
                    ks.get("historical_success_rate", 0.0) or 0.0
                ),
            },
        )):
            counts["edges_added"] += 1

        # CEO_DECISION -> GAME：PRODUCED_OUTCOME（决策产出什么结果）
        oc = rec.outcome or {}
        if store.add_edge(GraphEdge(
            src=ceo_node.id, tgt=game_node, type=EdgeType.PRODUCED_OUTCOME,
            payload={
                "success": bool(oc.get("success", False)),
                "success_rate": float(oc.get("success_rate", 0.0) or 0.0),
                "reward": float(oc.get("reward", 0.0) or 0.0),
                "rolled_back": bool(oc.get("rolled_back", False)),
                "simulated": bool(oc.get("simulated", False)),
            },
        )):
            counts["edges_added"] += 1

        return counts

    def attach_outcome(
        self, record_id: str, outcome: Dict[str, Any]
    ) -> bool:
        """结果回流：更新已存在 CEO_DECISION 节点的 outcome（幂等合并）。

        走 store 公开 ``add_node``（last-write-wins merge），不直接 append。
        返回是否有变化；图不可用 / 节点不存在 / 异常 → False（fail-open）。
        """
        if self.graph is None:
            return False
        try:
            store = self.graph.graph
            nid = node_id(NodeType.CEO_DECISION, record_id)
            node = store.get_node(nid)
            if node is None:
                return False
            merged = dict(node.payload.get("outcome", {}) or {})
            changed = False
            for k, v in outcome.items():
                if merged.get(k) != v:
                    merged[k] = v
                    changed = True
            if not changed:
                return False
            # P3.5.3：结果回流时盖上验证时间戳（供 Knowledge Decay 使用）
            merged["last_validated_at"] = datetime.now(timezone.utc).isoformat()
            # 用「新对象 + 合并后的 payload」走 add_node（last-write-wins 合并 + 落盘），
            # 不得原地改 existing 节点——否则 add_node 比对不到差异，不会落盘。
            data = node.to_dict()
            data["payload"] = dict(node.payload)
            data["payload"]["outcome"] = merged
            fresh = GraphNode.from_dict(data)
            return store.add_node(fresh)
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # P3.6.2：StrategicInsight 写入口（仍唯一 mutation owner）
    # ------------------------------------------------------------------ #
    def record_insight(self, insight: Any) -> Dict[str, int]:
        """写入一条 ``StrategicInsight``（STRATEGIC_INSIGHT 节点 + 支撑记忆边）。

        参数：insight 需有 ``to_node()``（STRATEGIC_INSIGHT 节点）与
        ``supporting_memories``（list[str] source_ref，做 INSIGHT_DERIVED_FROM_MEMORY 边）。

        返回 {"nodes_added", "edges_added"}；图不可用 / 异常 → 空计数（fail-open）。
        幂等：同 insight_id 重复写入不重复落盘。
        """
        if self.graph is None:
            return {"nodes_added": 0, "edges_added": 0}
        try:
            return self._record_insight(insight)
        except Exception:
            return {"nodes_added": 0, "edges_added": 0}

    def _record_insight(self, insight: Any) -> Dict[str, int]:
        counts: Dict[str, int] = {"nodes_added": 0, "edges_added": 0}
        store = self.graph.graph
        node = insight.to_node()
        if node.type != NodeType.STRATEGIC_INSIGHT:
            raise TypeError("record_insight expects a StrategicInsight node")
        if store.add_node(node):
            counts["nodes_added"] += 1
        for src_ref in getattr(insight, "supporting_memories", []) or []:
            if not src_ref:
                continue
            if store.add_edge(GraphEdge(
                src=node.id, tgt=str(src_ref),
                type=EdgeType.INSIGHT_DERIVED_FROM_MEMORY,
            )):
                counts["edges_added"] += 1
        return counts

    # ------------------------------------------------------------------ #
    # P3.6.3：CEOReflection 写入口（仍唯一 mutation owner）
    # ------------------------------------------------------------------ #
    def record_reflection(self, reflection: Any) -> Dict[str, int]:
        """写入一次 ``CEOReflection``（CEO_REFLECTION 节点 + 决策审计边）。

        幂等键 = ``reflection:{period}``（每天一条，同 period 重复写入不重复落盘）。

        参数：reflection 需有 ``period``（str）与 ``to_dict()``；wins/mistakes 的
        ``record_id`` 会生成 REFLECTION_DERIVED_FROM_DECISION 审计边
        （reflection → ceo_decision:{record_id}，append-only 可追溯）。

        返回 {"nodes_added", "edges_added"}；图不可用 / 异常 → 空计数（fail-open）。
        """
        if self.graph is None:
            return {"nodes_added": 0, "edges_added": 0}
        try:
            return self._record_reflection(reflection)
        except Exception:
            return {"nodes_added": 0, "edges_added": 0}

    def _record_reflection(self, reflection: Any) -> Dict[str, int]:
        counts: Dict[str, int] = {"nodes_added": 0, "edges_added": 0}
        store = self.graph.graph
        period = str(getattr(reflection, "period", "") or "")
        nid = node_id(NodeType.CEO_REFLECTION, period)
        data = reflection.to_dict()
        node = GraphNode(
            id=nid,
            type=NodeType.CEO_REFLECTION,
            label=f"reflection:{period}",
            payload=dict(data),
        )
        if store.add_node(node):
            counts["nodes_added"] += 1
        for item in (data.get("wins", []) + data.get("mistakes", [])):
            rid = str(item.get("record_id", "") or "")
            if not rid:
                continue
            if store.add_edge(GraphEdge(
                src=nid, tgt=node_id(NodeType.CEO_DECISION, rid),
                type=EdgeType.REFLECTION_DERIVED_FROM_DECISION,
            )):
                counts["edges_added"] += 1
        return counts

    # ------------------------------------------------------------------ #
    # P3.6.4：GovernanceRecord 写入口（唯一 mutation owner）
    # ------------------------------------------------------------------ #
    def govern_record(self, governance: Any) -> Dict[str, int]:
        """Append one governance declaration and its audit edges (fail-open)."""
        if self.graph is None:
            return {"nodes_added": 0, "edges_added": 0}
        try:
            data = governance.to_dict()
            gid = str(data.get("governance_id", "") or "")
            target = str(data.get("target_node_id", "") or "")
            if not gid or not target:
                return {"nodes_added": 0, "edges_added": 0}
            store = self.graph.graph
            # A governance action cannot point to a missing business target.
            if store.get_node(target) is None:
                return {"nodes_added": 0, "edges_added": 0}
            nid = node_id(NodeType.GOVERNANCE_RECORD, gid)
            node = GraphNode(
                id=nid, type=NodeType.GOVERNANCE_RECORD,
                label=f"governance:{data.get('action', '')}:{target}",
                payload=dict(data), created_at=str(data.get("created_at", "")),
            )
            counts = {"nodes_added": 0, "edges_added": 0}
            if store.add_node(node):
                counts["nodes_added"] += 1
            if store.add_edge(GraphEdge(
                src=nid, tgt=target, type=EdgeType.GOVERNANCE_APPLIED_TO,
                payload={
                    "action": data.get("action", ""),
                    "previous_state": data.get("previous_state", "active"),
                    "new_state": data.get("new_state", "active"),
                    "created_at": data.get("created_at", ""),
                },
            )):
                counts["edges_added"] += 1
            for source in data.get("merged_from", []) or []:
                if source and store.add_edge(GraphEdge(
                    src=nid, tgt=str(source), type=EdgeType.MERGE_SOURCE,
                )):
                    counts["edges_added"] += 1
            return counts
        except Exception:
            return {"nodes_added": 0, "edges_added": 0}


__all__ = ["DecisionKnowledgeRecord", "KnowledgeFeedbackRecorder"]
