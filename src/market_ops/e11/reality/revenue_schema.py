"""E11.6.1 Revenue Data Schema — 真实 IAP 收入数据模型。

定义游戏真实商业数据的稳定契约：

  AttributionSource — 归因来源 (ADJUST / APPSFLYER / FIREBASE / GOOGLE_PLAY / APP_STORE / INTERNAL)
  PayerType         — 付费用户类型 (FREE / MINI_PAYER / MID_PAYER / WHALE)
  RevenueEvent      — 单笔收入事件 (user_id, creative_id, genome_id, revenue)
  UserValueProfile  — 用户生命周期价值 (LTV, payer_type, purchase_count)
  RevenueSummary    — Genome 聚合收入 (total_users, total_payers, total_revenue, payer_rate, ARPU)

数据流：
  Adjust/Firebase/AppStore → RevenueEvent → RevenueSummary → Fitness → Evolution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# AttributionSource — 归因来源
# ═══════════════════════════════════════════════════════════

class AttributionSource(Enum):
    """归因数据来源。

    ADJUST       — Adjust 归因平台
    APPSFLYER    — AppsFlyer 归因平台
    FIREBASE     — Firebase Analytics
    GOOGLE_PLAY  — Google Play 原始数据
    APP_STORE    — App Store 原始数据
    INTERNAL     — 游戏内部数据
    """
    ADJUST = "adjust"
    APPSFLYER = "appsflyer"
    FIREBASE = "firebase"
    GOOGLE_PLAY = "google_play"
    APP_STORE = "app_store"
    INTERNAL = "internal"


# ═══════════════════════════════════════════════════════════
# PayerType — 付费用户类型
# ═══════════════════════════════════════════════════════════

class PayerType(Enum):
    """付费用户分层。

    FREE        — 免费用户 (total_revenue = $0)
    MINI_PAYER  — 小R ($0 < total_revenue < $10)
    MID_PAYER   — 中R ($10 <= total_revenue < $100)
    WHALE       — 大R (total_revenue >= $100)
    """
    FREE = "free"
    MINI_PAYER = "mini_payer"
    MID_PAYER = "mid_payer"
    WHALE = "whale"

    @classmethod
    def from_revenue(cls, total_revenue: float) -> PayerType:
        """根据累计收入判定用户层级。

        Args:
            total_revenue: 累计收入 (USD)

        Returns:
            PayerType
        """
        if total_revenue >= 100.0:
            return cls.WHALE
        elif total_revenue >= 10.0:
            return cls.MID_PAYER
        elif total_revenue > 0.0:
            return cls.MINI_PAYER
        else:
            return cls.FREE


# ═══════════════════════════════════════════════════════════
# RevenueEvent — 单笔收入事件
# ═══════════════════════════════════════════════════════════

@dataclass
class RevenueEvent:
    """一次真实收入事件。

    统一 Adjust、Firebase、Store 等不同来源的收入数据。

    对应：
        用户 → 购买 → 收入

    例如：
        RevenueEvent(
            event_id="rev_001",
            user_id="user_100",
            creative_id="creative_023",
            genome_id="genome_dragon",
            product_id="pack_small",
            revenue=4.99,
            currency="USD",
            country="US",
            source=AttributionSource.ADJUST,
        )
    """
    event_id: str = field(default_factory=lambda: f"rev_{uuid.uuid4().hex[:12]}")
    user_id: str = ""
    creative_id: str = ""
    genome_id: str = ""
    product_id: str = ""
    revenue: float = 0.0
    currency: str = "USD"
    country: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: AttributionSource = AttributionSource.INTERNAL

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        """事件是否有效（revenue > 0 且有 user_id）。"""
        return self.revenue > 0.0 and self.user_id != ""

    @property
    def has_genome(self) -> bool:
        """是否关联了 Genome。"""
        return self.genome_id != ""

    @property
    def has_creative(self) -> bool:
        """是否关联了 Creative。"""
        return self.creative_id != ""

    @property
    def is_attributed(self) -> bool:
        """是否可归因（同时有 genome_id 和 creative_id）。"""
        return self.has_genome and self.has_creative

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "creative_id": self.creative_id,
            "genome_id": self.genome_id,
            "product_id": self.product_id,
            "revenue": self.revenue,
            "currency": self.currency,
            "country": self.country,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevenueEvent:
        ts = data.get("timestamp")
        return cls(
            event_id=data.get("event_id", ""),
            user_id=data.get("user_id", ""),
            creative_id=data.get("creative_id", ""),
            genome_id=data.get("genome_id", ""),
            product_id=data.get("product_id", ""),
            revenue=data.get("revenue", 0.0),
            currency=data.get("currency", "USD"),
            country=data.get("country", ""),
            timestamp=datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc),
            source=AttributionSource(data.get("source", "internal")),
        )

    def __repr__(self) -> str:
        return (
            f"RevenueEvent(user={self.user_id!r}, "
            f"genome={self.genome_id!r}, "
            f"revenue={self.revenue}, "
            f"source={self.source.value})"
        )


# ═══════════════════════════════════════════════════════════
# UserValueProfile — 用户生命周期价值
# ═══════════════════════════════════════════════════════════

@dataclass
class UserValueProfile:
    """单个用户的 IAP 价值画像。

    追踪从安装到付费的完整生命周期。

    字段：
        - user_id: 用户标识
        - genome_id: 关联的 Genome ID
        - install_date: 安装日期
        - first_purchase_date: 首次购买日期
        - total_revenue: 累计收入
        - purchase_count: 购买次数
        - lifetime_days: 生命周期天数
        - payer_type: 付费层级

    例如：
        UserValueProfile(
            user_id="user_100",
            genome_id="genome_dragon",
            install_date="2026-07-01",
            first_purchase_date="2026-07-03",
            total_revenue=29.99,
            purchase_count=3,
            lifetime_days=30,
            payer_type=PayerType.MID_PAYER,
        )
    """
    user_id: str = ""
    genome_id: str = ""
    install_date: str = ""
    first_purchase_date: str = ""
    total_revenue: float = 0.0
    purchase_count: int = 0
    lifetime_days: int = 0
    payer_type: PayerType = PayerType.FREE

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_payer(self) -> bool:
        """是否付费用户。"""
        return self.payer_type != PayerType.FREE

    @property
    def days_to_first_purchase(self) -> int | None:
        """从安装到首购的天数。"""
        if not self.install_date or not self.first_purchase_date:
            return None
        try:
            install = datetime.fromisoformat(self.install_date)
            first = datetime.fromisoformat(self.first_purchase_date)
            return (first - install).days
        except (ValueError, TypeError):
            return None

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "genome_id": self.genome_id,
            "install_date": self.install_date,
            "first_purchase_date": self.first_purchase_date,
            "total_revenue": self.total_revenue,
            "purchase_count": self.purchase_count,
            "lifetime_days": self.lifetime_days,
            "payer_type": self.payer_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserValueProfile:
        return cls(
            user_id=data.get("user_id", ""),
            genome_id=data.get("genome_id", ""),
            install_date=data.get("install_date", ""),
            first_purchase_date=data.get("first_purchase_date", ""),
            total_revenue=data.get("total_revenue", 0.0),
            purchase_count=data.get("purchase_count", 0),
            lifetime_days=data.get("lifetime_days", 0),
            payer_type=PayerType(data.get("payer_type", "free")),
        )

    def __repr__(self) -> str:
        return (
            f"UserValueProfile(user={self.user_id!r}, "
            f"type={self.payer_type.value}, "
            f"revenue={self.total_revenue})"
        )


# ═══════════════════════════════════════════════════════════
# RevenueSummary — Genome 聚合收入
# ═══════════════════════════════════════════════════════════

@dataclass
class RevenueSummary:
    """一个 Genome 的聚合收入数据。

    汇总该 Genome 所吸引的所有用户的 IAP 商业表现。

    字段：
        - genome_id: Genome 标识
        - total_users: 总用户数
        - total_payers: 总付费用户数
        - total_revenue: 总收入
        - payer_rate: 付费率
        - arpu: ARPU
        - arppu: ARPPU
        - d7_revenue: D7 收入
        - d30_revenue: D30 收入
        - d90_revenue: D90 收入

    例如：
        Genome A:
          total_users=100000, total_payers=6000, payer_rate=0.06
          D30 revenue=$50000, ARPU=$0.50
    """
    genome_id: str = ""
    total_users: int = 0
    total_payers: int = 0
    total_revenue: float = 0.0
    payer_rate: float = 0.0
    arpu: float = 0.0
    arppu: float = 0.0
    d7_revenue: float = 0.0
    d30_revenue: float = 0.0
    d90_revenue: float = 0.0

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_significant(self) -> bool:
        """数据是否具有统计意义（total_users >= 100）。"""
        return self.total_users >= 100

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "total_users": self.total_users,
            "total_payers": self.total_payers,
            "total_revenue": self.total_revenue,
            "payer_rate": self.payer_rate,
            "arpu": self.arpu,
            "arppu": self.arppu,
            "d7_revenue": self.d7_revenue,
            "d30_revenue": self.d30_revenue,
            "d90_revenue": self.d90_revenue,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevenueSummary:
        return cls(
            genome_id=data.get("genome_id", ""),
            total_users=data.get("total_users", 0),
            total_payers=data.get("total_payers", 0),
            total_revenue=data.get("total_revenue", 0.0),
            payer_rate=data.get("payer_rate", 0.0),
            arpu=data.get("arpu", 0.0),
            arppu=data.get("arppu", 0.0),
            d7_revenue=data.get("d7_revenue", 0.0),
            d30_revenue=data.get("d30_revenue", 0.0),
            d90_revenue=data.get("d90_revenue", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"RevenueSummary(genome={self.genome_id!r}, "
            f"total_users={self.total_users}, "
            f"total_payers={self.total_payers}, "
            f"payer_rate={self.payer_rate}, "
            f"ARPU={self.arpu})"
        )