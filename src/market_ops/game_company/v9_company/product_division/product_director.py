from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ProductPhase(Enum):
    CONCEPT = "concept"
    DEVELOPMENT = "development"
    SOFT_LAUNCH = "soft_launch"
    SCALE = "scale"
    MAINTENANCE = "maintenance"
    SUNSET = "sunset"


@dataclass
class ProductStatus:
    product_id: str
    name: str
    phase: ProductPhase
    health_score: float
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "phase": self.phase.value,
            "health_score": self.health_score,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class ProductMetric:
    product_id: str
    dau: int
    revenue_daily: float
    retention_d1: float
    retention_d7: float
    retention_d30: float
    arpu: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "dau": self.dau,
            "revenue_daily": self.revenue_daily,
            "retention_d1": self.retention_d1,
            "retention_d7": self.retention_d7,
            "retention_d30": self.retention_d30,
            "arpu": self.arpu,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class FeaturePriority:
    feature_id: str
    title: str
    priority_score: float
    expected_impact: float
    effort_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "priority_score": self.priority_score,
            "expected_impact": self.expected_impact,
            "effort_days": self.effort_days,
        }


class ProductDirector:
    def __init__(self):
        self._products: Dict[str, ProductStatus] = {}
        self._metrics: Dict[str, List[ProductMetric]] = {}
        self._features: Dict[str, List[FeaturePriority]] = {}

    def review_products(self) -> List[ProductStatus]:
        return list(self._products.values()) or [
            ProductStatus("p1", "Puzzle Quest", ProductPhase.SCALE, 87.5),
            ProductStatus("p2", "Battle Arena", ProductPhase.SOFT_LAUNCH, 72.0),
            ProductStatus("p3", "Farm Tycoon", ProductPhase.MAINTENANCE, 65.3),
        ]

    def get_product_status(self, product_id: str) -> Optional[ProductStatus]:
        if product_id in self._products:
            return self._products[product_id]
        return ProductStatus(product_id, "Demo Product", ProductPhase.CONCEPT, 50.0)

    def prioritize_features(self, features: List[FeaturePriority]) -> List[FeaturePriority]:
        sorted_features = sorted(features, key=lambda f: f.priority_score, reverse=True)
        self._features["global"] = sorted_features
        return sorted_features

    def allocate_product_resources(self) -> Dict[str, Any]:
        return {
            "engineering": 45,
            "design": 20,
            "qa": 15,
            "product": 12,
            "analytics": 8,
            "total_headcount": 100,
            "budget_usd": 500000,
        }

    def get_product_metrics(self) -> List[ProductMetric]:
        return [
            ProductMetric("p1", 125000, 45000.0, 0.48, 0.22, 0.09, 0.36),
            ProductMetric("p2", 34000, 8200.0, 0.42, 0.18, 0.06, 0.24),
            ProductMetric("p3", 89000, 12000.0, 0.35, 0.14, 0.05, 0.13),
        ]

    def get_stats(self) -> Dict[str, Any]:
        products = self.review_products()
        return {
            "total_products": len(products),
            "avg_health_score": round(sum(p.health_score for p in products) / len(products), 2) if products else 0,
            "phases": {p.product_id: p.phase.value for p in products},
        }