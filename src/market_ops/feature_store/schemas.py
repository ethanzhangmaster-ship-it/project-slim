"""E11.1 — Feature Store 数据模型。

定义 CreativeFeatureSnapshot 的结构：
  - acquisition: CTR, CPI, CPM, impression_count, click_count
  - monetization: D1/D7/D30 ROAS, D1/D7/D30 revenue
  - quality: IAP fitness, payer rate, archetype quality, LTV tier
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AcquisitionFeature:
    """获客层特征 — 来自 Facebook."""

    ctr: float = 0.0
    cpi: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    impression_count: int = 0
    click_count: int = 0
    install_count: int = 0
    spend: float = 0.0
    frequency: float = 0.0
    video_play_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ctr": round(self.ctr, 4),
            "cpi": round(self.cpi, 2),
            "cpm": round(self.cpm, 2),
            "cpc": round(self.cpc, 2),
            "impression_count": self.impression_count,
            "click_count": self.click_count,
            "install_count": self.install_count,
            "spend": round(self.spend, 2),
            "frequency": round(self.frequency, 2),
            "video_play_rate": round(self.video_play_rate, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcquisitionFeature:
        return cls(
            ctr=float(data.get("ctr", 0)),
            cpi=float(data.get("cpi", 0)),
            cpm=float(data.get("cpm", 0)),
            cpc=float(data.get("cpc", 0)),
            impression_count=int(data.get("impression_count", 0)),
            click_count=int(data.get("click_count", 0)),
            install_count=int(data.get("install_count", 0)),
            spend=float(data.get("spend", 0)),
            frequency=float(data.get("frequency", 0)),
            video_play_rate=float(data.get("video_play_rate", 0)),
        )


@dataclass
class MonetizationFeature:
    """变现层特征 — 来自 Adjust."""

    d1_roas: float = 0.0
    d7_roas: float = 0.0
    d30_roas: float = 0.0
    d1_revenue: float = 0.0
    d7_revenue: float = 0.0
    d30_revenue: float = 0.0
    d1_iap_revenue: float = 0.0
    d7_iap_revenue: float = 0.0
    d30_iap_revenue: float = 0.0
    d1_ad_revenue: float = 0.0
    d7_ad_revenue: float = 0.0
    d30_ad_revenue: float = 0.0
    payer_count: int = 0
    payer_rate: float = 0.0
    d30_ltv: float = 0.0
    adjust_cost: float = 0.0              # Adjust 侧花费（交叉验证）
    adjust_roas_d1: float = 0.0           # Adjust 原生 ROAS
    adjust_roas_d7: float = 0.0
    adjust_roas_d30: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "d1_roas": round(self.d1_roas, 4),
            "d7_roas": round(self.d7_roas, 4),
            "d30_roas": round(self.d30_roas, 4),
            "d1_revenue": round(self.d1_revenue, 2),
            "d7_revenue": round(self.d7_revenue, 2),
            "d30_revenue": round(self.d30_revenue, 2),
            "d1_iap_revenue": round(self.d1_iap_revenue, 2),
            "d7_iap_revenue": round(self.d7_iap_revenue, 2),
            "d30_iap_revenue": round(self.d30_iap_revenue, 2),
            "d1_ad_revenue": round(self.d1_ad_revenue, 2),
            "d7_ad_revenue": round(self.d7_ad_revenue, 2),
            "d30_ad_revenue": round(self.d30_ad_revenue, 2),
            "payer_count": self.payer_count,
            "payer_rate": round(self.payer_rate, 4),
            "d30_ltv": round(self.d30_ltv, 2),
            "adjust_cost": round(self.adjust_cost, 2),
            "adjust_roas_d1": round(self.adjust_roas_d1, 4),
            "adjust_roas_d7": round(self.adjust_roas_d7, 4),
            "adjust_roas_d30": round(self.adjust_roas_d30, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonetizationFeature:
        return cls(
            d1_roas=float(data.get("d1_roas", 0)),
            d7_roas=float(data.get("d7_roas", 0)),
            d30_roas=float(data.get("d30_roas", 0)),
            d1_revenue=float(data.get("d1_revenue", 0)),
            d7_revenue=float(data.get("d7_revenue", 0)),
            d30_revenue=float(data.get("d30_revenue", 0)),
            d1_iap_revenue=float(data.get("d1_iap_revenue", 0)),
            d7_iap_revenue=float(data.get("d7_iap_revenue", 0)),
            d30_iap_revenue=float(data.get("d30_iap_revenue", 0)),
            d1_ad_revenue=float(data.get("d1_ad_revenue", 0)),
            d7_ad_revenue=float(data.get("d7_ad_revenue", 0)),
            d30_ad_revenue=float(data.get("d30_ad_revenue", 0)),
            payer_count=int(data.get("payer_count", 0)),
            payer_rate=float(data.get("payer_rate", 0)),
            d30_ltv=float(data.get("d30_ltv", 0)),
            adjust_cost=float(data.get("adjust_cost", 0)),
            adjust_roas_d1=float(data.get("adjust_roas_d1", 0)),
            adjust_roas_d7=float(data.get("adjust_roas_d7", 0)),
            adjust_roas_d30=float(data.get("adjust_roas_d30", 0)),
        )


@dataclass
class QualityFeature:
    """质量层特征 — 来自 Creative Intelligence."""

    iap_fitness: float = 0.0
    winner_tier: str = ""
    recommendation: str = ""
    ltv_tier: str = ""
    archetype_quality: float = 0.0
    dna_future_value: float = 0.0
    journey_quality_score: float = 0.0
    is_winner: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "iap_fitness": round(self.iap_fitness, 2),
            "winner_tier": self.winner_tier,
            "recommendation": self.recommendation,
            "ltv_tier": self.ltv_tier,
            "archetype_quality": round(self.archetype_quality, 3),
            "dna_future_value": round(self.dna_future_value, 3),
            "journey_quality_score": round(self.journey_quality_score, 3),
            "is_winner": self.is_winner,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityFeature:
        return cls(
            iap_fitness=float(data.get("iap_fitness", 0)),
            winner_tier=data.get("winner_tier", ""),
            recommendation=data.get("recommendation", ""),
            ltv_tier=data.get("ltv_tier", ""),
            archetype_quality=float(data.get("archetype_quality", 0)),
            dna_future_value=float(data.get("dna_future_value", 0)),
            journey_quality_score=float(data.get("journey_quality_score", 0)),
            is_winner=bool(data.get("is_winner", False)),
        )


@dataclass
class CreativeFeatureSnapshot:
    """Creative Feature Snapshot — 特征快照。

    不是原始数据，而是从 Entity 层提取的 Feature 层。
    供 V5 Evolution Engine 直接读取。
    """

    creative_id: str = ""
    ad_id: str = ""
    platform: str = ""
    status: str = ""

    acquisition: AcquisitionFeature = field(default_factory=AcquisitionFeature)
    monetization: MonetizationFeature = field(default_factory=MonetizationFeature)
    quality: QualityFeature = field(default_factory=QualityFeature)

    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "platform": self.platform,
            "status": self.status,
            "acquisition": self.acquisition.to_dict(),
            "monetization": self.monetization.to_dict(),
            "quality": self.quality.to_dict(),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeFeatureSnapshot:
        return cls(
            creative_id=data.get("creative_id", ""),
            ad_id=data.get("ad_id", ""),
            platform=data.get("platform", "android"),
            status=data.get("status", "ACTIVE"),
            acquisition=AcquisitionFeature.from_dict(data.get("acquisition", {})),
            monetization=MonetizationFeature.from_dict(data.get("monetization", {})),
            quality=QualityFeature.from_dict(data.get("quality", {})),
            updated_at=data.get("updated_at", ""),
        )