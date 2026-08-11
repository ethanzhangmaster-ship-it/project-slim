"""Budget Policy - 预算策略"""
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BudgetPolicy:
    daily_budget: float = 100.0
    weekly_budget: float = 500.0
    monthly_budget: float = 2000.0
    warning_threshold: float = 0.8
    cutoff_threshold: float = 0.95
    priority_rules: Dict[str, float] = field(default_factory=lambda: {
        "P0": 1.0,
        "P1": 0.5,
        "P2": 0.0,
    })


class BudgetPolicyManager:
    """预算策略管理器"""

    def __init__(self, policy: BudgetPolicy = None):
        self.policy = policy or BudgetPolicy()
        self._daily_spent: float = 0.0
        self._weekly_spent: float = 0.0
        self._monthly_spent: float = 0.0
        self._priority_budgets: Dict[str, float] = {}
        self._calculate_priority_budgets()

    def _calculate_priority_budgets(self):
        total = self.policy.daily_budget
        for priority, ratio in self.policy.priority_rules.items():
            self._priority_budgets[priority] = total * ratio

    def can_afford(self, estimated_cost: float, priority: str = "P1") -> bool:
        available = self._priority_budgets.get(priority, 0)
        used = self.get_priority_spent(priority)
        remaining = available - used
        return remaining >= estimated_cost

    def add_cost(self, cost: float, priority: str = "P1"):
        self._daily_spent += cost
        self._weekly_spent += cost
        self._monthly_spent += cost

    def get_daily_spent(self) -> float:
        return self._daily_spent

    def get_daily_remaining(self) -> float:
        return max(0, self.policy.daily_budget - self._daily_spent)

    def get_daily_usage_percent(self) -> float:
        if self.policy.daily_budget == 0:
            return 0
        return round(self._daily_spent / self.policy.daily_budget * 100, 1)

    def get_priority_spent(self, priority: str) -> float:
        return self._daily_spent * self.policy.priority_rules.get(priority, 0)

    def get_priority_remaining(self, priority: str) -> float:
        available = self._priority_budgets.get(priority, 0)
        used = self.get_priority_spent(priority)
        return max(0, available - used)

    def is_warning(self) -> bool:
        return self.get_daily_usage_percent() >= self.policy.warning_threshold * 100

    def is_cutoff(self) -> bool:
        return self.get_daily_usage_percent() >= self.policy.cutoff_threshold * 100

    def get_status(self) -> Dict[str, Any]:
        return {
            "daily_budget": self.policy.daily_budget,
            "daily_spent": round(self._daily_spent, 2),
            "daily_remaining": round(self.get_daily_remaining(), 2),
            "usage_percent": self.get_daily_usage_percent(),
            "warning": self.is_warning(),
            "cutoff": self.is_cutoff(),
            "priority_budgets": {k: round(v, 2) for k, v in self._priority_budgets.items()},
        }

    def reset_daily(self):
        self._daily_spent = 0.0

    def reset_weekly(self):
        self._weekly_spent = 0.0

    def reset_monthly(self):
        self._monthly_spent = 0.0