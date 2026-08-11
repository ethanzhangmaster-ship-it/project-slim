"""E11.7.5 — Evolution Knowledge Graph Models。

KnowledgeNode:  知识节点（Genome, Mutation, Pattern, Strategy, Result, Category）
NodeType:       节点类型枚举
KnowledgeEdge:  知识边（关系 + 权重）
KnowledgePath:  知识路径
KnowledgeQuery: 图查询
KnowledgeQueryResult: 查询结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeType(str, Enum):
    """知识节点类型。"""
    GENOME = "genome"          # 基因组
    MUTATION = "mutation"      # 突变类型
    PATTERN = "pattern"        # 模式
    STRATEGY = "strategy"      # 策略
    RESULT = "result"          # 结果（success/failure/neutral/retired）
    CATEGORY = "category"      # 分类
    FITNESS = "fitness"        # 适应度变化
    CREATIVE = "creative"      # 创意


@dataclass
class KnowledgeNode:
    """知识节点。

    Attributes:
        node_id:   节点 ID
        node_type: 节点类型
        value:     节点值
        metadata:  元数据
        created_at: 创建时间
    """

    node_id: str = ""
    node_type: NodeType = NodeType.MUTATION
    value: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = f"node_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def key(self) -> str:
        """唯一键：node_type:value。"""
        return f"{self.node_type.value}:{self.value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "value": self.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return f"KnowledgeNode({self.node_type.value}:{self.value})"

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KnowledgeNode):
            return False
        return self.key == other.key


@dataclass
class KnowledgeEdge:
    """知识边。

    Attributes:
        source_id:   源节点 ID
        target_id:   目标节点 ID
        relation:    关系类型
        weight:      权重
        count:       出现次数
        metadata:    元数据
    """

    source_id: str = ""
    target_id: str = ""
    relation: str = ""
    weight: float = 1.0
    count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """唯一键：source_id → target_id : relation。"""
        return f"{self.source_id}→{self.target_id}:{self.relation}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "weight": self.weight,
            "count": self.count,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"KnowledgeEdge({self.source_id} "
            f"-{self.relation}-> "
            f"{self.target_id}, "
            f"w={self.weight})"
        )

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KnowledgeEdge):
            return False
        return self.key == other.key


@dataclass
class KnowledgePath:
    """知识路径。

    Attributes:
        nodes:     路径上的节点
        edges:     路径上的边
        total_weight: 路径总权重
        length:     路径长度
    """

    nodes: list[KnowledgeNode] = field(default_factory=list)
    edges: list[KnowledgeEdge] = field(default_factory=list)
    total_weight: float = 0.0

    @property
    def length(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "total_weight": self.total_weight,
            "length": self.length,
        }

    def __repr__(self) -> str:
        return f"KnowledgePath(len={self.length}, weight={self.total_weight:.2f})"


@dataclass
class KnowledgeQuery:
    """知识图谱查询。

    Attributes:
        node_type:   节点类型
        value:       节点值
        relation:    关系类型
        source_type: 源节点类型
        source_value: 源节点值
        target_type: 目标节点类型
        target_value: 目标节点值
        direction:   查询方向 (outgoing/incoming/both)
        max_depth:   最大深度
        min_weight:  最小权重
    """

    node_type: NodeType | None = None
    value: str | None = None
    relation: str | None = None
    source_type: NodeType | None = None
    source_value: str | None = None
    target_type: NodeType | None = None
    target_value: str | None = None
    direction: str = "outgoing"  # outgoing, incoming, both
    max_depth: int = 1
    min_weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": self.node_type.value if self.node_type else None,
            "value": self.value,
            "relation": self.relation,
            "source_type": self.source_type.value if self.source_type else None,
            "source_value": self.source_value,
            "target_type": self.target_type.value if self.target_type else None,
            "target_value": self.target_value,
            "direction": self.direction,
            "max_depth": self.max_depth,
            "min_weight": self.min_weight,
        }


@dataclass
class KnowledgeQueryResult:
    """知识图谱查询结果。

    Attributes:
        query:            原始查询
        nodes:            匹配的节点
        edges:            匹配的边
        paths:            知识路径
        total_nodes:      节点总数
        total_edges:      边总数
        success_rate:     成功率（如有）
        avg_fitness_gain: 平均适应度提升
        recommendation:   推荐
    """

    query: KnowledgeQuery = field(default_factory=KnowledgeQuery)
    nodes: list[KnowledgeNode] = field(default_factory=list)
    edges: list[KnowledgeEdge] = field(default_factory=list)
    paths: list[KnowledgePath] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    success_rate: float | None = None
    avg_fitness_gain: float | None = None
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query.to_dict(),
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "paths_count": len(self.paths),
            "success_rate": self.success_rate,
            "avg_fitness_gain": self.avg_fitness_gain,
            "recommendation": self.recommendation,
        }

    def __repr__(self) -> str:
        return (
            f"KnowledgeQueryResult(nodes={self.total_nodes}, "
            f"edges={self.total_edges}, "
            f"paths={len(self.paths)})"
        )


@dataclass
class KnowledgeStats:
    """知识图谱统计。"""

    total_nodes: int = 0
    total_edges: int = 0
    node_types: dict[str, int] = field(default_factory=dict)
    edge_relations: dict[str, int] = field(default_factory=dict)
    avg_weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "node_types": self.node_types,
            "edge_relations": self.edge_relations,
            "avg_weight": self.avg_weight,
        }

    def __repr__(self) -> str:
        return f"KnowledgeStats(nodes={self.total_nodes}, edges={self.total_edges})"