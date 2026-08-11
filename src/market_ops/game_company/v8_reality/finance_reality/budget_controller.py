from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class BudgetCategory(Enum):
    ADVERTISING = "advertising"
    OPERATIONS = "operations"
    DEVELOPMENT = "development"
    MARKETING = "marketing"
    SALES = "sales"
    ADMINISTRATION = "administration"
    OTHER = "other"


@dataclass
class Budget:
    category: BudgetCategory
    total_amount: float
    allocated_amount: float
    spent_amount: float
    remaining_amount: float
    start_date: datetime
    end_date: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "total_amount": self.total_amount,
            "allocated_amount": self.allocated_amount,
            "spent_amount": self.spent_amount,
            "remaining_amount": self.remaining_amount,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


@dataclass
class BudgetAllocation:
    category: BudgetCategory
    amount: float
    description: Optional[str] = None
    allocated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "amount": self.amount,
            "description": self.description,
            "allocated_at": self.allocated_at.isoformat() if self.allocated_at else None,
        }


class BudgetController:
    def __init__(self):
        self._budgets: Dict[str, Budget] = {}
        self._allocations: List[BudgetAllocation] = []

    def set_budget(self, category: str, amount: float, start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> Budget:
        try:
            category_enum = BudgetCategory(category)
        except ValueError:
            category_enum = BudgetCategory.OTHER

        start = start_date or datetime.now()
        end = end_date or (start + timedelta(days=30))

        budget = Budget(
            category=category_enum,
            total_amount=amount,
            allocated_amount=0.0,
            spent_amount=0.0,
            remaining_amount=amount,
            start_date=start,
            end_date=end,
        )
        self._budgets[category_enum.value] = budget
        return budget

    def get_budget(self, category: str) -> Optional[Budget]:
        try:
            category_enum = BudgetCategory(category)
        except ValueError:
            category_enum = BudgetCategory.OTHER
        return self._budgets.get(category_enum.value)

    def check_budget(self, category: str) -> Dict[str, Any]:
        budget = self.get_budget(category)
        if not budget:
            return {"status": "not_set", "category": category}

        utilization = budget.spent_amount / budget.total_amount * 100 if budget.total_amount > 0 else 0

        if utilization >= 100:
            status = "exceeded"
        elif utilization >= 90:
            status = "warning"
        elif utilization >= 70:
            status = "normal"
        else:
            status = "healthy"

        return {
            "status": status,
            "category": budget.category.value,
            "total_amount": budget.total_amount,
            "spent_amount": budget.spent_amount,
            "remaining_amount": budget.remaining_amount,
            "utilization_rate": round(utilization, 2),
        }

    def allocate_budget(self, category: str, amount: float, description: Optional[str] = None) -> BudgetAllocation:
        try:
            category_enum = BudgetCategory(category)
        except ValueError:
            category_enum = BudgetCategory.OTHER

        budget = self._budgets.get(category_enum.value)
        if budget and budget.allocated_amount + amount > budget.total_amount:
            raise ValueError(f"Allocation exceeds budget for {category}")

        allocation = BudgetAllocation(
            category=category_enum,
            amount=amount,
            description=description,
            allocated_at=datetime.now(),
        )
        self._allocations.append(allocation)

        if budget:
            budget.allocated_amount += amount
            budget.remaining_amount = budget.total_amount - budget.spent_amount

        return allocation

    def record_expense(self, category: str, amount: float) -> bool:
        budget = self.get_budget(category)
        if not budget:
            return False

        budget.spent_amount += amount
        budget.remaining_amount = budget.total_amount - budget.spent_amount
        return True

    def get_budget_summary(self) -> Dict[str, Any]:
        total_budget = sum(b.total_amount for b in self._budgets.values())
        total_spent = sum(b.spent_amount for b in self._budgets.values())
        total_remaining = sum(b.remaining_amount for b in self._budgets.values())
        total_allocated = sum(b.allocated_amount for b in self._budgets.values())

        by_category = {}
        for budget in self._budgets.values():
            by_category[budget.category.value] = {
                "total": budget.total_amount,
                "spent": budget.spent_amount,
                "remaining": budget.remaining_amount,
                "utilization": budget.spent_amount / budget.total_amount * 100 if budget.total_amount > 0 else 0,
            }

        return {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "total_remaining": total_remaining,
            "total_allocated": total_allocated,
            "overall_utilization": total_spent / total_budget * 100 if total_budget > 0 else 0,
            "by_category": by_category,
            "budget_count": len(self._budgets),
        }

    def get_all_budgets(self) -> List[Budget]:
        return list(self._budgets.values())

    def get_all_allocations(self) -> List[BudgetAllocation]:
        return list(self._allocations)