from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CashflowStatus:
    daily_budget: float
    monthly_burn: float
    actual_spend: float
    remaining_budget: float
    risk_level: str
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class CashflowController:
    def __init__(self):
        self.daily_budget_cap = 10000
        self.monthly_budget_cap = 300000
        self.risk_thresholds = {
            "low": 0.5,
            "medium": 0.75,
            "high": 0.9,
            "critical": 0.95,
        }

    def control(self, current_state: Dict[str, Any]) -> CashflowStatus:
        daily_budget = current_state.get("daily_budget", 5000)
        monthly_burn = current_state.get("monthly_burn", 0)
        actual_spend = current_state.get("actual_spend", 0)
        days_in_month = current_state.get("days_in_month", 30)
        current_day = current_state.get("current_day", 15)

        remaining_budget = max(self.monthly_budget_cap - monthly_burn, 0)
        daily_remaining = remaining_budget / max(days_in_month - current_day, 1)

        if actual_spend > 0:
            burn_rate = actual_spend / current_day if current_day > 0 else 0
            projected_monthly = burn_rate * days_in_month
            spend_ratio = projected_monthly / self.monthly_budget_cap
        else:
            spend_ratio = actual_spend / self.monthly_budget_cap

        if spend_ratio >= self.risk_thresholds["critical"]:
            risk_level = "CRITICAL"
            recommendations = ["Immediate spending freeze", "Pause all campaigns"]
            daily_budget = 0
        elif spend_ratio >= self.risk_thresholds["high"]:
            risk_level = "HIGH"
            recommendations = ["Reduce budget by 50%", "Pause non-critical campaigns"]
            daily_budget = min(daily_budget * 0.5, daily_remaining)
        elif spend_ratio >= self.risk_thresholds["medium"]:
            risk_level = "MEDIUM"
            recommendations = ["Monitor closely", "Reduce budget by 20%"]
            daily_budget = min(daily_budget * 0.8, daily_remaining)
        elif spend_ratio >= self.risk_thresholds["low"]:
            risk_level = "LOW"
            recommendations = ["Within budget", "Continue operations"]
        else:
            risk_level = "SAFE"
            recommendations = ["Budget underutilized", "Consider increasing spend"]

        return CashflowStatus(
            daily_budget=round(daily_budget, 2),
            monthly_burn=round(monthly_burn, 2),
            actual_spend=round(actual_spend, 2),
            remaining_budget=round(remaining_budget, 2),
            risk_level=risk_level,
            recommendations=recommendations,
        )

    def control_demo(self) -> CashflowStatus:
        data = {
            "daily_budget": 8000,
            "monthly_burn": 240000,
            "actual_spend": 220000,
            "days_in_month": 30,
            "current_day": 25,
        }
        return self.control(data)
