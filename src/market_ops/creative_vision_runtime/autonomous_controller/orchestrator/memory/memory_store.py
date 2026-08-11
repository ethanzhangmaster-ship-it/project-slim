"""E11.7.4 — Evolution Memory Store。

内存存储层：CRUD 操作。
第一版使用内存 dict，后续可替换为 SQLite / Vector DB。
"""

from __future__ import annotations

import logging
from typing import Any

from .models import EvolutionMemoryRecord, MemoryOutcome, MemoryStats

logger = logging.getLogger(__name__)


class EvolutionMemoryStore:
    """进化内存存储。

    基于内存 dict 的存储实现。

    Attributes:
        save_count:   已保存记录数
        remove_count: 已删除记录数
    """

    def __init__(self) -> None:
        self._records: dict[str, EvolutionMemoryRecord] = {}
        self._save_count: int = 0
        self._remove_count: int = 0

    # ── CRUD ──────────────────────────────────────────────

    def save(self, record: EvolutionMemoryRecord) -> str:
        """保存一条进化记忆。

        Args:
            record: EvolutionMemoryRecord

        Returns:
            memory_id
        """
        self._records[record.memory_id] = record
        self._save_count += 1
        logger.debug(f"Saved memory record: {record.memory_id}")
        return record.memory_id

    def save_batch(
        self, records: list[EvolutionMemoryRecord]
    ) -> list[str]:
        """批量保存。"""
        return [self.save(r) for r in records]

    def get(self, memory_id: str) -> EvolutionMemoryRecord | None:
        """按 ID 获取记录。"""
        return self._records.get(memory_id)

    def get_all(self) -> list[EvolutionMemoryRecord]:
        """获取所有记录。"""
        return list(self._records.values())

    def get_by_genome(self, genome_id: str) -> list[EvolutionMemoryRecord]:
        """按 genome_id 获取所有相关记录。"""
        return [
            r for r in self._records.values()
            if r.genome_id == genome_id
        ]

    def get_by_outcome(
        self, outcome: MemoryOutcome
    ) -> list[EvolutionMemoryRecord]:
        """按结果获取记录。"""
        return [
            r for r in self._records.values()
            if r.outcome == outcome
        ]

    def get_by_mutation_type(
        self, mutation_type: str
    ) -> list[EvolutionMemoryRecord]:
        """按突变类型获取记录。"""
        return [
            r for r in self._records.values()
            if r.mutation_type == mutation_type
        ]

    def get_by_category(
        self, category: str
    ) -> list[EvolutionMemoryRecord]:
        """按分类获取记录。"""
        return [
            r for r in self._records.values()
            if r.category == category
        ]

    def get_by_generation(
        self, generation: int
    ) -> list[EvolutionMemoryRecord]:
        """按代数获取记录。"""
        return [
            r for r in self._records.values()
            if r.generation == generation
        ]

    def update(self, memory_id: str, **kwargs: Any) -> bool:
        """更新记录字段。

        Returns:
            True 如果记录存在并更新成功。
        """
        record = self._records.get(memory_id)
        if record is None:
            return False
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        return True

    def remove(self, memory_id: str) -> bool:
        """删除记录。

        Returns:
            True 如果记录存在并删除成功。
        """
        if memory_id in self._records:
            del self._records[memory_id]
            self._remove_count += 1
            return True
        return False

    def remove_by_genome(self, genome_id: str) -> int:
        """删除指定 genome 的所有记录。

        Returns:
            删除数量。
        """
        to_remove = [
            mid for mid, r in self._records.items()
            if r.genome_id == genome_id
        ]
        for mid in to_remove:
            del self._records[mid]
            self._remove_count += 1
        return len(to_remove)

    def clear(self) -> int:
        """清空所有记录。

        Returns:
            删除数量。
        """
        count = len(self._records)
        self._records.clear()
        self._remove_count += count
        return count

    # ── 查询 ──────────────────────────────────────────────

    def count(self) -> int:
        """总记录数。"""
        return len(self._records)

    def contains(self, memory_id: str) -> bool:
        return memory_id in self._records

    def get_stats(self) -> MemoryStats:
        """生成内存统计。"""
        records = self.get_all()
        if not records:
            return MemoryStats()

        success = sum(1 for r in records if r.outcome == MemoryOutcome.SUCCESS)
        neutral = sum(1 for r in records if r.outcome == MemoryOutcome.NEUTRAL)
        failure = sum(1 for r in records if r.outcome == MemoryOutcome.FAILURE)
        retired = sum(1 for r in records if r.outcome == MemoryOutcome.RETIRED)
        genomes = set(r.genome_id for r in records)
        mutation_types = set(r.mutation_type for r in records if r.mutation_type)
        categories = set(r.category for r in records if r.category)
        avg_gain = sum(r.fitness_gain for r in records) / len(records)

        return MemoryStats(
            total_records=len(records),
            success_count=success,
            neutral_count=neutral,
            failure_count=failure,
            retired_count=retired,
            unique_genomes=len(genomes),
            unique_mutation_types=len(mutation_types),
            unique_categories=len(categories),
            avg_fitness_gain=round(avg_gain, 4),
        )

    # ── 属性 ──────────────────────────────────────────────

    @property
    def save_count(self) -> int:
        return self._save_count

    @property
    def remove_count(self) -> int:
        return self._remove_count

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, memory_id: str) -> bool:
        return self.contains(memory_id)

    def __repr__(self) -> str:
        return f"EvolutionMemoryStore(records={len(self._records)})"