from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import uuid


@dataclass
class BudgetAllocation:
    allocation_id: str
    project_id: str
    allocated_amount: float
    spent_amount: float
    remaining_amount: float
    currency: str = "USD"
    allocated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.remaining_amount == 0.0:
            self.remaining_amount = self.allocated_amount - self.spent_amount


@dataclass
class AllocationChange:
    change_id: str
    project_id: str
    previous_amount: float
    new_amount: float
    delta: float
    reason: str
    changed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.delta == 0.0:
            self.delta = self.new_amount - self.previous_amount


class BudgetAllocator:
    def __init__(self):
        self._allocations: Dict[str, BudgetAllocation] = {}
        self._changes: List[AllocationChange] = []
        self._total_budget: float = 0.0

    def allocate(self, budget: float, projects: List[dict]) -> List[BudgetAllocation]:
        self._total_budget = budget
        if not projects:
            return []

        total_weight = sum(p.get("weight", 1.0) for p in projects)
        allocations = []

        for project in projects:
            project_id = project.get("project_id", str(uuid.uuid4())[:8])
            weight = project.get("weight", 1.0)
            share = weight / total_weight
            amount = round(budget * share, 2)

            allocation = BudgetAllocation(
                allocation_id=str(uuid.uuid4())[:12],
                project_id=project_id,
                allocated_amount=amount,
                spent_amount=project.get("spent_amount", 0.0),
                remaining_amount=0.0,
            )
            allocations.append(allocation)
            self._allocations[project_id] = allocation

        return allocations

    def reallocate(self, project_id: str, amount: float, reason: str = "manual") -> Optional[AllocationChange]:
        if project_id not in self._allocations:
            return None

        current = self._allocations[project_id]
        change = AllocationChange(
            change_id=str(uuid.uuid4())[:12],
            project_id=project_id,
            previous_amount=current.allocated_amount,
            new_amount=amount,
            delta=0.0,
            reason=reason,
        )

        current.allocated_amount = amount
        current.remaining_amount = current.allocated_amount - current.spent_amount
        self._changes.append(change)
        return change

    def get_allocation(self) -> Dict[str, BudgetAllocation]:
        return dict(self._allocations)
