"""E11.2 — CreativeAssetReference 数据模型。

CreativeAssetReference 是 E11 Asset Binding Layer 的核心数据结构。
它描述 CreativeEntity 与本地素材文件之间的绑定关系。

Usage:
    ref = CreativeAssetReference(
        creative_id="2453146861847495",
        asset_type=AssetType.VIDEO,
        source=AssetSource.EAGLE,
        eagle_filename="P4-v2601536-mg-2d-juesezhanshi-en-42s-9X16.mp4",
        local_path="Y:\\Eagle\\...\\P4-v2601536-...mp4",
        match_method=MatchMethod.A_NUMBER,
        confidence=1.0,
    )
    asset = ref.to_creative_asset()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetSource(str, Enum):
    """素材来源。"""
    FACEBOOK = "facebook"
    EAGLE = "eagle"
    LOVART = "lovart"


class MatchMethod(str, Enum):
    """匹配方法。"""
    A_NUMBER = "a_number"         # A号匹配 (A536 → v2601536)
    FILENAME = "filename"          # 文件名序列号匹配
    EXACT_ID = "exact_id"          # 精确 creative_asset_id 匹配
    LEGACY_ID = "legacy_id"        # 旧格式 ID 匹配
    VIDEO_NUMBER = "video_number"  # 视频编号匹配
    UNKNOWN = "unknown"


class AssetType(str, Enum):
    """素材类型。"""
    VIDEO = "video"
    IMAGE = "image"


@dataclass
class CreativeAssetReference:
    """CreativeEntity ↔ 本地素材文件绑定记录。

    字段说明：
      creative_id:      Facebook creative_id（主键）
      asset_type:       素材类型（video / image）
      source:           素材来源（eagle / facebook / lovart）
      eagle_filename:   Eagle 文件名（含扩展名）
      local_path:       本地完整路径（可为空，Y: 盘可能未挂载）
      match_method:     匹配方法（a_number / filename / exact_id）
      confidence:       匹配置信度 0.0-1.0
      spend:            该素材的累计花费（来自 mapping 记录）
      revenue:          该素材的累计收入
      roas:             ROAS
      ad_name:          Facebook 广告名称
      a_number:         A号（从 ad_name 提取）
      eagle_v_number:   Eagle V号（从文件名提取）
    """

    creative_id: str = ""
    asset_type: AssetType = AssetType.VIDEO
    source: AssetSource = AssetSource.EAGLE

    # ── Eagle 标识 ──────────────────────────────────────
    eagle_filename: str = ""
    local_path: str = ""

    # ── 匹配信息 ────────────────────────────────────────
    match_method: MatchMethod = MatchMethod.UNKNOWN
    confidence: float = 0.0

    # ── 性能数据（来自 mapping 记录） ──────────────────
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    impressions: float = 0.0
    clicks: float = 0.0
    installs: int = 0

    # ── 匹配元数据 ──────────────────────────────────────
    ad_name: str = ""
    a_number: str = ""
    eagle_v_number: str = ""

    # ── 时间戳 ──────────────────────────────────────────
    bound_at: str = ""

    @property
    def is_bound(self) -> bool:
        """是否已绑定到本地文件。"""
        return bool(self.local_path) and self.confidence >= 0.85

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.95

    @property
    def is_eagle(self) -> bool:
        return self.source == AssetSource.EAGLE

    def to_creative_asset(self) -> dict[str, Any]:
        """转换为 CreativeAsset 可用的 dict。

        CreativeAsset 已有字段：eagle_path, eagle_filename, source_type,
        matched_confidence, match_method, video_path
        """
        asset = {
            "eagle_path": self.local_path,
            "eagle_filename": self.eagle_filename,
            "source_type": self.source.value.upper(),
            "matched_confidence": self.confidence,
            "match_method": self.match_method.value,
        }
        if self.asset_type == AssetType.VIDEO:
            asset["video_path"] = self.local_path
        return asset

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "asset_type": self.asset_type.value,
            "source": self.source.value,
            "eagle_filename": self.eagle_filename,
            "local_path": self.local_path,
            "match_method": self.match_method.value,
            "confidence": self.confidence,
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": self.roas,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "ad_name": self.ad_name,
            "a_number": self.a_number,
            "eagle_v_number": self.eagle_v_number,
            "bound_at": self.bound_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeAssetReference:
        return cls(
            creative_id=data.get("creative_id", ""),
            asset_type=AssetType(data.get("asset_type", "video")),
            source=AssetSource(data.get("source", "eagle")),
            eagle_filename=data.get("eagle_filename", ""),
            local_path=data.get("local_path", ""),
            match_method=MatchMethod(data.get("match_method", "unknown")),
            confidence=float(data.get("confidence", 0.0)),
            spend=float(data.get("spend", 0.0)),
            revenue=float(data.get("revenue", 0.0)),
            roas=float(data.get("roas", 0.0)),
            impressions=float(data.get("impressions", 0.0)),
            clicks=float(data.get("clicks", 0.0)),
            installs=int(data.get("installs", 0)),
            ad_name=data.get("ad_name", ""),
            a_number=data.get("a_number", ""),
            eagle_v_number=data.get("eagle_v_number", ""),
            bound_at=data.get("bound_at", ""),
        )

    def __repr__(self) -> str:
        return (
            f"CreativeAssetReference({self.creative_id}, "
            f"{self.asset_type.value}, {self.source.value}, "
            f"confidence={self.confidence})"
        )