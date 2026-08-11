"""E11 Phase 2 — Adjust Revenue Entity 数据模型。

定义 Adjust 收入数据的标准化数据结构。

每个 AdjustRevenueEntity 代表一个 creative 在 Adjust 中的归因数据：
  - 用户量（installs, sessions, purchasers）
  - 留存（D1/D7/D30）
  - 收入（IAP D1/D7/D30 + AD D1/D7/D30）

通过 AdjustCreativeMatcher 与 CreativeEntity 匹配后，
写入 CreativeEntity.performance.revenue。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AdjustRevenueEntity:
    """Adjust 收入数据实体。

    对应 Adjust 中一个 creative 的归因收入数据。

    Usage:
        entity = AdjustRevenueEntity(
            creative_asset_id="MW_VID_260721_000123",
            adjust_creative_id="adj_001",
            installs=2000,
            sessions=5000,
            purchasers=120,
            iap_d1=800.0,
            iap_d7=3000.0,
            iap_d30=10000.0,
            ad_d1=200.0,
            ad_d7=500.0,
            ad_d30=2000.0,
        )
        assert entity.total_revenue == 12000.0
    """

    # ── Identity ────────────────────────────────────────
    creative_asset_id: str = ""      # 匹配用：统一素材编号
    adjust_creative_id: str = ""     # Adjust creative_id
    legacy_id: str = ""              # 旧格式兼容：6位数字

    # ── Attribution ─────────────────────────────────────
    campaign: str = ""               # Adjust 归因 campaign
    adgroup: str = ""                # Adjust 归因 adgroup
    creative: str = ""               # Adjust 归因 creative name

    # ── Users ───────────────────────────────────────────
    installs: int = 0                # 安装数
    sessions: int = 0                # 会话数
    purchasers: int = 0              # 付费用户数
    payer_rate: float = 0.0          # 付费率 = purchasers / installs

    # ── Retention ───────────────────────────────────────
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    retention_d30: float = 0.0

    # ── IAP Revenue ─────────────────────────────────────
    iap_d1: float = 0.0
    iap_d7: float = 0.0
    iap_d30: float = 0.0

    # ── AD Revenue ──────────────────────────────────────
    ad_d1: float = 0.0
    ad_d7: float = 0.0
    ad_d30: float = 0.0

    # ── Cost & ROI ──────────────────────────────────────
    cost: float = 0.0                # Adjust 侧花费（用于交叉验证 Facebook spend）
    adjust_roas_d1: float = 0.0      # Adjust 原生 D1 ROAS
    adjust_roas_d7: float = 0.0      # Adjust 原生 D7 ROAS
    adjust_roas_d30: float = 0.0     # Adjust 原生 D30 ROAS

    # ── Metadata ────────────────────────────────────────
    date_start: str = ""             # 数据起始日期
    date_end: str = ""               # 数据结束日期
    synced_at: str = ""              # 同步时间

    # ── Computed ────────────────────────────────────────

    @property
    def total_revenue(self) -> float:
        """总收入 = IAP D30 + AD D30。"""
        return self.iap_d30 + self.ad_d30

    @property
    def total_iap(self) -> float:
        return self.iap_d30

    @property
    def total_ad(self) -> float:
        return self.ad_d30

    @property
    def has_revenue(self) -> bool:
        return self.total_revenue > 0.0

    @property
    def has_iap(self) -> bool:
        return self.iap_d30 > 0.0

    @property
    def has_users(self) -> bool:
        return self.installs > 0

    # ── Serialization ───────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "adjust_creative_id": self.adjust_creative_id,
            "legacy_id": self.legacy_id,
            "campaign": self.campaign,
            "adgroup": self.adgroup,
            "creative": self.creative,
            "installs": self.installs,
            "sessions": self.sessions,
            "purchasers": self.purchasers,
            "payer_rate": self.payer_rate,
            "retention_d1": self.retention_d1,
            "retention_d7": self.retention_d7,
            "retention_d30": self.retention_d30,
            "iap_d1": self.iap_d1,
            "iap_d7": self.iap_d7,
            "iap_d30": self.iap_d30,
            "ad_d1": self.ad_d1,
            "ad_d7": self.ad_d7,
            "ad_d30": self.ad_d30,
            "cost": self.cost,
            "adjust_roas_d1": self.adjust_roas_d1,
            "adjust_roas_d7": self.adjust_roas_d7,
            "adjust_roas_d30": self.adjust_roas_d30,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "synced_at": self.synced_at or datetime.now().isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdjustRevenueEntity:
        return cls(
            creative_asset_id=data.get("creative_asset_id", ""),
            adjust_creative_id=data.get("adjust_creative_id", ""),
            legacy_id=data.get("legacy_id", ""),
            campaign=data.get("campaign", ""),
            adgroup=data.get("adgroup", ""),
            creative=data.get("creative", ""),
            installs=int(data.get("installs", 0)),
            sessions=int(data.get("sessions", 0)),
            purchasers=int(data.get("purchasers", 0)),
            payer_rate=float(data.get("payer_rate", 0.0)),
            retention_d1=float(data.get("retention_d1", 0.0)),
            retention_d7=float(data.get("retention_d7", 0.0)),
            retention_d30=float(data.get("retention_d30", 0.0)),
            iap_d1=float(data.get("iap_d1", 0.0)),
            iap_d7=float(data.get("iap_d7", 0.0)),
            iap_d30=float(data.get("iap_d30", 0.0)),
            ad_d1=float(data.get("ad_d1", 0.0)),
            ad_d7=float(data.get("ad_d7", 0.0)),
            ad_d30=float(data.get("ad_d30", 0.0)),
            cost=float(data.get("cost", 0.0)),
            adjust_roas_d1=float(data.get("adjust_roas_d1", 0.0)),
            adjust_roas_d7=float(data.get("adjust_roas_d7", 0.0)),
            adjust_roas_d30=float(data.get("adjust_roas_d30", 0.0)),
            date_start=data.get("date_start", ""),
            date_end=data.get("date_end", ""),
            synced_at=data.get("synced_at", ""),
        )

    def __repr__(self) -> str:
        return (
            f"AdjustRevenueEntity(id={self.creative_asset_id!r}, "
            f"installs={self.installs}, "
            f"revenue=${self.total_revenue:,.0f})"
        )