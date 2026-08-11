from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class ProjectScore:
    project_id: str
    financial_score: float
    strategic_score: float
    execution_score: float
    market_score: float
    total_score: float = 0.0
    scored_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.total_score == 0.0:
            self.total_score = round(
                (self.financial_score * 0.35
                 + self.strategic_score * 0.25
                 + self.execution_score * 0.25
                 + self.market_score * 0.15), 2
            )


@dataclass
class RankedProject:
    rank: int
    project_id: str
    project_name: str
    score: ProjectScore
    priority: str = "medium"
    recommendation: str = ""


class ProjectRanker:
    def __init__(self):
        self._projects: List[RankedProject] = []
        self._score_history: List[ProjectScore] = []

    def score_project(self, project: dict) -> ProjectScore:
        project_id = project.get("project_id", "unknown")
        financial = project.get("financial_score", 50.0)
        strategic = project.get("strategic_score", 50.0)
        execution = project.get("execution_score", 50.0)
        market = project.get("market_score", 50.0)

        score = ProjectScore(
            project_id=project_id,
            financial_score=financial,
            strategic_score=strategic,
            execution_score=execution,
            market_score=market,
        )
        self._score_history.append(score)
        return score

    def rank_projects(self, projects: List[dict]) -> List[RankedProject]:
        scored = []
        for proj in projects:
            score = self.score_project(proj)
            scored.append({
                "project_id": proj.get("project_id", "unknown"),
                "project_name": proj.get("project_name", "Unnamed"),
                "score": score,
            })

        scored.sort(key=lambda x: x["score"].total_score, reverse=True)

        ranked = []
        for i, item in enumerate(scored, start=1):
            priority = "high" if i <= len(scored) * 0.2 else "medium" if i <= len(scored) * 0.5 else "low"
            recommendation = (
                "accelerate" if priority == "high" else
                "monitor" if priority == "medium" else "review"
            )
            ranked.append(RankedProject(
                rank=i,
                project_id=item["project_id"],
                project_name=item["project_name"],
                score=item["score"],
                priority=priority,
                recommendation=recommendation,
            ))

        self._projects = ranked
        return ranked

    def get_top_projects(self, n: int = 5) -> List[RankedProject]:
        return self._projects[:n]
