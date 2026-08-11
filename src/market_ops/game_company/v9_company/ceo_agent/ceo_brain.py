from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class DecisionType(Enum):
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    PRODUCT = "product"


class ObjectivePriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CEODecision:
    decision_id: str
    title: str
    decision_type: DecisionType
    description: str = ""
    rationale: str = ""
    expected_impact: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "title": self.title,
            "decision_type": self.decision_type.value,
            "description": self.description,
            "rationale": self.rationale,
            "expected_impact": self.expected_impact,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CompanyStatus:
    health_score: float = 0.0
    revenue_trend: str = "stable"
    team_morale: str = "good"
    product_velocity: str = "normal"
    market_position: str = "competitive"
    risks: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "health_score": self.health_score,
            "revenue_trend": self.revenue_trend,
            "team_morale": self.team_morale,
            "product_velocity": self.product_velocity,
            "market_position": self.market_position,
            "risks": self.risks,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class DailyBriefing:
    briefing_id: str
    date: str
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    wins: List[str] = field(default_factory=list)
    focus_areas: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "briefing_id": self.briefing_id,
            "date": self.date,
            "key_metrics": self.key_metrics,
            "alerts": self.alerts,
            "wins": self.wins,
            "focus_areas": self.focus_areas,
            "created_at": self.created_at.isoformat(),
        }


class CEOBrain:
    def __init__(self):
        self._objectives: List[Dict[str, Any]] = []
        self._decisions: List[CEODecision] = []
        self._briefings: List[DailyBriefing] = []
        self._company_status: CompanyStatus = CompanyStatus()
        self._performance_reviews: List[Dict[str, Any]] = []

    def daily_briefing(self) -> DailyBriefing:
        date_str = datetime.now().strftime("%Y-%m-%d")
        briefing_id = f"briefing_{date_str}"
        briefing = DailyBriefing(
            briefing_id=briefing_id,
            date=date_str,
            key_metrics={
                "revenue": 125000.0,
                "dau": 45000,
                "retention_d1": 0.42,
                "arpu": 2.78,
            },
            alerts=["Ad spend 12% over budget", "iOS review delay"],
            wins=["New feature launched", "Campaign ROI +18%"],
            focus_areas=["Optimize UA spend", "Prepare Q3 roadmap"],
        )
        self._briefings.append(briefing)
        return briefing

    def get_company_status(self) -> CompanyStatus:
        self._company_status = CompanyStatus(
            health_score=78.5,
            revenue_trend="up",
            team_morale="good",
            product_velocity="normal",
            market_position="competitive",
            risks=["Competitor price war", "Attribution signal loss"],
        )
        return self._company_status

    def generate_decisions(self) -> List[CEODecision]:
        decisions = [
            CEODecision(
                decision_id="dec_001",
                title="Increase Q3 marketing budget by 15%",
                decision_type=DecisionType.FINANCIAL,
                description="Reallocate budget to high-performing channels.",
                rationale="ROI on TikTok campaigns exceeded 150%.",
                expected_impact={"revenue": "+8%", "cac": "-5%"},
            ),
            CEODecision(
                decision_id="dec_002",
                title="Prioritize retention features over new genres",
                decision_type=DecisionType.PRODUCT,
                description="Shift 2 sprints to retention mechanics.",
                rationale="D1 retention dropped 3% last month.",
                expected_impact={"retention_d1": "+5%", "churn": "-2%"},
            ),
        ]
        self._decisions.extend(decisions)
        return decisions

    def review_performance(self) -> Dict[str, Any]:
        review = {
            "review_id": f"review_{datetime.now().strftime('%Y%m%d')}",
            "period": "monthly",
            "kpis": {
                "revenue_vs_target": 0.94,
                "user_growth": 0.12,
                "profit_margin": 0.22,
            },
            "top_performers": ["UA team", "Creative studio"],
            "areas_for_improvement": ["QA velocity", "Store conversion"],
            "timestamp": datetime.now().isoformat(),
        }
        self._performance_reviews.append(review)
        return review

    def set_objectives(self, objectives: List[Dict[str, Any]]) -> None:
        self._objectives = objectives

    def get_objectives(self) -> List[Dict[str, Any]]:
        if not self._objectives:
            return [
                {
                    "id": "obj_001",
                    "title": "Reach $5M ARR",
                    "priority": ObjectivePriority.CRITICAL.value,
                    "deadline": "2026-12-31",
                },
                {
                    "id": "obj_002",
                    "title": "Launch 3 new levels",
                    "priority": ObjectivePriority.HIGH.value,
                    "deadline": "2026-09-30",
                },
            ]
        return self._objectives

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_decisions": len(self._decisions),
            "total_briefings": len(self._briefings),
            "total_objectives": len(self._objectives),
            "total_reviews": len(self._performance_reviews),
            "latest_health_score": self._company_status.health_score,
        }
