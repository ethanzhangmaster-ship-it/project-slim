"""E12.7.5 Retrieval Engine — Growth OS 的 RAG 经验检索."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .experience_store import ExperienceStore
from .models import (
    GrowthExperience,
    GrowthPattern,
    MemoryQuery,
    MemoryType,
    Outcome,
    RetrievalResult,
)


class RetrievalEngine:
    """检索引擎 — 为 Agent/Planner 提供经验查询.

    类似 Growth OS 的 RAG (Retrieval-Augmented Generation).
    """

    def __init__(self, store: ExperienceStore | None = None):
        self._store = store or ExperienceStore()
        self._query_count: int = 0

    @property
    def store(self) -> ExperienceStore:
        return self._store

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── Retrieve ──────────────────────────────────────────────

    def retrieve(self, query: MemoryQuery) -> RetrievalResult:
        """检索相关经验和模式."""
        import time
        start = time.perf_counter()
        self._query_count += 1

        experiences = self._retrieve_experiences(query)
        patterns = self._retrieve_patterns(query)

        total = len(experiences) + len(patterns)
        retrieval_time = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            experiences=experiences,
            patterns=patterns,
            query=query,
            total_matches=total,
            retrieval_time_ms=round(retrieval_time, 2),
        )

    def retrieve_by_context(self, context: dict[str, Any]) -> RetrievalResult:
        """根据上下文检索 (便捷方法)."""
        query = MemoryQuery(
            product_id=context.get("product_id", ""),
            market=context.get("market", ""),
            channel=context.get("channel", ""),
            limit=context.get("limit", 10),
        )
        return self.retrieve(query)

    # ── Experience Retrieval ──────────────────────────────────

    def _retrieve_experiences(self, query: MemoryQuery) -> list[GrowthExperience]:
        """检索经验."""
        candidates = self._store.get_all()

        # Filter
        filtered = self._filter_experiences(candidates, query)

        # Score
        scored = self._score_experiences(filtered, query)

        # Sort
        scored.sort(key=lambda x: x[0], reverse=True)

        return [e for _, e in scored[:query.limit]]

    def _filter_experiences(
        self, experiences: list[GrowthExperience], query: MemoryQuery,
    ) -> list[GrowthExperience]:
        """过滤经验."""
        result: list[GrowthExperience] = []

        for exp in experiences:
            if not self._matches_query(exp, query):
                continue
            if query.min_learning_value > 0 and exp.learning_value < query.min_learning_value:
                continue
            if query.min_confidence > 0 and exp.confidence < query.min_confidence:
                continue
            if query.max_age_days > 0 and exp.age_days > query.max_age_days:
                continue
            result.append(exp)

        return result

    def _matches_query(self, exp: GrowthExperience, query: MemoryQuery) -> bool:
        """检查经验是否匹配查询条件."""
        if query.product_id and exp.product_id != query.product_id:
            return False
        if query.market and exp.context.market != query.market:
            return False
        if query.channel and exp.context.channel != query.channel:
            return False
        if query.memory_type and exp.memory_type != query.memory_type:
            return False
        if query.outcome and exp.result != query.outcome:
            return False
        if query.tags:
            if not any(tag in exp.tags for tag in query.tags):
                return False
        return True

    def _score_experiences(
        self, experiences: list[GrowthExperience], query: MemoryQuery,
    ) -> list[tuple[float, GrowthExperience]]:
        """对经验打分排序."""
        scored: list[tuple[float, GrowthExperience]] = []

        for exp in experiences:
            score = self._compute_experience_score(exp, query)
            scored.append((score, exp))

        return scored

    def _compute_experience_score(
        self, exp: GrowthExperience, query: MemoryQuery,
    ) -> float:
        """计算经验匹配分数."""
        score = 0.0

        # Sort by specified field — dominant weight
        if query.sort_by == "learning_value":
            score += exp.learning_value * 1.0
        elif query.sort_by == "confidence":
            score += exp.confidence * 1.0
        else:
            # Recency bias
            score += max(0.0, 0.5 - exp.age_days / 730.0)

        # Keyword matching bonus (secondary)
        if query.keywords:
            keyword_score = self._store._keyword_score(exp, query.keywords)
            score += keyword_score * 0.1

        # Success bonus (small)
        if exp.is_success:
            score += 0.05

        # Learning value bonus (small)
        score += exp.learning_value * 0.05

        return score

    # ── Pattern Retrieval ─────────────────────────────────────

    def _retrieve_patterns(self, query: MemoryQuery) -> list[GrowthPattern]:
        """检索模式."""
        candidates = self._store.get_all_patterns()

        # Filter
        filtered = self._filter_patterns(candidates, query)

        # Score
        scored = self._score_patterns(filtered, query)

        # Sort
        scored.sort(key=lambda x: x[0], reverse=True)

        return [p for _, p in scored[:query.limit]]

    def _filter_patterns(
        self, patterns: list[GrowthPattern], query: MemoryQuery,
    ) -> list[GrowthPattern]:
        """过滤模式."""
        result: list[GrowthPattern] = []

        for pat in patterns:
            if not self._matches_pattern_query(pat, query):
                continue
            if query.min_confidence > 0 and pat.confidence < query.min_confidence:
                continue
            if query.max_age_days > 0 and pat.age_days > query.max_age_days:
                continue
            result.append(pat)

        return result

    def _matches_pattern_query(self, pat: GrowthPattern, query: MemoryQuery) -> bool:
        """检查模式是否匹配查询."""
        if query.product_id and pat.product_id and pat.product_id != query.product_id:
            return False
        if query.market and pat.market and pat.market != query.market:
            return False
        if query.memory_type and pat.pattern_type != query.memory_type:
            return False
        return True

    def _score_patterns(
        self, patterns: list[GrowthPattern], query: MemoryQuery,
    ) -> list[tuple[float, GrowthPattern]]:
        """对模式打分排序."""
        scored: list[tuple[float, GrowthPattern]] = []

        for pat in patterns:
            score = self._compute_pattern_score(pat, query)
            scored.append((score, pat))

        return scored

    def _compute_pattern_score(
        self, pat: GrowthPattern, query: MemoryQuery,
    ) -> float:
        """计算模式匹配分数."""
        score = 0.0

        # Confidence-based
        score += pat.confidence * 0.3

        # Success rate
        score += pat.success_rate * 0.3

        # Usage count
        score += min(0.2, pat.usage_count * 0.02)

        # Recency
        score += max(0.0, 0.2 - pat.age_days / 730.0)

        # Keyword matching
        if query.keywords:
            keyword_score = self._store._pattern_keyword_score(pat, query.keywords)
            score += keyword_score * 0.2

        return score

    # ── Quick Query Helpers ───────────────────────────────────

    def get_successful_strategies(
        self, product_id: str, limit: int = 10,
    ) -> list[GrowthExperience]:
        """获取成功策略经验."""
        query = MemoryQuery(
            product_id=product_id,
            outcome=Outcome.SUCCESS,
            memory_type=MemoryType.STRATEGY_MEMORY,
            limit=limit,
        )
        return self.retrieve(query).experiences

    def get_failure_lessons(
        self, product_id: str, limit: int = 10,
    ) -> list[GrowthExperience]:
        """获取失败教训."""
        query = MemoryQuery(
            product_id=product_id,
            outcome=Outcome.FAILURE,
            limit=limit,
        )
        return self.retrieve(query).experiences

    def get_creative_patterns(
        self, product_id: str, limit: int = 10,
    ) -> list[GrowthPattern]:
        """获取创意模式."""
        query = MemoryQuery(
            product_id=product_id,
            memory_type=MemoryType.CREATIVE_MEMORY,
            limit=limit,
        )
        return self.retrieve(query).patterns

    def get_market_patterns(
        self, market: str, limit: int = 10,
    ) -> list[GrowthPattern]:
        """获取市场模式."""
        query = MemoryQuery(
            market=market,
            memory_type=MemoryType.SUCCESS_PATTERN,
            limit=limit,
        )
        return self.retrieve(query).patterns

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "query_count": self.query_count,
            "store_stats": self._store.get_statistics(),
        }