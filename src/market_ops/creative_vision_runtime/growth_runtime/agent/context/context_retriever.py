"""E13.7.2 Context Retriever — 上下文检索器.

从记忆系统、知识图谱和外部数据源检索相关上下文，
为 LLM 推理提供完整的背景信息。

设计原则:
  - 统一检索接口
  - 多源融合
  - 相关性排序
  - 上下文大小控制

用法:
    retriever = ContextRetriever()
    ctx = retriever.retrieve(query="creative fatigue", memory_systems={...})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Retrieval Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class RetrievalResult:
    """检索结果."""
    source: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Context Retriever
# ═══════════════════════════════════════════════════════════════


class ContextRetriever:
    """上下文检索器 — 从多个数据源检索相关上下文.

    检索源:
      - 模式记忆 (Pattern Memory)
      - 策略记忆 (Strategy Memory)
      - 失败记忆 (Failure Memory)
      - 知识图谱 (Knowledge Graph)
      - 历史行动 (Past Actions)
      - LLM 经验记忆 (LLM Experience Memory)

    用法:
        retriever = ContextRetriever()
        results = retriever.retrieve(
            query="creative fatigue",
            memory_systems={"semantic": sm, "failure": fm},
            llm_memory=llm_mem,
        )
    """

    def __init__(self, max_results: int = 20, max_per_source: int = 5):
        self._max_results = max_results
        self._max_per_source = max_per_source

    def retrieve(
        self,
        query: str,
        memory_systems: dict[str, Any] | None = None,
        llm_memory: Any = None,
        knowledge_graph: list[dict[str, Any]] | None = None,
        past_actions: list[dict[str, Any]] | None = None,
    ) -> list[RetrievalResult]:
        """从多个数据源检索相关上下文.

        Args:
            query: 查询关键词
            memory_systems: 记忆系统 {"semantic": ..., "episodic": ..., "failure": ..., "strategy": ...}
            llm_memory: LLM 经验记忆
            knowledge_graph: 知识图谱
            past_actions: 历史行动

        Returns:
            list[RetrievalResult]: 检索结果
        """
        all_results = []

        memory_systems = memory_systems or {}

        # 语义记忆
        if "semantic" in memory_systems:
            results = self._retrieve_from_semantic(
                memory_systems["semantic"], query
            )
            all_results.extend(results)

        # 策略记忆
        if "strategy" in memory_systems:
            results = self._retrieve_from_strategy(
                memory_systems["strategy"], query
            )
            all_results.extend(results)

        # 失败记忆
        if "failure" in memory_systems:
            results = self._retrieve_from_failure(
                memory_systems["failure"], query
            )
            all_results.extend(results)

        # 情景记忆
        if "episodic" in memory_systems:
            results = self._retrieve_from_episodic(
                memory_systems["episodic"], query
            )
            all_results.extend(results)

        # LLM 经验记忆
        if llm_memory:
            results = self._retrieve_from_llm_memory(llm_memory, query)
            all_results.extend(results)

        # 知识图谱
        if knowledge_graph:
            results = self._retrieve_from_knowledge(knowledge_graph, query)
            all_results.extend(results)

        # 历史行动
        if past_actions:
            results = self._retrieve_from_actions(past_actions, query)
            all_results.extend(results)

        # 排序并截断
        all_results.sort(key=lambda r: r.relevance, reverse=True)
        return all_results[:self._max_results]

    def retrieve_all(
        self,
        memory_systems: dict[str, Any] | None = None,
        llm_memory: Any = None,
        knowledge_graph: list[dict[str, Any]] | None = None,
        past_actions: list[dict[str, Any]] | None = None,
        top_n: int = 10,
    ) -> list[RetrievalResult]:
        """检索所有可用上下文 (不按关键词过滤).

        Args:
            memory_systems: 记忆系统
            llm_memory: LLM 经验记忆
            knowledge_graph: 知识图谱
            past_actions: 历史行动
            top_n: 每个源返回数量

        Returns:
            list[RetrievalResult]: 检索结果
        """
        all_results = []
        memory_systems = memory_systems or {}

        # 从各系统获取最近条目
        for source_name, system in memory_systems.items():
            try:
                if hasattr(system, "get_recent"):
                    recent = system.get_recent(top_n)
                    for item in recent:
                        all_results.append(RetrievalResult(
                            source=source_name,
                            content=item if isinstance(item, dict) else {"data": str(item)},
                            relevance=0.5,
                        ))
            except Exception:
                pass

        if llm_memory:
            recent = llm_memory.get_recent(top_n)
            for exp in recent:
                all_results.append(RetrievalResult(
                    source="llm_memory",
                    content=exp.to_dict(),
                    relevance=exp.quality_score,
                ))

        if past_actions:
            for action in past_actions[-top_n:]:
                all_results.append(RetrievalResult(
                    source="past_actions",
                    content=action,
                    relevance=0.5,
                ))

        if knowledge_graph:
            for kg in knowledge_graph[-top_n:]:
                all_results.append(RetrievalResult(
                    source="knowledge_graph",
                    content=kg,
                    relevance=0.4,
                ))

        all_results.sort(key=lambda r: r.relevance, reverse=True)
        return all_results[:self._max_results]

    def _retrieve_from_semantic(self, memory, query: str) -> list[RetrievalResult]:
        """从语义记忆检索."""
        try:
            knowledge = memory.query(query, n=self._max_per_source)
            return [
                RetrievalResult(
                    source="semantic_memory",
                    content={"concept": k.concept, "description": k.description},
                    relevance=k.confidence,
                )
                for k in knowledge
            ]
        except Exception:
            return []

    def _retrieve_from_strategy(self, memory, query: str) -> list[RetrievalResult]:
        """从策略记忆检索."""
        try:
            strategies = memory.query(query, n=self._max_per_source)
            return [
                RetrievalResult(
                    source="strategy_memory",
                    content={"name": s.get("name", ""), "effectiveness": s.get("effectiveness", 0)},
                    relevance=s.get("effectiveness", 0.5),
                )
                for s in strategies
            ]
        except Exception:
            return []

    def _retrieve_from_failure(self, memory, query: str) -> list[RetrievalResult]:
        """从失败记忆检索."""
        try:
            failures = memory.query(query, n=self._max_per_source)
            return [
                RetrievalResult(
                    source="failure_memory",
                    content={"pattern": f.get("pattern", ""), "lesson": f.get("lesson", "")},
                    relevance=0.6,
                )
                for f in failures
            ]
        except Exception:
            return []

    def _retrieve_from_episodic(self, memory, query: str) -> list[RetrievalResult]:
        """从情景记忆检索."""
        try:
            episodes = memory.get_recent(self._max_per_source)
            return [
                RetrievalResult(
                    source="episodic_memory",
                    content={"outcome": e.get("outcome", ""), "lessons": e.get("lessons", [])},
                    relevance=0.4,
                )
                for e in episodes
            ]
        except Exception:
            return []

    def _retrieve_from_llm_memory(self, memory, query: str) -> list[RetrievalResult]:
        """从 LLM 经验记忆检索."""
        try:
            experiences = memory.retrieve(query, top_k=self._max_per_source, min_quality=0.3)
            return [
                RetrievalResult(
                    source="llm_experience",
                    content=exp.to_dict(),
                    relevance=exp.quality_score,
                )
                for exp in experiences
            ]
        except Exception:
            return []

    def _retrieve_from_knowledge(
        self,
        knowledge: list[dict[str, Any]],
        query: str,
    ) -> list[RetrievalResult]:
        """从知识图谱检索."""
        query_lower = query.lower()
        results = []
        for item in knowledge:
            text = str(item).lower()
            relevance = sum(1 for w in query_lower.split() if w in text) / max(len(query_lower.split()), 1)
            if relevance > 0:
                results.append(RetrievalResult(
                    source="knowledge_graph",
                    content=item,
                    relevance=min(relevance, 0.8),
                ))
        return results[:self._max_per_source]

    def _retrieve_from_actions(
        self,
        actions: list[dict[str, Any]],
        query: str,
    ) -> list[RetrievalResult]:
        """从历史行动检索."""
        query_lower = query.lower()
        results = []
        for action in actions:
            text = str(action).lower()
            relevance = sum(1 for w in query_lower.split() if w in text) / max(len(query_lower.split()), 1)
            if relevance > 0:
                results.append(RetrievalResult(
                    source="past_actions",
                    content=action,
                    relevance=min(relevance, 0.7),
                ))
        return results[:self._max_per_source]