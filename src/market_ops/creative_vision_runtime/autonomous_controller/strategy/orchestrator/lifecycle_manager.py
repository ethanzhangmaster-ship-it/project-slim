"""E11.9 — Lifecycle Manager。

职责：进化周期状态管理。

功能：
  - 跟踪活跃周期
  - 防止重复进化
  - 管理状态转换
  - 限制并发周期数
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionCycle,
    EvolutionCycleStatus,
)

logger = logging.getLogger(__name__)

# 有效的状态转换
VALID_TRANSITIONS: dict[EvolutionCycleStatus, set[EvolutionCycleStatus]] = {
    EvolutionCycleStatus.IDLE: {
        EvolutionCycleStatus.DETECTING,
    },
    EvolutionCycleStatus.DETECTING: {
        EvolutionCycleStatus.PLANNING,
        EvolutionCycleStatus.CANCELLED,
    },
    EvolutionCycleStatus.PLANNING: {
        EvolutionCycleStatus.EXECUTING,
        EvolutionCycleStatus.FAILED,
    },
    EvolutionCycleStatus.EXECUTING: {
        EvolutionCycleStatus.EVALUATING,
        EvolutionCycleStatus.FAILED,
    },
    EvolutionCycleStatus.EVALUATING: {
        EvolutionCycleStatus.LEARNING,
        EvolutionCycleStatus.FAILED,
    },
    EvolutionCycleStatus.LEARNING: {
        EvolutionCycleStatus.COMPLETED,
        EvolutionCycleStatus.FAILED,
    },
    EvolutionCycleStatus.COMPLETED: set(),
    EvolutionCycleStatus.FAILED: set(),
    EvolutionCycleStatus.CANCELLED: set(),
}

MAX_ACTIVE_CYCLES = 3


class LifecycleManager:
    """生命周期管理器。

    Attributes:
        max_active:       最大活跃周期数
        transitions:      有效状态转换表
        active_cycles:    当前活跃周期
        completed_cycles: 已完成周期
    """

    def __init__(
        self,
        max_active: int = MAX_ACTIVE_CYCLES,
        transitions: dict | None = None,
    ) -> None:
        self._max_active = max_active
        self._transitions = transitions or VALID_TRANSITIONS
        self._active_cycles: list[EvolutionCycle] = []
        self._completed_cycles: list[EvolutionCycle] = []

    # ── 状态转换 ─────────────────────────────────────────

    def can_transition(
        self,
        cycle: EvolutionCycle,
        target: EvolutionCycleStatus,
    ) -> bool:
        """检查是否可以转换到目标状态。"""
        valid = self._transitions.get(cycle.status, set())
        return target in valid

    def transition(
        self,
        cycle: EvolutionCycle,
        target: EvolutionCycleStatus,
    ) -> bool:
        """执行状态转换。

        Returns:
            是否转换成功
        """
        if not self.can_transition(cycle, target):
            logger.warning(
                f"Cannot transition {cycle.cycle_id} from "
                f"{cycle.status.value} to {target.value}"
            )
            return False

        old_status = cycle.status
        cycle.status = target

        logger.info(
            f"Cycle {cycle.cycle_id}: {old_status.value} → {target.value}"
        )

        # 如果是终态，移出活跃列表
        if cycle.is_terminal:
            self._move_to_completed(cycle)

        return True

    # ── 周期管理 ─────────────────────────────────────────

    def register_cycle(self, cycle: EvolutionCycle) -> bool:
        """注册新周期。

        Returns:
            是否注册成功（超过最大活跃数则失败）
        """
        if len(self._active_cycles) >= self._max_active:
            logger.warning(
                f"Max active cycles ({self._max_active}) reached, "
                f"cannot register {cycle.cycle_id}"
            )
            return False

        self._active_cycles.append(cycle)
        return True

    def get_active_cycle_count(self) -> int:
        return len(self._active_cycles)

    def get_active_cycles(self) -> list[EvolutionCycle]:
        return list(self._active_cycles)

    def get_completed_cycles(self) -> list[EvolutionCycle]:
        return list(self._completed_cycles)

    def get_total_cycles(self) -> int:
        return len(self._active_cycles) + len(self._completed_cycles)

    def can_start_new(self) -> bool:
        """是否可以启动新周期。"""
        return len(self._active_cycles) < self._max_active

    def is_duplicate_opportunity(
        self, opportunity_type: str, time_window_seconds: float = 3600
    ) -> bool:
        """检查是否有重复机会（防止短时间内重复触发）。"""
        import time
        now = time.time()
        for cycle in self._active_cycles:
            created = cycle.created_at
            # 简单检查：同类型在活跃周期中
            if cycle.trigger_reason == opportunity_type:
                return True
        return False

    # ── 内部方法 ─────────────────────────────────────────

    def _move_to_completed(self, cycle: EvolutionCycle) -> None:
        """将周期移入完成列表。"""
        if cycle in self._active_cycles:
            self._active_cycles.remove(cycle)
        self._completed_cycles.append(cycle)

    # ── 统计 ────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        completed = [c for c in self._completed_cycles
                     if c.status == EvolutionCycleStatus.COMPLETED]
        failed = [c for c in self._completed_cycles
                  if c.status == EvolutionCycleStatus.FAILED]

        return {
            "active_cycles": len(self._active_cycles),
            "completed_cycles": len(completed),
            "failed_cycles": len(failed),
            "total_cycles": self.get_total_cycles(),
            "success_rate": (
                len(completed) / max(1, len(completed) + len(failed))
            ),
        }

    def __repr__(self) -> str:
        return (
            f"LifecycleManager("
            f"active={len(self._active_cycles)}, "
            f"completed={len(self._completed_cycles)})"
        )