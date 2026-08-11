from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class MonetizationType(Enum):
    IAP = "iap"
    SUBSCRIPTION = "subscription"
    ADS = "ads"
    HYBRID = "hybrid"


class PricingTier(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


@dataclass
class MonetizationMetrics:
    date: str
    total_revenue: float = 0.0
    iap_revenue: float = 0.0
    subscription_revenue: float = 0.0
    ad_revenue: float = 0.0
    arpu: float = 0.0
    arppu: float = 0.0
    payer_ratio: float = 0.0
    conversion_rate: float = 0.0
    subscription_conversion: float = 0.0
    avg_purchase_amount: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "total_revenue": self.total_revenue,
            "iap_revenue": self.iap_revenue,
            "subscription_revenue": self.subscription_revenue,
            "ad_revenue": self.ad_revenue,
            "arpu": self.arpu,
            "arppu": self.arppu,
            "payer_ratio": self.payer_ratio,
            "conversion_rate": self.conversion_rate,
            "subscription_conversion": self.subscription_conversion,
            "avg_purchase_amount": self.avg_purchase_amount,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ProductItem:
    item_id: str
    name: str
    price: float
    tier: PricingTier
    category: str = ""
    purchases: int = 0
    revenue: float = 0.0
    conversion_rate: float = 0.0
    popularity_rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "price": self.price,
            "tier": self.tier.value,
            "category": self.category,
            "purchases": self.purchases,
            "revenue": self.revenue,
            "conversion_rate": self.conversion_rate,
            "popularity_rank": self.popularity_rank,
        }


@dataclass
class MonetizationRecommendation:
    recommendation_id: str
    type: MonetizationType
    action: str
    expected_revenue_impact: float = 0.0
    confidence: float = 0.0
    priority: int = 5
    description: str = ""
    affected_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "type": self.type.value,
            "action": self.action,
            "expected_revenue_impact": self.expected_revenue_impact,
            "confidence": self.confidence,
            "priority": self.priority,
            "description": self.description,
            "affected_items": self.affected_items,
        }


class MonetizationOptimizer:
    def __init__(self):
        self._metrics: Dict[str, MonetizationMetrics] = {}
        self._items: Dict[str, ProductItem] = {}
        self._recommendations: List[MonetizationRecommendation] = []
        self._pricing_config: Dict[str, Any] = {}
        self._targets = {
            "arpu": 2.0,
            "payer_ratio": 0.05,
            "iap_conversion": 0.03,
        }

    def record_metrics(
        self,
        date: str,
        total_revenue: float = None,
        iap_revenue: float = None,
        subscription_revenue: float = None,
        ad_revenue: float = None
    ) -> MonetizationMetrics:
        metrics = MonetizationMetrics(
            date=date,
            total_revenue=total_revenue or random.uniform(5000, 50000),
            iap_revenue=iap_revenue or random.uniform(2000, 30000),
            subscription_revenue=subscription_revenue or random.uniform(1000, 15000),
            ad_revenue=ad_revenue or random.uniform(500, 5000),
            arpu=random.uniform(1.0, 5.0),
            arppu=random.uniform(10.0, 50.0),
            payer_ratio=random.uniform(0.02, 0.1),
            conversion_rate=random.uniform(0.01, 0.05),
            subscription_conversion=random.uniform(0.005, 0.02),
            avg_purchase_amount=random.uniform(5.0, 30.0),
        )
        self._metrics[date] = metrics
        return metrics

    def register_item(
        self,
        item_id: str,
        name: str,
        price: float,
        tier: PricingTier,
        category: str = ""
    ) -> ProductItem:
        item = ProductItem(
            item_id=item_id,
            name=name,
            price=price,
            tier=tier,
            category=category,
            purchases=random.randint(100, 5000),
            revenue=random.uniform(1000, 50000),
            conversion_rate=random.uniform(0.01, 0.1),
            popularity_rank=random.randint(1, 20),
        )
        self._items[item_id] = item
        return item

    def optimize_monetization(self) -> List[MonetizationRecommendation]:
        recommendations = []

        recent_metrics = list(self._metrics.values())[-7:]
        if recent_metrics:
            avg_arpu = sum(m.arpu for m in recent_metrics) / len(recent_metrics)
            avg_payer_ratio = sum(m.payer_ratio for m in recent_metrics) / len(recent_metrics)

            if avg_arpu < self._targets["arpu"]:
                rec = MonetizationRecommendation(
                    recommendation_id=f"rec_arpu_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    type=MonetizationType.HYBRID,
                    action="increase_arpu",
                    expected_revenue_impact=random.uniform(0.1, 0.3),
                    confidence=0.8,
                    priority=1,
                    description=f"ARPU ({avg_arpu:.2f}) below target - optimize pricing",
                )
                recommendations.append(rec)

            if avg_payer_ratio < self._targets["payer_ratio"]:
                rec = MonetizationRecommendation(
                    recommendation_id=f"rec_payer_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    type=MonetizationType.IAP,
                    action="improve_conversion",
                    expected_revenue_impact=random.uniform(0.05, 0.15),
                    confidence=0.75,
                    priority=2,
                    description=f"Payer ratio ({avg_payer_ratio:.2%}) below target - improve offers",
                )
                recommendations.append(rec)

        for item_id, item in self._items.items():
            if item.conversion_rate < 0.02 and item.tier != PricingTier.PREMIUM:
                rec = MonetizationRecommendation(
                    recommendation_id=f"rec_item_{item_id}",
                    type=MonetizationType.IAP,
                    action="adjust_price",
                    expected_revenue_impact=item.revenue * 0.1,
                    confidence=0.7,
                    priority=3,
                    description=f"Item '{item.name}' has low conversion - consider price adjustment",
                    affected_items=[item_id],
                )
                recommendations.append(rec)

            if item.popularity_rank > 15 and item.conversion_rate > 0.05:
                rec = MonetizationRecommendation(
                    recommendation_id=f"rec_promote_{item_id}",
                    type=MonetizationType.IAP,
                    action="promote_item",
                    expected_revenue_impact=item.revenue * 0.15,
                    confidence=0.85,
                    priority=2,
                    description=f"High-converting item '{item.name}' should be promoted",
                    affected_items=[item_id],
                )
                recommendations.append(rec)

        self._recommendations.extend(recommendations)
        return recommendations

    def analyze_pricing(self) -> Dict[str, Any]:
        analysis = {
            "items_by_tier": {},
            "tier_performance": {},
            "pricing_recommendations": [],
        }

        for tier in PricingTier:
            tier_items = [i for i in self._items.values() if i.tier == tier]
            analysis["items_by_tier"][tier.value] = len(tier_items)

            if tier_items:
                avg_revenue = sum(i.revenue for i in tier_items) / len(tier_items)
                avg_conversion = sum(i.conversion_rate for i in tier_items) / len(tier_items)
                analysis["tier_performance"][tier.value] = {
                    "avg_revenue": avg_revenue,
                    "avg_conversion": avg_conversion,
                    "best_item": max(tier_items, key=lambda i: i.revenue).name if tier_items else None,
                }

        return analysis

    def get_metrics(self, date: str = None) -> List[MonetizationMetrics]:
        if date:
            return [self._metrics.get(date)] if date in self._metrics else []
        return list(self._metrics.values())

    def get_item(self, item_id: str) -> Optional[ProductItem]:
        return self._items.get(item_id)

    def get_all_items(self) -> List[ProductItem]:
        return list(self._items.values())

    def get_top_items(self, limit: int = 10) -> List[ProductItem]:
        return sorted(self._items.values(), key=lambda i: i.revenue, reverse=True)[:limit]

    def get_recommendations(self) -> List[MonetizationRecommendation]:
        return list(self._recommendations)

    def update_item_performance(self, item_id: str, purchases: int, revenue: float) -> Optional[ProductItem]:
        item = self._items.get(item_id)
        if item:
            item.purchases = purchases
            item.revenue = revenue
            item.conversion_rate = purchases / max(1, purchases * 10)
        return item

    def get_stats(self) -> Dict[str, Any]:
        metrics = list(self._metrics.values())
        items = list(self._items.values())
        return {
            "total_metrics_records": len(metrics),
            "total_items": len(items),
            "items_by_tier": {
                tier.value: sum(1 for i in items if i.tier == tier)
                for tier in PricingTier
            },
            "total_recommendations": len(self._recommendations),
            "current_targets": self._targets,
            "average_arpu": sum(m.arpu for m in metrics) / len(metrics) if metrics else 0,
        }