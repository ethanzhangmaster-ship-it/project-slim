from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class PricingRecommendation:
    recommendation_id: str
    prices: Dict[str, float] = field(default_factory=dict)
    regions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    tier_pricing: List[float] = field(default_factory=list)


class PricingAgent:
    def __init__(self):
        self.recommendations: Dict[str, PricingRecommendation] = {}

    def price(self, genre: str, regions: List[str] = None) -> Dict[str, Dict[str, float]]:
        if regions is None:
            regions = ["US"]
        
        base_prices = self._generate_base_prices(genre)
        result = {}
        
        for region in regions:
            if region in ["US", "CA"]:
                result[region] = base_prices.copy()
            elif region in ["JP", "KR"]:
                result[region] = {k: round(v * 1.1, 2) for k, v in base_prices.items()}
            elif region in ["DE", "GB", "FR"]:
                result[region] = {k: round(v * 0.9, 2) for k, v in base_prices.items()}
            elif region in ["BR", "IN", "ID"]:
                result[region] = {k: round(v * 0.5, 2) for k, v in base_prices.items()}
            else:
                result[region] = base_prices.copy()
        
        return result

    def recommend(self, genre: str, audience: str) -> PricingRecommendation:
        tier_pricing = self._generate_tier_pricing()
        prices = self._generate_base_prices(genre)
        regions = self._generate_region_prices(prices)

        recommendation = PricingRecommendation(
            recommendation_id=f"price_{hash(genre + audience) % 10000:04d}",
            prices=prices,
            regions=regions,
            tier_pricing=tier_pricing,
        )

        self.recommendations[recommendation.recommendation_id] = recommendation
        return recommendation

    def _generate_tier_pricing(self) -> List[float]:
        return [0.99, 1.99, 2.99, 4.99, 7.99, 9.99, 14.99, 19.99]

    def _generate_base_prices(self, genre: str) -> Dict[str, float]:
        prices = {
            "Starter Pack": 4.99,
            "Small": 0.99,
            "Medium": 2.99,
            "Large": 9.99,
            "Monthly Pass": 9.99,
        }

        if "Premium" in genre or "Strategy" in genre:
            for key in prices:
                prices[key] *= 1.2

        return prices

    def _generate_region_prices(self, base_prices: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        regions = {
            "US": base_prices,
            "EU": {k: v * 0.9 for k, v in base_prices.items()},
            "JP": {k: round(v * 1.1, 2) for k, v in base_prices.items()},
            "CN": {k: round(v * 0.7, 2) for k, v in base_prices.items()},
        }
        return regions

    def recommend_demo(self) -> PricingRecommendation:
        return self.recommend("Merge + Decoration", "US Female 25-44")
