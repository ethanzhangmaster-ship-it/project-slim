"""E11.7.4 — Evolution Memory Index。

多级索引：mutation_type → category → memory_ids。
用于快速按类型和分类查找进化记忆。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from .models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
)

logger = logging.getLogger(__name__)


class MemoryIndex:
    """进化内存索引。

    三级索引结构：
      mutation_type → category → outcome → [memory_id, ...]

    支持快速查询：
      - 按 mutation_type 查找
      - 按 category 查找
      - 按 outcome 查找
      - 组合查找
    """

    def __init__(self) -> None:
        # mutation_type → {memory_id}
        self._mutation_index: dict[str, set[str]] = defaultdict(set)
        # category → {memory_id}
        self._category_index: dict[str, set[str]] = defaultdict(set)
        # outcome → {memory_id}
        self._outcome_index: dict[str, set[str]] = defaultdict(set)
        # pattern → {memory_id}
        self._pattern_index: dict[str, set[str]] = defaultdict(set)
        self._indexed_count: int = 0

    # ── 索引 ──────────────────────────────────────────────

    def index(self, record: EvolutionMemoryRecord) -> None:
        """索引一条记录。"""
        if record.mutation_type:
            self._mutation_index[record.mutation_type].add(record.memory_id)
        if record.category:
            self._category_index[record.category].add(record.memory_id)
        self._outcome_index[record.outcome.value].add(record.memory_id)
        for pattern in record.all_patterns:
            self._pattern_index[pattern].add(record.memory_id)
        self._indexed_count += 1

    def index_batch(self, records: list[EvolutionMemoryRecord]) -> None:
        """批量索引。"""
        for record in records:
            self.index(record)

    def remove(self, record: EvolutionMemoryRecord) -> None:
        """从索引中移除一条记录。"""
        if record.mutation_type:
            self._mutation_index[record.mutation_type].discard(record.memory_id)
        if record.category:
            self._category_index[record.category].discard(record.memory_id)
        self._outcome_index[record.outcome.value].discard(record.memory_id)
        for pattern in record.all_patterns:
            self._pattern_index[pattern].discard(record.memory_id)

    def rebuild(self, records: list[EvolutionMemoryRecord]) -> None:
        """重建索引（清空后重新索引）。"""
        self.clear()
        self.index_batch(records)

    # ── 查询 ──────────────────────────────────────────────

    def query_by_mutation_type(
        self, mutation_type: str
    ) -> set[str]:
        """按 mutation_type 查询。"""
        return self._mutation_index.get(mutation_type, set())

    def query_by_category(
        self, category: str
    ) -> set[str]:
        """按 category 查询。"""
        return self._category_index.get(category, set())

    def query_by_outcome(
        self, outcome: MemoryOutcome
    ) -> set[str]:
        """按 outcome 查询。"""
        return self._outcome_index.get(outcome.value, set())

    def query_by_pattern(
        self, pattern: str
    ) -> set[str]:
        """按 pattern 查询。"""
        return self._pattern_index.get(pattern, set())

    def query_by_patterns(
        self, patterns: list[str]
    ) -> set[str]:
        """按多个 pattern 查询（OR 逻辑）。"""
        if not patterns:
            return set()
        result: set[str] = set()
        for pattern in patterns:
            result |= self._pattern_index.get(pattern, set())
        return result

    def query(
        self,
        mutation_type: str | None = None,
        category: str | None = None,
        outcome: MemoryOutcome | None = None,
        patterns: list[str] | None = None,
    ) -> set[str]:
        """组合查询。

        多个条件之间是 AND 关系。
        """
        result: set[str] | None = None

        if mutation_type:
            ids = self.query_by_mutation_type(mutation_type)
            result = ids if result is None else result & ids

        if category:
            ids = self.query_by_category(category)
            result = ids if result is None else result & ids

        if outcome:
            ids = self.query_by_outcome(outcome)
            result = ids if result is None else result & ids

        if patterns:
            ids = self.query_by_patterns(patterns)
            result = ids if result is None else result & ids

        return result if result is not None else set()

    # ── 聚合 ──────────────────────────────────────────────

    def get_mutation_types(self) -> list[str]:
        """获取所有 mutation_type。"""
        return sorted(self._mutation_index.keys())

    def get_categories(self) -> list[str]:
        """获取所有 category。"""
        return sorted(self._category_index.keys())

    def get_patterns(self) -> list[str]:
        """获取所有 pattern。"""
        return sorted(self._pattern_index.keys())

    def get_index_size(self, index_name: str) -> int:
        """获取指定索引的大小。"""
        index_map = {
            "mutation": self._mutation_index,
            "category": self._category_index,
            "outcome": self._outcome_index,
            "pattern": self._pattern_index,
        }
        idx = index_map.get(index_name, {})
        return sum(len(v) for v in idx.values())

    # ── 管理 ──────────────────────────────────────────────

    def clear(self) -> None:
        self._mutation_index.clear()
        self._category_index.clear()
        self._outcome_index.clear()
        self._pattern_index.clear()
        self._indexed_count = 0

    # ── 属性 ──────────────────────────────────────────────

    @property
    def indexed_count(self) -> int:
        return self._indexed_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "mutation_types": len(self._mutation_index),
            "categories": len(self._category_index),
            "outcomes": len(self._outcome_index),
            "patterns": len(self._pattern_index),
            "indexed_count": self._indexed_count,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryIndex(mutation_types={len(self._mutation_index)}, "
            f"categories={len(self._category_index)}, "
            f"patterns={len(self._pattern_index)})"
        )