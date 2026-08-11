"""E11.7.2 — Evolution Budget Manager。

统一入口：预算检查 + 消耗记录。

职责：
  - check(): 检查任务是否可以执行
  - consume(): 记录任务消耗
  - complete(): 任务完成，扣减活跃数
  - 预算级别切换
  - 每日自动重置
"""

from __future__ import annotations

import logging
from typing import Any

from .models import EvolutionBudget, BudgetUsage, BudgetDecision, BudgetLevel
from .budget_tracker import BudgetTracker
from .budget_policy import BudgetPolicy

logger = logging.getLogger(__name__)


class EvolutionBudgetManager:
    """进化预算管理器。

    统一入口：预算检查 + 消耗记录。

    Attributes:
        budget:    预算定义
        tracker:   BudgetTracker
        policy:    BudgetPolicy
    """

    def __init__(
        self,
        budget: EvolutionBudget | None = None,
        tracker: BudgetTracker | None = None,
        policy: BudgetPolicy | None = None,
    ) -> None:
        self._budget = budget or EvolutionBudget.normal()
        self._tracker = tracker or BudgetTracker()
        self._policy = policy or BudgetPolicy()

    # ── 核心接口：check ──────────────────────────────────

    def check(self) -> BudgetDecision:
        """检查当前预算是否允许执行新任务。

        Returns:
            BudgetDecision
        """
        return self._policy.check(self._budget, self._tracker.usage())

    def check_batch(self, count: int = 1) -> BudgetDecision:
        """批量检查。"""
        return self._policy.check_batch(self._budget, self._tracker.usage(), count)

    def can_execute(self) -> bool:
        """是否可以执行新任务。"""
        return self.check().allowed

    # ── 核心接口：consume ────────────────────────────────

    def consume(
        self,
        task_count: int = 1,
        mutation_count: int = 0,
        generation_count: int = 0,
        cost: float = 0.0,
    ) -> BudgetDecision:
        """消耗预算。

        先检查，如果允许则记录消耗。

        Args:
            task_count:       任务数
            mutation_count:   突变数
            generation_count: 生成数
            cost:             花费

        Returns:
            BudgetDecision（如果 allowed=True 则已记录消耗）
        """
        decision = self.check()
        if not decision.allowed:
            return decision

        # 记录消耗
        self._tracker.record_task(task_count)
        if mutation_count > 0:
            self._tracker.record_mutation(mutation_count)
        if generation_count > 0:
            self._tracker.record_generation(generation_count)
        if cost > 0:
            self._tracker.record_cost(cost)
        self._tracker.record_active_increment(task_count)

        return decision

    def complete(
        self,
        cost: float = 0.0,
    ) -> None:
        """任务完成。"""
        self._tracker.record_task_complete(cost)

    def complete_batch(
        self,
        count: int = 1,
        cost: float = 0.0,
    ) -> None:
        """批量完成。"""
        for _ in range(count):
            self._tracker.record_task_complete(cost / count if count > 0 else 0.0)

    # ── 预算管理 ──────────────────────────────────────────

    def set_budget(self, budget: EvolutionBudget) -> None:
        """切换预算。"""
        self._budget = budget
        logger.info(f"Budget switched to {budget.level.value}")

    def set_level(self, level: BudgetLevel) -> None:
        """切换预算级别。"""
        level_map = {
            BudgetLevel.LIBERAL: EvolutionBudget.liberal,
            BudgetLevel.NORMAL: EvolutionBudget.normal,
            BudgetLevel.CONSERVATIVE: EvolutionBudget.conservative,
            BudgetLevel.LOCKED: EvolutionBudget.locked,
        }
        factory = level_map.get(level, EvolutionBudget.normal)
        self._budget = factory()
        logger.info(f"Budget level set to {level.value}")

    def lock(self) -> None:
        """锁定预算（禁止一切进化）。"""
        self.set_level(BudgetLevel.LOCKED)

    def unlock(self) -> None:
        """解锁预算（恢复为 NORMAL）。"""
        self.set_level(BudgetLevel.NORMAL)

    # ── 查询 ──────────────────────────────────────────────

    def usage(self) -> BudgetUsage:
        return self._tracker.usage()

    def get_budget(self) -> EvolutionBudget:
        return self._budget

    def get_remaining_tasks(self) -> int:
        return max(0, self._budget.daily_task_limit - self._tracker.get_tasks_used())

    def get_remaining_cost(self) -> float:
        return max(0.0, self._budget.max_daily_cost - self._tracker.get_cost_used())

    def get_remaining_slots(self) -> int:
        return max(
            0,
            self._budget.max_parallel_tasks - self._tracker.get_active_tasks(),
        )

    def get_utilization(self) -> float:
        """预算利用率（0.0-1.0）。"""
        if self._budget.daily_task_limit == 0:
            return 0.0
        return min(1.0, self._tracker.get_tasks_used() / self._budget.daily_task_limit)

    def get_cost_utilization(self) -> float:
        """花费利用率（0.0-1.0）。"""
        if self._budget.max_daily_cost == 0:
            return 0.0
        return min(1.0, self._tracker.get_cost_used() / self._budget.max_daily_cost)

    # ── Stats ─────────────────────────────────────────────

    @property
    def budget(self) -> EvolutionBudget:
        return self._budget

    def get_stats(self) -> dict[str, Any]:
        return {
            "budget": self._budget.to_dict(),
            "usage": self._tracker.usage().to_dict(),
            "policy": self._policy.get_stats(),
            "remaining_tasks": self.get_remaining_tasks(),
            "remaining_cost": self.get_remaining_cost(),
            "remaining_slots": self.get_remaining_slots(),
            "utilization": self.get_utilization(),
            "cost_utilization": self.get_cost_utilization(),
            "total_cost": self._tracker.get_total_cost(),
            "total_tasks": self._tracker.get_total_tasks(),
        }

    def reset(self) -> None:
        self._tracker.reset()
        self._policy.reset()

    def __repr__(self) -> str:
        return (
            f"EvolutionBudgetManager(level={self._budget.level.value}, "
            f"used={self._tracker.get_tasks_used()}/{self._budget.daily_task_limit}, "
            f"cost=${self._tracker.get_cost_used():.2f}/${self._budget.max_daily_cost:.2f})"
        )