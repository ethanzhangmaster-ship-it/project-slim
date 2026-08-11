from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class CreativeStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    FATIGUED = "fatigued"
    WINNER = "winner"


@dataclass
class CreativePerformance:
    creative_id: str
    name: str
    status: CreativeStatus = CreativeStatus.ACTIVE
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    roas: float = 0.0
    cpi: float = 0.0
    first_seen: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "name": self.name,
            "status": self.status.value,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": self.spend,
            "revenue": self.revenue,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "roas": self.roas,
            "cpi": self.cpi,
            "first_seen": self.first_seen.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class CreativeAnalysis:
    creative_id: str
    performance: CreativePerformance
    score: float = 0.0
    trend: str = "stable"
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "performance": self.performance.to_dict(),
            "score": self.score,
            "trend": self.trend,
            "insights": self.insights,
            "recommendations": self.recommendations,
        }


@dataclass
class CreativeElement:
    element_type: str
    value: str
    performance_impact: float = 0.0
    win_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_type": self.element_type,
            "value": self.value,
            "performance_impact": self.performance_impact,
            "win_rate": self.win_rate,
        }


class CreativeAnalyzer:
    def __init__(self):
        self._creatives: Dict[str, CreativePerformance] = {}
        self._analyses: Dict[str, CreativeAnalysis] = {}
        self._winning_elements: List[CreativeElement] = []

    def register_creative(self, creative_id: str, name: str, **kwargs) -> CreativePerformance:
        performance = CreativePerformance(
            creative_id=creative_id,
            name=name,
            **{k: v for k, v in kwargs.items() if hasattr(CreativePerformance, k)}
        )
        self._creatives[creative_id] = performance
        return performance

    def analyze_creative(self, creative_id: str) -> Optional[CreativeAnalysis]:
        performance = self._creatives.get(creative_id)
        if not performance:
            return None

        score = self._calculate_score(performance)
        trend = self._determine_trend(performance)
        insights = self._generate_insights(performance)
        recommendations = self._generate_recommendations(performance, score)

        analysis = CreativeAnalysis(
            creative_id=creative_id,
            performance=performance,
            score=score,
            trend=trend,
            insights=insights,
            recommendations=recommendations,
        )
        self._analyses[creative_id] = analysis
        return analysis

    def _calculate_score(self, performance: CreativePerformance) -> float:
        score = 0.0
        if performance.roas > 2.0:
            score += 40
        elif performance.roas > 1.5:
            score += 30
        elif performance.roas > 1.0:
            score += 20
        elif performance.roas > 0.5:
            score += 10

        if performance.ctr > 0.05:
            score += 20
        elif performance.ctr > 0.03:
            score += 15
        elif performance.ctr > 0.01:
            score += 10

        if performance.cvr > 0.1:
            score += 20
        elif performance.cvr > 0.05:
            score += 15
        elif performance.cvr > 0.02:
            score += 10

        if performance.impressions > 100000:
            score += 20
        elif performance.impressions > 50000:
            score += 15
        elif performance.impressions > 10000:
            score += 10

        return min(100, score)

    def _determine_trend(self, performance: CreativePerformance) -> str:
        if performance.roas > 1.5 and performance.ctr > 0.03:
            return "rising"
        elif performance.roas < 0.8 or performance.ctr < 0.01:
            return "declining"
        return "stable"

    def _generate_insights(self, performance: CreativePerformance) -> List[str]:
        insights = []
        if performance.roas > 2.0:
            insights.append("Excellent ROAS performance - strong candidate for scaling")
        if performance.ctr > 0.05:
            insights.append("High CTR indicates strong creative appeal")
        if performance.cvr > 0.1:
            insights.append("Excellent conversion rate - landing page is effective")
        if performance.roas < 0.8:
            insights.append("ROAS below target - consider pausing or optimizing")
        if performance.ctr < 0.01:
            insights.append("Low CTR - creative may need refresh")
        return insights

    def _generate_recommendations(self, performance: CreativePerformance, score: float) -> List[str]:
        recommendations = []
        if score >= 80:
            recommendations.append("Scale budget by 30-50%")
            recommendations.append("Use as template for new creatives")
        elif score >= 60:
            recommendations.append("Continue monitoring performance")
            recommendations.append("Consider minor optimizations")
        elif score >= 40:
            recommendations.append("Test variations of this creative")
            recommendations.append("Review targeting settings")
        else:
            recommendations.append("Consider pausing this creative")
            recommendations.append("Analyze what's not working")
        return recommendations

    def get_performance(self, creative_id: str) -> Optional[CreativePerformance]:
        return self._creatives.get(creative_id)

    def compare_creatives(self, creative_ids: List[str]) -> Dict[str, Any]:
        comparisons = {}
        for cid in creative_ids:
            if cid in self._creatives:
                perf = self._creatives[cid]
                comparisons[cid] = {
                    "creative_id": cid,
                    "roas": perf.roas,
                    "ctr": perf.ctr,
                    "cvr": perf.cvr,
                    "score": self._calculate_score(perf),
                }

        if comparisons:
            sorted_by_roas = sorted(comparisons.items(), key=lambda x: x[1]["roas"], reverse=True)
            sorted_by_score = sorted(comparisons.items(), key=lambda x: x[1]["score"], reverse=True)
            return {
                "comparisons": comparisons,
                "ranked_by_roas": [c[0] for c in sorted_by_roas],
                "ranked_by_score": [c[0] for c in sorted_by_score],
                "best_performer": sorted_by_score[0][0] if sorted_by_score else None,
            }
        return {"comparisons": {}, "ranked_by_roas": [], "ranked_by_score": [], "best_performer": None}

    def get_winning_elements(self, min_performance_impact: float = 0.1) -> List[CreativeElement]:
        winning = [e for e in self._winning_elements if e.performance_impact >= min_performance_impact]
        return sorted(winning, key=lambda x: x.performance_impact, reverse=True)

    def add_winning_element(self, element_type: str, value: str, performance_impact: float, win_rate: float) -> CreativeElement:
        element = CreativeElement(
            element_type=element_type,
            value=value,
            performance_impact=performance_impact,
            win_rate=win_rate,
        )
        self._winning_elements.append(element)
        return element

    def get_all_creatives(self) -> List[CreativePerformance]:
        return list(self._creatives.values())

    def get_top_performers(self, limit: int = 10) -> List[CreativePerformance]:
        creatives = list(self._creatives.values())
        return sorted(creatives, key=lambda c: c.roas, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._creatives)
        active = sum(1 for c in self._creatives.values() if c.status == CreativeStatus.ACTIVE)
        winners = sum(1 for c in self._creatives.values() if c.status == CreativeStatus.WINNER)
        avg_roas = sum(c.roas for c in self._creatives.values()) / total if total > 0 else 0
        avg_ctr = sum(c.ctr for c in self._creatives.values()) / total if total > 0 else 0
        return {
            "total_creatives": total,
            "active_creatives": active,
            "winning_creatives": winners,
            "average_roas": avg_roas,
            "average_ctr": avg_ctr,
            "total_analyses": len(self._analyses),
            "winning_elements": len(self._winning_elements),
        }