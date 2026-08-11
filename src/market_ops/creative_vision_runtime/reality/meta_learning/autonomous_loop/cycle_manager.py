"""E12.5.5 — Cycle Manager。

管理 Meta Learning Cycle 的生命周期。

状态机:
  CREATED → COLLECTING → MINING → OPTIMIZING → EXECUTING → LEARNING → COMPLETED

支持:
  - 状态转换验证
  - 失败恢复
  - 多周期管理
  - 周期历史记录
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import MetaCycleStatus, MetaLearningCycle, TriggerReason


# 合法的状态转换
_VALID_TRANSITIONS: dict[MetaCycleStatus, set[MetaCycleStatus]] = {
    MetaCycleStatus.CREATED: {MetaCycleStatus.COLLECTING, MetaCycleStatus.FAILED},
    MetaCycleStatus.COLLECTING: {MetaCycleStatus.MINING, MetaCycleStatus.FAILED},
    MetaCycleStatus.MINING: {MetaCycleStatus.OPTIMIZING, MetaCycleStatus.FAILED},
    MetaCycleStatus.OPTIMIZING: {MetaCycleStatus.EXECUTING, MetaCycleStatus.FAILED},
    MetaCycleStatus.EXECUTING: {MetaCycleStatus.LEARNING, MetaCycleStatus.FAILED},
    MetaCycleStatus.LEARNING: {MetaCycleStatus.COMPLETED, MetaCycleStatus.FAILED},
    MetaCycleStatus.COMPLETED: set(),
    MetaCycleStatus.FAILED: set(),
}


class CycleManager:
    """学习周期管理器。

    Usage:
        >>> manager = CycleManager()
        >>> cycle = manager.create_cycle("p04")
        >>> manager.advance(cycle)  # CREATED → COLLECTING
        >>> manager.complete(cycle, "Learning successful")
    """

    def __init__(self) -> None:
        self._cycles: dict[str, MetaLearningCycle] = {}
        self._history: list[MetaLearningCycle] = []
        self._cycle_counter: int = 0

    # ── Create ─────────────────────────────────────────────

    def create_cycle(
        self,
        product_id: str,
        trigger_reason: TriggerReason = TriggerReason.SCHEDULED,
    ) -> MetaLearningCycle:
        """创建新的学习周期。

        Args:
            product_id:     产品 ID
            trigger_reason: 触发原因

        Returns:
            MetaLearningCycle
        """
        self._cycle_counter += 1
        cycle = MetaLearningCycle(
            product_id=product_id,
            trigger_reason=trigger_reason,
            cycle_number=self._cycle_counter,
        )
        self._cycles[cycle.cycle_id] = cycle
        return cycle

    # ── Advance ────────────────────────────────────────────

    def advance(self, cycle: MetaLearningCycle) -> MetaLearningCycle:
        """推进周期到下一状态。

        Args:
            cycle: 当前周期

        Returns:
            更新后的周期

        Raises:
            ValueError: 非法状态转换
        """
        current = cycle.status
        next_states = _VALID_TRANSITIONS.get(current, set())

        if not next_states:
            if current == MetaCycleStatus.COMPLETED:
                raise ValueError(f"Cycle {cycle.cycle_id} already completed")
            if current == MetaCycleStatus.FAILED:
                raise ValueError(f"Cycle {cycle.cycle_id} already failed, cannot advance")
            raise ValueError(f"No valid transition from {current.value}")

        next_state = self._next_in_order(current, next_states)
        cycle.status = next_state
        return cycle

    def _next_in_order(
        self,
        current: MetaCycleStatus,
        valid: set[MetaCycleStatus],
    ) -> MetaCycleStatus:
        """按顺序选择下一个状态。"""
        order = [
            MetaCycleStatus.COLLECTING,
            MetaCycleStatus.MINING,
            MetaCycleStatus.OPTIMIZING,
            MetaCycleStatus.EXECUTING,
            MetaCycleStatus.LEARNING,
            MetaCycleStatus.COMPLETED,
        ]
        for s in order:
            if s in valid:
                return s
        return MetaCycleStatus.FAILED

    def advance_to(self, cycle: MetaLearningCycle, target: MetaCycleStatus) -> MetaLearningCycle:
        """推进到指定状态。

        Args:
            cycle:  当前周期
            target: 目标状态

        Returns:
            更新后的周期

        Raises:
            ValueError: 非法状态转换
        """
        valid = _VALID_TRANSITIONS.get(cycle.status, set())
        if target not in valid:
            raise ValueError(
                f"Cannot transition from {cycle.status.value} to {target.value}"
            )
        cycle.status = target
        return cycle

    # ── Complete / Fail ────────────────────────────────────

    def complete(self, cycle: MetaLearningCycle, summary: str = "") -> MetaLearningCycle:
        """标记周期完成。

        Args:
            cycle:   当前周期
            summary: 周期总结

        Returns:
            更新后的周期
        """
        if cycle.status not in (MetaCycleStatus.LEARNING, MetaCycleStatus.EXECUTING):
            # 允许提前完成（例如空数据）
            pass
        cycle.mark_completed(summary)
        self._archive(cycle)
        return cycle

    def fail(self, cycle: MetaLearningCycle, error: str) -> MetaLearningCycle:
        """标记周期失败。

        Args:
            cycle: 当前周期
            error: 错误信息

        Returns:
            更新后的周期
        """
        cycle.mark_failed(error)
        self._archive(cycle)
        return cycle

    def _archive(self, cycle: MetaLearningCycle) -> None:
        """归档周期。"""
        if cycle.cycle_id in self._cycles:
            del self._cycles[cycle.cycle_id]
        self._history.append(cycle)

    # ── Query ──────────────────────────────────────────────

    def get_cycle(self, cycle_id: str) -> MetaLearningCycle | None:
        """获取周期（活跃或历史）。"""
        if cycle_id in self._cycles:
            return self._cycles[cycle_id]
        for c in self._history:
            if c.cycle_id == cycle_id:
                return c
        return None

    def get_active_cycles(self) -> list[MetaLearningCycle]:
        """获取活跃周期。"""
        return [c for c in self._cycles.values() if c.is_active]

    def get_active_cycles_for_product(self, product_id: str) -> list[MetaLearningCycle]:
        """获取产品的活跃周期。"""
        return [
            c for c in self._cycles.values()
            if c.product_id == product_id and c.is_active
        ]

    def get_history(self, product_id: str = "") -> list[MetaLearningCycle]:
        """获取历史周期。

        Args:
            product_id: 产品 ID（空 = 全部）

        Returns:
            历史周期列表
        """
        if not product_id:
            return list(self._history)
        return [c for c in self._history if c.product_id == product_id]

    def get_last_completed(self, product_id: str) -> MetaLearningCycle | None:
        """获取最近完成的周期。"""
        completed = [
            c for c in self._history
            if c.product_id == product_id and c.is_successful
        ]
        if not completed:
            return None
        return max(completed, key=lambda c: c.end_time or datetime.min.replace(tzinfo=timezone.utc))

    # ── Stats ──────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        active = len(self._cycles)
        total = len(self._history) + active
        successful = sum(1 for c in self._history if c.is_successful)
        failed = sum(1 for c in self._history if c.status == MetaCycleStatus.FAILED)

        return {
            "total_cycles": total,
            "active_cycles": active,
            "completed_cycles": successful,
            "failed_cycles": failed,
            "history_count": len(self._history),
            "cycle_counter": self._cycle_counter,
        }

    def clear(self) -> None:
        """清空所有周期。"""
        self._cycles.clear()
        self._history.clear()
        self._cycle_counter = 0

    def __repr__(self) -> str:
        return f"CycleManager(active={len(self._cycles)}, history={len(self._history)})"