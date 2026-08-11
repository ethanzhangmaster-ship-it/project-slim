from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class FeatureCategory(Enum):
    MONETIZATION = "monetization"
    RETENTION = "retention"
    ACQUISITION = "acquisition"
    ENGAGEMENT = "engagement"
    TECH = "tech"


@dataclass
class Feature:
    feature_id: str
    title: str
    category: FeatureCategory
    description: str
    estimated_effort_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "category": self.category.value,
            "description": self.description,
            "estimated_effort_days": self.estimated_effort_days,
        }


@dataclass
class FeatureImpact:
    feature_id: str
    retention_lift: float
    revenue_lift: float
    engagement_lift: float
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "retention_lift": self.retention_lift,
            "revenue_lift": self.revenue_lift,
            "engagement_lift": self.engagement_lift,
            "confidence": self.confidence,
        }


@dataclass
class FeaturePipeline:
    features: List[Feature] = field(default_factory=list)
    current_sprint: str = ""
    backlog_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "features": [f.to_dict() for f in self.features],
            "current_sprint": self.current_sprint,
            "backlog_size": self.backlog_size,
        }


class FeatureStrategy:
    def __init__(self):
        self._features: Dict[str, Feature] = {}
        self._impacts: Dict[str, FeatureImpact] = {}
        self._pipeline: FeaturePipeline = FeaturePipeline()

    def analyze_feature_impact(self, feature: Feature) -> FeatureImpact:
        impact = FeatureImpact(
            feature_id=feature.feature_id,
            retention_lift=0.05,
            revenue_lift=0.08,
            engagement_lift=0.12,
            confidence=0.75,
        )
        self._impacts[feature.feature_id] = impact
        return impact

    def prioritize_features(self) -> List[Feature]:
        features = list(self._features.values()) or [
            Feature("f1", "Battle Pass", FeatureCategory.MONETIZATION, "Seasonal progression system", 14),
            Feature("f2", "Guild System", FeatureCategory.RETENTION, "Social guilds with rewards", 21),
            Feature("f3", "Referral Program", FeatureCategory.ACQUISITION, "Invite friends for bonuses", 7),
            Feature("f4", "Daily Quests", FeatureCategory.ENGAGEMENT, "Rotating daily objectives", 5),
            Feature("f5", "Server Migration", FeatureCategory.TECH, "Cross-server player transfer", 30),
        ]
        return sorted(features, key=lambda f: f.estimated_effort_days)

    def get_feature_pipeline(self) -> FeaturePipeline:
        features = self.prioritize_features()
        self._pipeline = FeaturePipeline(
            features=features,
            current_sprint="Sprint 42",
            backlog_size=len(features) + 8,
        )
        return self._pipeline

    def evaluate_feature(self, feature_id: str) -> Optional[FeatureImpact]:
        if feature_id in self._impacts:
            return self._impacts[feature_id]
        return FeatureImpact(feature_id, 0.03, 0.05, 0.07, 0.60)

    def plan_feature_rollout(self, feature_id: str) -> Dict[str, Any]:
        return {
            "feature_id": feature_id,
            "rollout_phases": ["internal", "beta", "soft_launch", "global"],
            "target_audience_pct": [5, 15, 30, 100],
            "estimated_days": 28,
            "success_criteria": {"retention_d7": 0.20, "revenue_lift": 0.05},
        }

    def get_stats(self) -> Dict[str, Any]:
        features = list(self._features.values())
        category_counts = {cat.value: 0 for cat in FeatureCategory}
        for f in features:
            category_counts[f.category.value] += 1
        return {
            "total_features": len(features),
            "category_distribution": category_counts,
            "pipeline_backlog": self._pipeline.backlog_size,
        }