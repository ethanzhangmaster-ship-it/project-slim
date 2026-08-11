"""E11.7.4 — Pattern Retriever。

核心智能模块：Query → Retrieve → Rank → Insight。

负责：
  - 按查询条件检索记忆
  - 对结果进行评分和排序
  - 生成统计摘要和推荐
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from .models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
    MemoryQuery,
    MemoryQueryResult,
)
from .memory_store import EvolutionMemoryStore
from .memory_index import MemoryIndex

logger = logging.getLogger(__name__)


class PatternRetriever:
    """模式检索器。

    负责从 MemoryStore + MemoryIndex 中检索、评分和总结。

    Attributes:
        store:  EvolutionMemoryStore
        index:  MemoryIndex
        retrieve_count: 检索次数
    """

    def __init__(
        self,
        store: EvolutionMemoryStore | None = None,
        index: MemoryIndex | None = None,
    ) -> None:
        self._store = store if store is not None else EvolutionMemoryStore()
        self._index = index if index is not None else MemoryIndex()
        self._retrieve_count: int = 0

    # ── 核心接口 ──────────────────────────────────────────

    def retrieve(
        self, query: MemoryQuery
    ) -> MemoryQueryResult:
        """根据查询检索记忆。

        流程：
          1. Index 查询 → memory_ids
          2. Store 获取 → records
          3. 过滤（fitness_gain, outcome）
          4. 评分排序
          5. 统计摘要

        Args:
            query: MemoryQuery

        Returns:
            MemoryQueryResult
        """
        self._retrieve_count += 1

        # 1. 通过 Index 查询
        memory_ids = self._index.query(
            mutation_type=query.mutation_type,
            category=query.category,
            outcome=query.outcome,
            patterns=query.patterns if query.patterns else None,
        )

        # 2. 从 Store 获取记录
        records: list[EvolutionMemoryRecord] = []
        for mid in memory_ids:
            record = self._store.get(mid)
            if record:
                records.append(record)

        # 如果没有 Index 命中，回退到全量扫描
        if not records and not query.mutation_type and not query.category and not query.patterns:
            records = self._store.get_all()

        # 3. 过滤
        records = self._filter_records(records, query)

        # 4. 评分排序（按 fitness_gain 降序）
        records.sort(key=lambda r: r.fitness_gain, reverse=True)

        # 5. 限制数量
        if query.max_records > 0 and len(records) > query.max_records:
            records = records[:query.max_records]

        # 6. 统计
        return self._summarize(query, records)

    def retrieve_batch(
        self, queries: list[MemoryQuery]
    ) -> list[MemoryQueryResult]:
        """批量检索。"""
        return [self.retrieve(q) for q in queries]

    # ── 过滤 ──────────────────────────────────────────────

    def _filter_records(
        self,
        records: list[EvolutionMemoryRecord],
        query: MemoryQuery,
    ) -> list[EvolutionMemoryRecord]:
        """应用过滤条件。"""
        filtered = records

        # fitness_gain 过滤
        if query.min_fitness_gain > 0:
            filtered = [
                r for r in filtered
                if r.fitness_gain >= query.min_fitness_gain
            ]

        # outcome 过滤（如果 Index 未覆盖）
        if query.outcome and not query.mutation_type and not query.category and not query.patterns:
            filtered = [
                r for r in filtered
                if r.outcome == query.outcome
            ]

        return filtered

    # ── 统计 ──────────────────────────────────────────────

    def _summarize(
        self,
        query: MemoryQuery,
        records: list[EvolutionMemoryRecord],
    ) -> MemoryQueryResult:
        """生成查询结果统计。"""
        total = len(records)
        if total == 0:
            return MemoryQueryResult(
                query=query,
                records=[],
                total_matches=0,
                recommendation="No matching records found",
            )

        success_count = sum(1 for r in records if r.outcome == MemoryOutcome.SUCCESS)
        failure_count = sum(1 for r in records if r.outcome == MemoryOutcome.FAILURE)
        success_rate = success_count / total if total > 0 else 0.0
        avg_gain = sum(r.fitness_gain for r in records) / total if total > 0 else 0.0

        # 最佳/最差模式
        best_patterns = self._extract_best_patterns(records, top_n=3)
        bad_patterns = self._extract_worst_patterns(records, top_n=3)

        # 推荐
        recommendation = self._generate_recommendation(
            success_rate, avg_gain, best_patterns
        )

        return MemoryQueryResult(
            query=query,
            records=records,
            total_matches=total,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=round(success_rate, 4),
            avg_gain=round(avg_gain, 4),
            best_patterns=best_patterns,
            bad_patterns=bad_patterns,
            recommendation=recommendation,
        )

    # ── 模式提取 ──────────────────────────────────────────

    @staticmethod
    def _extract_best_patterns(
        records: list[EvolutionMemoryRecord],
        top_n: int = 3,
    ) -> list[str]:
        """从成功记录中提取最佳模式。"""
        success_records = [
            r for r in records if r.outcome == MemoryOutcome.SUCCESS
        ]
        counter: Counter[str] = Counter()
        for r in success_records:
            for pattern in r.success_patterns:
                counter[pattern] += 1
        return [p for p, _ in counter.most_common(top_n)]

    @staticmethod
    def _extract_worst_patterns(
        records: list[EvolutionMemoryRecord],
        top_n: int = 3,
    ) -> list[str]:
        """从失败记录中提取最差模式。"""
        failure_records = [
            r for r in records if r.outcome == MemoryOutcome.FAILURE
        ]
        counter: Counter[str] = Counter()
        for r in failure_records:
            for pattern in r.failure_patterns:
                counter[pattern] += 1
        return [p for p, _ in counter.most_common(top_n)]

    @staticmethod
    def _generate_recommendation(
        success_rate: float,
        avg_gain: float,
        best_patterns: list[str],
    ) -> str:
        """生成推荐文字。"""
        if success_rate >= 0.7:
            return f"Recommended: high success rate ({success_rate:.0%}), consider amplifying"
        elif success_rate >= 0.4:
            return f"Moderate: {success_rate:.0%} success, explore with caution"
        elif success_rate > 0:
            return f"Risky: low success rate ({success_rate:.0%}), avoid unless experimenting"
        else:
            return "No successful records, recommend avoiding this strategy"

    # ── 属性 ──────────────────────────────────────────────

    @property
    def retrieve_count(self) -> int:
        return self._retrieve_count

    @property
    def store(self) -> EvolutionMemoryStore:
        return self._store

    @property
    def index(self) -> MemoryIndex:
        return self._index

    def get_stats(self) -> dict[str, Any]:
        return {
            "retrieve_count": self._retrieve_count,
            "store_size": len(self._store),
            "index_stats": self._index.get_stats(),
        }

    def reset(self) -> None:
        self._retrieve_count = 0

    def __repr__(self) -> str:
        return f"PatternRetriever(retrieved={self._retrieve_count})"