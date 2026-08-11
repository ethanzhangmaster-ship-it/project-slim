"""E13.1.3 Adjust Models — Adjust 归因与用户生命周期数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class AdjustEventType(str, Enum):
    """Adjust 事件类型 — 标准化后的事件名称."""
    INSTALL = "install"
    SESSION = "session"
    REATTRIBUTION = "reattribution"
    TUTORIAL_COMPLETE = "tutorial_complete"
    LEVEL_COMPLETE = "level_complete"
    PURCHASE = "purchase"
    AD_REVENUE = "ad_revenue"
    SUBSCRIPTION = "subscription"
    CUSTOM_EVENT = "custom_event"
    UNINSTALL = "uninstall"


class AdjustRevenueType(str, Enum):
    """Adjust 收入类型."""
    IAP = "iap"           # 内购
    IAA = "iaa"           # 广告收入
    SUBSCRIPTION = "subscription"  # 订阅
    HYBRID = "hybrid"     # 混合


class AdjustNetwork(str, Enum):
    """Adjust 归因网络."""
    META = "meta"
    GOOGLE = "google"
    ASA = "asa"
    TIKTOK = "tiktok"
    UNITY = "unity"
    APPLOVIN = "applovin"
    IRONSOURCE = "ironsource"
    MINTEGRAL = "mintegral"
    ORGANIC = "organic"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Adjust User Event
# ═══════════════════════════════════════════════════════════════


@dataclass
class AdjustUserEvent:
    """Adjust 统一用户事件.

    支持 install, session, purchase, ad_revenue, tutorial_complete 等所有事件类型.
    """

    event_id: str = ""
    user_id: str = ""
    product_id: str = ""
    event_name: AdjustEventType = AdjustEventType.CUSTOM_EVENT
    timestamp: str = ""

    # Revenue
    revenue: float = 0.0
    currency: str = "USD"
    revenue_type: AdjustRevenueType = AdjustRevenueType.IAP

    # Properties
    properties: dict[str, Any] = field(default_factory=dict)

    # Attribution context
    network: str = ""
    campaign_id: str = ""
    adgroup_id: str = ""
    creative_id: str = ""

    # Device
    device_id: str = ""
    os_name: str = ""
    os_version: str = ""
    app_version: str = ""
    country: str = ""

    # Metadata
    raw_event: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "event_name": self.event_name.value,
            "timestamp": self.timestamp,
            "revenue": round(self.revenue, 4),
            "currency": self.currency,
            "revenue_type": self.revenue_type.value,
            "network": self.network,
            "campaign_id": self.campaign_id,
            "country": self.country,
            "os_name": self.os_name,
            "app_version": self.app_version,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_revenue_event(self) -> bool:
        return self.revenue > 0

    @property
    def is_install(self) -> bool:
        return self.event_name == AdjustEventType.INSTALL

    @property
    def is_purchase(self) -> bool:
        return self.event_name == AdjustEventType.PURCHASE

    @property
    def is_ad_revenue(self) -> bool:
        return self.event_name == AdjustEventType.AD_REVENUE


# ═══════════════════════════════════════════════════════════════
# Attribution Record
# ═══════════════════════════════════════════════════════════════


@dataclass
class AttributionRecord:
    """Adjust 归因记录 — 连接用户与广告来源."""

    user_id: str = ""
    network: AdjustNetwork = AdjustNetwork.UNKNOWN
    campaign_id: str = ""
    campaign_name: str = ""
    adgroup_id: str = ""
    adgroup_name: str = ""
    creative_id: str = ""
    creative_name: str = ""

    install_time: str = ""
    click_time: str = ""
    attribution_time: str = ""

    country: str = ""
    language: str = ""
    device_type: str = ""

    # Organic / Paid
    is_organic: bool = True

    # Metadata
    raw_data: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "network": self.network.value,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "adgroup_id": self.adgroup_id,
            "creative_id": self.creative_id,
            "install_time": self.install_time,
            "country": self.country,
            "is_organic": self.is_organic,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_paid(self) -> bool:
        return not self.is_organic

    @property
    def source_platform(self) -> str:
        """映射到 E13.1.1 DataSource."""
        network_map = {
            AdjustNetwork.META: "meta_ads",
            AdjustNetwork.GOOGLE: "google_ads",
            AdjustNetwork.ASA: "asa",
            AdjustNetwork.TIKTOK: "tiktok",
            AdjustNetwork.UNITY: "unity",
            AdjustNetwork.APPLOVIN: "max",
            AdjustNetwork.IRONSOURCE: "ironsource",
            AdjustNetwork.MINTEGRAL: "mintegral",
            AdjustNetwork.ORGANIC: "organic",
        }
        return network_map.get(self.network, "unknown")


# ═══════════════════════════════════════════════════════════════
# Retention Snapshot
# ═══════════════════════════════════════════════════════════════


@dataclass
class RetentionSnapshot:
    """Adjust 留存快照 — 按 cohort 的留存率."""

    product_id: str = ""
    cohort_date: str = ""
    cohort_size: int = 0

    d1: float = 0.0
    d3: float = 0.0
    d7: float = 0.0
    d14: float = 0.0
    d30: float = 0.0
    d60: float = 0.0
    d90: float = 0.0

    # Network breakdown
    by_network: dict[str, dict[str, float]] = field(default_factory=dict)

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "cohort_date": self.cohort_date,
            "cohort_size": self.cohort_size,
            "d1": round(self.d1, 4),
            "d3": round(self.d3, 4),
            "d7": round(self.d7, 4),
            "d14": round(self.d14, 4),
            "d30": round(self.d30, 4),
            "d60": round(self.d60, 4),
            "d90": round(self.d90, 4),
            "fetched_at": self.fetched_at,
        }

    @property
    def d7_retention_rate(self) -> float:
        return self.d7

    @property
    def d30_retention_rate(self) -> float:
        return self.d30

    @property
    def is_healthy(self) -> bool:
        """D7 留存 >= 20% 视为健康."""
        return self.d7 >= 0.2

    def to_e1311_retention_curve(self) -> Any:
        """转换为 E13.1.1 RetentionCurve."""
        from ..models import DataSource, RetentionCurve
        return RetentionCurve(
            product_id=self.product_id,
            platform=DataSource.ADJUST,
            cohort_date=self.cohort_date,
            d1_retention=self.d1,
            d3_retention=self.d3,
            d7_retention=self.d7,
            d14_retention=self.d14,
            d30_retention=self.d30,
            d60_retention=self.d60,
            d90_retention=self.d90,
            cohort_size=self.cohort_size,
        )


# ═══════════════════════════════════════════════════════════════
# User Value Snapshot
# ═══════════════════════════════════════════════════════════════


@dataclass
class UserValueSnapshot:
    """用户价值快照 — 核心输出，进入 Reality Layer."""

    product_id: str = ""
    date: str = ""

    # User counts
    total_users: int = 0
    new_users: int = 0
    active_users: int = 0
    paying_users: int = 0

    # Revenue breakdown
    total_revenue: float = 0.0
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    subscription_revenue: float = 0.0

    # Unit economics
    arpu: float = 0.0
    arppu: float = 0.0
    paying_rate: float = 0.0

    # Retention
    retention: RetentionSnapshot | None = None

    # Attribution breakdown
    by_network: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Installs
    installs: int = 0

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "date": self.date,
            "total_users": self.total_users,
            "new_users": self.new_users,
            "active_users": self.active_users,
            "paying_users": self.paying_users,
            "total_revenue": round(self.total_revenue, 4),
            "iap_revenue": round(self.iap_revenue, 4),
            "ad_revenue": round(self.ad_revenue, 4),
            "subscription_revenue": round(self.subscription_revenue, 4),
            "arpu": round(self.arpu, 4),
            "arppu": round(self.arppu, 4),
            "paying_rate": round(self.paying_rate, 4),
            "installs": self.installs,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_iaa_dominant(self) -> bool:
        return self.ad_revenue > self.iap_revenue

    @property
    def is_iap_dominant(self) -> bool:
        return self.iap_revenue > self.ad_revenue

    @property
    def revenue_per_user(self) -> float:
        if self.total_users == 0:
            return 0.0
        return self.total_revenue / self.total_users

    @property
    def ltv_indicator(self) -> float:
        """LTV 指示器: ARPU × 30 (粗略估算)."""
        return self.arpu * 30.0


# ═══════════════════════════════════════════════════════════════
# Adjust API Response
# ═══════════════════════════════════════════════════════════════


@dataclass
class AdjustAPIResponse:
    """Adjust API 响应包装."""
    success: bool = True
    data: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    error_code: str = ""
    has_more: bool = False
    next_page_token: str = ""
    total_count: int = 0
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data_count": len(self.data),
            "error_message": self.error_message,
            "error_code": self.error_code,
            "has_more": self.has_more,
            "total_count": self.total_count,
        }

    @property
    def is_error(self) -> bool:
        return not self.success