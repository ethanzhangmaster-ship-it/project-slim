from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class BudgetStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


@dataclass
class BudgetAllocation:
    allocation_id: str
    category: str
    budget_amount: float
    spent_amount: float = 0.0
    daily_limit: float = 0.0
    weekly_limit: float = 0.0
    monthly_limit: float = 0.0
    warning_threshold: float = 0.8
    critical_threshold: float = 0.95
    auto_scale_enabled: bool = False
    max_scale_multiplier: float = 2.0
    roas_threshold: float = 1.5


@dataclass
class BudgetChangeRequest:
    request_id: str
    category: str
    current_budget: float
    requested_budget: float
    change_reason: str
    roi_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)


class BudgetGuard:
    def __init__(self, total_budget: float = 100000.0):
        self.total_budget = total_budget
        self.total_spent = 0.0
        self._allocations: Dict[str, BudgetAllocation] = {}
        self._change_history: List[BudgetChangeRequest] = []
        self._daily_spend: Dict[str, float] = {}

    def allocate(
        self,
        category: str,
        amount: float,
        daily_limit: float = None,
        warning_threshold: float = 0.8,
        auto_scale: bool = False,
    ) -> BudgetAllocation:
        allocation_id = f"budget_{hash(category + str(datetime.now())) % 10000:04d}"

        if daily_limit is None:
            daily_limit = amount / 30

        allocation = BudgetAllocation(
            allocation_id=allocation_id,
            category=category,
            budget_amount=amount,
            daily_limit=daily_limit,
            weekly_limit=daily_limit * 7,
            monthly_limit=amount,
            warning_threshold=warning_threshold,
            auto_scale_enabled=auto_scale,
        )

        self._allocations[category] = allocation
        return allocation

    def record_spend(self, category: str, amount: float, date_str: str = None) -> BudgetStatus:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        allocation = self._allocations.get(category)
        if not allocation:
            allocation = self.allocate(category, amount * 10)

        allocation.spent_amount += amount
        self.total_spent += amount

        if date_str not in self._daily_spend:
            self._daily_spend[date_str] = 0
        self._daily_spend[date_str] += amount

        return self.get_budget_status(category)

    def get_budget_status(self, category: str) -> BudgetStatus:
        allocation = self._allocations.get(category)
        if not allocation:
            return BudgetStatus.OK

        utilization = allocation.spent_amount / allocation.budget_amount if allocation.budget_amount > 0 else 0

        if utilization >= 1.0:
            return BudgetStatus.EXCEEDED
        elif utilization >= allocation.critical_threshold:
            return BudgetStatus.CRITICAL
        elif utilization >= allocation.warning_threshold:
            return BudgetStatus.WARNING
        else:
            return BudgetStatus.OK

    def can_spend(self, category: str, amount: float) -> bool:
        allocation = self._allocations.get(category)
        if not allocation:
            return False

        if allocation.spent_amount + amount > allocation.budget_amount:
            return False

        today = datetime.now().strftime("%Y-%m-%d")
        daily_spend = self._daily_spend.get(today, 0)
        if daily_spend + amount > allocation.daily_limit:
            return False

        return True

    def request_budget_increase(
        self,
        category: str,
        new_budget: float,
        reason: str,
        roi_data: Dict[str, Any] = None,
    ) -> BudgetChangeRequest:
        allocation = self._allocations.get(category)
        if not allocation:
            allocation = self.allocate(category, new_budget * 0.5)

        request = BudgetChangeRequest(
            request_id=f"budget_req_{hash(category + str(datetime.now())) % 10000:04d}",
            category=category,
            current_budget=allocation.budget_amount,
            requested_budget=new_budget,
            change_reason=reason,
            roi_data=roi_data or {},
        )

        roas = (roi_data or {}).get("roas", 0)
        payback_days = (roi_data or {}).get("payback_days", 999)

        if allocation.auto_scale_enabled and roas >= allocation.roas_threshold and payback_days <= 180:
            max_budget = allocation.budget_amount * allocation.max_scale_multiplier
            if new_budget <= max_budget:
                allocation.budget_amount = new_budget
                allocation.daily_limit = new_budget / 30
                request.status = "auto_approved"

        self._change_history.append(request)
        return request

    def approve_increase(self, request_id: str) -> bool:
        for req in self._change_history:
            if req.request_id == request_id and req.status == "pending":
                allocation = self._allocations.get(req.category)
                if allocation:
                    allocation.budget_amount = req.requested_budget
                    allocation.daily_limit = req.requested_budget / 30
                req.status = "approved"
                return True
        return False

    def get_daily_spend(self, date_str: str = None) -> float:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        return self._daily_spend.get(date_str, 0)

    def get_overall_status(self) -> Dict[str, Any]:
        overall_utilization = self.total_spent / self.total_budget if self.total_budget > 0 else 0
        categories = {}
        for cat, alloc in self._allocations.items():
            categories[cat] = {
                "budget": alloc.budget_amount,
                "spent": alloc.spent_amount,
                "utilization": round(alloc.spent_amount / alloc.budget_amount * 100, 2) if alloc.budget_amount > 0 else 0,
                "status": self.get_budget_status(cat).value,
            }

        return {
            "total_budget": self.total_budget,
            "total_spent": self.total_spent,
            "utilization_percent": round(overall_utilization * 100, 2),
            "daily_spend": self.get_daily_spend(),
            "categories": categories,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_allocations": len(self._allocations),
            "total_budget": self.total_budget,
            "total_spent": self.total_spent,
            "budget_changes": len(self._change_history),
            "auto_approved_changes": sum(1 for r in self._change_history if r.status == "auto_approved"),
        }
