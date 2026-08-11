"""E12.5.3 — Knowledge Graph Models。

Creative Intelligence Knowledge Graph 核心数据模型。

节点类型:
  PRODUCT, CREATIVE, GENE, PATTERN, MARKET, AUDIENCE, PLATFORM, METRIC, EXPERIMENT

关系类型:
  IMPROVES, BELONGS_TO, WORKS_FOR, SIMILAR_TO, CAUSES, COMBINES_WITH, FAILED_WITH

图结构:
  Gene → Pattern → Market/Audience/Platform → Metric → Experiment
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── NodeType ───────────────────────────────────────────────


class NodeType(str, Enum):
    """知识图谱节点类型。"""

    PRODUCT = "product"
    CREATIVE = "creative"
    GENE = "gene"
    PATTERN = "pattern"
    MARKET = "market"
    AUDIENCE = "audience"
    PLATFORM = "platform"
    METRIC = "metric"
    EXPERIMENT = "experiment"


# ── RelationType ───────────────────────────────────────────


class RelationType(str, Enum):
    """知识图谱关系类型。"""

    IMPROVES = "improves"           # Gene/Pattern 提升某个 Metric
    BELONGS_TO = "belongs_to"       # Gene 属于某个 Pattern
    WORKS_FOR = "works_for"         # Pattern 适用于某 Audience/Market/Platform
    SIMILAR_TO = "similar_to"       # 两个 Pattern 相似
    CAUSES = "causes"               # 因果链
    COMBINES_WITH = "combines_with" # 两个 Gene 组合效果好
    FAILED_WITH = "failed_with"     # 组合失败
    TRANSFERS_TO = "transfers_to"   # 跨产品迁移
    SUPPORTS = "supports"           # 证据支持
    PRODUCED_BY = "produced_by"     # 实验结果来源于某 Experiment


# ── KnowledgeNode ──────────────────────────────────────────


@dataclass
class KnowledgeNode:
    """知识图谱节点。

    Attributes:
        node_id:     唯一标识
        node_type:   节点类型
        name:        人类可读名称
        attributes:  属性字典
        confidence:  置信度 [0, 1]
        created_at:  创建时间
        labels:      额外标签
        source_ids:  来源 ID 列表（如 pattern_id, gene_feature 等）
    """

    node_id: str = ""
    node_type: NodeType = NodeType.GENE
    name: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=_now)
    labels: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = _gen_id("NODE")

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.60

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value if isinstance(self.node_type, NodeType) else self.node_type,
            "name": self.name,
            "attributes": self.attributes,
            "confidence": round(self.confidence, 4),
            "created_at": self.created_at.isoformat(),
            "labels": self.labels,
            "source_ids": self.source_ids,
            "is_reliable": self.is_reliable,
        }

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KnowledgeNode):
            return NotImplemented
        return self.node_id == other.node_id

    def __repr__(self) -> str:
        return (
            f"KnowledgeNode({self.node_type.value}, "
            f"name='{self.name[:20]}', "
            f"conf={self.confidence:.2f})"
        )


# ── KnowledgeEdge ──────────────────────────────────────────


@dataclass
class KnowledgeEdge:
    """知识图谱边。

    Attributes:
        edge_id:         唯一标识
        source_id:       源节点 ID
        target_id:       目标节点 ID
        relation_type:   关系类型
        weight:          权重 [0, 1]
        evidence_count:  证据数量（实验次数）
        confidence:      置信度 [0, 1]
        attributes:      额外属性
        created_at:      创建时间
    """

    edge_id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation_type: RelationType = RelationType.IMPROVES
    weight: float = 0.0
    evidence_count: int = 0
    confidence: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.edge_id:
            self.edge_id = _gen_id("EDGE")

    @property
    def is_reliable(self) -> bool:
        return self.evidence_count >= 5 and self.confidence >= 0.60

    @property
    def is_strong(self) -> bool:
        return self.evidence_count >= 20 and self.confidence >= 0.80

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value if isinstance(self.relation_type, RelationType) else self.relation_type,
            "weight": round(self.weight, 4),
            "evidence_count": self.evidence_count,
            "confidence": round(self.confidence, 4),
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat(),
            "is_reliable": self.is_reliable,
            "is_strong": self.is_strong,
        }

    def __hash__(self) -> int:
        return hash(self.edge_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KnowledgeEdge):
            return NotImplemented
        return self.edge_id == other.edge_id

    def __repr__(self) -> str:
        return (
            f"KnowledgeEdge({self.source_id[:8]} "
            f"-{self.relation_type.value}-> "
            f"{self.target_id[:8]}, "
            f"w={self.weight:.2f})"
        )


# ── GraphQuery ─────────────────────────────────────────────


@dataclass
class GraphQuery:
    """图查询请求。

    Attributes:
        query_type:        查询类型
        target_node_type:  目标节点类型
        target_metric:     目标指标（如 CTR, ROAS）
        gene_categories:   基因类别筛选
        market:            市场筛选
        product_id:        产品筛选
        platform:          平台筛选
        max_results:       最大结果数
        min_confidence:    最低置信度
        min_evidence:      最低证据数
    """

    query_type: str = "find_patterns"
    target_node_type: NodeType | None = None
    target_metric: str = ""
    gene_categories: list[str] = field(default_factory=list)
    market: str = ""
    product_id: str = ""
    platform: str = ""
    max_results: int = 10
    min_confidence: float = 0.60
    min_evidence: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_type": self.query_type,
            "target_node_type": self.target_node_type.value if self.target_node_type else None,
            "target_metric": self.target_metric,
            "gene_categories": self.gene_categories,
            "market": self.market,
            "product_id": self.product_id,
            "platform": self.platform,
            "max_results": self.max_results,
            "min_confidence": self.min_confidence,
            "min_evidence": self.min_evidence,
        }


# ── GraphQueryResult ───────────────────────────────────────


@dataclass
class GraphQueryResult:
    """图查询结果。

    Attributes:
        query:            原始查询
        nodes:            匹配节点
        edges:            匹配边
        paths:            匹配路径
        recommendations:  推荐列表
        summary:          结果摘要
    """

    query: GraphQuery = field(default_factory=GraphQuery)
    nodes: list[KnowledgeNode] = field(default_factory=list)
    edges: list[KnowledgeEdge] = field(default_factory=list)
    paths: list[list[KnowledgeEdge]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query.to_dict(),
            "nodes_found": len(self.nodes),
            "edges_found": len(self.edges),
            "paths_found": len(self.paths),
            "recommendations_count": len(self.recommendations),
            "summary": self.summary,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "paths": [
                [e.to_dict() for e in path] for path in self.paths
            ],
            "recommendations": self.recommendations,
        }

    def __repr__(self) -> str:
        return (
            f"GraphQueryResult(nodes={len(self.nodes)}, "
            f"edges={len(self.edges)}, "
            f"recs={len(self.recommendations)})"
        )


# ── GraphStats ─────────────────────────────────────────────


@dataclass
class GraphStats:
    """图统计信息。"""

    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    edges_by_type: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    connected_components: int = 0
    densest_subgraph: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "nodes_by_type": self.nodes_by_type,
            "edges_by_type": self.edges_by_type,
            "avg_confidence": round(self.avg_confidence, 4),
            "connected_components": self.connected_components,
            "densest_subgraph": self.densest_subgraph,
        }

    def __repr__(self) -> str:
        return (
            f"GraphStats(nodes={self.total_nodes}, "
            f"edges={self.total_edges})"
        )