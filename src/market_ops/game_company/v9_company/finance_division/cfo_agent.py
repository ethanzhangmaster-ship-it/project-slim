from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List


class FinancialStatus(Enum):
    HEALTHY = "healthy"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CashPosition:
    total_cash: float
    reserved_cash: float
    available_cash: float
    currency: str = "USD"
    date: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "total_cash": self.total_cash,
            "reserved_cash": self.reserved_cash,
            "available_cash": self.available_cash,
            "currency": self.currency,
            "date": self.date,
        }


@dataclass
class FinancialHealth:
    status: FinancialStatus
    cash_ratio: float
    debt_ratio: float
    burn_rate: float
    score: int

    def to_dict(self):
        return {
            "status": self.status.value,
            "cash_ratio": self.cash_ratio,
            "debt_ratio": self.debt_ratio,
            "burn_rate": self.burn_rate,
            "score": self.score,
        }


@dataclass
class SpendingRequest:
    request_id: str
    amount: float
    department: str
    reason: str
    status: str = "pending"

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "amount": self.amount,
            "department": self.department,
            "reason": self.reason,
            "status": self.status,
        }


class CFOAgent:
    def __init__(self):
        self._cash = CashPosition(
            total_cash=5000000.0,
            reserved_cash=1000000.0,
            available_cash=4000000.0,
        )
        self._health = FinancialHealth(
            status=FinancialStatus.HEALTHY,
            cash_ratio=0.35,
            debt_ratio=0.12,
            burn_rate=450000.0,
            score=85,
        )
        self._requests: List[SpendingRequest] = []
        self._budget_status = {
            "total_budget": 12000000.0,
            "spent": 3500000.0,
            "remaining": 8500000.0,
        }

    def daily_finance_review(self) -> Dict:
        return {
            "date": datetime.now().isoformat(),
            "cash_position": self._cash.to_dict(),
            "financial_health": self._health.to_dict(),
            "pending_requests": len(self._requests),
        }

    def get_cash_position(self) -> CashPosition:
        return self._cash

    def get_financial_health(self) -> FinancialHealth:
        return self._health

    def approve_spending(self, request: SpendingRequest) -> bool:
        if self._cash.available_cash >= request.amount:
            request.status = "approved"
            self._cash.available_cash -= request.amount
            self._cash.reserved_cash += request.amount
            self._requests.append(request)
            return True
        request.status = "rejected"
        return False

    def get_budget_status(self) -> Dict:
        return {
            "budget": self._budget_status,
            "cash_position": self._cash.to_dict(),
        }

    def get_stats(self) -> Dict:
        return {
            "total_requests": len(self._requests),
            "approved_requests": sum(1 for r in self._requests if r.status == "approved"),
            "cash_position": self._cash.to_dict(),
            "financial_health": self._health.to_dict(),
        }
