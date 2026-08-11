"""E11.7.4 — Evolution Memory。

Evolution Memory 模块为 Autonomous Creative Controller 提供长期记忆能力。

核心组件:
  EvolutionMemoryRecord  — 完整进化经验记录
  MemoryOutcome           — 经验结果
  MemoryQuery             — 检索查询
  MemoryQueryResult       — 查询结果
  MemoryInsight           — 全局洞察
  MemoryStats             — 内存统计

  EvolutionMemoryStore    — 内存存储（CRUD）
  MemoryIndex             — 多级索引
  PatternRetriever        — 模式检索与评分
  EvolutionMemoryEngine   — 统一入口（remember / recall / learn）
"""

from .models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
    MemoryQuery,
    MemoryQueryResult,
    MemoryInsight,
    MemoryStats,
)
from .memory_store import EvolutionMemoryStore
from .memory_index import MemoryIndex
from .pattern_retriever import PatternRetriever
from .memory_engine import EvolutionMemoryEngine

__all__ = [
    # Models
    "EvolutionMemoryRecord",
    "MemoryOutcome",
    "MemoryQuery",
    "MemoryQueryResult",
    "MemoryInsight",
    "MemoryStats",
    # Core
    "EvolutionMemoryStore",
    "MemoryIndex",
    "PatternRetriever",
    "EvolutionMemoryEngine",
]