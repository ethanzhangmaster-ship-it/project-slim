from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AdRecommendation:
    recommendation_id: str
    ads: List[Dict[str, Any]] = field(default_factory=list)
    ecpms: Dict[str, float] = field(default_factory=dict)
    frequency_caps: Dict[str, int] = field(default_factory=dict)
    placements: List[str] = field(default_factory=list)


class AdOptimizer:
    def __init__(self):
        self.recommendations: Dict[str, AdRecommendation] = {}

    def optimize(self, genre: str, audience: str = "Female 25-44", **kwargs) -> AdRecommendation:
        retention_score = kwargs.get("retention_score", 0.5)
        ads = self._generate_ad_configuration(genre)
        ecpms = self._calculate_ecpms(genre, audience)
        frequency_caps = self._calculate_frequency_caps(genre)
        placements = self._determine_placements(genre)
        
        if retention_score > 0.7:
            frequency_caps["Reward Video"] += 5

        recommendation = AdRecommendation(
            recommendation_id=f"ad_{hash(genre + audience) % 10000:04d}",
            ads=ads,
            ecpms=ecpms,
            frequency_caps=frequency_caps,
            placements=placements,
        )

        self.recommendations[recommendation.recommendation_id] = recommendation
        return recommendation

    def _generate_ad_configuration(self, genre: str) -> List[Dict[str, Any]]:
        return [
            {
                "type": "Reward Video",
                "placement": "After Level Complete",
                "reward": "Energy Refill",
                "frequency": "Every 3 levels",
            },
            {
                "type": "Interstitial",
                "placement": "Between Levels",
                "frequency": "Every 180 seconds",
            },
            {
                "type": "Banner",
                "placement": "Bottom of Screen",
                "frequency": "Always",
            },
        ]

    def _calculate_ecpms(self, genre: str, audience: str) -> Dict[str, float]:
        ecpms = {
            "Reward Video": 12.0,
            "Interstitial": 8.0,
            "Banner": 1.5,
        }

        if "Female" in audience:
            ecpms["Reward Video"] *= 1.1
            ecpms["Interstitial"] *= 1.05

        return ecpms

    def _calculate_frequency_caps(self, genre: str) -> Dict[str, int]:
        return {
            "Reward Video": 10,
            "Interstitial": 5,
            "Banner": 0,
        }

    def _determine_placements(self, genre: str) -> List[str]:
        placements = ["After Level", "Between Levels", "Main Menu"]
        
        if "Merge" in genre:
            placements.append("After Merge")
        if "Decoration" in genre:
            placements.append("After Decoration")

        return placements

    def optimize_demo(self) -> AdRecommendation:
        return self.optimize("Merge + Decoration", "US Female 25-44")
