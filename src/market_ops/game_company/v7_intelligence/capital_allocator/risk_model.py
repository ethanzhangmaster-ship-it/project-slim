from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import math
import random


@dataclass
class RiskAssessment:
    assessment_id: str
    project_id: str
    market_risk: float
    execution_risk: float
    financial_risk: float
    technology_risk: float
    overall_risk_score: float = 0.0
    risk_level: str = "medium"
    assessed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.overall_risk_score == 0.0:
            self.overall_risk_score = round(
                (self.market_risk * 0.25
                 + self.execution_risk * 0.30
                 + self.financial_risk * 0.30
                 + self.technology_risk * 0.15), 2
            )
        if self.risk_level == "medium":
            if self.overall_risk_score < 0.3:
                self.risk_level = "low"
            elif self.overall_risk_score > 0.7:
                self.risk_level = "high"


@dataclass
class PortfolioRisk:
    portfolio_id: str
    avg_risk_score: float
    max_risk_project_id: Optional[str]
    min_risk_project_id: Optional[str]
    diversification_score: float
    var_95: float
    var_99: float
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    assessed_at: datetime = field(default_factory=datetime.utcnow)


class RiskModel:
    def __init__(self):
        self._assessments: Dict[str, RiskAssessment] = {}
        self._portfolio_history: List[PortfolioRisk] = []

    def assess_risk(self, project: dict) -> RiskAssessment:
        project_id = project.get("project_id", "unknown")

        market = project.get("market_risk", random.uniform(0.1, 0.9))
        execution = project.get("execution_risk", random.uniform(0.1, 0.9))
        financial = project.get("financial_risk", random.uniform(0.1, 0.9))
        technology = project.get("technology_risk", random.uniform(0.1, 0.9))

        assessment = RiskAssessment(
            assessment_id=f"ra-{project_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            project_id=project_id,
            market_risk=round(market, 2),
            execution_risk=round(execution, 2),
            financial_risk=round(financial, 2),
            technology_risk=round(technology, 2),
        )
        self._assessments[project_id] = assessment
        return assessment

    def get_portfolio_risk(self, project_ids: Optional[List[str]] = None) -> PortfolioRisk:
        ids = project_ids or list(self._assessments.keys())
        relevant = [self._assessments[pid] for pid in ids if pid in self._assessments]

        if not relevant:
            return PortfolioRisk(
                portfolio_id="empty",
                avg_risk_score=0.0,
                max_risk_project_id=None,
                min_risk_project_id=None,
                diversification_score=0.0,
                var_95=0.0,
                var_99=0.0,
            )

        scores = [r.overall_risk_score for r in relevant]
        avg_risk = round(sum(scores) / len(scores), 2)
        max_risk = max(relevant, key=lambda x: x.overall_risk_score)
        min_risk = min(relevant, key=lambda x: x.overall_risk_score)

        correlations = {}
        for a in relevant:
            correlations[a.project_id] = {}
            for b in relevant:
                correlations[a.project_id][b.project_id] = round(random.uniform(-0.3, 0.8), 2) if a.project_id != b.project_id else 1.0

        diversification = round(1.0 - (sum(
            correlations[a.project_id][b.project_id]
            for a in relevant for b in relevant if a.project_id != b.project_id
        ) / max(len(relevant) * (len(relevant) - 1), 1)), 2)

        var95, var99 = self.calculate_var(scores)

        portfolio = PortfolioRisk(
            portfolio_id=f"pf-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            avg_risk_score=avg_risk,
            max_risk_project_id=max_risk.project_id,
            min_risk_project_id=min_risk.project_id,
            diversification_score=diversification,
            var_95=var95,
            var_99=var99,
            correlation_matrix=correlations,
        )
        self._portfolio_history.append(portfolio)
        return portfolio

    def calculate_var(self, returns: Optional[List[float]] = None) -> tuple:
        scores = returns if returns is not None else [
            a.overall_risk_score for a in self._assessments.values()
        ]
        if not scores:
            return 0.0, 0.0

        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        std_dev = math.sqrt(variance)

        var_95 = round(mean - 1.645 * std_dev, 2)
        var_99 = round(mean - 2.326 * std_dev, 2)
        return var_95, var_99
