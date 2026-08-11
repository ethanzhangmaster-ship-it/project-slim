"""E12.7.5 Memory Controller — 统一入口，协调所有记忆组件."""

from __future__ import annotations

from typing import Any

from ..execution.models import ExecutionPlan

from .experience_store import ExperienceStore
from .memory_extractor import MemoryExtractor
from .memory_optimizer import MemoryOptimizer
from .models import (
    GrowthExperience,
    GrowthPattern,
    MemoryQuery,
    MemoryType,
    Outcome,
    RetrievalResult,
)
from .pattern_learner import PatternLearner
from .retrieval_engine import RetrievalEngine


class MemoryController:
    """记忆控制器 — Growth OS 长期记忆的统一入口.

    流程:
      1. ExecutionResult → Extract Experience
      2. Store Memory
      3. Learn Pattern
      4. Update Knowledge
      5. Expose Retrieval API
    """

    def __init__(
        self,
        store: ExperienceStore | None = None,
        extractor: MemoryExtractor | None = None,
        learner: PatternLearner | None = None,
        retriever: RetrievalEngine | None = None,
        optimizer: MemoryOptimizer | None = None,
    ):
        self._store = store or ExperienceStore()
        self._extractor = extractor or MemoryExtractor()
        self._learner = learner or PatternLearner()
        self._optimizer = optimizer or MemoryOptimizer()
        self._retriever = retriever or RetrievalEngine(store=self._store)

    @property
    def store(self) -> ExperienceStore:
        return self._store

    @property
    def extractor(self) -> MemoryExtractor:
        return self._extractor

    @property
    def learner(self) -> PatternLearner:
        return self._learner

    @property
    def retriever(self) -> RetrievalEngine:
        return self._retriever

    @property
    def optimizer(self) -> MemoryOptimizer:
        return self._optimizer

    # ── Ingest Pipeline ───────────────────────────────────────

    def ingest(self, plan: ExecutionPlan) -> dict[str, Any]:
        """摄入执行结果: 提取 → 存储 → 学习 → 优化.

        Returns:
            包含 experiences, patterns, stats 的字典
        """
        # Step 1: Extract
        experiences = self._extractor.extract_from_plan(plan)

        # Step 2: Store
        self._store.save_batch(experiences)

        # Step 3: Learn patterns
        patterns = self._learner.learn(self._store.get_all())
        self._store.save_patterns(patterns)

        # Step 4: Optimize (cleanup old)
        cleanup_stats = self._optimizer.cleanup(self._store)

        return {
            "experiences_extracted": len(experiences),
            "patterns_learned": len(patterns),
            "cleanup": cleanup_stats,
            "total_experiences": self._store.experience_count,
            "total_patterns": self._store.pattern_count,
        }

    def ingest_batch(self, plans: list[ExecutionPlan]) -> dict[str, Any]:
        """批量摄入多个执行结果."""
        total_exp = 0
        for plan in plans:
            experiences = self._extractor.extract_from_plan(plan)
            self._store.save_batch(experiences)
            total_exp += len(experiences)

        patterns = self._learner.learn(self._store.get_all())
        self._store.save_patterns(patterns)

        cleanup_stats = self._optimizer.cleanup(self._store)

        return {
            "experiences_extracted": total_exp,
            "patterns_learned": len(patterns),
            "cleanup": cleanup_stats,
            "total_experiences": self._store.experience_count,
            "total_patterns": self._store.pattern_count,
        }

    def ingest_experience(self, experience: GrowthExperience) -> GrowthExperience:
        """直接摄入单个经验."""
        self._store.save(experience)
        return experience

    # ── Retrieve ──────────────────────────────────────────────

    def retrieve(self, query: MemoryQuery) -> RetrievalResult:
        """检索经验."""
        return self._retriever.retrieve(query)

    def retrieve_by_context(self, context: dict[str, Any]) -> RetrievalResult:
        """根据上下文检索."""
        return self._retriever.retrieve_by_context(context)

    # ── Learn ─────────────────────────────────────────────────

    def learn_patterns(self) -> list[GrowthPattern]:
        """从当前所有经验中学习模式."""
        all_experiences = self._store.get_all()
        return self._learner.learn(all_experiences)

    def learn_and_store(self) -> list[GrowthPattern]:
        """学习并存储模式."""
        patterns = self.learn_patterns()
        self._store.save_patterns(patterns)
        return patterns

    # ── Optimize ──────────────────────────────────────────────

    def optimize(self) -> dict[str, int]:
        """执行记忆优化."""
        # Apply decay
        decay_stats = self._optimizer.apply_decay(self._store)

        # Cleanup
        cleanup_stats = self._optimizer.cleanup(self._store)

        # Promote
        high_value = self._optimizer.get_high_value_experiences(self._store)
        promote_count = 0
        if len(high_value) >= self._learner._min_experiences:
            patterns = self._optimizer.promote_to_pattern(high_value, self._learner)
            self._store.save_patterns(patterns)
            promote_count = len(patterns)

        return {
            **decay_stats,
            **cleanup_stats,
            "patterns_promoted": promote_count,
        }

    # ── Query Helpers ─────────────────────────────────────────

    def get_success_cases(self, product_id: str = "") -> list[GrowthExperience]:
        """获取成功案例."""
        if product_id:
            cases = self._store.get_by_product(product_id)
            return [c for c in cases if c.is_success]
        return self._store.get_success_cases()

    def get_failure_cases(self, product_id: str = "") -> list[GrowthExperience]:
        """获取失败案例."""
        if product_id:
            cases = self._store.get_by_product(product_id)
            return [c for c in cases if c.is_failure]
        return self._store.get_failure_cases()

    def get_by_product(self, product_id: str) -> list[GrowthExperience]:
        """按产品获取经验."""
        return self._store.get_by_product(product_id)

    def get_by_type(self, memory_type: MemoryType) -> list[GrowthExperience]:
        """按类型获取经验."""
        return self._store.get_by_type(memory_type)

    def search(self, keywords: list[str], limit: int = 10) -> list[GrowthExperience]:
        """关键词搜索."""
        return self._store.search(keywords, limit=limit)

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "store": self._store.get_statistics(),
            "retriever": self._retriever.get_summary(),
            "optimizer": self._optimizer.get_summary(),
            "extractor": {"extraction_count": self._extractor.extraction_count},
            "learner": {"learn_count": self._learner.learn_count},
        }