from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class InvestmentAllocation:
    allocations: Dict[str, float] = field(default_factory=dict)
    reserve: float = 0.0
    total_budget: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocations": self.allocations,
            "reserve": self.reserve,
            "total_budget": self.total_budget,
        }


@dataclass
class ProjectInvestment:
    project_name: str = ""
    allocated_amount: float = 0.0
    expected_roi: float = 0.0
    risk_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "allocated_amount": self.allocated_amount,
            "expected_roi": self.expected_roi,
            "risk_score": self.risk_score,
        }


class InvestmentEngine:
    def __init__(self):
        self._portfolio: List[ProjectInvestment] = []

    def allocate_budget(self, projects: List[Dict[str, Any]], total_budget: float) -> InvestmentAllocation:
        total_score = sum(p.get("score", 1.0) for p in projects)
        if total_score == 0:
            total_score = len(projects) or 1

        allocations = {}
        reserve = total_budget * 0.1
        allocatable = total_budget - reserve

        for project in projects:
            score = project.get("score", 1.0)
            amount = allocatable * (score / total_score)
            allocations[project.get("name", "unknown")] = round(amount, 2)

        return InvestmentAllocation(
            allocations=allocations,
            reserve=round(reserve, 2),
            total_budget=total_budget,
        )

    def evaluate_project(self, project: Dict[str, Any]) -> ProjectInvestment:
        expected_roi = project.get("expected_roi", 0.0)
        risk_score = project.get("risk_score", 0.5)
        allocated_amount = project.get("budget", 0.0)

        investment = ProjectInvestment(
            project_name=project.get("name", "unknown"),
            allocated_amount=allocated_amount,
            expected_roi=expected_roi,
            risk_score=risk_score,
        )
        self._portfolio.append(investment)
        return investment

    def get_portfolio(self) -> List[ProjectInvestment]:
        return self._portfolio.copy()
