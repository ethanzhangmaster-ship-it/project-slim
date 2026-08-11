"""E12.5.3 — Meta Knowledge Graph。

Creative Intelligence Knowledge Graph，建立创意元素之间的因果关系和上下文关系。

核心模块:
  - models:              KnowledgeNode, KnowledgeEdge, NodeType, RelationType
  - graph_store:         图存储引擎（邻接表）
  - node_builder:        Pattern/Gene → KnowledgeNode 转换
  - relationship_engine: 自动关系发现
  - graph_query:         图查询引擎（E11 集成接口）

图结构:
  Gene → Pattern → Market/Audience/Platform → Metric → Experiment

查询场景:
  - find_best_genes_for_metric:  查询提升指标的最佳基因
  - recommend_mutation:          为 E11 推荐突变策略
  - find_transfer_candidates:    跨产品迁移
  - find_gene_combinations:      最佳基因组合
  - get_causal_chain:            因果链分析
"""

from .models import (
    GraphQuery,
    GraphQueryResult,
    GraphStats,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationType,
)
from .graph_store import GraphStore
from .node_builder import NodeBuilder
from .relationship_engine import RelationshipEngine
from .graph_query import GraphQueryEngine

__all__ = [
    # Models
    "NodeType",
    "RelationType",
    "KnowledgeNode",
    "KnowledgeEdge",
    "GraphQuery",
    "GraphQueryResult",
    "GraphStats",
    # Engines
    "GraphStore",
    "NodeBuilder",
    "RelationshipEngine",
    "GraphQueryEngine",
]