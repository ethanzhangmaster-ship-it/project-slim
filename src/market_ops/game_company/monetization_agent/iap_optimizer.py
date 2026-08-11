from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class IAPRecommendation:
    recommendation_id: str
    products: List[Dict[str, Any]] = field(default_factory=list)
    conversion_rate: float = 0.0
    revenue_per_user: float = 0.0


class IAPOptimizer:
    def __init__(self):
        self.recommendations: Dict[str, IAPRecommendation] = {}

    def optimize(self, genre: str, audience: str = "Female 25-44", **kwargs) -> IAPRecommendation:
        target_ltv = kwargs.get("target_ltv", None)
        products = self._generate_products(genre, audience)
        conversion_rate = self._calculate_conversion_rate(audience)
        revenue_per_user = self._calculate_revenue(products, conversion_rate)
        
        if target_ltv:
            products = self._adjust_for_ltv(products, target_ltv, conversion_rate)

        recommendation = IAPRecommendation(
            recommendation_id=f"iap_{hash(genre + audience) % 10000:04d}",
            products=products,
            conversion_rate=round(conversion_rate, 2),
            revenue_per_user=round(revenue_per_user, 2),
        )

        self.recommendations[recommendation.recommendation_id] = recommendation
        return recommendation

    def _generate_products(self, genre: str, audience: str) -> List[Dict[str, Any]]:
        base_products = [
            {"name": "Starter Pack", "price": 4.99, "contents": ["500 Gems", "10000 Coins", "1 Energy Refill"]},
            {"name": "Small Gem Pack", "price": 0.99, "contents": ["100 Gems"]},
            {"name": "Medium Gem Pack", "price": 2.99, "contents": ["350 Gems"]},
            {"name": "Large Gem Pack", "price": 9.99, "contents": ["1000 Gems"]},
        ]

        if "Decoration" in genre:
            base_products.append({"name": "Decoration Bundle", "price": 7.99, "contents": ["Exclusive Decorations"]})
        
        if "35" in audience or "40" in audience:
            base_products.append({"name": "Monthly Pass", "price": 9.99, "contents": ["Daily Gems", "Double Rewards"]})

        return base_products

    def _calculate_conversion_rate(self, audience: str) -> float:
        base = 0.025
        
        if "Female" in audience:
            base += 0.01
        if "35" in audience or "40" in audience:
            base += 0.008
        
        return min(base, 0.05)

    def _calculate_revenue(self, products: List[Dict[str, Any]], conversion_rate: float) -> float:
        avg_price = sum(p["price"] for p in products) / len(products)
        return avg_price * conversion_rate

    def _adjust_for_ltv(self, products: List[Dict[str, Any]], target_ltv: float, conversion_rate: float) -> List[Dict[str, Any]]:
        adjusted = []
        for p in products:
            desired_price = target_ltv / conversion_rate / len(products)
            if p["price"] < desired_price * 0.5:
                p["price"] = round(p["price"] * 1.5, 2)
            adjusted.append(p)
        return adjusted

    def optimize_demo(self) -> IAPRecommendation:
        return self.optimize("Merge + Decoration", "US Female 25-44")
