from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class Department(Enum):
    PRODUCT = "product"
    GROWTH = "growth"
    TECH = "tech"
    OPERATIONS = "operations"
    RND = "rnd"


@dataclass
class Budget:
    total_budget: float
    fiscal_year: int
    currency: str = "USD"

    def to_dict(self):
        return {
            "total_budget": self.total_budget,
            "fiscal_year": self.fiscal_year,
            "currency": self.currency,
        }


@dataclass
class BudgetPlan:
    department: Department
    allocated: float
    spent: float
    remaining: float

    def to_dict(self):
        return {
            "department": self.department.value,
            "allocated": self.allocated,
            "spent": self.spent,
            "remaining": self.remaining,
        }


@dataclass
class BudgetVariance:
    department: Department
    budgeted: float
    actual: float
    variance: float
    variance_percent: float

    def to_dict(self):
        return {
            "department": self.department.value,
            "budgeted": self.budgeted,
            "actual": self.actual,
            "variance": self.variance,
            "variance_percent": self.variance_percent,
        }


class BudgetStrategy:
    def __init__(self):
        self._budget: Optional[Budget] = None
        self._plans: Dict[Department, BudgetPlan] = {}
        self._variances: List[BudgetVariance] = []

    def set_budget(self, budget: Budget) -> None:
        self._budget = budget

    def get_budget_plan(self) -> Dict:
        return {
            "budget": self._budget.to_dict() if self._budget else None,
            "plans": {k.value: v.to_dict() for k, v in self._plans.items()},
        }

    def allocate_department_budget(self, department: Department, amount: float) -> BudgetPlan:
        plan = BudgetPlan(
            department=department,
            allocated=amount,
            spent=0.0,
            remaining=amount,
        )
        self._plans[department] = plan
        return plan

    def get_budget_variance(self) -> List[BudgetVariance]:
        return self._variances

    def get_budget_recommendations(self) -> List[Dict]:
        recommendations = []
        for dept, plan in self._plans.items():
            if plan.remaining < plan.allocated * 0.2:
                recommendations.append({
                    "department": dept.value,
                    "recommendation": "increase_budget",
                    "reason": "remaining below 20%",
                })
        return recommendations

    def get_stats(self) -> Dict:
        total_allocated = sum(p.allocated for p in self._plans.values())
        total_spent = sum(p.spent for p in self._plans.values())
        return {
            "total_budget": self._budget.total_budget if self._budget else 0.0,
            "total_allocated": total_allocated,
            "total_spent": total_spent,
            "departments": len(self._plans),
        }
