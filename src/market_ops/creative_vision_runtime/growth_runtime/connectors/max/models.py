"""E13.1.4 MAX Models — AppLovin MAX 广告变现数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class MAXAdFormat(str, Enum):
    """MAX 广告格式."""
    INTERSTITIAL = "interstitial"
    REWARDED = "rewarded"
    BANNER = "banner"
    MREC = "mrec"
    NATIVE = "native"
    APP_OPEN = "app_open"


class MAXNetwork(str, Enum):
    """MAX 广告网络."""
    META = "meta"
    ADMOB = "admob"
    UNITY = "unity"
    APPLOVIN = "applovin"
    IRONSOURCE = "ironsource"
    MINTEGRAL = "mintegral"
    VUNGLE = "vungle"
    CHARTBOOST = "chartboost"
    FYBER = "fyber"
    INMOBI = "inmobi"
    ADCOLONY = "adcolony"
    SNA = "sna"
    PANGLE = "pangle"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class MAXRevenueType(str, Enum):
    """MAX 收入类型."""
    IMPRESSION = "impression"
    ECPM = "ecpm"
    ARPDAU = "arpdau"
    FILL_RATE = "fill_rate"
    SHOW_RATE = "show_rate"


# ═══════════════════════════════════════════════════════════════
# MAX Account
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXAccount:
    """MAX 广告账户."""
    account_id: str = ""
    api_key: str = ""
    name: str = ""
    status: str = "active"
    currency: str = "USD"
    timezone: str = "UTC"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "status": self.status,
            "currency": self.currency,
        }


# ═══════════════════════════════════════════════════════════════
# MAX Ad Unit
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXAdUnit:
    """MAX 广告单元 (Placement)."""
    ad_unit_id: str = ""
    name: str = ""
    ad_format: MAXAdFormat = MAXAdFormat.INTERSTITIAL
    app_id: str = ""
    app_name: str = ""
    package_name: str = ""
    platform: str = ""  # ios / android
    status: str = "active"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ad_unit_id": self.ad_unit_id,
            "name": self.name,
            "ad_format": self.ad_format.value,
            "app_id": self.app_id,
            "platform": self.platform,
            "status": self.status,
        }


# ═══════════════════════════════════════════════════════════════
# MAX Revenue Event
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXRevenueEvent:
    """MAX 单次广告收入事件 (Impression-level)."""
    event_id: str = ""
    ad_unit_id: str = ""
    ad_unit_name: str = ""
    ad_format: MAXAdFormat = MAXAdFormat.REWARDED

    # Revenue
    revenue: float = 0.0
    revenue_usd: float = 0.0
    currency: str = "USD"

    # Network
    network: MAXNetwork = MAXNetwork.UNKNOWN
    network_placement: str = ""

    # Country
    country: str = ""
    country_code: str = ""

    # Device
    device_id: str = ""
    platform: str = ""  # ios / android

    # Timestamp
    timestamp: str = ""
    date: str = ""

    # Metadata
    raw_event: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ad_unit_id": self.ad_unit_id,
            "ad_format": self.ad_format.value,
            "revenue": round(self.revenue, 6),
            "revenue_usd": round(self.revenue_usd, 6),
            "currency": self.currency,
            "network": self.network.value,
            "country": self.country,
            "platform": self.platform,
            "date": self.date,
            "timestamp": self.timestamp,
        }

    @property
    def is_rewarded(self) -> bool:
        return self.ad_format == MAXAdFormat.REWARDED

    @property
    def is_interstitial(self) -> bool:
        return self.ad_format == MAXAdFormat.INTERSTITIAL


# ═══════════════════════════════════════════════════════════════
# MAX Performance
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXPerformance:
    """MAX 聚合表现数据 (按 Ad Unit / Network / Country)."""
    ad_unit_id: str = ""
    ad_unit_name: str = ""
    product_id: str = ""

    # Dimensions
    date: str = ""
    network: MAXNetwork = MAXNetwork.UNKNOWN
    country: str = ""
    ad_format: MAXAdFormat = MAXAdFormat.REWARDED

    # Impressions & Revenue
    impressions: int = 0
    revenue: float = 0.0
    ecpm: float = 0.0

    # Engagement
    clicks: int = 0
    ctr: float = 0.0

    # Fill & Show
    requests: int = 0
    fills: int = 0
    fill_rate: float = 0.0
    show_rate: float = 0.0

    # DAU
    dau: int = 0
    arpdau: float = 0.0

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "ad_unit_id": self.ad_unit_id,
            "ad_unit_name": self.ad_unit_name,
            "product_id": self.product_id,
            "date": self.date,
            "network": self.network.value,
            "country": self.country,
            "ad_format": self.ad_format.value,
            "impressions": self.impressions,
            "revenue": round(self.revenue, 6),
            "ecpm": round(self.ecpm, 4),
            "clicks": self.clicks,
            "ctr": round(self.ctr, 6),
            "fill_rate": round(self.fill_rate, 4),
            "show_rate": round(self.show_rate, 4),
            "dau": self.dau,
            "arpdau": round(self.arpdau, 6),
            "fetched_at": self.fetched_at,
        }

    @property
    def revenue_per_impression(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.revenue / self.impressions

    def is_high_ecpm(self, threshold: float = 10.0) -> bool:
        return self.ecpm >= threshold


# ═══════════════════════════════════════════════════════════════
# MAX Revenue Snapshot
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXRevenueSnapshot:
    """MAX 每日收入快照 — 核心输出，进入 Reality Layer."""
    product_id: str = ""
    date: str = ""

    # Aggregated revenue
    total_revenue: float = 0.0
    total_impressions: int = 0
    total_requests: int = 0
    total_fills: int = 0

    # Unit economics
    ecpm: float = 0.0
    fill_rate: float = 0.0
    show_rate: float = 0.0

    # DAU & ARPDAU
    dau: int = 0
    arpdau: float = 0.0

    # By ad format
    by_format: dict[str, dict[str, Any]] = field(default_factory=dict)

    # By network
    by_network: dict[str, dict[str, Any]] = field(default_factory=dict)

    # By country
    by_country: dict[str, dict[str, Any]] = field(default_factory=dict)

    # By ad unit
    by_ad_unit: dict[str, dict[str, Any]] = field(default_factory=dict)

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "date": self.date,
            "total_revenue": round(self.total_revenue, 6),
            "total_impressions": self.total_impressions,
            "total_requests": self.total_requests,
            "total_fills": self.total_fills,
            "ecpm": round(self.ecpm, 4),
            "fill_rate": round(self.fill_rate, 4),
            "show_rate": round(self.show_rate, 4),
            "dau": self.dau,
            "arpdau": round(self.arpdau, 6),
            "fetched_at": self.fetched_at,
        }

    @property
    def revenue_per_impression(self) -> float:
        if self.total_impressions == 0:
            return 0.0
        return self.total_revenue / self.total_impressions

    @property
    def impressions_per_user(self) -> float:
        if self.dau == 0:
            return 0.0
        return self.total_impressions / self.dau

    @property
    def is_iaa_healthy(self) -> bool:
        """IAA 健康: ARPDAU > $0.01 且 fill_rate > 50%."""
        return self.arpdau >= 0.01 and self.fill_rate >= 0.5

    @property
    def ad_revenue_metrics(self) -> dict[str, Any]:
        """广告收入指标 — 供 Reality Layer 消费."""
        return {
            "ad_revenue": round(self.total_revenue, 6),
            "total_impressions": self.total_impressions,
            "ecpm": round(self.ecpm, 4),
            "fill_rate": round(self.fill_rate, 4),
            "show_rate": round(self.show_rate, 4),
            "dau": self.dau,
            "arpdau": round(self.arpdau, 6),
        }


# ═══════════════════════════════════════════════════════════════
# MAX API Response
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXAPIResponse:
    """MAX API 响应包装."""
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


# ═══════════════════════════════════════════════════════════════
# MAX Waterfall Entry
# ═══════════════════════════════════════════════════════════════


@dataclass
class MAXWaterfallEntry:
    """MAX Waterfall / Bidding 条目."""
    ad_unit_id: str = ""
    network: MAXNetwork = MAXNetwork.UNKNOWN
    network_placement: str = ""
    priority: int = 0

    # Bidding
    is_bidding: bool = False
    bid_price: float = 0.0
    win_price: float = 0.0
    win_rate: float = 0.0

    # Performance
    impressions: int = 0
    revenue: float = 0.0
    ecpm: float = 0.0
    fill_rate: float = 0.0

    date: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "ad_unit_id": self.ad_unit_id,
            "network": self.network.value,
            "priority": self.priority,
            "is_bidding": self.is_bidding,
            "bid_price": round(self.bid_price, 4),
            "win_price": round(self.win_price, 4),
            "win_rate": round(self.win_rate, 4),
            "impressions": self.impressions,
            "revenue": round(self.revenue, 6),
            "ecpm": round(self.ecpm, 4),
            "fill_rate": round(self.fill_rate, 4),
            "date": self.date,
        }