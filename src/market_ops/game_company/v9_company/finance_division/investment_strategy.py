from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class InvestmentRisk(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SPECULATIVE = "speculative"


@dataclass
class InvestmentOpportunity:
    opp_id: str
    name: str
    amount: float
    risk: InvestmentRisk
    expected_roi: float
    timeline_months: int

    def to_dict(self):
        return {
            "opp_id": self.opp_id,
            "name": self.name,
            "amount": self.amount,
            "risk": self.risk.value,
            "expected_roi": self.expected_roi,
            "timeline_months": self.timeline_months,
        }


@dataclass
class InvestmentPipeline:
    opportunities: List[InvestmentOpportunity]
    total_value: float

    def to_dict(self):
        return {
            "opportunities": [o.to_dict() for o in self.opportunities],
            "total_value": self.total_value,
        }


@dataclass
class ROIProjection:
    investment_id: str
    projected_roi: float
    best_case: float
    worst_case: float
    probability_success: float

    def to_dict(self):
        return {
            "investment_id": self.investment_id,
            "projected_roi": self.projected_roi,
            "best_case": self.best_case,
            "worst_case": self.worst_case,
            "probability_success": self.probability_success,
        }


class InvestmentStrategy:
    def __init__(self):
        self._opportunities: List[InvestmentOpportunity] = [
            InvestmentOpportunity(
                opp_id="inv_001",
                name="New Market Expansion",
                amount=500000.0,
                risk=InvestmentRisk.MEDIUM,
                expected_roi=0.25,
                timeline_months=12,
            ),
            InvestmentOpportunity(
                opp_id="inv_002",
                name="AI Integration",
                amount=300000.0,
                risk=InvestmentRisk.HIGH,
                expected_roi=0.40,
                timeline_months=8,
            ),
        ]
        self._evaluations: Dict[str, Dict] = {}

    def evaluate_investment(self, opportunity: InvestmentOpportunity) -> Dict:
        score = opportunity.expected_roi * 100
        if opportunity.risk == InvestmentRisk.LOW:
            score += 20
        elif opportunity.risk == InvestmentRisk.HIGH:
            score -= 10
        result = {
            "opportunity": opportunity.to_dict(),
            "score": score,
            "recommendation": "proceed" if score > 25 else "review",
        }
        self._evaluations[opportunity.opp_id] = result
        return result

    def get_investment_pipeline(self) -> InvestmentPipeline:
        total = sum(o.amount for o in self._opportunities)
        return InvestmentPipeline(
            opportunities=self._opportunities,
            total_value=total,
        )

    def prioritize_investments(self) -> List[InvestmentOpportunity]:
        return sorted(
            self._opportunities,
            key=lambda x: x.expected_roi,
            reverse=True,
        )

    def get_roi_projection(self, investment_id: str) -> Optional[ROIProjection]:
        opp = next((o for o in self._opportunities if o.opp_id == investment_id), None)
        if not opp:
            return None
        return ROIProjection(
            investment_id=investment_id,
            projected_roi=opp.expected_roi,
            best_case=opp.expected_roi * 1.5,
            worst_case=opp.expected_roi * 0.3,
            probability_success=0.75 if opp.risk != InvestmentRisk.SPECULATIVE else 0.45,
        )

    def get_stats(self) -> Dict:
        total = sum(o.amount for o in self._opportunities)
        avg_roi = sum(o.expected_roi for o in self._opportunities) / len(self._opportunities) if self._opportunities else 0.0
        return {
            "opportunity_count": len(self._opportunities),
            "total_value": total,
            "average_roi": avg_roi,
            "evaluations": len(self._evaluations),
        }
