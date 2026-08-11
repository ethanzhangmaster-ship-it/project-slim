"""E11.7.2 — Evolution Budget Models。

EvolutionBudget:  资源额度定义
BudgetUsage:      当前消耗统计
BudgetDecision:   预算检查结果
BudgetLevel:      预算级别
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetLevel(str, Enum):
    """预算级别。"""
    LIBERAL = "liberal"      # 宽松：几乎不限制
    NORMAL = "normal"        # 正常：标准限制
    CONSERVATIVE = "conservative"  # 保守：严格限制
    LOCKED = "locked"        # 锁定：禁止一切进化


@dataclass
class EvolutionBudget:
    """进化预算定义。

    Attributes:
        budget_id:              预算 ID
        daily_task_limit:       每日最大任务数
        daily_mutation_limit:   每日最大突变数
        daily_generation_limit: 每日最大生成数
        max_parallel_tasks:     最大并行任务数
        max_daily_cost:         每日最大花费
        level:                  预算级别
        metadata:               附加元数据
    """

    budget_id: str = ""
    daily_task_limit: int = 100
    daily_mutation_limit: int = 50
    daily_generation_limit: int = 30
    max_parallel_tasks: int = 5
    max_daily_cost: float = 100.0
    level: BudgetLevel = BudgetLevel.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.budget_id:
            self.budget_id = f"eb_{uuid.uuid4().hex[:12]}"

    @classmethod
    def liberal(cls) -> EvolutionBudget:
        """宽松预算。"""
        return cls(
            daily_task_limit=200,
            daily_mutation_limit=100,
            daily_generation_limit=60,
            max_parallel_tasks=10,
            max_daily_cost=500.0,
            level=BudgetLevel.LIBERAL,
        )

    @classmethod
    def normal(cls) -> EvolutionBudget:
        """正常预算。"""
        return cls(
            daily_task_limit=100,
            daily_mutation_limit=50,
            daily_generation_limit=30,
            max_parallel_tasks=5,
            max_daily_cost=100.0,
            level=BudgetLevel.NORMAL,
        )

    @classmethod
    def conservative(cls) -> EvolutionBudget:
        """保守预算。"""
        return cls(
            daily_task_limit=20,
            daily_mutation_limit=10,
            daily_generation_limit=5,
            max_parallel_tasks=2,
            max_daily_cost=20.0,
            level=BudgetLevel.CONSERVATIVE,
        )

    @classmethod
    def locked(cls) -> EvolutionBudget:
        """锁定预算（禁止一切进化）。"""
        return cls(
            daily_task_limit=0,
            daily_mutation_limit=0,
            daily_generation_limit=0,
            max_parallel_tasks=0,
            max_daily_cost=0.0,
            level=BudgetLevel.LOCKED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "daily_task_limit": self.daily_task_limit,
            "daily_mutation_limit": self.daily_mutation_limit,
            "daily_generation_limit": self.daily_generation_limit,
            "max_parallel_tasks": self.max_parallel_tasks,
            "max_daily_cost": self.max_daily_cost,
            "level": self.level.value,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionBudget({self.level.value}, "
            f"tasks={self.daily_task_limit}/day, "
            f"cost=${self.max_daily_cost}/day)"
        )


@dataclass
class BudgetUsage:
    """当前预算消耗统计。

    Attributes:
        date:              统计日期
        tasks_used:        已用任务数
        mutations_used:    已用突变数
        generations_used:  已用生成数
        cost_used:         已用花费
        active_tasks:      当前活跃任务数
    """

    date: str = ""
    tasks_used: int = 0
    mutations_used: int = 0
    generations_used: int = 0
    cost_used: float = 0.0
    active_tasks: int = 0

    def __post_init__(self) -> None:
        if not self.date:
            self.date = _today()

    def is_new_day(self) -> bool:
        """是否是新的一天（与当前日期不同）。"""
        return self.date != _today()

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "tasks_used": self.tasks_used,
            "mutations_used": self.mutations_used,
            "generations_used": self.generations_used,
            "cost_used": self.cost_used,
            "active_tasks": self.active_tasks,
        }

    def __repr__(self) -> str:
        return (
            f"BudgetUsage({self.date}, "
            f"tasks={self.tasks_used}, "
            f"mutations={self.mutations_used}, "
            f"cost=${self.cost_used:.2f})"
        )


@dataclass
class BudgetDecision:
    """预算检查结果。

    Attributes:
        allowed:           是否允许执行
        reason:            拒绝原因（allowed=False 时）
        remaining_tasks:   剩余任务配额
        remaining_mutations: 剩余突变配额
        remaining_cost:    剩余花费配额
        remaining_slots:   剩余并行槽位
    """

    allowed: bool = True
    reason: str = ""
    remaining_tasks: int = 0
    remaining_mutations: int = 0
    remaining_cost: float = 0.0
    remaining_slots: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "remaining_tasks": self.remaining_tasks,
            "remaining_mutations": self.remaining_mutations,
            "remaining_cost": self.remaining_cost,
            "remaining_slots": self.remaining_slots,
        }

    def __repr__(self) -> str:
        status = "ALLOWED" if self.allowed else f"DENIED: {self.reason}"
        return f"BudgetDecision({status})"