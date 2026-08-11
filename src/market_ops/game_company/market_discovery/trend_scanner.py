from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class MarketTrend:
    trend_id: str
    platform: str
    genre: str
    trend_score: float = 0.0
    growth_rate: float = 0.0
    volume: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class TrendScanner:
    def __init__(self):
        self.trends: List[MarketTrend] = []

    def scan(self, sources: List[str] = None) -> List[MarketTrend]:
        if sources is None:
            sources = ["app_store", "google_play", "meta_ads", "tiktok", "reddit"]
        
        new_trends = []
        
        for source in sources:
            source_trends = self._scan_source(source)
            new_trends.extend(source_trends)
        
        self.trends.extend(new_trends)
        return new_trends

    def _scan_source(self, source: str) -> List[MarketTrend]:
        trend_map = {
            "app_store": [
                {"genre": "Merge + Decoration", "score": 85, "growth": 0.35, "volume": 500000},
                {"genre": "Cozy Games", "score": 78, "growth": 0.28, "volume": 350000},
                {"genre": "Puzzle RPG", "score": 72, "growth": 0.22, "volume": 400000},
            ],
            "google_play": [
                {"genre": "Merge + Decoration", "score": 82, "growth": 0.32, "volume": 450000},
                {"genre": "Idle RPG", "score": 75, "growth": 0.25, "volume": 600000},
            ],
            "meta_ads": [
                {"genre": "Merge + Decoration", "score": 88, "growth": 0.4, "volume": 800000},
                {"genre": "Casual Strategy", "score": 70, "growth": 0.18, "volume": 300000},
            ],
            "tiktok": [
                {"genre": "Cozy Witch", "score": 90, "growth": 0.5, "volume": 200000},
                {"genre": "Merge + Story", "score": 80, "growth": 0.3, "volume": 250000},
            ],
            "reddit": [
                {"genre": "Cozy Games", "score": 85, "growth": 0.38, "volume": 150000},
                {"genre": "Merge Puzzle", "score": 78, "growth": 0.28, "volume": 120000},
            ],
        }
        
        trends = trend_map.get(source, [])
        return [
            MarketTrend(
                trend_id=f"{source}_{hash(genre['genre']) % 1000:03d}",
                platform=source,
                genre=genre["genre"],
                trend_score=genre["score"],
                growth_rate=genre["growth"],
                volume=genre["volume"],
            )
            for genre in trends
        ]

    def get_trends(self) -> List[MarketTrend]:
        return self.trends
    
    def get_trends_by_type(self, trend_type: str) -> List[MarketTrend]:
        return [t for t in self.trends if trend_type.lower() in t.genre.lower()]
    
    def get_hot_genres(self, top_n: int = 5) -> List[Dict[str, Any]]:
        genre_scores = {}
        
        for trend in self.trends:
            if trend.genre not in genre_scores:
                genre_scores[trend.genre] = {"score": 0, "count": 0, "growth": 0}
            genre_scores[trend.genre]["score"] += trend.trend_score
            genre_scores[trend.genre]["count"] += 1
            genre_scores[trend.genre]["growth"] += trend.growth_rate
        
        results = []
        for genre, data in genre_scores.items():
            results.append({
                "genre": genre,
                "avg_score": round(data["score"] / data["count"], 1),
                "avg_growth": round(data["growth"] / data["count"], 2),
                "sources": data["count"],
            })
        
        return sorted(results, key=lambda x: x["avg_score"], reverse=True)[:top_n]

    def scan_demo(self) -> List[MarketTrend]:
        return self.scan(["app_store", "meta_ads", "tiktok"])
