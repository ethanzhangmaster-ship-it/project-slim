"""Budget Manager"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class BudgetRecord:
    date: str
    platform: str
    task_id: str
    cost: float


class BudgetManager:
    """预算管理器 - 追踪每日/每月预算使用"""

    def __init__(self, daily_budget: float = 100.0, monthly_budget: float = 2000.0):
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self._records: Dict[str, list] = {}

    def add_expense(self, platform: str, task_id: str, cost: float):
        today = date.today().isoformat()
        if today not in self._records:
            self._records[today] = []
        self._records[today].append(BudgetRecord(
            date=today,
            platform=platform,
            task_id=task_id,
            cost=cost,
        ))

    def get_daily_spent(self, target_date: str = None) -> float:
        if target_date is None:
            target_date = date.today().isoformat()
        records = self._records.get(target_date, [])
        return sum(r.cost for r in records)

    def get_daily_remaining(self, target_date: str = None) -> float:
        spent = self.get_daily_spent(target_date)
        return max(0, self.daily_budget - spent)

    def get_daily_usage_percent(self, target_date: str = None) -> float:
        if self.daily_budget == 0:
            return 0
        return self.get_daily_spent(target_date) / self.daily_budget * 100

    def can_afford(self, cost: float, target_date: str = None) -> bool:
        remaining = self.get_daily_remaining(target_date)
        return remaining >= cost

    def get_platform_cost(self, platform: str, target_date: str = None) -> float:
        if target_date is None:
            target_date = date.today().isoformat()
        records = self._records.get(target_date, [])
        return sum(r.cost for r in records if r.platform == platform)

    def get_summary(self, target_date: str = None) -> Dict[str, Any]:
        if target_date is None:
            target_date = date.today().isoformat()
        spent = self.get_daily_spent(target_date)
        remaining = self.get_daily_remaining(target_date)
        records = self._records.get(target_date, [])

        platform_breakdown = {}
        for r in records:
            if r.platform not in platform_breakdown:
                platform_breakdown[r.platform] = 0
            platform_breakdown[r.platform] += r.cost

        return {
            "date": target_date,
            "daily_budget": self.daily_budget,
            "spent": round(spent, 2),
            "remaining": round(remaining, 2),
            "usage_percent": round(spent / self.daily_budget * 100, 1) if self.daily_budget else 0,
            "task_count": len(records),
            "platform_breakdown": {k: round(v, 2) for k, v in platform_breakdown.items()},
        }
