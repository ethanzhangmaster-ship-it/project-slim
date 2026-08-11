from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class MarketInsight:
    insight_id: str
    topic: str
    impact: str
    confidence: float
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class MarketStrategy:
    def __init__(self):
        self.market_data = {
            "meta": {"trend": "up", "competition": "high", "opportunity": 0.75},
            "google": {"trend": "stable", "competition": "medium", "opportunity": 0.65},
            "tiktok": {"trend": "up", "competition": "low", "opportunity": 0.85},
            "asa": {"trend": "stable", "competition": "high", "opportunity": 0.6},
        }

    def analyze(self, data: Dict[str, Any]) -> List[MarketInsight]:
        insights = []

        platform = data.get("platform", "")
        if platform and platform in self.market_data:
            platform_data = self.market_data[platform]
            
            if platform_data["trend"] == "up" and platform_data["opportunity"] > 0.7:
                insights.append(MarketInsight(
                    insight_id=f"insight_{hash(platform)}_001",
                    topic=f"{platform} Growth Opportunity",
                    impact="positive",
                    confidence=platform_data["opportunity"],
                    recommendations=[
                        f"Increase budget on {platform}",
                        f"Expand creative testing on {platform}",
                    ],
                ))

            if platform_data["competition"] == "high":
                insights.append(MarketInsight(
                    insight_id=f"insight_{hash(platform)}_002",
                    topic=f"{platform} Competition",
                    impact="negative",
                    confidence=0.85,
                    recommendations=[
                        "Focus on creative differentiation",
                        "Optimize bids carefully",
                    ],
                ))

        country = data.get("country", "")
        if country == "US":
            insights.append(MarketInsight(
                insight_id="insight_us_001",
                topic="US Market Saturation",
                impact="neutral",
                confidence=0.75,
                recommendations=[
                    "Explore tier 2 countries",
                    "Target niche segments",
                ],
            ))

        return insights

    def analyze_demo(self) -> List[MarketInsight]:
        data = {"platform": "tiktok", "country": "US"}
        return self.analyze(data)
