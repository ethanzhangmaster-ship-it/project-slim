"""E11.5.1 Feedback Schema — IAP 产品性能反馈数据模型。

定义 Performance Feedback 的稳定契约：

  UAMetrics           — UA 投放指标 (impressions, clicks, installs, spend)
  EngagementMetrics   — 用户行为指标 (retention, sessions, playtime, level_progress)
  IAPMetrics          — 商业化指标 (revenue, payer_count, pay_rate, arppu, arpu, LTV)
  PerformanceFeedback — 统一反馈对象 (creative_id + UA + Engagement + IAP)

数据流：
  UA Adapter ──→ UAMetrics
  Analytics Adapter ──→ EngagementMetrics
  IAP Adapter ──→ IAPMetrics
       ↓
  PerformanceFeedback → FeedbackRepository → E11.5.3 Fitness Engine
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════
# UAMetrics — UA 投放指标
# ═══════════════════════════════════════════════════════════

@dataclass
class UAMetrics:
    """UA 投放数据指标。

    包含原始数据和计算指标。

    例如：
        UAMetrics(
            impressions=100000,
            clicks=50000,
            installs=30000,
            spend=10000.0,
        )
    """
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    spend: float = 0.0

    # ── 计算属性 ──────────────────────────────────────

    @property
    def ctr(self) -> float:
        """CTR = clicks / impressions。"""
        if self.impressions <= 0:
            return 0.0
        return round(self.clicks / self.impressions, 4)

    @property
    def cpi(self) -> float:
        """CPI = spend / installs。"""
        if self.installs <= 0:
            return 0.0
        return round(self.spend / self.installs, 4)

    @property
    def install_cvr(self) -> float:
        """Install CVR = installs / clicks。"""
        if self.clicks <= 0:
            return 0.0
        return round(self.installs / self.clicks, 4)

    @property
    def cpm(self) -> float:
        """CPM = (spend / impressions) * 1000。"""
        if self.impressions <= 0:
            return 0.0
        return round((self.spend / self.impressions) * 1000, 4)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "spend": self.spend,
            "ctr": self.ctr,
            "cpi": self.cpi,
            "install_cvr": self.install_cvr,
            "cpm": self.cpm,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UAMetrics:
        return cls(
            impressions=data.get("impressions", 0),
            clicks=data.get("clicks", 0),
            installs=data.get("installs", 0),
            spend=data.get("spend", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"UAMetrics(imp={self.impressions}, "
            f"installs={self.installs}, "
            f"spend={self.spend}, "
            f"CPI={self.cpi})"
        )


# ═══════════════════════════════════════════════════════════
# EngagementMetrics — 用户行为指标
# ═══════════════════════════════════════════════════════════

@dataclass
class EngagementMetrics:
    """IAP 产品用户行为指标。

    例如：
        EngagementMetrics(
            d1_retention=0.45,
            d7_retention=0.35,
            d30_retention=0.15,
            sessions=12.5,
            playtime=42.0,
            level_progress=5.3,
        )
    """
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0
    sessions: float = 0.0
    playtime: float = 0.0       # 分钟
    level_progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "d1_retention": self.d1_retention,
            "d7_retention": self.d7_retention,
            "d30_retention": self.d30_retention,
            "sessions": self.sessions,
            "playtime": self.playtime,
            "level_progress": self.level_progress,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EngagementMetrics:
        return cls(
            d1_retention=data.get("d1_retention", 0.0),
            d7_retention=data.get("d7_retention", 0.0),
            d30_retention=data.get("d30_retention", 0.0),
            sessions=data.get("sessions", 0.0),
            playtime=data.get("playtime", 0.0),
            level_progress=data.get("level_progress", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"EngagementMetrics(d1_ret={self.d1_retention}, "
            f"d7_ret={self.d7_retention}, "
            f"playtime={self.playtime}m)"
        )


# ═══════════════════════════════════════════════════════════
# IAPMetrics — 商业化指标
# ═══════════════════════════════════════════════════════════

@dataclass
class IAPMetrics:
    """IAP 商业化指标。

    包含付费转化、ARPU/ARPPU 和 LTV。

    例如：
        IAPMetrics(
            revenue=50000.0,
            iap_revenue=48000.0,
            payer_count=500,
            purchase_count=1200,
            installs=30000,
            d7_ltv=1.2,
            d30_ltv=3.5,
            d90_ltv=8.0,
        )
    """
    revenue: float = 0.0
    iap_revenue: float = 0.0
    payer_count: int = 0
    purchase_count: int = 0
    installs: int = 0
    d7_ltv: float = 0.0
    d30_ltv: float = 0.0
    d90_ltv: float = 0.0

    # ── 计算属性 ──────────────────────────────────────

    @property
    def pay_rate(self) -> float:
        """付费率 = payer_count / installs。"""
        if self.installs <= 0:
            return 0.0
        return round(self.payer_count / self.installs, 4)

    @property
    def arpu(self) -> float:
        """ARPU = revenue / installs。"""
        if self.installs <= 0:
            return 0.0
        return round(self.revenue / self.installs, 4)

    @property
    def arppu(self) -> float:
        """ARPPU = revenue / payer_count。"""
        if self.payer_count <= 0:
            return 0.0
        return round(self.revenue / self.payer_count, 4)

    @property
    def avg_purchase_value(self) -> float:
        """平均单次付费金额 = revenue / purchase_count。"""
        if self.purchase_count <= 0:
            return 0.0
        return round(self.revenue / self.purchase_count, 4)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "revenue": self.revenue,
            "iap_revenue": self.iap_revenue,
            "payer_count": self.payer_count,
            "purchase_count": self.purchase_count,
            "installs": self.installs,
            "pay_rate": self.pay_rate,
            "arpu": self.arpu,
            "arppu": self.arppu,
            "avg_purchase_value": self.avg_purchase_value,
            "d7_ltv": self.d7_ltv,
            "d30_ltv": self.d30_ltv,
            "d90_ltv": self.d90_ltv,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IAPMetrics:
        return cls(
            revenue=data.get("revenue", 0.0),
            iap_revenue=data.get("iap_revenue", 0.0),
            payer_count=data.get("payer_count", 0),
            purchase_count=data.get("purchase_count", 0),
            installs=data.get("installs", 0),
            d7_ltv=data.get("d7_ltv", 0.0),
            d30_ltv=data.get("d30_ltv", 0.0),
            d90_ltv=data.get("d90_ltv", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"IAPMetrics(revenue={self.revenue}, "
            f"payers={self.payer_count}, "
            f"ARPU={self.arpu}, "
            f"pay_rate={self.pay_rate})"
        )


# ═══════════════════════════════════════════════════════════
# PerformanceFeedback — 统一反馈对象
# ═══════════════════════════════════════════════════════════

@dataclass
class PerformanceFeedback:
    """代表一个 Creative / Campaign 带来的真实用户商业价值。

    将 UA 数据、用户行为数据和 IAP 付费数据统一为一个反馈对象。

    例如：
        PerformanceFeedback(
            creative_id="creative_001",
            campaign_id="campaign_001",
            source="facebook",
            period="2026-01-01_to_2026-01-07",
            ua_metrics=UAMetrics(...),
            engagement_metrics=EngagementMetrics(...),
            monetization_metrics=IAPMetrics(...),
        )
    """
    feedback_id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    creative_id: str = ""
    campaign_id: str = ""
    source: str = ""                                    # "facebook" | "google" | "asa" | "tiktok"
    period: str = ""                                    # "2026-01-01_to_2026-01-07"
    ua_metrics: UAMetrics | None = None
    engagement_metrics: EngagementMetrics | None = None
    monetization_metrics: IAPMetrics | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def has_ua_data(self) -> bool:
        return self.ua_metrics is not None

    @property
    def has_engagement_data(self) -> bool:
        return self.engagement_metrics is not None

    @property
    def has_monetization_data(self) -> bool:
        return self.monetization_metrics is not None

    @property
    def is_complete(self) -> bool:
        """是否包含所有三类数据。"""
        return self.has_ua_data and self.has_engagement_data and self.has_monetization_data

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "source": self.source,
            "period": self.period,
            "ua_metrics": self.ua_metrics.to_dict() if self.ua_metrics else None,
            "engagement_metrics": self.engagement_metrics.to_dict() if self.engagement_metrics else None,
            "monetization_metrics": self.monetization_metrics.to_dict() if self.monetization_metrics else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerformanceFeedback:
        created_at = data.get("created_at")
        return cls(
            feedback_id=data.get("feedback_id", ""),
            creative_id=data.get("creative_id", ""),
            campaign_id=data.get("campaign_id", ""),
            source=data.get("source", ""),
            period=data.get("period", ""),
            ua_metrics=UAMetrics.from_dict(data["ua_metrics"]) if data.get("ua_metrics") else None,
            engagement_metrics=EngagementMetrics.from_dict(data["engagement_metrics"]) if data.get("engagement_metrics") else None,
            monetization_metrics=IAPMetrics.from_dict(data["monetization_metrics"]) if data.get("monetization_metrics") else None,
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"PerformanceFeedback(id={self.feedback_id!r}, "
            f"creative={self.creative_id!r}, "
            f"source={self.source!r}, "
            f"complete={self.is_complete})"
        )