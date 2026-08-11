from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CompanyStrategy:
    strategy_id: str
    projects: List[Dict[str, Any]] = field(default_factory=list)
    resource_allocation: Dict[str, float] = field(default_factory=dict)
    quarterly_goals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    overall_objective: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class CEOBrain:
    def __init__(self):
        self.project_priorities = {}

    def make_strategy(self, company_context: Dict[str, Any]) -> CompanyStrategy:
        target_arr = company_context.get("target_arr", 10_000_000)
        timeline = company_context.get("timeline", 12)
        resources = company_context.get("resources", {})
        existing_data = company_context.get("existing_data", {})

        projects = self._generate_projects(existing_data, target_arr)
        allocation = self._allocate_resources(projects, resources)
        quarterly_goals = self._generate_quarterly_goals(projects, timeline)

        return CompanyStrategy(
            strategy_id=f"strategy_{hash(str(company_context)) % 10000:04d}",
            projects=projects,
            resource_allocation=allocation,
            quarterly_goals=quarterly_goals,
            overall_objective=f"${target_arr:,.0f} ARR in {timeline} months",
            confidence=self._calculate_confidence(projects),
        )

    def _generate_projects(self, existing_data: Dict[str, Any], target_arr: float) -> List[Dict[str, Any]]:
        projects = []
        
        if existing_data.get("has_merge_game"):
            projects.append({
                "id": "project_merge_cozy",
                "name": "Merge Cozy",
                "genre": "Merge + Decoration",
                "budget_share": 0.4,
                "risk": "medium",
                "expected_revenue": target_arr * 0.5,
            })
        
        projects.append({
            "id": "project_next_genre",
            "name": "Next Genre Discovery",
            "genre": "Market Opportunity",
            "budget_share": 0.2,
            "risk": "high",
            "expected_revenue": target_arr * 0.3,
        })
        
        projects.append({
            "id": "project_aso_optimization",
            "name": "ASO Optimization",
            "genre": "Operational",
            "budget_share": 0.1,
            "risk": "low",
            "expected_revenue": target_arr * 0.1,
        })
        
        projects.append({
            "id": "project_experiments",
            "name": "R&D Experiments",
            "genre": "Innovation",
            "budget_share": 0.1,
            "risk": "high",
            "expected_revenue": target_arr * 0.1,
        })

        return projects

    def _allocate_resources(self, projects: List[Dict[str, Any]], resources: Dict[str, Any]) -> Dict[str, float]:
        allocation = {"development": 40, "ua": 40, "aso": 10, "experiments": 10}
        
        total_share = sum(p["budget_share"] for p in projects)
        if total_share > 0:
            for project in projects:
                allocation[project["id"]] = project["budget_share"] * 100
        
        return allocation

    def _generate_quarterly_goals(self, projects: List[Dict[str, Any]], timeline: int) -> Dict[str, Dict[str, Any]]:
        quarters = min(timeline // 3, 4)
        goals = {}
        
        for q in range(1, quarters + 1):
            if q == 1:
                goals[f"Q{q}"] = {"phase": "Prototype", "milestones": ["MVP Complete", "Market Validation", "Internal Testing"]}
            elif q == 2:
                goals[f"Q{q}"] = {"phase": "Soft Launch", "milestones": ["Beta Release", "User Feedback", "Monetization Setup"]}
            elif q == 3:
                goals[f"Q{q}"] = {"phase": "Scale", "milestones": ["Full Launch", "UA Scale", "Revenue Optimization"]}
            else:
                goals[f"Q{q}"] = {"phase": "Optimize", "milestones": ["Profitability", "New Feature Launch", "Next Project Planning"]}
        
        return goals

    def _calculate_confidence(self, projects: List[Dict[str, Any]]) -> float:
        base_confidence = 0.7
        for project in projects:
            if project["risk"] == "low":
                base_confidence += 0.05
            elif project["risk"] == "high":
                base_confidence -= 0.03
        
        return min(base_confidence, 0.95)

    def make_strategy_demo(self) -> CompanyStrategy:
        context = {
            "target_arr": 10_000_000,
            "timeline": 12,
            "resources": {"developers": 2, "ua_budget": 5000},
            "existing_data": {"has_merge_game": True},
        }
        return self.make_strategy(context)
