"""E11.7.2 — Budget Tracker。

实时统计预算消耗，支持每日自动重置。

职责：
  - 记录任务消耗（record_task）
  - 记录突变消耗（record_mutation）
  - 记录生成消耗（record_generation）
  - 记录花费（record_cost）
  - 查询当前消耗（usage）
  - 每日自动重置（daily rollover）
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .models import BudgetUsage

logger = logging.getLogger(__name__)


class BudgetTracker:
    """预算消耗追踪器。

    Attributes:
        record_count: 记录次数
    """

    def __init__(self) -> None:
        self._usage = BudgetUsage()
        self._record_count: int = 0
        self._total_cost: float = 0.0
        self._total_tasks: int = 0

    # ── 记录消耗 ──────────────────────────────────────────

    def record_task(self, count: int = 1) -> None:
        """记录任务消耗。"""
        self._ensure_daily_reset()
        self._usage.tasks_used += count
        self._total_tasks += count
        self._record_count += 1

    def record_mutation(self, count: int = 1) -> None:
        """记录突变消耗。"""
        self._ensure_daily_reset()
        self._usage.mutations_used += count
        self._record_count += 1

    def record_generation(self, count: int = 1) -> None:
        """记录生成消耗。"""
        self._ensure_daily_reset()
        self._usage.generations_used += count
        self._record_count += 1

    def record_cost(self, cost: float) -> None:
        """记录花费。"""
        self._ensure_daily_reset()
        self._usage.cost_used += cost
        self._total_cost += cost
        self._record_count += 1

    def record_active_increment(self, count: int = 1) -> None:
        """活跃任务数 +1。"""
        self._usage.active_tasks += count

    def record_active_decrement(self, count: int = 1) -> None:
        """活跃任务数 -1（不低于 0）。"""
        self._usage.active_tasks = max(0, self._usage.active_tasks - count)

    def record_task_complete(self, cost: float = 0.0) -> None:
        """任务完成：记录花费 + 减少活跃任务。"""
        self.record_cost(cost)
        self.record_active_decrement()

    # ── 查询 ──────────────────────────────────────────────

    def usage(self) -> BudgetUsage:
        """获取当前消耗统计。"""
        self._ensure_daily_reset()
        return self._usage

    def get_active_tasks(self) -> int:
        return self._usage.active_tasks

    def get_tasks_used(self) -> int:
        self._ensure_daily_reset()
        return self._usage.tasks_used

    def get_cost_used(self) -> float:
        self._ensure_daily_reset()
        return self._usage.cost_used

    def get_total_cost(self) -> float:
        """获取累计总花费（不清零）。"""
        return self._total_cost

    def get_total_tasks(self) -> int:
        """获取累计总任务数（不清零）。"""
        return self._total_tasks

    # ── 每日重置 ──────────────────────────────────────────

    def _ensure_daily_reset(self) -> None:
        """检查是否需要每日重置。"""
        if self._usage.is_new_day():
            logger.info(
                f"Daily budget reset: {self._usage.date} → {date.today().isoformat()}"
            )
            self._daily_reset()

    def _daily_reset(self) -> None:
        """重置每日消耗。"""
        self._usage = BudgetUsage()

    def force_reset(self) -> None:
        """强制重置每日消耗。"""
        self._daily_reset()

    # ── Stats ─────────────────────────────────────────────

    @property
    def record_count(self) -> int:
        return self._record_count

    def get_stats(self) -> dict[str, Any]:
        self._ensure_daily_reset()
        return {
            "date": self._usage.date,
            "tasks_used": self._usage.tasks_used,
            "mutations_used": self._usage.mutations_used,
            "generations_used": self._usage.generations_used,
            "cost_used": self._usage.cost_used,
            "active_tasks": self._usage.active_tasks,
            "total_cost": self._total_cost,
            "total_tasks": self._total_tasks,
            "record_count": self._record_count,
        }

    def reset(self) -> None:
        """完全重置（包括累计统计）。"""
        self._usage = BudgetUsage()
        self._record_count = 0
        self._total_cost = 0.0
        self._total_tasks = 0

    def __repr__(self) -> str:
        return (
            f"BudgetTracker(date={self._usage.date}, "
            f"tasks={self._usage.tasks_used}, "
            f"cost=${self._usage.cost_used:.2f})"
        )