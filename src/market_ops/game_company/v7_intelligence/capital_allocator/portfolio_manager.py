from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import uuid

from .project_ranker import ProjectRanker, RankedProject
from .budget_allocator import BudgetAllocator, BudgetAllocation
from .risk_model import RiskModel, PortfolioRisk
from .kill_decision import KillDecision, KillRecommendation


@dataclass
class PortfolioSummary:
    portfolio_id: str
    total_projects: int
    active_projects: int
    total_budget: float
    total_spent: float
    total_remaining: float
    avg_project_score: float
    risk_level: str
    top_project_id: Optional[str]
    bottom_project_id: Optional[str]
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PortfolioOptimization:
    optimization_id: str
    recommended_additions: List[dict] = field(default_factory=list)
    recommended_removals: List[str] = field(default_factory=list)
    budget_reallocation: Dict[str, float] = field(default_factory=dict)
    expected_return_improvement: float = 0.0
    expected_risk_reduction: float = 0.0
    optimized_at: datetime = field(default_factory=datetime.utcnow)


class PortfolioManager:
    def __init__(self, portfolio_id: Optional[str] = None):
        self.portfolio_id = portfolio_id or f"pf-{uuid.uuid4().hex[:8]}"
        self._projects: Dict[str, dict] = {}
        self._ranker = ProjectRanker()
        self._allocator = BudgetAllocator()
        self._risk_model = RiskModel()
        self._kill_decision = KillDecision()
        self._budget: float = 0.0

    def add_project(self, project: dict) -> str:
        project_id = project.get("project_id", str(uuid.uuid4())[:8])
        project["project_id"] = project_id
        self._projects[project_id] = project
        return project_id

    def remove_project(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            return True
        return False

    def get_portfolio_summary(self) -> PortfolioSummary:
        project_list = list(self._projects.values())
        active = len([p for p in project_list if p.get("status", "active") == "active"])

        total_spent = sum(p.get("spent_amount", 0.0) for p in project_list)
        total_remaining = self._budget - total_spent

        scores = [p.get("score", 50.0) for p in project_list]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        top_id = max(project_list, key=lambda x: x.get("score", 0.0))["project_id"] if project_list else None
        bottom_id = min(project_list, key=lambda x: x.get("score", 0.0))["project_id"] if project_list else None

        risk_level = "low" if avg_score > 75 else "medium" if avg_score > 50 else "high"

        return PortfolioSummary(
            portfolio_id=self.portfolio_id,
            total_projects=len(project_list),
            active_projects=active,
            total_budget=self._budget,
            total_spent=total_spent,
            total_remaining=total_remaining,
            avg_project_score=avg_score,
            risk_level=risk_level,
            top_project_id=top_id,
            bottom_project_id=bottom_id,
        )

    def optimize_portfolio(self) -> PortfolioOptimization:
        project_list = list(self._projects.values())

        ranked = self._ranker.rank_projects(project_list)
        top_ids = {rp.project_id for rp in self._ranker.get_top_projects(3)}

        removals = []
        for proj in project_list:
            rec = self._kill_decision.should_kill(proj)
            if rec.should_kill:
                removals.append(proj["project_id"])

        budget_map = {}
        if self._budget > 0 and project_list:
            allocations = self._allocator.allocate(self._budget, project_list)
            for alloc in allocations:
                budget_map[alloc.project_id] = alloc.allocated_amount

        expected_return = round(len(top_ids) * 0.05, 2)
        expected_risk = round(len(removals) * 0.08, 2)

        return PortfolioOptimization(
            optimization_id=f"opt-{uuid.uuid4().hex[:8]}",
            recommended_additions=[{"type": "high_score_project", "target_score": 85.0}],
            recommended_removals=removals,
            budget_reallocation=budget_map,
            expected_return_improvement=expected_return,
            expected_risk_reduction=expected_risk,
        )
