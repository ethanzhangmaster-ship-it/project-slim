from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class DecisionScore:
    revenue_impact: float = 0.0
    strategic_fit: float = 0.0
    risk_adjustment: float = 0.0
    confidence: float = 0.0
    total_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revenue_impact": self.revenue_impact,
            "strategic_fit": self.strategic_fit,
            "risk_adjustment": self.risk_adjustment,
            "confidence": self.confidence,
            "total_score": self.total_score,
        }


@dataclass
class ScoredDecision:
    decision_name: str = ""
    score: DecisionScore = field(default_factory=DecisionScore)
    risk_level: str = "medium"
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_name": self.decision_name,
            "score": self.score.to_dict(),
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
        }


class DecisionEngine:
    def __init__(self):
        self._scored_decisions: List[ScoredDecision] = []

    def score_decision(self, decision_data: Dict[str, Any]) -> DecisionScore:
        revenue_impact = decision_data.get("revenue_impact", 0.0)
        strategic_fit = decision_data.get("strategic_fit", 0.0)
        risk_adjustment = decision_data.get("risk_adjustment", 0.0)
        confidence = decision_data.get("confidence", 0.5)

        total_score = (revenue_impact * 0.4 + strategic_fit * 0.3 +
                       risk_adjustment * 0.2 + confidence * 0.1)

        return DecisionScore(
            revenue_impact=revenue_impact,
            strategic_fit=strategic_fit,
            risk_adjustment=risk_adjustment,
            confidence=confidence,
            total_score=round(total_score, 4),
        )

    def evaluate(self, options: List[Dict[str, Any]]) -> List[ScoredDecision]:
        decisions = []
        for opt in options:
            score = self.score_decision(opt)
            decision = ScoredDecision(
                decision_name=opt.get("name", "unknown"),
                score=score,
                risk_level=opt.get("risk_level", "medium"),
                recommendation=opt.get("recommendation", ""),
            )
            decisions.append(decision)
        self._scored_decisions.extend(decisions)
        return decisions

    def rank(self, decisions: List[ScoredDecision]) -> List[ScoredDecision]:
        return sorted(decisions, key=lambda d: d.score.total_score, reverse=True)
