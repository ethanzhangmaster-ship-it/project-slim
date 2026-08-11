from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AllocationPlan:
    plan_id: str
    allocations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    total_budget: float = 0.0
    remaining_budget: float = 0.0
    risk_level: str = "low"
    timestamp: datetime = field(default_factory=datetime.now)


class ResourceAllocator:
    def __init__(self):
        self.allocation_history: List[AllocationPlan] = []

    def allocate(self, projects, resources: Dict[str, Any] = None) -> AllocationPlan:
        if resources is None:
            resources = {}
        
        if isinstance(projects, list) and len(projects) > 0 and isinstance(projects[0], dict):
            budget = resources.get("budget", 100000)
            return self._allocate_from_projects(budget, projects)
        
        if isinstance(projects, float) or isinstance(projects, int):
            budget = projects
            project_list = resources if isinstance(resources, list) else []
            return self._allocate_from_projects(budget, project_list)
        
        return AllocationPlan(plan_id="alloc_default")

    def _allocate_from_projects(self, budget: float, projects: List[Dict[str, Any]]) -> AllocationPlan:
        allocations = {}
        
        total_share = sum(p.get("budget_share", 0) for p in projects)
        if total_share == 0:
            total_share = 1.0
        
        for project in projects:
            project_id = project.get("id", project.get("name", str(hash(str(project)))))
            share = project.get("budget_share", 0.25)
            project_budget = budget * share
            
            allocations[project_id] = {
                "budget": round(project_budget, 2),
                "share": round(share * 100, 1),
                "risk": project.get("risk", "medium"),
            }
        
        remaining = budget - sum(a["budget"] for a in allocations.values())
        
        risk_level = self._calculate_risk(projects)
        
        plan = AllocationPlan(
            plan_id=f"alloc_{hash(str(projects)) % 10000:04d}",
            allocations=allocations,
            total_budget=budget,
            remaining_budget=round(remaining, 2),
            risk_level=risk_level,
        )
        
        self.allocation_history.append(plan)
        return plan

    def reallocate(self, plan_id: str, new_budget: float) -> Optional[AllocationPlan]:
        existing = next((p for p in self.allocation_history if p.plan_id == plan_id), None)
        if not existing:
            return None
        
        projects = [{"id": pid, "budget_share": alloc["share"] / 100, "risk": alloc["risk"]} 
                    for pid, alloc in existing.allocations.items()]
        
        return self.allocate(new_budget, projects)

    def _calculate_risk(self, projects: List[Dict[str, Any]]) -> str:
        high_risk_count = sum(1 for p in projects if p.get("risk") == "high")
        medium_risk_count = sum(1 for p in projects if p.get("risk") == "medium")
        
        total = len(projects)
        if total == 0:
            return "low"
        
        risk_ratio = (high_risk_count * 1.0 + medium_risk_count * 0.5) / total
        
        if risk_ratio > 0.6:
            return "high"
        elif risk_ratio > 0.3:
            return "medium"
        else:
            return "low"

    def allocate_demo(self) -> AllocationPlan:
        projects = [
            {"id": "project_A", "name": "Merge Cozy", "budget_share": 0.4, "risk": "medium"},
            {"id": "project_B", "name": "Next Genre", "budget_share": 0.3, "risk": "high"},
            {"id": "project_C", "name": "ASO", "budget_share": 0.2, "risk": "low"},
            {"id": "project_D", "name": "Experiments", "budget_share": 0.1, "risk": "high"},
        ]
        return self.allocate(120000, projects)
