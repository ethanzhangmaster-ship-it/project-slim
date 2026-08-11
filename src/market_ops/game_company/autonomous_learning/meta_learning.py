from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class LearningInsight:
    insight_id: str
    category: str
    insight: str
    supporting_data: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class MetaLearning:
    def __init__(self):
        self.insights: Dict[str, LearningInsight] = {}

    def learn(self, project_history: List[Dict[str, Any]]) -> List[LearningInsight]:
        insights = []
        
        insights.extend(self._learn_game_types(project_history))
        insights.extend(self._learn_market_trends(project_history))
        insights.extend(self._learn_monetization_patterns(project_history))
        
        for insight in insights:
            self.insights[insight.insight_id] = insight
        
        return insights

    def _learn_game_types(self, history: List[Dict[str, Any]]) -> List[LearningInsight]:
        insights = []
        genre_success = {}
        
        for project in history:
            genre = project.get("genre", "Unknown")
            success = project.get("success", False)
            if genre not in genre_success:
                genre_success[genre] = {"total": 0, "success": 0}
            genre_success[genre]["total"] += 1
            if success:
                genre_success[genre]["success"] += 1

        for genre, stats in genre_success.items():
            rate = stats["success"] / stats["total"]
            if rate > 0.6:
                insight = LearningInsight(
                    insight_id=f"insight_genre_{hash(genre) % 10000:04d}",
                    category="game_type",
                    insight=f"{genre} games have high success rate: {rate:.1%}",
                    supporting_data=[{"genre": genre, "success_rate": rate}],
                    confidence=min(rate, 0.9),
                )
                insights.append(insight)
        
        return insights

    def _learn_market_trends(self, history: List[Dict[str, Any]]) -> List[LearningInsight]:
        insights = []
        region_performance = {}
        
        for project in history:
            regions = project.get("regions", ["US"])
            revenue = project.get("revenue", 0)
            for region in regions:
                if region not in region_performance:
                    region_performance[region] = {"count": 0, "total_revenue": 0}
                region_performance[region]["count"] += 1
                region_performance[region]["total_revenue"] += revenue

        top_regions = sorted(
            region_performance.items(),
            key=lambda x: x[1]["total_revenue"] / x[1]["count"],
            reverse=True
        )[:3]

        for region, stats in top_regions:
            avg_revenue = stats["total_revenue"] / stats["count"]
            insight = LearningInsight(
                insight_id=f"insight_region_{hash(region) % 10000:04d}",
                category="market",
                insight=f"{region} shows strong revenue potential: ${avg_revenue:,.0f} avg",
                supporting_data=[{"region": region, "avg_revenue": avg_revenue}],
                confidence=0.75,
            )
            insights.append(insight)
        
        return insights

    def _learn_monetization_patterns(self, history: List[Dict[str, Any]]) -> List[LearningInsight]:
        insights = []
        arpdau_by_type = {}
        
        for project in history:
            genre = project.get("genre", "Unknown")
            arpdau = project.get("arpdau", 0)
            if genre not in arpdau_by_type:
                arpdau_by_type[genre] = []
            arpdau_by_type[genre].append(arpdau)

        for genre, arpdaus in arpdau_by_type.items():
            avg_arpdau = sum(arpdaus) / len(arpdaus)
            if avg_arpdau > 0.2:
                insight = LearningInsight(
                    insight_id=f"insight_arpdau_{hash(genre) % 10000:04d}",
                    category="monetization",
                    insight=f"{genre} games achieve high ARPDAU: ${avg_arpdau:.2f}",
                    supporting_data=[{"genre": genre, "avg_arpdau": avg_arpdau}],
                    confidence=0.7,
                )
                insights.append(insight)
        
        return insights

    def learn_demo(self) -> List[LearningInsight]:
        history = [
            {"genre": "Merge", "success": True, "regions": ["US"], "revenue": 100000, "arpdau": 0.25},
            {"genre": "Merge", "success": True, "regions": ["US", "UK"], "revenue": 80000, "arpdau": 0.22},
            {"genre": "Match 3", "success": False, "regions": ["US"], "revenue": 30000, "arpdau": 0.12},
            {"genre": "Simulation", "success": True, "regions": ["DE"], "revenue": 60000, "arpdau": 0.30},
            {"genre": "Merge", "success": True, "regions": ["JP"], "revenue": 90000, "arpdau": 0.28},
        ]
        return self.learn(history)
