"""E11.7.2 — Budget Policy。

预算规则检查：根据 EvolutionBudget 和 BudgetUsage 判断是否允许执行。

检查规则：
  1. Locked 级别 → 一律拒绝
  2. 任务数超限 → 拒绝
  3. 突变数超限 → 拒绝
  4. 生成数超限 → 拒绝
  5. 花费超限 → 拒绝
  6. 并发超限 → 拒绝
  7. 全部通过 → 允许
"""

from __future__ import annotations

import logging
from typing import Any

from .models import EvolutionBudget, BudgetUsage, BudgetDecision, BudgetLevel

logger = logging.getLogger(__name__)


class BudgetPolicy:
    """预算策略检查器。

    根据预算定义和当前消耗，判断任务是否允许执行。

    Attributes:
        check_count: 检查次数
        deny_count:  拒绝次数
    """

    def __init__(self) -> None:
        self._check_count: int = 0
        self._deny_count: int = 0

    def check(
        self,
        budget: EvolutionBudget,
        usage: BudgetUsage,
    ) -> BudgetDecision:
        """检查预算是否允许执行。

        Args:
            budget: 预算定义
            usage:  当前消耗

        Returns:
            BudgetDecision
        """
        self._check_count += 1

        remaining_tasks = budget.daily_task_limit - usage.tasks_used
        remaining_mutations = budget.daily_mutation_limit - usage.mutations_used
        remaining_cost = budget.max_daily_cost - usage.cost_used
        remaining_slots = budget.max_parallel_tasks - usage.active_tasks

        # 1. Locked
        if budget.level == BudgetLevel.LOCKED:
            return self._deny(
                "Budget is locked — no evolution allowed",
                remaining_tasks, remaining_mutations, remaining_cost, remaining_slots,
            )

        # 2. Task limit
        if remaining_tasks <= 0:
            return self._deny(
                f"Daily task limit reached ({budget.daily_task_limit})",
                remaining_tasks, remaining_mutations, remaining_cost, remaining_slots,
            )

        # 3. Mutation limit
        if remaining_mutations <= 0:
            return self._deny(
                f"Daily mutation limit reached ({budget.daily_mutation_limit})",
                remaining_tasks, remaining_mutations, remaining_cost, remaining_slots,
            )

        # 4. Generation limit
        remaining_generations = budget.daily_generation_limit - usage.generations_used
        if remaining_generations <= 0:
            return self._deny(
                f"Daily generation limit reached ({budget.daily_generation_limit})",
                remaining_tasks, remaining_mutations, remaining_cost, remaining_slots,
            )

        # 5. Cost limit
        if remaining_cost <= 0:
            return self._deny(
                f"Daily cost limit reached (${budget.max_daily_cost:.2f})",
                remaining_tasks, remaining_mutations, remaining_cost, remaining_slots,
            )

        # 6. Concurrency limit
        if remaining_slots <= 0:
            return self._deny(
                f"Max parallel tasks reached ({budget.max_parallel_tasks})",
                remaining_tasks, remaining_mutations, remaining_cost, remaining_slots,
            )

        # 7. Allowed
        return BudgetDecision(
            allowed=True,
            remaining_tasks=remaining_tasks - 1,  # 预扣
            remaining_mutations=remaining_mutations,
            remaining_cost=remaining_cost,
            remaining_slots=remaining_slots - 1,  # 预扣
        )

    def check_batch(
        self,
        budget: EvolutionBudget,
        usage: BudgetUsage,
        count: int = 1,
    ) -> BudgetDecision:
        """批量检查：检查能否执行 count 个任务。

        Args:
            budget: 预算定义
            usage:  当前消耗
            count:  计划执行的任务数

        Returns:
            BudgetDecision
        """
        self._check_count += 1

        remaining_tasks = budget.daily_task_limit - usage.tasks_used
        remaining_slots = budget.max_parallel_tasks - usage.active_tasks

        if remaining_tasks < count:
            return self._deny(
                f"Not enough task quota: need {count}, have {remaining_tasks}",
                remaining_tasks, 0, 0, remaining_slots,
            )

        if remaining_slots < count:
            return self._deny(
                f"Not enough parallel slots: need {count}, have {remaining_slots}",
                remaining_tasks, 0, 0, remaining_slots,
            )

        return self.check(budget, usage)

    # ── 内部 ──────────────────────────────────────────────

    def _deny(
        self,
        reason: str,
        remaining_tasks: int,
        remaining_mutations: int,
        remaining_cost: float,
        remaining_slots: int,
    ) -> BudgetDecision:
        self._deny_count += 1
        return BudgetDecision(
            allowed=False,
            reason=reason,
            remaining_tasks=remaining_tasks,
            remaining_mutations=remaining_mutations,
            remaining_cost=remaining_cost,
            remaining_slots=remaining_slots,
        )

    # ── Stats ─────────────────────────────────────────────

    @property
    def check_count(self) -> int:
        return self._check_count

    @property
    def deny_count(self) -> int:
        return self._deny_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "check_count": self._check_count,
            "deny_count": self._deny_count,
            "allow_rate": (
                1 - self._deny_count / self._check_count
                if self._check_count > 0
                else 1.0
            ),
        }

    def reset(self) -> None:
        self._check_count = 0
        self._deny_count = 0

    def __repr__(self) -> str:
        return (
            f"BudgetPolicy(checks={self._check_count}, "
            f"denies={self._deny_count})"
        )