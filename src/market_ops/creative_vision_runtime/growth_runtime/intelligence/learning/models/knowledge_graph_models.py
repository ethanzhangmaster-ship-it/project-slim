"""E13.7.9 Knowledge Graph Update Models — 知识图谱更新协议.

Day 7.9 Step 5:
  将 Memory Consolidation Pipeline 的结果同步到 KnowledgeGraph，
  建立 Pattern → Node + Edge 的可追溯知识网络。

核心模型:
  1. KnowledgeGraphNode        — 图谱节点 (Pattern/Context/Outcome)
  2. KnowledgeGraphEdge        — 图谱边 (reinforces/contradicts/evidence_for)
  3. GraphUpdateResult         — 单模式图谱更新结果
  4. GraphBatchUpdateResult    — 批量图谱更新结果

设计原则:
  - 与现有 evolution_models.KnowledgeGraph 互补 (节点层 vs 拓扑层)
  - 纯数据模型，不包含执行逻辑
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. NodeType / EdgeType
# ═══════════════════════════════════════════════════════════════


class NodeType(str, Enum):
    """图谱节点类型."""
    PATTERN = "pattern"       # 模式节点 (来自 PatternMemory)
    CONTEXT = "context"       # 上下文节点 (条件/受众/产品)
    OUTCOME = "outcome"       # 结果节点 (ROAS/LTV/留存)
    STRATEGY = "strategy"     # 策略节点 (来自 StrategyMemory)


class EdgeType(str, Enum):
    """图谱边类型."""
    REINFORCES = "reinforces"       # 强化关系 (成功经验增强)
    CONTRADICTS = "contradicts"     # 矛盾关系 (失败经验削弱)
    DERIVES_FROM = "derives_from"   # 派生关系 (Pattern 来自 Experience)
    EVIDENCE_FOR = "evidence_for"   # 证据关系 (Experience 支持 Pattern)
    SIMILAR_TO = "similar_to"       # 相似关系 (Pattern 间相似)
    DECAYS_TO = "decays_to"         # 衰减关系 (Pattern 衰减后状态)


# ═══════════════════════════════════════════════════════════════
# 2. KnowledgeGraphNode
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeGraphNode:
    """知识图谱节点 — Pattern 在图谱中的表示.

    Attributes:
        node_id: 节点唯一标识
        node_type: 节点类型
        label: 可读标签
        pattern_ref: 关联的 PatternMemory.pattern_id (仅 PATTERN 类型)
        confidence: 节点置信度 [0, 1]
        weight: 节点权重 [0, 1]
        tags: 标签
        edge_count: 关联边数量
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType = NodeType.PATTERN
    label: str = ""
    pattern_ref: str | None = None
    confidence: float = 0.5
    weight: float = 1.0
    tags: list[str] = field(default_factory=list)
    edge_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_high_confidence(self) -> bool:
        """是否高置信度."""
        return self.confidence >= 0.7

    @property
    def is_low_confidence(self) -> bool:
        """是否低置信度."""
        return self.confidence < 0.3

    @property
    def is_isolated(self) -> bool:
        """是否孤立节点 (无边)."""
        return self.edge_count == 0

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "pattern_ref": self.pattern_ref,
            "confidence": self.confidence,
            "weight": self.weight,
            "tags": self.tags,
            "edge_count": self.edge_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. KnowledgeGraphEdge
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeGraphEdge:
    """知识图谱边 — 节点间的关系.

    Attributes:
        edge_id: 边唯一标识
        source_id: 源节点 ID
        target_id: 目标节点 ID
        edge_type: 边类型
        weight: 边权重 [0, 1]
        confidence: 边置信度 [0, 1]
        evidence_count: 证据数量 (支持该边的经验数)
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.EVIDENCE_FOR
    weight: float = 0.5
    confidence: float = 0.5
    evidence_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_strong(self) -> bool:
        """是否强关系."""
        return self.weight >= 0.7

    @property
    def is_weak(self) -> bool:
        """是否弱关系."""
        return self.weight < 0.3

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 4. GraphUpdateResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class GraphUpdateResult:
    """单模式图谱更新结果 — 一次图谱同步对单个 Pattern 的影响.

    Attributes:
        result_id: 结果唯一标识
        pattern_id: 关联的 PatternMemory.pattern_id
        node_id: 图谱节点 ID
        action: 更新动作 (created/updated/strengthened/weakened/removed/unchanged)
        node_confidence_before: 更新前节点置信度
        node_confidence_after: 更新后节点置信度
        node_weight_before: 更新前节点权重
        node_weight_after: 更新后节点权重
        edges_added: 新增边数
        edges_updated: 更新边数
        edges_removed: 移除边数
        changed: 是否发生变化
        reason: 更新原因
        created_at: 创建时间
        metadata: 扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    node_id: str = ""
    action: str = "unchanged"
    node_confidence_before: float = 0.0
    node_confidence_after: float = 0.0
    node_weight_before: float = 1.0
    node_weight_after: float = 1.0
    edges_added: int = 0
    edges_updated: int = 0
    edges_removed: int = 0
    changed: bool = False
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def was_created(self) -> bool:
        return self.action == "created"

    @property
    def was_updated(self) -> bool:
        return self.action in ("updated", "strengthened", "weakened")

    @property
    def was_strengthened(self) -> bool:
        return self.action == "strengthened"

    @property
    def was_weakened(self) -> bool:
        return self.action == "weakened"

    @property
    def confidence_delta(self) -> float:
        return round(self.node_confidence_after - self.node_confidence_before, 4)

    @property
    def weight_delta(self) -> float:
        return round(self.node_weight_after - self.node_weight_before, 4)

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "pattern_id": self.pattern_id,
            "node_id": self.node_id,
            "action": self.action,
            "node_confidence_before": self.node_confidence_before,
            "node_confidence_after": self.node_confidence_after,
            "node_weight_before": self.node_weight_before,
            "node_weight_after": self.node_weight_after,
            "edges_added": self.edges_added,
            "edges_updated": self.edges_updated,
            "edges_removed": self.edges_removed,
            "changed": self.changed,
            "reason": self.reason,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 5. GraphBatchUpdateResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class GraphBatchUpdateResult:
    """批量图谱更新结果 — 一次完整图谱同步的输出.

    Attributes:
        batch_id: 批次唯一标识
        total_nodes: 总节点数
        nodes_created: 新增节点数
        nodes_updated: 更新节点数
        nodes_strengthened: 强化节点数
        nodes_weakened: 衰减节点数
        nodes_unchanged: 未变化节点数
        total_edges: 总边数
        edges_added: 新增边数
        edges_updated: 更新边数
        edges_removed: 移除边数
        results: 各节点更新结果
        update_summary: 更新摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_nodes: int = 0
    nodes_created: int = 0
    nodes_updated: int = 0
    nodes_strengthened: int = 0
    nodes_weakened: int = 0
    nodes_unchanged: int = 0
    total_edges: int = 0
    edges_added: int = 0
    edges_updated: int = 0
    edges_removed: int = 0
    results: list[GraphUpdateResult] = field(default_factory=list)
    update_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_results(
        cls,
        results: list[GraphUpdateResult],
        total_edges: int = 0,
    ) -> GraphBatchUpdateResult:
        """从更新结果列表创建批量结果."""
        n = len(results)
        created = [r for r in results if r.action == "created"]
        updated = [r for r in results if r.action == "updated"]
        strengthened = [r for r in results if r.action == "strengthened"]
        weakened = [r for r in results if r.action == "weakened"]
        unchanged = [r for r in results if not r.changed]

        edges_added = sum(r.edges_added for r in results)
        edges_updated = sum(r.edges_updated for r in results)
        edges_removed = sum(r.edges_removed for r in results)

        summary = cls._build_summary(
            n, len(created), len(updated), len(strengthened),
            len(weakened), len(unchanged),
            total_edges, edges_added, edges_updated, edges_removed,
        )

        return cls(
            total_nodes=n,
            nodes_created=len(created),
            nodes_updated=len(updated),
            nodes_strengthened=len(strengthened),
            nodes_weakened=len(weakened),
            nodes_unchanged=len(unchanged),
            total_edges=total_edges,
            edges_added=edges_added,
            edges_updated=edges_updated,
            edges_removed=edges_removed,
            results=results,
            update_summary=summary,
        )

    @staticmethod
    def _build_summary(
        total_nodes: int,
        created: int,
        updated: int,
        strengthened: int,
        weakened: int,
        unchanged: int,
        total_edges: int,
        edges_added: int,
        edges_updated: int,
        edges_removed: int,
    ) -> str:
        """构建更新摘要."""
        lines = [
            "-" * 50,
            "  Knowledge Graph Update Summary",
            "-" * 50,
            f"  Total nodes:         {total_nodes:>4d}",
            f"  Created:             {created:>4d}",
            f"  Updated:             {updated:>4d}",
            f"  Strengthened:        {strengthened:>4d}",
            f"  Weakened:            {weakened:>4d}",
            f"  Unchanged:           {unchanged:>4d}",
            "-" * 50,
            f"  Total edges:         {total_edges:>4d}",
            f"  Edges added:         {edges_added:>4d}",
            f"  Edges updated:       {edges_updated:>4d}",
            f"  Edges removed:       {edges_removed:>4d}",
            "-" * 50,
        ]
        return "\n".join(lines)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        return self.total_nodes == 0

    @property
    def has_changes(self) -> bool:
        return (self.nodes_created + self.nodes_updated
                + self.nodes_strengthened + self.nodes_weakened
                + self.edges_added + self.edges_updated + self.edges_removed) > 0

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_nodes": self.total_nodes,
            "nodes_created": self.nodes_created,
            "nodes_updated": self.nodes_updated,
            "nodes_strengthened": self.nodes_strengthened,
            "nodes_weakened": self.nodes_weakened,
            "nodes_unchanged": self.nodes_unchanged,
            "total_edges": self.total_edges,
            "edges_added": self.edges_added,
            "edges_updated": self.edges_updated,
            "edges_removed": self.edges_removed,
            "results": [r.to_dict() for r in self.results],
            "update_summary": self.update_summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "NodeType",
    "EdgeType",
    "KnowledgeGraphNode",
    "KnowledgeGraphEdge",
    "GraphUpdateResult",
    "GraphBatchUpdateResult",
]