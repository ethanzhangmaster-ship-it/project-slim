"""E13.2 Reality Data Pipeline — 数据中台层.

将 E13.1 Connectors 的原始数据转化为可查询、可推理的知识图谱，
为 E11 Evolution Engine 提供真实商业数据驱动的进化能力。

模块:
  - models:         Pipeline 统一数据模型
  - ingestion:      E13.2.1 统一数据接入管道
  - attribution:    E13.2.2 收入归因引擎
  - feature_store:  E13.2.3 创意特征向量生成
  - knowledge_graph: E13.2.4 知识图谱构建
"""

from .attribution import RevenueAttributionEngine
from .feature_store import GrowthFeatureStore
from .ingestion import DataIngestionPipeline, EventDeduplicator, EventNormalizer, EventValidator
from .knowledge_graph import KnowledgeGraphBuilder
from .models import (
    AttributionEdge,
    AttributionType,
    CreativeFitnessVector,
    EdgeType,
    EventStatus,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
    NormalizedEvent,
    PipelineConfig,
    PipelineStage,
    PipelineStats,
    RawEvent,
)

__all__ = [
    # Enums
    "PipelineStage",
    "EventStatus",
    "NodeType",
    "EdgeType",
    "AttributionType",
    # Models
    "RawEvent",
    "NormalizedEvent",
    "AttributionEdge",
    "CreativeFitnessVector",
    "KnowledgeNode",
    "KnowledgeEdge",
    "KnowledgeGraph",
    "PipelineConfig",
    "PipelineStats",
    # E13.2.1
    "DataIngestionPipeline",
    "EventValidator",
    "EventNormalizer",
    "EventDeduplicator",
    # E13.2.2
    "RevenueAttributionEngine",
    # E13.2.3
    "GrowthFeatureStore",
    # E13.2.4
    "KnowledgeGraphBuilder",
]