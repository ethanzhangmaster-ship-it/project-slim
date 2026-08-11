"""E12.7.7 Memory API — 查看 AI 学习经验和模式."""

from __future__ import annotations

from typing import Any

from ..memory.memory_controller import MemoryController
from ..memory.models import GrowthExperience, GrowthPattern, MemoryType, Outcome

from .models import PatternView


class MemoryAPI:
    """记忆 API — 查看 AI 学习经验和模式.

    提供:
      - get_patterns():          获取学习模式
      - get_success_patterns():  获取成功模式
      - get_experiences():       获取经验列表
      - get_experience_detail(): 经验详情
      - search_memory():         搜索记忆
      - get_memory_stats():      记忆统计
    """

    def __init__(self, memory: MemoryController | None = None):
        self._memory = memory or MemoryController()
        self._query_count: int = 0

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── Patterns ──────────────────────────────────────────────

    def get_patterns(self, product_id: str = "") -> list[PatternView]:
        """获取学习模式."""
        self._query_count += 1

        patterns = self._memory.learn_patterns()
        result: list[PatternView] = []

        for p in patterns:
            if product_id and p.product_id != product_id:
                continue
            result.append(self._pattern_to_view(p))

        return result

    def get_success_patterns(self, min_confidence: float = 0.5) -> list[PatternView]:
        """获取成功模式."""
        self._query_count += 1

        patterns = self._memory.learn_patterns()
        return [
            self._pattern_to_view(p)
            for p in patterns
            if p.confidence >= min_confidence and p.outcome == Outcome.SUCCESS
        ]

    def get_pattern_detail(self, pattern_id: str) -> dict[str, Any] | None:
        """获取模式详情."""
        self._query_count += 1

        patterns = self._memory.learn_patterns()
        for p in patterns:
            if p.pattern_id == pattern_id:
                return self._build_pattern_detail(p)
        return None

    # ── Experiences ───────────────────────────────────────────

    def get_experiences(
        self, product_id: str = "", memory_type: str = "",
    ) -> list[dict[str, Any]]:
        """获取经验列表."""
        self._query_count += 1

        if product_id:
            experiences = self._memory.get_by_product(product_id)
        elif memory_type:
            try:
                mt = MemoryType(memory_type)
                experiences = self._memory.get_by_type(mt)
            except ValueError:
                experiences = []
        else:
            # Get all - use search with empty keywords
            experiences = self._memory.search([])

        return [self._experience_to_dict(e) for e in experiences]

    def get_experience_detail(self, experience_id: str) -> dict[str, Any] | None:
        """获取经验详情."""
        self._query_count += 1

        experiences = self._memory.search([])
        for e in experiences:
            if e.experience_id == experience_id:
                return self._experience_to_dict(e)
        return None

    def get_success_experiences(self, product_id: str = "") -> list[dict[str, Any]]:
        """获取成功经验."""
        self._query_count += 1

        experiences = self._memory.get_success_cases(product_id)
        return [self._experience_to_dict(e) for e in experiences]

    def get_failure_experiences(self, product_id: str = "") -> list[dict[str, Any]]:
        """获取失败经验."""
        self._query_count += 1

        experiences = self._memory.get_failure_cases(product_id)
        return [self._experience_to_dict(e) for e in experiences]

    # ── Search ────────────────────────────────────────────────

    def search_memory(self, keywords: list[str], limit: int = 10) -> list[dict[str, Any]]:
        """搜索记忆."""
        self._query_count += 1

        experiences = self._memory.search(keywords, limit=limit)
        return [self._experience_to_dict(e) for e in experiences]

    # ── Stats ─────────────────────────────────────────────────

    def get_memory_stats(self) -> dict[str, Any]:
        """获取记忆统计."""
        self._query_count += 1

        summary = self._memory.get_summary()
        store = summary.get("store", {})

        return {
            "total_experiences": store.get("total_experiences", 0),
            "total_patterns": store.get("total_patterns", 0),
            "success_cases": len(self._memory.get_success_cases()),
            "failure_cases": len(self._memory.get_failure_cases()),
            "query_count": self._query_count,
            "extractor": summary.get("extractor", {}),
            "retriever": summary.get("retriever", {}),
            "optimizer": summary.get("optimizer", {}),
        }

    # ── Helpers ───────────────────────────────────────────────

    def _pattern_to_view(self, p: GrowthPattern) -> PatternView:
        """将 GrowthPattern 转换为 PatternView."""
        return PatternView(
            pattern_id=p.pattern_id,
            name=p.name,
            description=p.description,
            usage_count=p.usage_count,
            success_rate=p.success_rate,
            avg_roas=p.metrics.roas if p.metrics else 0.0,
            confidence=p.confidence,
            reliability=p.reliability,
            gene_tags=list(p.gene_tags) if p.gene_tags else [],
            created_at=p.created_at.isoformat() if p.created_at else "",
        )

    def _build_pattern_detail(self, p: GrowthPattern) -> dict[str, Any]:
        """构建模式详情."""
        view = self._pattern_to_view(p)
        return {
            **view.to_dict(),
            "product_id": p.product_id,
            "outcome": p.outcome.value if p.outcome else "",
            "memory_type": p.memory_type.value if p.memory_type else "",
            "supporting_experience_ids": p.supporting_experience_ids,
        }

    def _experience_to_dict(self, e: GrowthExperience) -> dict[str, Any]:
        """将 GrowthExperience 转为字典."""
        return {
            "experience_id": e.experience_id,
            "product_id": e.product_id,
            "strategy_id": e.strategy_id,
            "memory_type": e.memory_type.value if e.memory_type else "",
            "outcome": e.outcome.value if e.outcome else "",
            "context": e.context.to_dict() if e.context else {},
            "metrics": e.metrics.to_dict() if e.metrics else {},
            "key_findings": e.key_findings,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "query_count": self._query_count,
            "memory_stats": self.get_memory_stats(),
        }