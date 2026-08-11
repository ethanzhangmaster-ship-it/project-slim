"""E13.1.2 Meta Ads Models — Meta 广告平台标准数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class MetaCampaignObjective(str, Enum):
    """Meta 广告系列目标."""
    APP_INSTALLS = "APP_INSTALLS"
    CONVERSIONS = "CONVERSIONS"
    REACH = "REACH"
    BRAND_AWARENESS = "BRAND_AWARENESS"
    LINK_CLICKS = "LINK_CLICKS"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    ENGAGEMENT = "ENGAGEMENT"
    APP_EVENTS = "APP_EVENTS"
    UNKNOWN = "UNKNOWN"


class MetaCampaignStatus(str, Enum):
    """Meta 广告系列状态."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"
    IN_PROCESS = "IN_PROCESS"
    WITH_ISSUES = "WITH_ISSUES"
    UNKNOWN = "UNKNOWN"


class MetaAccountStatus(str, Enum):
    """Meta 广告账户状态."""
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNSETTLED = "UNSETTLED"
    PENDING_RISK_REVIEW = "PENDING_RISK_REVIEW"
    PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
    IN_GRACE_PERIOD = "IN_GRACE_PERIOD"
    PENDING_CLOSURE = "PENDING_CLOSURE"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class MetaInsightLevel(str, Enum):
    """Meta 洞察数据层级."""
    ACCOUNT = "account"
    CAMPAIGN = "campaign"
    ADSET = "adset"
    AD = "ad"


class MetaInsightAction(str, Enum):
    """Meta 洞察动作类型."""
    MOBILE_APP_INSTALL = "mobile_app_install"
    PURCHASE = "purchase"
    APP_CUSTOM_EVENT = "app_custom_event"
    LINK_CLICK = "link_click"
    LANDING_PAGE_VIEW = "landing_page_view"
    VIDEO_VIEW = "video_view"
    POST_ENGAGEMENT = "post_engagement"


# ═══════════════════════════════════════════════════════════════
# Meta Account
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetaAccount:
    """Meta 广告账户."""
    account_id: str = ""
    name: str = ""
    currency: str = "USD"
    timezone: str = "UTC"
    status: MetaAccountStatus = MetaAccountStatus.UNKNOWN
    business_name: str = ""
    balance: float = 0.0
    amount_spent: float = 0.0
    created_at: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "currency": self.currency,
            "timezone": self.timezone,
            "status": self.status.value,
            "business_name": self.business_name,
            "balance": round(self.balance, 2),
            "amount_spent": round(self.amount_spent, 2),
            "created_at": self.created_at,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_active(self) -> bool:
        return self.status == MetaAccountStatus.ACTIVE


# ═══════════════════════════════════════════════════════════════
# Meta Campaign
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetaCampaign:
    """Meta 广告系列."""
    campaign_id: str = ""
    account_id: str = ""
    name: str = ""
    objective: MetaCampaignObjective = MetaCampaignObjective.UNKNOWN
    status: MetaCampaignStatus = MetaCampaignStatus.UNKNOWN
    daily_budget: float = 0.0
    lifetime_budget: float = 0.0
    bid_strategy: str = ""
    created_at: str = ""
    updated_at: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "account_id": self.account_id,
            "name": self.name,
            "objective": self.objective.value,
            "status": self.status.value,
            "daily_budget": round(self.daily_budget, 2),
            "lifetime_budget": round(self.lifetime_budget, 2),
            "bid_strategy": self.bid_strategy,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_active(self) -> bool:
        return self.status == MetaCampaignStatus.ACTIVE

    @property
    def is_paused(self) -> bool:
        return self.status == MetaCampaignStatus.PAUSED


# ═══════════════════════════════════════════════════════════════
# Meta AdSet
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetaAdSet:
    """Meta 广告组."""
    adset_id: str = ""
    campaign_id: str = ""
    account_id: str = ""
    name: str = ""
    status: MetaCampaignStatus = MetaCampaignStatus.UNKNOWN
    daily_budget: float = 0.0
    lifetime_budget: float = 0.0
    bid_amount: float = 0.0
    optimization_goal: str = ""
    billing_event: str = ""
    targeting: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "adset_id": self.adset_id,
            "campaign_id": self.campaign_id,
            "account_id": self.account_id,
            "name": self.name,
            "status": self.status.value,
            "daily_budget": round(self.daily_budget, 2),
            "lifetime_budget": round(self.lifetime_budget, 2),
            "bid_amount": round(self.bid_amount, 4),
            "optimization_goal": self.optimization_goal,
            "billing_event": self.billing_event,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "fetched_at": self.fetched_at,
        }


# ═══════════════════════════════════════════════════════════════
# Meta Creative
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetaCreative:
    """Meta 广告创意."""
    creative_id: str = ""
    name: str = ""
    account_id: str = ""
    title: str = ""
    body: str = ""
    thumbnail_url: str = ""
    image_url: str = ""
    video_url: str = ""
    call_to_action: str = ""
    image_hash: str = ""
    video_hash: str = ""
    object_story_spec: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "name": self.name,
            "account_id": self.account_id,
            "title": self.title,
            "body": self.body,
            "thumbnail_url": self.thumbnail_url,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "call_to_action": self.call_to_action,
            "image_hash": self.image_hash,
            "video_hash": self.video_hash,
            "created_at": self.created_at,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_video(self) -> bool:
        return bool(self.video_url)

    @property
    def is_image(self) -> bool:
        return bool(self.image_url) and not self.video_url

    @property
    def media_type(self) -> str:
        if self.video_url:
            return "video"
        if self.image_url:
            return "image"
        return "unknown"


# ═══════════════════════════════════════════════════════════════
# Meta Performance
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetaPerformance:
    """Meta 广告表现数据 — 统一标准化格式."""
    campaign_id: str = ""
    adset_id: str = ""
    creative_id: str = ""
    account_id: str = ""
    date_start: str = ""
    date_stop: str = ""

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
    purchases: int = 0
    cpa: float = 0.0

    # Fatigue signals
    frequency: float = 0.0
    quality_ranking: str = ""
    engagement_rate_ranking: str = ""
    conversion_rate_ranking: str = ""

    # Actions breakdown
    actions: dict[str, int] = field(default_factory=dict)
    action_values: dict[str, float] = field(default_factory=dict)

    # Cost per action
    cost_per_action_type: dict[str, float] = field(default_factory=dict)

    # Meta specifics
    reach: int = 0
    unique_clicks: int = 0
    social_spend: float = 0.0
    social_impressions: int = 0

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "creative_id": self.creative_id,
            "account_id": self.account_id,
            "date_start": self.date_start,
            "date_stop": self.date_stop,
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
            "purchases": self.purchases,
            "cpa": round(self.cpa, 4),
            "frequency": round(self.frequency, 2),
            "quality_ranking": self.quality_ranking,
            "engagement_rate_ranking": self.engagement_rate_ranking,
            "conversion_rate_ranking": self.conversion_rate_ranking,
            "reach": self.reach,
            "unique_clicks": self.unique_clicks,
            "fetched_at": self.fetched_at,
        }

    @property
    def is_profitable(self) -> bool:
        return self.roas > 1.0

    @property
    def is_fatigued(self) -> bool:
        """判断素材是否疲劳."""
        return self.frequency > 3.0 and self.ctr < 0.02

    @property
    def has_scaling_potential(self) -> bool:
        """判断是否有扩量潜力."""
        return self.roas > 1.5 and self.impressions > 1000

    @property
    def ctr_trend_indicator(self) -> str:
        """CTR 趋势指示."""
        if self.ctr < 0.01:
            return "declining"
        if self.ctr < 0.02:
            return "stable"
        return "rising"


# ═══════════════════════════════════════════════════════════════
# Meta API Response
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetaAPIResponse:
    """Meta API 响应包装."""
    success: bool = True
    data: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    error_code: int = 0
    error_type: str = ""
    paging: dict[str, Any] = field(default_factory=dict)
    rate_limit_remaining: int = 0
    request_id: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data_count": len(self.data),
            "error_message": self.error_message,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "has_paging": bool(self.paging),
            "rate_limit_remaining": self.rate_limit_remaining,
            "request_id": self.request_id,
        }

    @property
    def has_more(self) -> bool:
        return "next" in self.paging

    @property
    def is_error(self) -> bool:
        return not self.success


# ═══════════════════════════════════════════════════════════════
# Creative Fatigue Signal
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeFatigueSignal:
    """创意疲劳信号."""
    creative_id: str = ""
    campaign_id: str = ""
    adset_id: str = ""

    # Current period
    current_ctr: float = 0.0
    current_frequency: float = 0.0
    current_cpm: float = 0.0
    current_spend: float = 0.0

    # Previous period
    previous_ctr: float = 0.0
    previous_frequency: float = 0.0
    previous_cpm: float = 0.0

    # Delta
    ctr_change: float = 0.0
    frequency_change: float = 0.0
    cpm_change: float = 0.0

    # Assessment
    fatigue_score: float = 0.0
    fatigue_level: str = "low"
    recommendation: str = ""

    date: str = ""
    period_days: int = 7
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "current_ctr": round(self.current_ctr, 6),
            "current_frequency": round(self.current_frequency, 2),
            "current_cpm": round(self.current_cpm, 4),
            "current_spend": round(self.current_spend, 2),
            "previous_ctr": round(self.previous_ctr, 6),
            "previous_frequency": round(self.previous_frequency, 2),
            "previous_cpm": round(self.previous_cpm, 4),
            "ctr_change": round(self.ctr_change, 4),
            "frequency_change": round(self.frequency_change, 2),
            "cpm_change": round(self.cpm_change, 4),
            "fatigue_score": round(self.fatigue_score, 2),
            "fatigue_level": self.fatigue_level,
            "recommendation": self.recommendation,
            "date": self.date,
            "period_days": self.period_days,
        }

    @property
    def is_fatigued(self) -> bool:
        return self.fatigue_level in ("high", "critical")


# ═══════════════════════════════════════════════════════════════
# Scaling Opportunity
# ═══════════════════════════════════════════════════════════════


@dataclass
class ScalingOpportunity:
    """预算扩量机会."""
    campaign_id: str = ""
    account_id: str = ""

    # Current state
    current_daily_budget: float = 0.0
    current_spend: float = 0.0
    current_roas: float = 0.0
    current_installs: int = 0

    # Suggested
    suggested_daily_budget: float = 0.0
    suggested_budget_increase_pct: float = 0.0
    estimated_roas_at_scale: float = 0.0
    estimated_installs_at_scale: int = 0

    # Assessment
    confidence: float = 0.0
    reason: str = ""
    date: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "account_id": self.account_id,
            "current_daily_budget": round(self.current_daily_budget, 2),
            "current_spend": round(self.current_spend, 2),
            "current_roas": round(self.current_roas, 4),
            "current_installs": self.current_installs,
            "suggested_daily_budget": round(self.suggested_daily_budget, 2),
            "suggested_budget_increase_pct": round(self.suggested_budget_increase_pct, 2),
            "estimated_roas_at_scale": round(self.estimated_roas_at_scale, 4),
            "estimated_installs_at_scale": self.estimated_installs_at_scale,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
            "date": self.date,
        }

    @property
    def is_viable(self) -> bool:
        return self.confidence > 0.5 and self.suggested_budget_increase_pct > 0