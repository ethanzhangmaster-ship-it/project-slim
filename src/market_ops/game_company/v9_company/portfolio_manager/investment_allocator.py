from dataclasses import dataclass
from typing import Dict, List


@dataclass
class InvestmentAllocation:
    game_id: str
    amount: float
    percentage: float

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "amount": self.amount,
            "percentage": self.percentage,
        }


@dataclass
class InvestmentPerformance:
    game_id: str
    invested: float
    returned: float
    roi: float

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "invested": self.invested,
            "returned": self.returned,
            "roi": self.roi,
        }


@dataclass
class AllocationPlan:
    total_amount: float
    allocations: List[InvestmentAllocation]
    strategy: str

    def to_dict(self):
        return {
            "total_amount": self.total_amount,
            "allocations": [a.to_dict() for a in self.allocations],
            "strategy": self.strategy,
        }


class InvestmentAllocator:
    def __init__(self):
        self._allocations: List[InvestmentAllocation] = []
        self._performance: Dict[str, InvestmentPerformance] = {}

    def allocate_investment(self, total_amount: float) -> AllocationPlan:
        games = ["g001", "g002", "g003"]
        equal_share = total_amount / len(games)
        allocations = [
            InvestmentAllocation(
                game_id=g,
                amount=equal_share,
                percentage=1.0 / len(games),
            )
            for g in games
        ]
        self._allocations = allocations
        return AllocationPlan(
            total_amount=total_amount,
            allocations=allocations,
            strategy="equal_weight",
        )

    def get_allocation_plan(self) -> AllocationPlan:
        if not self._allocations:
            return self.allocate_investment(1000000.0)
        total = sum(a.amount for a in self._allocations)
        return AllocationPlan(
            total_amount=total,
            allocations=self._allocations,
            strategy="equal_weight",
        )

    def adjust_allocation(self, game_id: str, amount: float) -> InvestmentAllocation:
        allocation = InvestmentAllocation(
            game_id=game_id,
            amount=amount,
            percentage=0.0,
        )
        self._allocations.append(allocation)
        return allocation

    def get_investment_performance(self) -> List[InvestmentPerformance]:
        return list(self._performance.values())

    def get_stats(self) -> Dict:
        total_allocated = sum(a.amount for a in self._allocations)
        return {
            "allocation_count": len(self._allocations),
            "total_allocated": total_allocated,
            "performance_tracked": len(self._performance),
        }
