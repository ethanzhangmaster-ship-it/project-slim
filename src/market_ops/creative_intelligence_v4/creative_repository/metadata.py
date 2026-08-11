"""V4.0 Creative Intelligence Platform — Creative Repository Metadata.

Unified metadata model for all creative assets (image + video).
Single source of truth for the entire creative pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CreativeType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MonetizationType(str, Enum):
    IAA = "iaa"
    IAP = "iap"


class OptimizationGoal(str, Enum):
    AEO = "aeo"
    VALUE_ROAS = "value_roas"
    INSTALL = "install"


class CreativeStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    WINNER = "winner"
    LOSER = "loser"
    ARCHIVED = "archived"
    PENDING_REVIEW = "pending_review"


@dataclass
class CreativeMetadata:
    """Complete metadata for a single creative asset in the repository."""

    creative_id: str = ""
    creative_type: CreativeType = CreativeType.IMAGE
    monetization: MonetizationType = MonetizationType.IAA
    optimization_goal: OptimizationGoal = OptimizationGoal.INSTALL

    # Source identification
    source_facebook_id: str = ""
    source_adjust_id: str = ""
    source_eagle_path: str = ""

    # Geography
    country: str = ""
    platform: str = "facebook"

    # Status
    status: CreativeStatus = CreativeStatus.ACTIVE

    # Performance (from Facebook + Adjust)
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpm: float = 0.0
    cpi: float = 0.0
    ipm: float = 0.0
    installs: int = 0
    purchases: int = 0
    purchase_value: float = 0.0
    roas_d1: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    ltv_d30: float = 0.0
    ltv_d90: float = 0.0
    retention_d1: float = 0.0
    retention_d7: float = 0.0

    # DNA
    has_image_dna: bool = False
    has_video_dna: bool = False

    # Review
    review_score: float = 0.0
    review_count: int = 0

    # Generation
    generation_depth: int = 0
    parent_creative_id: str = ""
    mutation_type: str = ""

    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    first_seen: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_type": self.creative_type.value,
            "monetization": self.monetization.value,
            "optimization_goal": self.optimization_goal.value,
            "source_facebook_id": self.source_facebook_id,
            "source_adjust_id": self.source_adjust_id,
            "source_eagle_path": self.source_eagle_path,
            "country": self.country,
            "platform": self.platform,
            "status": self.status.value,
            "performance": {
                "spend": self.spend,
                "impressions": self.impressions,
                "clicks": self.clicks,
                "ctr": self.ctr,
                "cpm": self.cpm,
                "cpi": self.cpi,
                "ipm": self.ipm,
                "installs": self.installs,
                "purchases": self.purchases,
                "purchase_value": self.purchase_value,
                "roas_d1": self.roas_d1,
                "roas_d7": self.roas_d7,
                "roas_d30": self.roas_d30,
                "ltv_d30": self.ltv_d30,
                "ltv_d90": self.ltv_d90,
                "retention_d1": self.retention_d1,
                "retention_d7": self.retention_d7,
            },
            "has_image_dna": self.has_image_dna,
            "has_video_dna": self.has_video_dna,
            "review_score": self.review_score,
            "review_count": self.review_count,
            "generation_depth": self.generation_depth,
            "parent_creative_id": self.parent_creative_id,
            "mutation_type": self.mutation_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeMetadata:
        perf = data.get("performance", {})
        return cls(
            creative_id=data.get("creative_id", ""),
            creative_type=CreativeType(data.get("creative_type", "image")),
            monetization=MonetizationType(data.get("monetization", "iaa")),
            optimization_goal=OptimizationGoal(data.get("optimization_goal", "install")),
            source_facebook_id=data.get("source_facebook_id", ""),
            source_adjust_id=data.get("source_adjust_id", ""),
            source_eagle_path=data.get("source_eagle_path", ""),
            country=data.get("country", ""),
            platform=data.get("platform", "facebook"),
            status=CreativeStatus(data.get("status", "active")),
            spend=perf.get("spend", 0),
            impressions=perf.get("impressions", 0),
            clicks=perf.get("clicks", 0),
            ctr=perf.get("ctr", 0),
            cpm=perf.get("cpm", 0),
            cpi=perf.get("cpi", 0),
            ipm=perf.get("ipm", 0),
            installs=perf.get("installs", 0),
            purchases=perf.get("purchases", 0),
            purchase_value=perf.get("purchase_value", 0),
            roas_d1=perf.get("roas_d1", 0),
            roas_d7=perf.get("roas_d7", 0),
            roas_d30=perf.get("roas_d30", 0),
            ltv_d30=perf.get("ltv_d30", 0),
            ltv_d90=perf.get("ltv_d90", 0),
            retention_d1=perf.get("retention_d1", 0),
            retention_d7=perf.get("retention_d7", 0),
            has_image_dna=data.get("has_image_dna", False),
            has_video_dna=data.get("has_video_dna", False),
            review_score=data.get("review_score", 0),
            review_count=data.get("review_count", 0),
            generation_depth=data.get("generation_depth", 0),
            parent_creative_id=data.get("parent_creative_id", ""),
            mutation_type=data.get("mutation_type", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            first_seen=data.get("first_seen", ""),
            last_seen=data.get("last_seen", ""),
        )