"""E11.6.2 Adjust Schema — Adjust 原始数据模型。

定义 Adjust 归因事件的原始数据结构：

  RevenueType      — 收入类型 (IAP / AD / TOTAL)
  AdjustRawEvent   — Adjust 原始事件 (user_id, event_name, revenue, creative, campaign, ...)

所有 Adjust 数据通过此模型统一进入 E11 Reality Layer。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# RevenueType — Adjust 收入类型
# ═══════════════════════════════════════════════════════════

class RevenueType(Enum):
    """Adjust 收入类型。

    IAP   — 内购收入 (purchase, subscription)
    AD    — 广告收入 (ad_revenue)
    TOTAL — 混合收入 (总收)
    """
    IAP = "iap"
    AD = "ad"
    TOTAL = "total"


# ═══════════════════════════════════════════════════════════
# AdjustRawEvent — Adjust 原始事件
# ═══════════════════════════════════════════════════════════

@dataclass
class AdjustRawEvent:
    """Adjust 原始归因事件。

    对应 Adjust 回调 / API 返回的原始数据。

    字段：
        - adjust_event_id: Adjust 事件 ID
        - user_id: 用户标识
        - event_name: 事件名称 (e.g. "purchase", "ad_revenue", "install")
        - revenue: 收入金额
        - currency: 货币
        - revenue_type: 收入类型
        - campaign: 广告系列
        - adgroup: 广告组
        - creative: 素材 ID
        - country: 国家
        - timestamp: 事件时间

    例如：
        AdjustRawEvent(
            adjust_event_id="adj_abc123",
            user_id="12345",
            event_name="purchase",
            revenue=4.99,
            revenue_type=RevenueType.IAP,
            creative="dragon_hook_001",
            campaign="campaign_001",
            country="US",
        )
    """
    adjust_event_id: str = ""
    user_id: str = ""
    event_name: str = ""
    revenue: float = 0.0
    currency: str = "USD"
    revenue_type: RevenueType = RevenueType.TOTAL
    campaign: str = ""
    adgroup: str = ""
    creative: str = ""
    country: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_iap(self) -> bool:
        """是否内购收入事件。"""
        return self.revenue_type == RevenueType.IAP and self.revenue > 0.0

    @property
    def is_ad(self) -> bool:
        """是否广告收入事件。"""
        return self.revenue_type == RevenueType.AD and self.revenue > 0.0

    @property
    def is_purchase(self) -> bool:
        """是否购买事件（event_name 包含 purchase）。"""
        return "purchase" in self.event_name.lower()

    @property
    def is_install(self) -> bool:
        """是否安装事件。"""
        return self.event_name.lower() == "install"

    @property
    def has_creative(self) -> bool:
        """是否关联了创意素材。"""
        return self.creative != ""

    @property
    def has_campaign(self) -> bool:
        """是否关联了广告系列。"""
        return self.campaign != ""

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjust_event_id": self.adjust_event_id,
            "user_id": self.user_id,
            "event_name": self.event_name,
            "revenue": self.revenue,
            "currency": self.currency,
            "revenue_type": self.revenue_type.value,
            "campaign": self.campaign,
            "adgroup": self.adgroup,
            "creative": self.creative,
            "country": self.country,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdjustRawEvent:
        ts = data.get("timestamp")
        return cls(
            adjust_event_id=data.get("adjust_event_id", ""),
            user_id=data.get("user_id", ""),
            event_name=data.get("event_name", ""),
            revenue=data.get("revenue", 0.0),
            currency=data.get("currency", "USD"),
            revenue_type=RevenueType(data.get("revenue_type", "total")),
            campaign=data.get("campaign", ""),
            adgroup=data.get("adgroup", ""),
            creative=data.get("creative", ""),
            country=data.get("country", ""),
            timestamp=datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"AdjustRawEvent(event={self.adjust_event_id!r}, "
            f"user={self.user_id!r}, "
            f"name={self.event_name!r}, "
            f"revenue={self.revenue}, "
            f"type={self.revenue_type.value})"
        )