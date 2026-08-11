from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class OpportunityResult:
    opportunity_id: str
    genre: str
    region: str
    audience: str
    competition: str
    keyword_gap: float = 0.0
    opportunity_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0


class OpportunityScore:
    def __init__(self):
        self.opportunities: List[OpportunityResult] = []

    def score(self, market_data: Dict[str, Any]) -> OpportunityResult:
        genre = market_data.get("genre", "")
        region = market_data.get("region", "US")
        audience = market_data.get("audience", "Female 25-44")
        competition_level = market_data.get("competition", "medium")
        trend_score = market_data.get("trend_score", 50)
        keyword_gap = market_data.get("keyword_gap", 50)

        score = self._calculate_score(trend_score, keyword_gap, competition_level)
        recommendations = self._generate_recommendations(genre, score)
        confidence = self._calculate_confidence(market_data)

        result = OpportunityResult(
            opportunity_id=f"opp_{hash(genre + region) % 10000:04d}",
            genre=genre,
            region=region,
            audience=audience,
            competition=competition_level,
            keyword_gap=keyword_gap,
            opportunity_score=round(score, 1),
            recommendations=recommendations,
            confidence=round(confidence, 2),
        )

        self.opportunities.append(result)
        return result

    def _calculate_score(self, trend_score: float, keyword_gap, competition: str) -> float:
        if isinstance(keyword_gap, str):
            gap_map = {"high": 80, "medium": 50, "low": 20}
            keyword_gap = gap_map.get(keyword_gap, 50)
        elif not isinstance(keyword_gap, (int, float)):
            keyword_gap = 50
        
        score = trend_score * 0.4 + keyword_gap * 0.3
        
        competition_bonus = {
            "low": 20,
            "medium": 10,
            "high": -5,
        }
        
        score += competition_bonus.get(competition, 0)
        
        return min(score, 100)

    def rank(self, opportunities: List[Dict[str, Any]]) -> List[OpportunityResult]:
        results = []
        for opp in opportunities:
            result = self.score(opp)
            results.append(result)
        return sorted(results, key=lambda x: x.opportunity_score, reverse=True)

    def _generate_recommendations(self, genre: str, score: float) -> List[str]:
        recommendations = []
        
        if score > 80:
            recommendations.append(f"Increase budget for {genre}")
            recommendations.append("Prioritize creative production")
            recommendations.append("Start UA testing immediately")
        elif score > 60:
            recommendations.append(f"Monitor {genre} closely")
            recommendations.append("Prepare creative assets")
        else:
            recommendations.append("Consider alternative genres")
            recommendations.append("Wait for better timing")
        
        return recommendations

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        keyword_gap = data.get("keyword_gap", 50)
        if isinstance(keyword_gap, str):
            gap_map = {"high": 80, "medium": 50, "low": 20}
            keyword_gap = gap_map.get(keyword_gap, 50)
        
        factors = [
            data.get("trend_score", 50) / 100,
            keyword_gap / 100,
            0.7 if data.get("competition") == "medium" else 0.5,
        ]
        return sum(factors) / len(factors)

    def get_top_opportunities(self, threshold: float = 70) -> List[OpportunityResult]:
        return sorted(
            [o for o in self.opportunities if o.opportunity_score >= threshold],
            key=lambda x: x.opportunity_score,
            reverse=True,
        )

    def score_demo(self) -> OpportunityResult:
        market_data = {
            "genre": "Merge + Decoration",
            "region": "US",
            "audience": "Female 25-44",
            "competition": "medium",
            "trend_score": 85,
            "keyword_gap": 80,
        }
        return self.score(market_data)
