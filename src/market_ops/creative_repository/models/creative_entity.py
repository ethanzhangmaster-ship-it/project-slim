"""E11 Phase 2 — Creative Core Entity (升级版)。

统一的创意生命周期对象，是所有数据源（Facebook/Adjust/Eagle/Lovart）的聚合视图。

Phase 2 升级：
  - CreativePerformance 重构为 acquisition/revenue/metrics 子结构
  - Revenue 按 D1/D7/D30 拆分 IAP 和 AD 收入
  - ROAS/CPI 改为计算属性，不再存储原始数据
  - 新增 AcquisitionData / RevenueData 子模型

数据源到字段的映射：
  - Facebook → sources.facebook_id,  performance.acquisition,  asset (urls)
  - Adjust   → sources.adjust_id,    performance.revenue
  - Eagle    → sources.eagle_path,   asset (local paths)
  - Lovart   → sources.lovart_id,    analysis (DNA)

ID 格式：{产品前缀}_{类型}_{日期}_{序号}
  例如：MW_IMG_260721_000123 (Merge Witches 图片)
        MW_VIDEO_260721_000456 (Merge Witches 视频)

兼容旧格式：同时保留 legacy_id（纯6位数字 000123）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class CreativeType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════
# Identity
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeIdentity:
    """创意身份信息。"""
    name: str = ""           # 素材名称
    type: CreativeType = CreativeType.UNKNOWN
    product: str = ""        # 产品前缀，如 "MW" (Merge Witches)
    language: str = ""       # 语言，如 "en", "zh"
    country: str = ""        # 国家，如 "US", "JP"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "product": self.product,
            "language": self.language,
            "country": self.country,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeIdentity:
        ct = data.get("type", "unknown")
        try:
            ctype = CreativeType(ct)
        except ValueError:
            ctype = CreativeType.UNKNOWN
        return cls(
            name=data.get("name", ""),
            type=ctype,
            product=data.get("product", ""),
            language=data.get("language", ""),
            country=data.get("country", ""),
            tags=data.get("tags", []),
        )


# ═══════════════════════════════════════════════════════════
# Sources
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeSources:
    """各数据源的外部 ID 映射。"""
    facebook_id: str = ""     # Facebook creative_id
    adjust_id: str = ""       # Adjust creative_id
    eagle_path: str = ""      # Eagle 本地路径
    lovart_id: str = ""       # Lovart 生成 ID

    @property
    def has_facebook(self) -> bool:
        return bool(self.facebook_id)

    @property
    def has_adjust(self) -> bool:
        return bool(self.adjust_id)

    @property
    def has_eagle(self) -> bool:
        return bool(self.eagle_path)

    @property
    def has_lovart(self) -> bool:
        return bool(self.lovart_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "facebook_id": self.facebook_id,
            "adjust_id": self.adjust_id,
            "eagle_path": self.eagle_path,
            "lovart_id": self.lovart_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeSources:
        return cls(
            facebook_id=data.get("facebook_id", ""),
            adjust_id=data.get("adjust_id", ""),
            eagle_path=data.get("eagle_path", ""),
            lovart_id=data.get("lovart_id", ""),
        )


# ═══════════════════════════════════════════════════════════
# Performance — Acquisition (Facebook)
# ═══════════════════════════════════════════════════════════

@dataclass
class AcquisitionData:
    """Facebook 投放数据（获取成本）。

    由 Facebook Ingestion 写入，记录广告的投放表现。
    """
    spend: float = 0.0        # 总花费
    impressions: int = 0      # 展示次数
    clicks: int = 0           # 点击次数
    ctr: float = 0.0          # 点击率 (%)
    cpc: float = 0.0          # 单次点击成本
    cpm: float = 0.0          # 千次展示成本
    installs: int = 0         # 安装数

    @property
    def has_data(self) -> bool:
        return self.spend > 0.0 or self.impressions > 0

    @property
    def cpi(self) -> float:
        """CPI = spend / installs。"""
        if self.installs <= 0:
            return 0.0
        return round(self.spend / self.installs, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": self.ctr,
            "cpc": self.cpc,
            "cpm": self.cpm,
            "installs": self.installs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcquisitionData:
        return cls(
            spend=float(data.get("spend", 0.0)),
            impressions=int(data.get("impressions", 0)),
            clicks=int(data.get("clicks", 0)),
            ctr=float(data.get("ctr", 0.0)),
            cpc=float(data.get("cpc", 0.0)),
            cpm=float(data.get("cpm", 0.0)),
            installs=int(data.get("installs", 0)),
        )


# ═══════════════════════════════════════════════════════════
# Performance — Revenue (Adjust)
# ═══════════════════════════════════════════════════════════

@dataclass
class RevenueData:
    """Adjust 收入数据（按 D1/D7/D30 拆分 IAP 和 AD）。

    由 Adjust Ingestion 写入，记录用户生命周期价值。
    """
    # ── IAP 收入 ────────────────────────────────────────
    iap_d1: float = 0.0
    iap_d7: float = 0.0
    iap_d30: float = 0.0

    # ── AD 收入 ─────────────────────────────────────────
    ad_d1: float = 0.0
    ad_d7: float = 0.0
    ad_d30: float = 0.0

    # ── User ────────────────────────────────────────────
    purchases: int = 0        # 付费次数
    payer_count: int = 0      # 付费用户数
    payer_rate: float = 0.0   # 付费率

    # ── Cost ────────────────────────────────────────────
    adjust_cost: float = 0.0   # Adjust 侧花费（交叉验证）
    adjust_roas_d1: float = 0.0  # Adjust 原生 D1 ROAS
    adjust_roas_d7: float = 0.0  # Adjust 原生 D7 ROAS
    adjust_roas_d30: float = 0.0 # Adjust 原生 D30 ROAS

    @property
    def total_iap(self) -> float:
        return self.iap_d30

    @property
    def total_ad(self) -> float:
        return self.ad_d30

    @property
    def total_revenue(self) -> float:
        """总收入 = IAP D30 + AD D30。"""
        return self.iap_d30 + self.ad_d30

    @property
    def has_data(self) -> bool:
        return self.total_revenue > 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iap_d1": self.iap_d1,
            "iap_d7": self.iap_d7,
            "iap_d30": self.iap_d30,
            "ad_d1": self.ad_d1,
            "ad_d7": self.ad_d7,
            "ad_d30": self.ad_d30,
            "purchases": self.purchases,
            "payer_count": self.payer_count,
            "payer_rate": self.payer_rate,
            "adjust_cost": self.adjust_cost,
            "adjust_roas_d1": self.adjust_roas_d1,
            "adjust_roas_d7": self.adjust_roas_d7,
            "adjust_roas_d30": self.adjust_roas_d30,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevenueData:
        return cls(
            iap_d1=float(data.get("iap_d1", 0.0)),
            iap_d7=float(data.get("iap_d7", 0.0)),
            iap_d30=float(data.get("iap_d30", 0.0)),
            ad_d1=float(data.get("ad_d1", 0.0)),
            ad_d7=float(data.get("ad_d7", 0.0)),
            ad_d30=float(data.get("ad_d30", 0.0)),
            purchases=int(data.get("purchases", 0)),
            payer_count=int(data.get("payer_count", 0)),
            payer_rate=float(data.get("payer_rate", 0.0)),
            adjust_cost=float(data.get("adjust_cost", 0.0)),
            adjust_roas_d1=float(data.get("adjust_roas_d1", 0.0)),
            adjust_roas_d7=float(data.get("adjust_roas_d7", 0.0)),
            adjust_roas_d30=float(data.get("adjust_roas_d30", 0.0)),
        )


# ═══════════════════════════════════════════════════════════
# CreativePerformance — 统一效果数据
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativePerformance:
    """统一投放效果数据。

    包含：
      - acquisition: Facebook 投放数据（获取成本）
      - revenue:     Adjust 收入数据（用户价值）
      - metrics:     计算指标（ROAS, CPI 等，不存储，实时计算）

    Usage:
        perf = CreativePerformance(
            acquisition=AcquisitionData(spend=5000, installs=2000),
            revenue=RevenueData(iap_d30=12000, payer_count=120),
        )
        assert perf.cpi == 2.5
        assert perf.roas_d30 == 2.4
    """

    acquisition: AcquisitionData = field(default_factory=AcquisitionData)
    revenue: RevenueData = field(default_factory=RevenueData)

    # ── Computed Metrics ────────────────────────────────

    @property
    def cpi(self) -> float:
        """CPI = spend / installs。"""
        return self.acquisition.cpi

    @property
    def arpu(self) -> float:
        """ARPU = revenue / installs。"""
        if self.acquisition.installs <= 0:
            return 0.0
        return round(self.revenue.total_revenue / self.acquisition.installs, 2)

    @property
    def ltv_d30(self) -> float:
        """LTV D30 = D30 收入 / 安装数。"""
        return self.arpu

    @property
    def roas_d1(self) -> float:
        """ROAS D1 = (IAP D1 + AD D1) / spend。"""
        if self.acquisition.spend <= 0:
            return 0.0
        return round((self.revenue.iap_d1 + self.revenue.ad_d1) / self.acquisition.spend, 4)

    @property
    def roas_d7(self) -> float:
        """ROAS D7 = (IAP D7 + AD D7) / spend。"""
        if self.acquisition.spend <= 0:
            return 0.0
        return round((self.revenue.iap_d7 + self.revenue.ad_d7) / self.acquisition.spend, 4)

    @property
    def roas_d30(self) -> float:
        """ROAS D30 = (IAP D30 + AD D30) / spend。"""
        if self.acquisition.spend <= 0:
            return 0.0
        return round((self.revenue.iap_d30 + self.revenue.ad_d30) / self.acquisition.spend, 4)

    @property
    def roi(self) -> float:
        """简单 ROI = total_revenue / spend。"""
        if self.acquisition.spend <= 0:
            return 0.0
        return round(self.revenue.total_revenue / self.acquisition.spend, 4)

    # ── Status ──────────────────────────────────────────

    @property
    def has_acquisition(self) -> bool:
        return self.acquisition.has_data

    @property
    def has_revenue(self) -> bool:
        return self.revenue.has_data

    @property
    def roas_d30_str(self) -> str:
        roas = self.roas_d30
        return f"{roas:.2%}" if roas > 0 else "N/A"

    # ── Serialization ───────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "acquisition": self.acquisition.to_dict(),
            "revenue": self.revenue.to_dict(),
            "metrics": {
                "cpi": self.cpi,
                "arpu": self.arpu,
                "ltv_d30": self.ltv_d30,
                "roas_d1": self.roas_d1,
                "roas_d7": self.roas_d7,
                "roas_d30": self.roas_d30,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativePerformance:
        # 兼容旧格式（flat structure）
        if "acquisition" in data:
            acquisition = AcquisitionData.from_dict(data["acquisition"])
        else:
            acquisition = AcquisitionData.from_dict(data)

        if "revenue" in data:
            rev_data = data["revenue"]
            if isinstance(rev_data, dict):
                revenue = RevenueData.from_dict(rev_data)
            else:
                # 旧格式：revenue 是 float，忽略
                revenue = RevenueData()
        else:
            revenue = RevenueData()

        return cls(acquisition=acquisition, revenue=revenue)


# ═══════════════════════════════════════════════════════════
# Asset
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeAsset:
    """素材文件路径（Phase 3 升级：增加 Eagle/Lovart 绑定字段）。"""
    image_url: str = ""        # 图片 URL
    image_path: str = ""       # 本地图片路径
    video_url: str = ""        # 视频 URL
    video_path: str = ""       # 本地视频路径（Eagle）
    thumbnail_url: str = ""

    # Phase 3 新增：素材来源绑定
    eagle_path: str = ""              # Eagle 本地素材完整路径
    eagle_filename: str = ""          # Eagle 文件名（用于调试）
    lovart_generation_id: str = ""    # Lovart 生成任务 ID
    source_type: str = ""             # "FACEBOOK" | "LOVART" | "EAGLE"
    matched_confidence: float = 0.0   # 匹配置信度 0.0-1.0
    match_method: str = ""            # 匹配方法: "a_number" | "filename" | "exact_id"

    @property
    def has_image(self) -> bool:
        return bool(self.image_url) or bool(self.image_path)

    @property
    def has_video(self) -> bool:
        return bool(self.video_url) or bool(self.video_path)

    @property
    def has_eagle(self) -> bool:
        return bool(self.eagle_path)

    @property
    def has_lovart(self) -> bool:
        return bool(self.lovart_generation_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_url": self.image_url,
            "image_path": self.image_path,
            "video_url": self.video_url,
            "video_path": self.video_path,
            "thumbnail_url": self.thumbnail_url,
            "eagle_path": self.eagle_path,
            "eagle_filename": self.eagle_filename,
            "lovart_generation_id": self.lovart_generation_id,
            "source_type": self.source_type,
            "matched_confidence": self.matched_confidence,
            "match_method": self.match_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeAsset:
        return cls(
            image_url=data.get("image_url", ""),
            image_path=data.get("image_path", ""),
            video_url=data.get("video_url", ""),
            video_path=data.get("video_path", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            eagle_path=data.get("eagle_path", ""),
            eagle_filename=data.get("eagle_filename", ""),
            lovart_generation_id=data.get("lovart_generation_id", ""),
            source_type=data.get("source_type", ""),
            matched_confidence=float(data.get("matched_confidence", 0.0)),
            match_method=data.get("match_method", ""),
        )


# ═══════════════════════════════════════════════════════════
# Analysis
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeAnalysis:
    """创意分析数据（Phase 4 Lovart 填充）。"""
    image_dna: dict[str, Any] = field(default_factory=dict)
    video_dna: dict[str, Any] = field(default_factory=dict)
    hook_type: str = ""
    reward_type: str = ""
    emotion: str = ""
    style: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_dna": self.image_dna,
            "video_dna": self.video_dna,
            "hook_type": self.hook_type,
            "reward_type": self.reward_type,
            "emotion": self.emotion,
            "style": self.style,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeAnalysis:
        return cls(
            image_dna=data.get("image_dna", {}),
            video_dna=data.get("video_dna", {}),
            hook_type=data.get("hook_type", ""),
            reward_type=data.get("reward_type", ""),
            emotion=data.get("emotion", ""),
            style=data.get("style", ""),
            notes=data.get("notes", ""),
        )


# ═══════════════════════════════════════════════════════════
# CreativeEntity — 核心聚合对象
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeEntity:
    """统一的创意生命周期对象。

    这是所有数据源的聚合视图。每个数据源通过各自的同步器写入对应字段。

    数据源到字段的映射：
      Facebook → sources.facebook_id, performance (acquisition), asset (urls)
      Adjust   → sources.adjust_id,  performance (revenue)
      Eagle    → sources.eagle_path, asset (video_path)
      Lovart   → sources.lovart_id,  analysis

    Usage:
        entity = CreativeEntity(
            creative_asset_id="MW_IMG_260721_000123",
            identity=CreativeIdentity(name="witch_merge", type=CreativeType.IMAGE),
        )
        # Facebook 同步后
        entity.merge_facebook_data(fb_entity)
        # Adjust 同步后
        entity.merge_adjust_data(adjust_data)
    """

    creative_asset_id: str = ""
    legacy_id: str = ""         # 旧格式兼容，如 "000123"

    identity: CreativeIdentity = field(default_factory=CreativeIdentity)
    sources: CreativeSources = field(default_factory=CreativeSources)
    performance: CreativePerformance = field(default_factory=CreativePerformance)
    asset: CreativeAsset = field(default_factory=CreativeAsset)
    analysis: CreativeAnalysis = field(default_factory=CreativeAnalysis)

    # ── Metadata ────────────────────────────────────────
    created_at: str = ""
    updated_at: str = ""
    synced_sources: list[str] = field(default_factory=list)  # ["facebook", "adjust", ...]

    # ── Properties ──────────────────────────────────────

    @property
    def is_video(self) -> bool:
        return self.identity.type == CreativeType.VIDEO

    @property
    def is_image(self) -> bool:
        return self.identity.type == CreativeType.IMAGE

    @property
    def has_performance(self) -> bool:
        return self.performance.has_acquisition

    @property
    def has_revenue(self) -> bool:
        return self.performance.has_revenue

    @property
    def display_name(self) -> str:
        return self.identity.name or self.creative_asset_id

    # ── Merge from sources ──────────────────────────────

    def merge_facebook_data(self, fb_entity: Any) -> None:
        """从 FacebookCreativeEntity 合并数据（Phase 2 升级）。"""
        from datetime import datetime

        self.sources.facebook_id = fb_entity.creative_id

        # Identity
        self.identity.name = fb_entity.ad_name
        self.identity.type = fb_entity.creative_type

        # Performance → Acquisition
        acq = self.performance.acquisition
        acq.spend = fb_entity.spend
        acq.impressions = fb_entity.impressions
        acq.clicks = fb_entity.clicks
        acq.ctr = fb_entity.ctr
        acq.cpc = fb_entity.cpc
        acq.cpm = fb_entity.cpm
        acq.installs = fb_entity.installs

        # Asset
        self.asset.image_url = fb_entity.image_url
        self.asset.thumbnail_url = fb_entity.thumbnail_url
        self.asset.video_url = fb_entity.video_id

        self.updated_at = datetime.now().isoformat()
        if "facebook" not in self.synced_sources:
            self.synced_sources.append("facebook")

    def merge_adjust_data(self, adjust_data: dict[str, Any]) -> None:
        """从 Adjust 数据合并（Phase 2 升级）。

        Args:
            adjust_data: 包含 iap_d1/d7/d30, ad_d1/d7/d30, purchases, payer_count,
                         payer_rate 等字段的字典，或 AdjustRevenueEntity.to_dict()
        """
        from datetime import datetime

        self.sources.adjust_id = adjust_data.get("adjust_id", "") or adjust_data.get("adjust_creative_id", "")

        # Performance → Revenue (D1/D7/D30 拆分)
        rev = self.performance.revenue
        rev.iap_d1 = float(adjust_data.get("iap_d1", 0.0))
        rev.iap_d7 = float(adjust_data.get("iap_d7", 0.0))
        rev.iap_d30 = float(adjust_data.get("iap_d30", 0.0))
        rev.ad_d1 = float(adjust_data.get("ad_d1", 0.0))
        rev.ad_d7 = float(adjust_data.get("ad_d7", 0.0))
        rev.ad_d30 = float(adjust_data.get("ad_d30", 0.0))
        rev.purchases = int(adjust_data.get("purchases", 0))
        rev.payer_count = int(adjust_data.get("payer_count", 0))
        rev.payer_rate = float(adjust_data.get("payer_rate", 0.0))
        rev.adjust_cost = float(adjust_data.get("adjust_cost", 0.0) or adjust_data.get("cost", 0.0))
        rev.adjust_roas_d1 = float(adjust_data.get("adjust_roas_d1", 0.0))
        rev.adjust_roas_d7 = float(adjust_data.get("adjust_roas_d7", 0.0))
        rev.adjust_roas_d30 = float(adjust_data.get("adjust_roas_d30", 0.0))

        self.updated_at = datetime.now().isoformat()
        if "adjust" not in self.synced_sources:
            self.synced_sources.append("adjust")

    def merge_eagle_data(self, eagle_data: dict[str, Any]) -> None:
        """从 Eagle 数据合并。"""
        from datetime import datetime

        self.sources.eagle_path = eagle_data.get("eagle_path", "")
        self.asset.video_path = eagle_data.get("video_path", "")
        self.asset.image_path = eagle_data.get("image_path", "")

        self.updated_at = datetime.now().isoformat()
        if "eagle" not in self.synced_sources:
            self.synced_sources.append("eagle")

    def merge_lovart_data(self, lovart_data: dict[str, Any]) -> None:
        """从 Lovart 数据合并。"""
        from datetime import datetime

        self.sources.lovart_id = lovart_data.get("lovart_id", "")

        self.analysis.image_dna = lovart_data.get("image_dna", {})
        self.analysis.video_dna = lovart_data.get("video_dna", {})
        self.analysis.hook_type = lovart_data.get("hook_type", "")
        self.analysis.reward_type = lovart_data.get("reward_type", "")
        self.analysis.emotion = lovart_data.get("emotion", "")
        self.analysis.style = lovart_data.get("style", "")

        self.updated_at = datetime.now().isoformat()
        if "lovart" not in self.synced_sources:
            self.synced_sources.append("lovart")

    # ── Serialization ───────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "legacy_id": self.legacy_id,
            "identity": self.identity.to_dict(),
            "sources": self.sources.to_dict(),
            "performance": self.performance.to_dict(),
            "asset": self.asset.to_dict(),
            "analysis": self.analysis.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "synced_sources": self.synced_sources,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeEntity:
        return cls(
            creative_asset_id=data.get("creative_asset_id", ""),
            legacy_id=data.get("legacy_id", ""),
            identity=CreativeIdentity.from_dict(data.get("identity", {})),
            sources=CreativeSources.from_dict(data.get("sources", {})),
            performance=CreativePerformance.from_dict(data.get("performance", {})),
            asset=CreativeAsset.from_dict(data.get("asset", {})),
            analysis=CreativeAnalysis.from_dict(data.get("analysis", {})),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            synced_sources=data.get("synced_sources", []),
        )

    def __repr__(self) -> str:
        return (
            f"CreativeEntity(id={self.creative_asset_id!r}, "
            f"type={self.identity.type.value}, "
            f"sources={self.synced_sources})"
        )