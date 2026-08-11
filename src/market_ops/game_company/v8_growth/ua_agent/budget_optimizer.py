from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import random


@dataclass
class BudgetAllocation:
    campaign_id: str
    allocated_amount: float
    previous_amount: float = 0.0
    utilization: float = 0.0
    expected_roi: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "allocated_amount": self.allocated_amount,
            "previous_amount": self.previous_amount,
            "utilization": self.utilization,
            "expected_roi": self.expected_roi,
        }


@dataclass
class BudgetChange:
    change_id: str
    from_campaign: str
    to_campaign: str
    amount: float
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "from_campaign": self.from_campaign,
            "to_campaign": self.to_campaign,
            "amount": self.amount,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BudgetRecommendation:
    recommendation_id: str
    allocations: List[BudgetAllocation] = field(default_factory=list)
    changes: List[BudgetChange] = field(default_factory=list)
    expected_total_roi: float = 0.0
    total_budget: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "allocations": [a.to_dict() for a in self.allocations],
            "changes": [c.to_dict() for c in self.changes],
            "expected_total_roi": self.expected_total_roi,
            "total_budget": self.total_budget,
            "confidence": self.confidence,
        }


class BudgetOptimizer:
    def __init__(self):
        self._allocations: Dict[str, BudgetAllocation] = {}
        self._history: List[BudgetChange] = []

    def set_allocation(self, allocation: BudgetAllocation):
        self._allocations[allocation.campaign_id] = allocation

    def optimize_budget(self, campaigns: List[Dict[str, Any]]) -> BudgetRecommendation:
        total_budget = sum(c.get("budget", 0) for c in campaigns)
        total_roas = sum(c.get("roas", 0) * c.get("budget", 1) for c in campaigns)
        avg_roas = total_roas / total_budget if total_budget > 0 else 0

        allocations = []
        for campaign in campaigns:
            roas = campaign.get("roas", 1)
            current_budget = campaign.get("budget", 0)

            if roas > 1.5:
                new_budget = current_budget * 1.3
            elif roas < 0.8:
                new_budget = current_budget * 0.7
            else:
                new_budget = current_budget

            allocations.append(BudgetAllocation(
                campaign_id=campaign.get("campaign_id", "unknown"),
                allocated_amount=new_budget,
                previous_amount=current_budget,
                utilization=campaign.get("budget_utilization", 0.8),
                expected_roi=roas,
            ))

        rec_id = f"budget_rec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return BudgetRecommendation(
            recommendation_id=rec_id,
            allocations=allocations,
            expected_total_roi=avg_roas,
            total_budget=total_budget,
            confidence=0.85,
        )

    def allocate_budget(self, total_budget: float) -> List[BudgetAllocation]:
        total_weight = sum(a.expected_roi for a in self._allocations.values())
        allocations = []

        for campaign_id, allocation in self._allocations.items():
            weight = allocation.expected_roi / total_weight if total_weight > 0 else 1 / len(self._allocations)
            new_amount = total_budget * weight
            allocation.previous_amount = allocation.allocated_amount
            allocation.allocated_amount = new_amount
            allocations.append(allocation)

        return allocations

    def reallocate_budget(self, from_campaign: str, to_campaign: str, amount: float) -> BudgetChange:
        change_id = f"change_{hash(from_campaign + to_campaign + str(datetime.now())) % 100000:05d}"
        change = BudgetChange(
            change_id=change_id,
            from_campaign=from_campaign,
            to_campaign=to_campaign,
            amount=amount,
            reason="Performance-based reallocation",
        )
        self._history.append(change)

        if from_campaign in self._allocations:
            self._allocations[from_campaign].allocated_amount -= amount
        if to_campaign in self._allocations:
            self._allocations[to_campaign].allocated_amount += amount

        return change

    def get_budget_recommendations(self) -> List[BudgetRecommendation]:
        return []

    def get_allocation(self, campaign_id: str) -> Optional[BudgetAllocation]:
        return self._allocations.get(campaign_id)

    def get_allocations(self) -> List[BudgetAllocation]:
        return list(self._allocations.values())

    def get_history(self, limit: int = 100) -> List[BudgetChange]:
        return self._history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        total_budget = sum(a.allocated_amount for a in self._allocations.values())
        avg_roi = sum(a.expected_roi for a in self._allocations.values()) / len(self._allocations) if self._allocations else 0
        return {
            "total_campaigns": len(self._allocations),
            "total_budget": total_budget,
            "avg_expected_roi": avg_roi,
            "total_reallocations": len(self._history),
        }