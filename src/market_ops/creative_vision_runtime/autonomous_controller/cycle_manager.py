"""E11.5.1 — Cycle Manager。

管理多个进化循环的生命周期。

核心职责：
  1. 记录所有循环历史
  2. 跟踪当前活跃循环
  3. 提供循环查询和统计
  4. 支持多循环序列 (Cycle N → Cycle N+1)
"""

from __future__ import annotations

import logging
from typing import Any

from .models import CycleRecord, CycleResult, CycleStatus

logger = logging.getLogger(__name__)


class CycleManager:
    """进化循环管理器。

    管理多个 CycleRecord，追踪循环历史和状态。

    Attributes:
        cycles:        所有循环记录
        active_cycle:  当前活跃循环
        total_cycles:  总循环数
    """

    def __init__(self) -> None:
        self._cycles: list[CycleRecord] = []
        self._active_cycle: CycleRecord | None = None
        self._total_cycles: int = 0

    # ── Cycle Lifecycle ─────────────────────────────────

    def start_cycle(
        self,
        asset_ids: list[str],
        winner_asset_ids: list[str] | None = None,
    ) -> CycleRecord:
        """开始新循环。

        Args:
            asset_ids:        素材 ID 列表
            winner_asset_ids: Winner 素材 ID 列表

        Returns:
            新 CycleRecord

        Raises:
            RuntimeError: 已有活跃循环
        """
        if self._active_cycle is not None:
            raise RuntimeError(
                f"Active cycle already exists: {self._active_cycle.cycle_id}"
            )

        self._total_cycles += 1
        record = CycleRecord(
            cycle_number=self._total_cycles,
            input_asset_ids=list(asset_ids),
            winner_asset_ids=list(winner_asset_ids or []),
        )
        record.mark_started()

        self._active_cycle = record
        self._cycles.append(record)

        logger.info(f"Cycle #{record.cycle_number} started: {record.cycle_id}")
        return record

    def complete_cycle(self) -> CycleRecord | None:
        """完成当前活跃循环。"""
        if self._active_cycle is None:
            logger.warning("No active cycle to complete")
            return None

        self._active_cycle.mark_completed()
        completed = self._active_cycle
        self._active_cycle = None

        logger.info(
            f"Cycle #{completed.cycle_number} completed: "
            f"{completed.total_mutations} mutations, "
            f"{completed.genome_count} genomes"
        )
        return completed

    def fail_cycle(self, error: str) -> CycleRecord | None:
        """标记当前活跃循环为失败。"""
        if self._active_cycle is None:
            logger.warning("No active cycle to fail")
            return None

        self._active_cycle.mark_failed(error)
        failed = self._active_cycle
        self._active_cycle = None

        logger.error(f"Cycle #{failed.cycle_number} failed: {error}")
        return failed

    # ── Query ───────────────────────────────────────────

    def get_cycle(self, cycle_id: str) -> CycleRecord | None:
        """按 ID 查找循环。"""
        for cycle in self._cycles:
            if cycle.cycle_id == cycle_id:
                return cycle
        return None

    def get_cycle_by_number(self, cycle_number: int) -> CycleRecord | None:
        """按序号查找循环。"""
        for cycle in self._cycles:
            if cycle.cycle_number == cycle_number:
                return cycle
        return None

    def get_active_cycle(self) -> CycleRecord | None:
        """获取当前活跃循环。"""
        return self._active_cycle

    def get_history(self) -> list[CycleRecord]:
        """获取所有已完成的循环历史。"""
        return [c for c in self._cycles if c.is_completed or c.is_failed]

    def get_all_cycles(self) -> list[CycleRecord]:
        """获取所有循环记录。"""
        return list(self._cycles)

    def get_recent_results(self, n: int = 5) -> list[CycleResult]:
        """获取最近 N 个循环的结果摘要。"""
        completed = self.get_history()
        recent = completed[-n:] if len(completed) > n else completed
        return [CycleResult.from_record(c) for c in recent]

    # ── Stats ───────────────────────────────────────────

    @property
    def total_cycles(self) -> int:
        return self._total_cycles

    @property
    def completed_count(self) -> int:
        return sum(1 for c in self._cycles if c.is_completed)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self._cycles if c.is_failed)

    @property
    def total_mutations(self) -> int:
        return sum(c.total_mutations for c in self._cycles)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_cycles": self._total_cycles,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "total_mutations": self.total_mutations,
            "active_cycle": self._active_cycle.cycle_id if self._active_cycle else None,
            "history_summary": [
                CycleResult.from_record(c).to_dict() if hasattr(CycleResult, "to_dict") else str(c)
                for c in self.get_history()[-5:]
            ],
        }

    def __repr__(self) -> str:
        return (
            f"CycleManager(total={self._total_cycles}, "
            f"completed={self.completed_count}, "
            f"failed={self.failed_count})"
        )