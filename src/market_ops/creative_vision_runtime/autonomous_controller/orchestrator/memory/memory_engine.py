"""E11.7.4 — Evolution Memory Engine。

统一入口：remember → recall → learn。

Three core capabilities:
  remember()  — Feedback → MemoryRecord → Store + Index
  recall()    — MemoryQuery → Retrieve → MemoryQueryResult
  learn()     — All records → MemoryInsight

完整链路：
  Experiment → Feedback → MemoryEngine.remember()
  Policy needs context → MemoryEngine.recall(query)
  Periodic analysis → MemoryEngine.learn()
"""

from __future__ import annotations

import logging
from typing import Any

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

logger = logging.getLogger(__name__)


class EvolutionMemoryEngine:
    """进化记忆引擎。

    统一入口：管理记忆的存储、检索和洞察。

    Attributes:
        store:      EvolutionMemoryStore
        index:      MemoryIndex
        retriever:  PatternRetriever
        remember_count: 记录次数
        recall_count:   检索次数
    """

    def __init__(
        self,
        store: EvolutionMemoryStore | None = None,
        index: MemoryIndex | None = None,
        retriever: PatternRetriever | None = None,
    ) -> None:
        self._store = store if store is not None else EvolutionMemoryStore()
        self._index = index if index is not None else MemoryIndex()
        self._retriever = retriever or PatternRetriever(
            store=self._store, index=self._index
        )
        self._remember_count: int = 0
        self._recall_count: int = 0

    # ── remember ──────────────────────────────────────────

    def remember(
        self,
        genome_id: str,
        mutation_type: str,
        fitness_before: float,
        fitness_after: float,
        category: str = "",
        parent_genome_id: str | None = None,
        mutation_params: dict[str, Any] | None = None,
        creative_id: str | None = None,
        outcome: MemoryOutcome | None = None,
        success_patterns: list[str] | None = None,
        failure_patterns: list[str] | None = None,
        generation: int = 0,
        notes: str = "",
    ) -> EvolutionMemoryRecord:
        """记录一次进化经验。

        Args:
            genome_id:         基因组 ID
            mutation_type:     突变类型
            fitness_before:    突变前适应度
            fitness_after:     突变后适应度
            category:          分类
            parent_genome_id:  父代 ID
            mutation_params:   突变参数
            creative_id:       创意 ID
            outcome:           结果（None 则自动推断）
            success_patterns:  成功模式
            failure_patterns:  失败模式
            generation:        代数
            notes:             备注

        Returns:
            EvolutionMemoryRecord
        """
        # 自动推断 outcome
        if outcome is None:
            fitness_gain = fitness_after - fitness_before
            if fitness_gain > 0.01:
                outcome = MemoryOutcome.SUCCESS
            elif fitness_gain < -0.01:
                outcome = MemoryOutcome.FAILURE
            else:
                outcome = MemoryOutcome.NEUTRAL

        record = EvolutionMemoryRecord(
            genome_id=genome_id,
            parent_genome_id=parent_genome_id,
            mutation_type=mutation_type,
            mutation_params=mutation_params or {},
            creative_id=creative_id,
            category=category,
            fitness_before=fitness_before,
            fitness_after=fitness_after,
            outcome=outcome,
            success_patterns=success_patterns or [],
            failure_patterns=failure_patterns or [],
            generation=generation,
            notes=notes,
        )

        # 存储 + 索引
        self._store.save(record)
        self._index.index(record)
        self._remember_count += 1

        logger.debug(
            f"Remembered: genome={genome_id}, "
            f"mutation={mutation_type}, "
            f"outcome={outcome.value}, "
            f"gain={record.fitness_gain:+.2f}"
        )
        return record

    def remember_from_feedback(
        self,
        feedback: dict[str, Any],
    ) -> EvolutionMemoryRecord:
        """从 feedback dict 创建记忆。

        feedback dict 格式：
          {
            "genome_id": str,
            "mutation_type": str,
            "fitness_before": float,
            "fitness_after": float,
            "category": str (optional),
            "parent_genome_id": str (optional),
            ...
          }

        Returns:
            EvolutionMemoryRecord
        """
        return self.remember(
            genome_id=feedback.get("genome_id", ""),
            mutation_type=feedback.get("mutation_type", ""),
            fitness_before=feedback.get("fitness_before", 0.0),
            fitness_after=feedback.get("fitness_after", 0.0),
            category=feedback.get("category", ""),
            parent_genome_id=feedback.get("parent_genome_id"),
            mutation_params=feedback.get("mutation_params"),
            creative_id=feedback.get("creative_id"),
            outcome=feedback.get("outcome"),
            success_patterns=feedback.get("success_patterns", []),
            failure_patterns=feedback.get("failure_patterns", []),
            generation=feedback.get("generation", 0),
            notes=feedback.get("notes", ""),
        )

    def remember_batch(
        self, feedbacks: list[dict[str, Any]]
    ) -> list[EvolutionMemoryRecord]:
        """批量记录。"""
        return [self.remember_from_feedback(f) for f in feedbacks]

    # ── recall ────────────────────────────────────────────

    def recall(
        self,
        mutation_type: str | None = None,
        category: str | None = None,
        patterns: list[str] | None = None,
        min_fitness_gain: float = 0.0,
        outcome: MemoryOutcome | None = None,
        max_records: int = 100,
    ) -> MemoryQueryResult:
        """检索历史经验。

        Args:
            mutation_type:   突变类型
            category:        分类
            patterns:        模式列表
            min_fitness_gain: 最低适应度提升
            outcome:         结果过滤
            max_records:     最大返回记录数

        Returns:
            MemoryQueryResult
        """
        self._recall_count += 1

        query = MemoryQuery(
            mutation_type=mutation_type,
            category=category,
            patterns=patterns or [],
            min_fitness_gain=min_fitness_gain,
            outcome=outcome,
            max_records=max_records,
        )

        return self._retriever.retrieve(query)

    def recall_by_query(self, query: MemoryQuery) -> MemoryQueryResult:
        """通过 MemoryQuery 对象检索。"""
        self._recall_count += 1
        return self._retriever.retrieve(query)

    # ── learn ─────────────────────────────────────────────

    def learn(self) -> MemoryInsight:
        """从所有记忆生成全局洞察。

        分析所有记录，按 mutation_type 和 category 聚合统计，
        生成最佳/最差突变类型和模式推荐。

        Returns:
            MemoryInsight
        """
        records = self._store.get_all()

        if not records:
            return MemoryInsight(
                total_records=0,
                recommendation="No memory records available for learning",
            )

        total = len(records)
        success_count = sum(1 for r in records if r.outcome == MemoryOutcome.SUCCESS)
        overall_success_rate = success_count / total if total > 0 else 0.0
        overall_avg_gain = sum(r.fitness_gain for r in records) / total if total > 0 else 0.0

        # 按 mutation_type 聚合
        by_mutation: dict[str, MemoryQueryResult] = {}
        for mt in self._index.get_mutation_types():
            query = MemoryQuery(mutation_type=mt)
            by_mutation[mt] = self._retriever.retrieve(query)

        # 按 category 聚合
        by_category: dict[str, MemoryQueryResult] = {}
        for cat in self._index.get_categories():
            query = MemoryQuery(category=cat)
            by_category[cat] = self._retriever.retrieve(query)

        # 最佳/最差 mutation_type
        best_mutation = ""
        worst_mutation = ""
        best_rate = -1.0
        worst_rate = 2.0
        for mt, result in by_mutation.items():
            if result.total_matches >= 3:
                if result.success_rate > best_rate:
                    best_rate = result.success_rate
                    best_mutation = mt
                if result.success_rate < worst_rate:
                    worst_rate = result.success_rate
                    worst_mutation = mt

        # 最成功/最失败模式
        top_success = self._extract_global_patterns(records, "success", 5)
        top_failure = self._extract_global_patterns(records, "failure", 5)

        # 推荐
        recommendation = self._generate_global_recommendation(
            overall_success_rate, best_mutation, worst_mutation, top_success
        )

        return MemoryInsight(
            total_records=total,
            overall_success_rate=round(overall_success_rate, 4),
            overall_avg_gain=round(overall_avg_gain, 4),
            by_mutation_type=by_mutation,
            by_category=by_category,
            best_mutation=best_mutation,
            worst_mutation=worst_mutation,
            top_success_patterns=top_success,
            top_failure_patterns=top_failure,
            recommendation=recommendation,
        )

    # ── 查询 ──────────────────────────────────────────────

    def get_record(self, memory_id: str) -> EvolutionMemoryRecord | None:
        return self._store.get(memory_id)

    def get_all_records(self) -> list[EvolutionMemoryRecord]:
        return self._store.get_all()

    def get_memory_stats(self) -> MemoryStats:
        return self._store.get_stats()

    def remove_record(self, memory_id: str) -> bool:
        record = self._store.get(memory_id)
        if record:
            self._index.remove(record)
        return self._store.remove(memory_id)

    def clear(self) -> None:
        self._store.clear()
        self._index.clear()

    # ── 内部 ──────────────────────────────────────────────

    @staticmethod
    def _extract_global_patterns(
        records: list[EvolutionMemoryRecord],
        pattern_type: str,
        top_n: int = 5,
    ) -> list[str]:
        """从所有记录中提取全局模式。"""
        from collections import Counter
        counter: Counter[str] = Counter()
        pattern_attr = (
            "success_patterns" if pattern_type == "success" else "failure_patterns"
        )
        for r in records:
            for pattern in getattr(r, pattern_attr, []):
                counter[pattern] += 1
        return [p for p, _ in counter.most_common(top_n)]

    @staticmethod
    def _generate_global_recommendation(
        overall_success_rate: float,
        best_mutation: str,
        worst_mutation: str,
        top_success_patterns: list[str],
    ) -> str:
        parts: list[str] = []
        if best_mutation:
            parts.append(f"Best mutation: {best_mutation}")
        if worst_mutation:
            parts.append(f"Avoid: {worst_mutation}")
        if top_success_patterns:
            parts.append(f"Top patterns: {', '.join(top_success_patterns[:3])}")
        if overall_success_rate >= 0.6:
            parts.append(f"Overall success rate {overall_success_rate:.0%} — system is learning well")
        elif overall_success_rate >= 0.3:
            parts.append(f"Overall success rate {overall_success_rate:.0%} — room for improvement")
        else:
            parts.append(f"Overall success rate {overall_success_rate:.0%} — consider strategy review")
        return "; ".join(parts) if parts else "Insufficient data for recommendation"

    # ── 属性 ──────────────────────────────────────────────

    @property
    def store(self) -> EvolutionMemoryStore:
        return self._store

    @property
    def index(self) -> MemoryIndex:
        return self._index

    @property
    def retriever(self) -> PatternRetriever:
        return self._retriever

    @property
    def remember_count(self) -> int:
        return self._remember_count

    @property
    def recall_count(self) -> int:
        return self._recall_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "remember_count": self._remember_count,
            "recall_count": self._recall_count,
            "store": {
                "size": len(self._store),
                "stats": self._store.get_stats().to_dict(),
            },
            "index": self._index.get_stats(),
            "retriever": self._retriever.get_stats(),
        }

    def reset(self) -> None:
        self._store.clear()
        self._index.clear()
        self._remember_count = 0
        self._recall_count = 0
        self._retriever.reset()

    def __repr__(self) -> str:
        return (
            f"EvolutionMemoryEngine(remembered={self._remember_count}, "
            f"recalled={self._recall_count}, "
            f"store={len(self._store)})"
        )