"""E13.7.2 Context — 增长上下文模块.

提供 LLM 推理所需的完整业务上下文构建和检索能力:
  - growth_context: GrowthContext 数据模型和构建器
  - context_retriever: 多源上下文检索器
"""

from .context_retriever import ContextRetriever, RetrievalResult
from .growth_context import (
    CreativeSnapshot,
    GrowthContext,
    GrowthContextBuilder,
    MetricsSnapshot,
)

__all__ = [
    "MetricsSnapshot",
    "CreativeSnapshot",
    "GrowthContext",
    "GrowthContextBuilder",
    "RetrievalResult",
    "ContextRetriever",
]