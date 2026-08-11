"""E13.1.1 Connector Models — 统一数据模型，标准化所有外部平台的数据格式."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class DataSource(str, Enum):
    """数据来源."""
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    ASA = "asa"
    ADJUST = "adjust"
    APPSFLYER = "appsflyer"
    FIREBASE = "firebase"
    APP_STORE = "app_store"
    GOOGLE_PLAY = "google_play"
    MAX = "max"
    ADMOB = "admob"
    MINTEGRAL = "mintegral"
    IRONSOURCE = "ironsource"
    INTERNAL = "internal"


class MetricType(str, Enum):
    """指标类型."""
    SPEND = "spend"
    REVENUE = "revenue"
    IMPRESSION = "impression"
    CLICK = "click"
    INSTALL = "install"
    ROAS = "roas"
    CTR = "ctr"
    CPI = "cpi"
    CPM = "cpm"
    CPC = "cpc"
    CPA = "cpa"
    RETENTION = "retention"
    LTV = "ltv"
    DAU = "dau"
    SESSION = "session"
    CONVERSION = "conversion"
    PAYER_RATE = "payer_rate"
    ARPU = "arpu"
    ARPPU = "arppu"


class DataGranularity(str, Enum):
    """数据粒度."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    LIFETIME = "lifetime"


class ConnectorStatus(str, Enum):
    """连接器状态."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    AUTH_EXPIRED = "auth_expired"


class ConnectorHealth(str, Enum):
    """连接器健康状态."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Campaign Metrics
# ═══════════════════════════════════════════════════════════════


@dataclass
class CampaignMetrics:
    """统一广告系列指标 — 所有广告平台的标准格式.

    映射:
      Meta Ads campaign_id → campaign_id
      Google Ads campaign_id → campaign_id
    """

    campaign_id: str = ""
    campaign_name: str = ""
    platform: DataSource = DataSource.META_ADS
    product_id: str = ""

    # Spend & Revenue
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0

    # Engagement
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0

    # Conversions
    installs: int = 0
    cpi: float = 0.0
    cpa: float = 0.0

    # Time
    date: str = ""
    granularity: DataGranularity = DataGranularity.DAILY
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "platform": self.platform.value,
            "product_id": self.product_id,
            "spend": round(self.spend, 4),
            "revenue": round(self.revenue, 4),
            "roas": round(self.roas, 4),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": round(self.ctr, 6),
            "cpm": round(self.cpm, 4),
            "cpc": round(self.cpc, 4),
            "installs": self.installs,
            "cpi": round(self.cpi, 4),
            "cpa": round(self.cpa, 4),
            "date": self.date,
            "granularity": self.granularity.value,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_profitable(self) -> bool:
        return self.roas > 1.0

    @property
    def engagement_rate(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.clicks / self.impressions


@dataclass
class AdSetMetrics:
    """广告组指标."""
    adset_id: str = ""
    adset_name: str = ""
    campaign_id: str = ""
    platform: DataSource = DataSource.META_ADS
    product_id: str = ""

    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    installs: int = 0
    cpi: float = 0.0

    date: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "adset_id": self.adset_id,
            "adset_name": self.adset_name,
            "campaign_id": self.campaign_id,
            "platform": self.platform.value,
            "product_id": self.product_id,
            "spend": round(self.spend, 4),
            "revenue": round(self.revenue, 4),
            "roas": round(self.roas, 4),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": round(self.ctr, 6),
            "installs": self.installs,
            "cpi": round(self.cpi, 4),
            "date": self.date,
            "fetched_at": self.fetched_at,
        }


@dataclass
class CreativeMetrics:
    """创意级别指标."""
    creative_id: str = ""
    creative_name: str = ""
    adset_id: str = ""
    campaign_id: str = ""
    platform: DataSource = DataSource.META_ADS
    product_id: str = ""

    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    installs: int = 0
    revenue: float = 0.0
    roas: float = 0.0

    # Fatigue signals
    frequency: float = 0.0
    ctr_trend: float = 0.0  # delta vs previous period

    date: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "adset_id": self.adset_id,
            "campaign_id": self.campaign_id,
            "platform": self.platform.value,
            "product_id": self.product_id,
            "spend": round(self.spend, 4),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": round(self.ctr, 6),
            "installs": self.installs,
            "revenue": round(self.revenue, 4),
            "roas": round(self.roas, 4),
            "frequency": round(self.frequency, 2),
            "ctr_trend": round(self.ctr_trend, 4),
            "date": self.date,
            "fetched_at": self.fetched_at,
        }

    def is_fatigued(self, freq_threshold: float = 3.0, ctr_drop_threshold: float = -0.20) -> bool:
        """判断创意是否疲劳."""
        return self.frequency >= freq_threshold and self.ctr_trend <= ctr_drop_threshold


# ═══════════════════════════════════════════════════════════════
# Revenue & LTV
# ═══════════════════════════════════════════════════════════════


@dataclass
class UserRevenueCurve:
    """用户收入曲线 — 从 Adjust/Appsflyer 获取."""
    product_id: str = ""
    platform: DataSource = DataSource.ADJUST
    cohort_date: str = ""

    # Revenue per user at each day
    d0_revenue: float = 0.0
    d1_revenue: float = 0.0
    d7_revenue: float = 0.0
    d30_revenue: float = 0.0
    d60_revenue: float = 0.0
    d90_revenue: float = 0.0
    d120_revenue: float = 0.0
    d180_revenue: float = 0.0
    d365_revenue: float = 0.0

    # Predicted LTV
    predicted_ltv: float = 0.0
    ltv_confidence: float = 0.0

    # Cohort size
    cohort_size: int = 0

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "platform": self.platform.value,
            "cohort_date": self.cohort_date,
            "d0_revenue": round(self.d0_revenue, 6),
            "d1_revenue": round(self.d1_revenue, 6),
            "d7_revenue": round(self.d7_revenue, 6),
            "d30_revenue": round(self.d30_revenue, 6),
            "d60_revenue": round(self.d60_revenue, 6),
            "d90_revenue": round(self.d90_revenue, 6),
            "d120_revenue": round(self.d120_revenue, 6),
            "d180_revenue": round(self.d180_revenue, 6),
            "d365_revenue": round(self.d365_revenue, 6),
            "predicted_ltv": round(self.predicted_ltv, 4),
            "ltv_confidence": round(self.ltv_confidence, 2),
            "cohort_size": self.cohort_size,
            "fetched_at": self.fetched_at,
        }

    @property
    def total_realized_revenue(self) -> float:
        return (self.d0_revenue + self.d1_revenue + self.d7_revenue +
                self.d30_revenue + self.d60_revenue + self.d90_revenue +
                self.d120_revenue + self.d180_revenue + self.d365_revenue)


@dataclass
class RetentionCurve:
    """留存曲线."""
    product_id: str = ""
    platform: DataSource = DataSource.ADJUST
    cohort_date: str = ""

    d1_retention: float = 0.0
    d3_retention: float = 0.0
    d7_retention: float = 0.0
    d14_retention: float = 0.0
    d30_retention: float = 0.0
    d60_retention: float = 0.0
    d90_retention: float = 0.0

    payer_rate: float = 0.0
    cohort_size: int = 0

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "platform": self.platform.value,
            "cohort_date": self.cohort_date,
            "d1_retention": round(self.d1_retention, 4),
            "d3_retention": round(self.d3_retention, 4),
            "d7_retention": round(self.d7_retention, 4),
            "d14_retention": round(self.d14_retention, 4),
            "d30_retention": round(self.d30_retention, 4),
            "d60_retention": round(self.d60_retention, 4),
            "d90_retention": round(self.d90_retention, 4),
            "payer_rate": round(self.payer_rate, 4),
            "cohort_size": self.cohort_size,
            "fetched_at": self.fetched_at,
        }


# ═══════════════════════════════════════════════════════════════
# Gameplay Metrics
# ═══════════════════════════════════════════════════════════════


@dataclass
class GameplayMetrics:
    """游戏内指标 — 从 Firebase / App Store 获取."""
    product_id: str = ""
    platform: DataSource = DataSource.FIREBASE

    # DAU/MAU
    dau: int = 0
    mau: int = 0

    # Sessions
    sessions: int = 0
    avg_session_duration: float = 0.0
    sessions_per_user: float = 0.0

    # Progression
    tutorial_completion_rate: float = 0.0
    level1_completion: float = 0.0
    level5_completion: float = 0.0
    level10_completion: float = 0.0

    # Events
    key_events: int = 0

    date: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "platform": self.platform.value,
            "dau": self.dau,
            "mau": self.mau,
            "sessions": self.sessions,
            "avg_session_duration": round(self.avg_session_duration, 2),
            "sessions_per_user": round(self.sessions_per_user, 2),
            "tutorial_completion_rate": round(self.tutorial_completion_rate, 4),
            "level1_completion": round(self.level1_completion, 4),
            "level5_completion": round(self.level5_completion, 4),
            "level10_completion": round(self.level10_completion, 4),
            "key_events": self.key_events,
            "date": self.date,
            "fetched_at": self.fetched_at,
        }


# ═══════════════════════════════════════════════════════════════
# Unified Growth Data Event
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthDataEvent:
    """统一增长数据事件 — 所有外部数据进入 Growth OS 的标准格式."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: MetricType = MetricType.SPEND
    source: DataSource = DataSource.META_ADS
    product_id: str = ""
    date: str = ""

    # Metrics payload
    metrics: dict[str, Any] = field(default_factory=dict)

    # Metadata
    campaign_id: str = ""
    adset_id: str = ""
    creative_id: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "product_id": self.product_id,
            "date": self.date,
            "metrics": self.metrics,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "creative_id": self.creative_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_campaign_metrics(cls, metrics: CampaignMetrics) -> GrowthDataEvent:
        """从 CampaignMetrics 创建事件."""
        return cls(
            event_type=MetricType.SPEND,
            source=metrics.platform,
            product_id=metrics.product_id,
            date=metrics.date,
            metrics={
                "spend": metrics.spend,
                "revenue": metrics.revenue,
                "roas": metrics.roas,
                "impressions": metrics.impressions,
                "clicks": metrics.clicks,
                "installs": metrics.installs,
            },
            campaign_id=metrics.campaign_id,
        )

    @classmethod
    def from_retention(cls, retention: RetentionCurve) -> GrowthDataEvent:
        """从 RetentionCurve 创建事件."""
        return cls(
            event_type=MetricType.RETENTION,
            source=retention.platform,
            product_id=retention.product_id,
            date=retention.cohort_date,
            metrics={
                "d1_retention": retention.d1_retention,
                "d7_retention": retention.d7_retention,
                "d30_retention": retention.d30_retention,
                "payer_rate": retention.payer_rate,
            },
        )


# ═══════════════════════════════════════════════════════════════
# Connector Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConnectorConfig:
    """连接器配置."""
    connector_type: DataSource = DataSource.META_ADS
    api_version: str = ""
    base_url: str = ""
    auth_type: str = "oauth2"  # oauth2, api_key, token

    # Credentials (never log these)
    access_token: str = ""
    refresh_token: str = ""
    api_key: str = ""
    app_id: str = ""
    app_secret: str = ""

    # Rate limiting
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    retry_max_attempts: int = 3
    retry_backoff_seconds: float = 1.0

    # Timeouts
    connect_timeout: float = 10.0
    read_timeout: float = 30.0

    # Account
    account_id: str = ""
    accounts: list[str] = field(default_factory=list)

    # Data
    lookback_days: int = 90
    default_granularity: DataGranularity = DataGranularity.DAILY

    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_type": self.connector_type.value,
            "api_version": self.api_version,
            "base_url": self.base_url,
            "auth_type": self.auth_type,
            "max_requests_per_minute": self.max_requests_per_minute,
            "max_requests_per_hour": self.max_requests_per_hour,
            "retry_max_attempts": self.retry_max_attempts,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "account_id": self.account_id,
            "accounts": self.accounts,
            "lookback_days": self.lookback_days,
        }


# ═══════════════════════════════════════════════════════════════
# Connector Info
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConnectorInfo:
    """连接器信息 — 用于注册和监控."""
    connector_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source: DataSource = DataSource.META_ADS
    status: ConnectorStatus = ConnectorStatus.UNINITIALIZED
    health: ConnectorHealth = ConnectorHealth.UNKNOWN

    # Stats
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_success_at: str = ""
    last_error_at: str = ""
    last_error_message: str = ""

    # Rate limit
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    is_rate_limited: bool = False

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "name": self.name,
            "source": self.source.value,
            "status": self.status.value,
            "health": self.health.value,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "is_rate_limited": self.is_rate_limited,
            "created_at": self.created_at,
        }

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests