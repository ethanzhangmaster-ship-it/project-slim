"""E11.7.5 — Evolution Knowledge Graph。

将 Evolution Memory 中的经验记录连接成可推理的知识网络。

核心组件:
  KnowledgeNode          — 知识节点
  NodeType               — 节点类型
  KnowledgeEdge          — 知识边
  KnowledgePath          — 知识路径
  KnowledgeQuery         — 图查询
  KnowledgeQueryResult   — 查询结果
  KnowledgeStats         — 图统计

  KnowledgeGraphStore    — 图存储（节点 + 边）
  KnowledgeBuilder       — 知识构建器（Memory → Graph）
  GraphQueryEngine       — 图查询引擎
  KnowledgeEngine        — 统一入口（ingest / analyze / recommend）
"""

from .models import (
    KnowledgeNode,
    NodeType,
    KnowledgeEdge,
    KnowledgePath,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeStats,
)
from .graph_store import KnowledgeGraphStore
from .knowledge_builder import KnowledgeBuilder
from .graph_query import GraphQueryEngine
from .knowledge_engine import KnowledgeEngine

__all__ = [
    # Models
    "KnowledgeNode",
    "NodeType",
    "KnowledgeEdge",
    "KnowledgePath",
    "KnowledgeQuery",
    "KnowledgeQueryResult",
    "KnowledgeStats",
    # Core
    "KnowledgeGraphStore",
    "KnowledgeBuilder",
    "GraphQueryEngine",
    "KnowledgeEngine",
]