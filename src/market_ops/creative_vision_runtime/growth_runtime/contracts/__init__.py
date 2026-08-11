"""E15.0.2 Growth Data Contract — 统一数据格式.

将所有外部数据源 (Meta, Adjust, MAX, Store) 统一为 UnifiedGrowthEvent，
确保 Agent 接收到一致的数据格式。

支持的事件类型:
  - install:          安装事件
  - purchase:         购买事件
  - revenue:          收入事件
  - ad_spend:         广告花费
  - creative_result:  创意结果
  - campaign_result:  广告系列结果
  - experiment_result: 实验结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventSource(str, Enum):
    """数据来源."""
    META = "meta"
    ADJUST = "adjust"
    MAX = "max"
    STORE = "store"
    INTERNAL = "internal"


class EventType(str, Enum):
    """统一事件类型."""
    INSTALL = "install"
    PURCHASE = "purchase"
    REVENUE = "revenue"
    AD_SPEND = "ad_spend"
    CREATIVE_RESULT = "creative_result"
    CAMPAIGN_RESULT = "campaign_result"
    EXPERIMENT_RESULT = "experiment_result"


@dataclass
class UnifiedGrowthEvent:
    """统一增长事件 — 所有外部数据源的统一格式.

    Attributes:
        event_id:     事件唯一标识
        game_id:      游戏/产品 ID
        source:       数据来源 (Meta/Adjust/MAX/Store)
        event_type:   事件类型
        timestamp:    事件时间
        metrics:      指标数据 (根据事件类型不同)
        campaign_id:  广告系列 ID
        creative_id:  创意 ID
        platform:     平台标识
        raw_data:     原始数据 (用于调试)
        metadata:     扩展元数据
    """

    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    game_id: str = ""
    source: EventSource = EventSource.INTERNAL
    event_type: EventType = EventType.AD_SPEND
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: dict[str, Any] = field(default_factory=dict)
    campaign_id: str = ""
    creative_id: str = ""
    platform: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ──────────────────────────────────────

    @classmethod
    def from_meta_insight(
        cls,
        game_id: str,
        campaign_id: str,
        impressions: int,
        clicks: int,
        spend: float,
        revenue: float,
        roas: float,
        **kwargs: Any,
    ) -> UnifiedGrowthEvent:
        """从 Meta Ads Insight 创建."""
        return cls(
            game_id=game_id,
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id=campaign_id,
            platform="facebook",
            metrics={
                "impressions": impressions,
                "clicks": clicks,
                "spend": spend,
                "revenue": revenue,
                "roas": roas,
                "ctr": round(clicks / impressions, 4) if impressions > 0 else 0.0,
                "cpa": round(spend / clicks, 2) if clicks > 0 else 0.0,
            },
            raw_data=kwargs,
        )

    @classmethod
    def from_adjust_install(
        cls,
        game_id: str,
        installs: int,
        campaign_id: str = "",
        **kwargs: Any,
    ) -> UnifiedGrowthEvent:
        """从 Adjust 安装回调创建."""
        return cls(
            game_id=game_id,
            source=EventSource.ADJUST,
            event_type=EventType.INSTALL,
            campaign_id=campaign_id,
            platform="adjust",
            metrics={"installs": installs},
            raw_data=kwargs,
        )

    @classmethod
    def from_adjust_revenue(
        cls,
        game_id: str,
        revenue: float,
        purchases: int = 0,
        campaign_id: str = "",
        **kwargs: Any,
    ) -> UnifiedGrowthEvent:
        """从 Adjust 收入回调创建."""
        return cls(
            game_id=game_id,
            source=EventSource.ADJUST,
            event_type=EventType.REVENUE,
            campaign_id=campaign_id,
            platform="adjust",
            metrics={
                "revenue": revenue,
                "purchases": purchases,
                "arpu": round(revenue / purchases, 2) if purchases > 0 else 0.0,
            },
            raw_data=kwargs,
        )

    @classmethod
    def from_creative_result(
        cls,
        game_id: str,
        creative_id: str,
        campaign_id: str,
        impressions: int,
        clicks: int,
        spend: float,
        revenue: float,
        **kwargs: Any,
    ) -> UnifiedGrowthEvent:
        """从创意结果创建."""
        return cls(
            game_id=game_id,
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id=campaign_id,
            creative_id=creative_id,
            platform="facebook",
            metrics={
                "impressions": impressions,
                "clicks": clicks,
                "spend": spend,
                "revenue": revenue,
                "roas": round(revenue / spend, 4) if spend > 0 else 0.0,
                "ctr": round(clicks / impressions, 4) if impressions > 0 else 0.0,
            },
            raw_data=kwargs,
        )

    @classmethod
    def from_ad_spend(
        cls,
        game_id: str,
        spend: float,
        campaign_id: str = "",
        source: EventSource = EventSource.META,
        **kwargs: Any,
    ) -> UnifiedGrowthEvent:
        """从广告花费创建."""
        return cls(
            game_id=game_id,
            source=source,
            event_type=EventType.AD_SPEND,
            campaign_id=campaign_id,
            metrics={"spend": spend},
            raw_data=kwargs,
        )

    # ── Properties ───────────────────────────────────────────

    @property
    def roas(self) -> float:
        return self.metrics.get("roas", 0.0)

    @property
    def spend(self) -> float:
        return self.metrics.get("spend", 0.0)

    @property
    def revenue(self) -> float:
        return self.metrics.get("revenue", 0.0)

    @property
    def impressions(self) -> int:
        return self.metrics.get("impressions", 0)

    @property
    def clicks(self) -> int:
        return self.metrics.get("clicks", 0)

    @property
    def ctr(self) -> float:
        return self.metrics.get("ctr", 0.0)

    @property
    def installs(self) -> int:
        return self.metrics.get("installs", 0)

    @property
    def has_creative_data(self) -> bool:
        return bool(self.creative_id)

    @property
    def has_campaign_data(self) -> bool:
        return bool(self.campaign_id)

    # ── Validation ───────────────────────────────────────────

    def validate(self) -> list[str]:
        """验证事件完整性.

        Returns:
            错误信息列表 (空列表表示有效)
        """
        errors: list[str] = []
        if not self.game_id:
            errors.append("game_id is required")
        if not self.event_type:
            errors.append("event_type is required")
        if not self.metrics:
            errors.append("metrics cannot be empty")
        return errors

    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    # ── Serialization ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "game_id": self.game_id,
            "source": self.source.value,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "campaign_id": self.campaign_id,
            "creative_id": self.creative_id,
            "platform": self.platform,
            "metadata": self.metadata,
        }

    def to_agent_input(self) -> dict[str, Any]:
        """转换为 Agent 可消费的输入格式."""
        return {
            "game_id": self.game_id,
            "source": self.source.value,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "campaign_id": self.campaign_id,
            "creative_id": self.creative_id,
        }


class EventAggregator:
    """事件聚合器 — 将多个 UnifiedGrowthEvent 聚合为 Agent 可用的汇总数据.

    用法:
        aggregator = EventAggregator()
        events = [event1, event2, ...]
        summary = aggregator.aggregate(events, game_id="P04")
    """

    def aggregate(
        self,
        events: list[UnifiedGrowthEvent],
        game_id: str = "",
    ) -> dict[str, Any]:
        """聚合事件列表.

        Returns:
            {
                "game_id": "P04",
                "event_count": N,
                "total_spend": X,
                "total_revenue": X,
                "total_installs": N,
                "roas": X,
                "by_source": {...},
                "by_type": {...},
                "campaigns": {...},
                "creatives": {...}
            }
        """
        if not events:
            return {"game_id": game_id, "event_count": 0}

        total_spend = 0.0
        total_revenue = 0.0
        total_installs = 0
        total_impressions = 0
        total_clicks = 0

        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}
        campaigns: dict[str, dict[str, float]] = {}
        creatives: dict[str, dict[str, float]] = {}

        for e in events:
            total_spend += e.spend
            total_revenue += e.revenue
            total_installs += e.installs
            total_impressions += e.impressions
            total_clicks += e.clicks

            by_source[e.source.value] = by_source.get(e.source.value, 0) + 1
            by_type[e.event_type.value] = by_type.get(e.event_type.value, 0) + 1

            if e.campaign_id:
                c = campaigns.setdefault(e.campaign_id, {"spend": 0, "revenue": 0, "installs": 0})
                c["spend"] += e.spend
                c["revenue"] += e.revenue
                c["installs"] += e.installs

            if e.creative_id:
                c = creatives.setdefault(e.creative_id, {"spend": 0, "revenue": 0, "impressions": 0})
                c["spend"] += e.spend
                c["revenue"] += e.revenue
                c["impressions"] += e.impressions

        return {
            "game_id": game_id,
            "event_count": len(events),
            "total_spend": round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "total_installs": total_installs,
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "roas": round(total_revenue / total_spend, 4) if total_spend > 0 else 0.0,
            "ctr": round(total_clicks / total_impressions, 4) if total_impressions > 0 else 0.0,
            "by_source": by_source,
            "by_type": by_type,
            "campaigns": campaigns,
            "creatives": creatives,
        }


__all__ = [
    "UnifiedGrowthEvent",
    "EventSource",
    "EventType",
    "EventAggregator",
]