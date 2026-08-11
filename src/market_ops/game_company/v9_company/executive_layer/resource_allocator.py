from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class ResourceType(Enum):
    BUDGET = "budget"
    PEOPLE = "people"
    TIME = "time"
    TECH = "tech"


@dataclass
class ResourceRequest:
    request_id: str
    department: str
    resource_type: ResourceType
    amount: float = 0.0
    justification: str = ""
    deadline: str = ""
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "department": self.department,
            "resource_type": self.resource_type.value,
            "amount": self.amount,
            "justification": self.justification,
            "deadline": self.deadline,
            "status": self.status,
        }


@dataclass
class ResourceAllocation:
    allocation_id: str
    department: str
    resource_type: ResourceType
    allocated_amount: float = 0.0
    used_amount: float = 0.0
    period: str = ""
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "department": self.department,
            "resource_type": self.resource_type.value,
            "allocated_amount": self.allocated_amount,
            "used_amount": self.used_amount,
            "period": self.period,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ResourceUtilization:
    utilization_id: str
    department: str
    resource_type: ResourceType
    utilization_rate: float = 0.0
    efficiency_score: float = 0.0
    trends: Dict[str, float] = field(default_factory=dict)
    reported_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "utilization_id": self.utilization_id,
            "department": self.department,
            "resource_type": self.resource_type.value,
            "utilization_rate": self.utilization_rate,
            "efficiency_score": self.efficiency_score,
            "trends": self.trends,
            "reported_at": self.reported_at.isoformat(),
        }


class ResourceAllocator:
    def __init__(self):
        self._allocations: Dict[str, ResourceAllocation] = {}
        self._requests: Dict[str, ResourceRequest] = {}
        self._utilization: Dict[str, ResourceUtilization] = {}

    def allocate_resources(
        self,
        resources: Dict[str, Dict[ResourceType, float]],
        requests: List[ResourceRequest],
    ) -> List[ResourceAllocation]:
        allocations = []
        for req in requests:
            dept_resources = resources.get(req.department, {})
            allocated = min(req.amount, dept_resources.get(req.resource_type, 0))

            allocation = ResourceAllocation(
                allocation_id=f"alloc_{req.request_id}",
                department=req.department,
                resource_type=req.resource_type,
                allocated_amount=allocated,
                period=datetime.now().strftime("%Y-%m"),
            )
            allocations.append(allocation)
            self._allocations[allocation.allocation_id] = allocation
            self._requests[req.request_id] = req
            req.status = "allocated"

        return allocations

    def get_allocation_plan(self) -> List[ResourceAllocation]:
        return list(self._allocations.values())

    def reallocate(self, from_department: str, to_department: str, amount: float) -> bool:
        source_allocs = [
            a for a in self._allocations.values()
            if a.department == from_department and a.allocated_amount >= amount
        ]
        if not source_allocs:
            return False

        source = source_allocs[0]
        source.allocated_amount -= amount
        source.updated_at = datetime.now()

        new_alloc = ResourceAllocation(
            allocation_id=f"alloc_realloc_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            department=to_department,
            resource_type=source.resource_type,
            allocated_amount=amount,
            period=source.period,
        )
        self._allocations[new_alloc.allocation_id] = new_alloc
        return True

    def get_utilization(self) -> List[ResourceUtilization]:
        if not self._utilization:
            return [
                ResourceUtilization(
                    utilization_id="util_001",
                    department="ua",
                    resource_type=ResourceType.BUDGET,
                    utilization_rate=0.88,
                    efficiency_score=0.76,
                    trends={"weekly": 0.85, "monthly": 0.88},
                ),
                ResourceUtilization(
                    utilization_id="util_002",
                    department="product",
                    resource_type=ResourceType.PEOPLE,
                    utilization_rate=0.92,
                    efficiency_score=0.81,
                    trends={"weekly": 0.90, "monthly": 0.92},
                ),
            ]
        return list(self._utilization.values())

    def get_stats(self) -> Dict[str, Any]:
        total_allocated = sum(a.allocated_amount for a in self._allocations.values())
        total_used = sum(a.used_amount for a in self._allocations.values())
        return {
            "total_allocations": len(self._allocations),
            "total_requests": len(self._requests),
            "total_allocated_amount": total_allocated,
            "total_used_amount": total_used,
            "utilization_rate": total_used / total_allocated if total_allocated else 0.0,
        }
