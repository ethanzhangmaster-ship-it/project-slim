from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class RiskAssessment:
    assessment_id: str
    risks: List[Dict[str, Any]] = field(default_factory=list)
    overall_risk: str = "low"
    risk_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class RiskEngine:
    def __init__(self):
        self.assessments: Dict[str, RiskAssessment] = {}

    def assess(self, game_data: Dict[str, Any], market_data: Dict[str, Any]) -> RiskAssessment:
        risks = []
        
        risks.extend(self._assess_market_risks(market_data))
        risks.extend(self._assess_product_risks(game_data))
        risks.extend(self._assess_financial_risks(game_data))

        risk_score = self._calculate_risk_score(risks)
        overall_risk = self._determine_overall_risk(risk_score)
        recommendations = self._generate_recommendations(risks)

        assessment = RiskAssessment(
            assessment_id=f"risk_{hash(str(game_data)) % 10000:04d}",
            risks=risks,
            overall_risk=overall_risk,
            risk_score=round(risk_score, 2),
            recommendations=recommendations,
        )

        self.assessments[assessment.assessment_id] = assessment
        return assessment

    def _assess_market_risks(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        risks = []
        
        competition = market_data.get("competition", "medium")
        if competition == "high":
            risks.append({"type": "market", "level": "high", "description": "High market competition"})
        
        trend_score = market_data.get("trend_score", 50)
        if trend_score < 60:
            risks.append({"type": "market", "level": "medium", "description": "Low trend score"})
        
        return risks

    def _assess_product_risks(self, game_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        risks = []
        
        d30 = game_data.get("d30", 0.09)
        if d30 < 0.05:
            risks.append({"type": "product", "level": "high", "description": "Low retention predicted"})
        
        arpdau = game_data.get("arpdau", 0.15)
        if arpdau < 0.1:
            risks.append({"type": "product", "level": "medium", "description": "Low ARPDAU predicted"})
        
        return risks

    def _assess_financial_risks(self, game_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        risks = []
        
        payback = game_data.get("payback_days", 180)
        if payback > 180:
            risks.append({"type": "financial", "level": "high", "description": "Long payback period"})
        
        roi = game_data.get("roi", 0)
        if roi < 50:
            risks.append({"type": "financial", "level": "medium", "description": "Low ROI predicted"})
        
        return risks

    def _calculate_risk_score(self, risks: List[Dict[str, Any]]) -> float:
        score = 0
        for risk in risks:
            if risk["level"] == "high":
                score += 30
            elif risk["level"] == "medium":
                score += 15
        return min(score, 100)

    def _determine_overall_risk(self, score: float) -> str:
        if score >= 60:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    def _generate_recommendations(self, risks: List[Dict[str, Any]]) -> List[str]:
        recommendations = []
        
        for risk in risks:
            if risk["type"] == "market" and risk["level"] == "high":
                recommendations.append("Differentiate from competitors")
            if risk["type"] == "product" and risk["level"] == "high":
                recommendations.append("Improve retention mechanics")
            if risk["type"] == "financial" and risk["level"] == "high":
                recommendations.append("Reduce budget or find cheaper UA channels")
        
        if not recommendations:
            recommendations.append("Low risk, proceed with launch")
        
        return recommendations

    def assess_demo(self) -> RiskAssessment:
        game_data = {"d30": 0.09, "arpdau": 0.15, "payback_days": 90, "roi": 80}
        market_data = {"competition": "medium", "trend_score": 85}
        return self.assess(game_data, market_data)
