"""E11 Phase 1 — Facebook Creative Entity 数据模型。

定义 Facebook 广告素材的标准化数据结构。

Phase 1.5 升级：
  - 增加 legacy_id 字段，兼容旧 6 位数字编号
  - 增加 to_creative_entity() 方法，转换为统一 CreativeEntity
  - creative_asset_id 升级为 {产品}_{类型}_{日期}_{序号} 格式

暂不实现：
  - Adjust 匹配
  - Eagle 匹配
  - DNA 提取
  - 自动生成
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from market_ops.creative_repository.models.creative_entity import CreativeEntity


class CreativeType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


@dataclass
class FacebookCreativeEntity:
    """Facebook 广告素材标准化实体。

    将 Facebook Graph API 的 ads/creatives/insights 合并为统一结构。
    每个 Entity 对应一个 creative_asset_id。

    Phase 1.5: creative_asset_id 升级为 MW_IMG_260721_000123 格式，
    legacy_id 保留旧 6 位数字编号。

    Usage:
        entity = FacebookCreativeEntity(
            creative_asset_id="MW_IMG_260721_000123",
            legacy_id="000123",
            creative_type=CreativeType.VIDEO,
            creative_id="123456",
            ad_name="dragon_video_000123",
        )
    """

    # ── Identity ────────────────────────────────────────
    creative_asset_id: str = ""  # 新格式: MW_IMG_260721_000123
    legacy_id: str = ""          # 旧格式兼容: "000123"
    creative_id: str = ""        # Facebook creative_id
    ad_id: str = ""              # Facebook ad_id
    ad_name: str = ""

    # ── Account ─────────────────────────────────────────
    account_id: str = ""
    campaign_id: str = ""
    campaign_name: str = ""
    adset_id: str = ""
    adset_name: str = ""

    # ── Type ────────────────────────────────────────────
    creative_type: CreativeType = CreativeType.UNKNOWN

    # ── Asset ───────────────────────────────────────────
    image_url: str = ""
    thumbnail_url: str = ""
    video_id: str = ""
    duration: float = 0.0        # v1.4: 视频时长（秒），IMAGE 类型为 0.0
    resolution: str = ""         # v1.4: 分辨率 "WIDTHxHEIGHT"，IMAGE 类型为空

    # ── Text ────────────────────────────────────────────
    primary_text: str = ""
    headline: str = ""
    description: str = ""
    call_to_action: str = ""

    # ── Performance ─────────────────────────────────────
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    installs: int = 0

    # ── Status ──────────────────────────────────────────
    status: str = ""
    created_time: str = ""
    updated_time: str = ""

    # ── Sync metadata ───────────────────────────────────
    synced_at: str = ""
    sync_source: str = "facebook"

    # ── Properties ──────────────────────────────────────

    @property
    def is_video(self) -> bool:
        return self.creative_type == CreativeType.VIDEO

    @property
    def is_image(self) -> bool:
        return self.creative_type == CreativeType.IMAGE

    @property
    def has_asset_id(self) -> bool:
        return bool(self.creative_asset_id)

    @property
    def has_performance(self) -> bool:
        return self.spend > 0.0 or self.impressions > 0

    @property
    def cpm_str(self) -> str:
        return f"${self.cpm:.2f}" if self.cpm > 0 else "N/A"

    # ── Serialization ───────────────────────────────────

    def to_creative_entity(self, product: str = "MW") -> CreativeEntity:
        """转换为统一 CreativeEntity。

        将 Facebook 视角的数据映射到 CreativeEntity 的对应字段：
          - sources.facebook_id ← creative_id
          - performance (acquisition) ← spend/impressions/clicks/...
          - asset (urls) ← image_url/video_id/thumbnail_url

        Args:
            product: 产品前缀，如 "MW" (Merge Witches)

        Returns:
            CreativeEntity
        """
        from market_ops.creative_repository.models.creative_entity import (
            CreativeEntity,
            CreativeIdentity,
            CreativeSources,
            AcquisitionData,
            CreativePerformance,
            CreativeAsset,
        )

        # 生成新格式 ID（如果还没有）
        if not self.creative_asset_id or self.creative_asset_id == self.legacy_id:
            type_prefix = "IMG" if self.is_image else "VID"
            date_str = self._extract_date_str()
            seq = self.legacy_id if self.legacy_id else "000000"
            new_id = f"{product}_{type_prefix}_{date_str}_{seq}"
        else:
            new_id = self.creative_asset_id

        return CreativeEntity(
            creative_asset_id=new_id,
            legacy_id=self.legacy_id or self.creative_asset_id,
            identity=CreativeIdentity(
                name=self.ad_name,
                type=self.creative_type,
                product=product,
            ),
            sources=CreativeSources(
                facebook_id=self.creative_id,
            ),
            performance=CreativePerformance(
                acquisition=AcquisitionData(
                    spend=self.spend,
                    impressions=self.impressions,
                    clicks=self.clicks,
                    ctr=self.ctr,
                    cpc=self.cpc,
                    cpm=self.cpm,
                    installs=self.installs,
                ),
            ),
            asset=CreativeAsset(
                image_url=self.image_url,
                thumbnail_url=self.thumbnail_url,
                video_url=self.video_id,
            ),
            synced_sources=["facebook"],
            created_at=self.created_time,
            updated_at=self.synced_at or datetime.now().isoformat(),
        )

    def _extract_date_str(self) -> str:
        """从 created_time 提取 YYMMDD 格式日期。"""
        if self.created_time:
            try:
                # Facebook 格式: "2026-07-01T00:00:00+0000"
                dt = datetime.fromisoformat(self.created_time[:19])
                return dt.strftime("%y%m%d")
            except (ValueError, IndexError):
                pass
        return datetime.now().strftime("%y%m%d")

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "legacy_id": self.legacy_id,
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "ad_name": self.ad_name,
            "account_id": self.account_id,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "adset_id": self.adset_id,
            "adset_name": self.adset_name,
            "creative_type": self.creative_type.value,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "video_id": self.video_id,
            "duration": self.duration,
            "resolution": self.resolution,
            "primary_text": self.primary_text,
            "headline": self.headline,
            "description": self.description,
            "call_to_action": self.call_to_action,
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": self.ctr,
            "cpc": self.cpc,
            "cpm": self.cpm,
            "installs": self.installs,
            "status": self.status,
            "created_time": self.created_time,
            "updated_time": self.updated_time,
            "synced_at": self.synced_at,
            "sync_source": self.sync_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FacebookCreativeEntity:
        ct = data.get("creative_type", "unknown")
        try:
            creative_type = CreativeType(ct)
        except ValueError:
            creative_type = CreativeType.UNKNOWN

        return cls(
            creative_asset_id=data.get("creative_asset_id", ""),
            legacy_id=data.get("legacy_id", ""),
            creative_id=data.get("creative_id", ""),
            ad_id=data.get("ad_id", ""),
            ad_name=data.get("ad_name", ""),
            account_id=data.get("account_id", ""),
            campaign_id=data.get("campaign_id", ""),
            campaign_name=data.get("campaign_name", ""),
            adset_id=data.get("adset_id", ""),
            adset_name=data.get("adset_name", ""),
            creative_type=creative_type,
            image_url=data.get("image_url", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            video_id=data.get("video_id", ""),
            duration=float(data.get("duration", 0.0)),
            resolution=data.get("resolution", ""),
            primary_text=data.get("primary_text", ""),
            headline=data.get("headline", ""),
            description=data.get("description", ""),
            call_to_action=data.get("call_to_action", ""),
            spend=float(data.get("spend", 0.0)),
            impressions=int(data.get("impressions", 0)),
            clicks=int(data.get("clicks", 0)),
            ctr=float(data.get("ctr", 0.0)),
            cpc=float(data.get("cpc", 0.0)),
            cpm=float(data.get("cpm", 0.0)),
            installs=int(data.get("installs", 0)),
            status=data.get("status", ""),
            created_time=data.get("created_time", ""),
            updated_time=data.get("updated_time", ""),
            synced_at=data.get("synced_at", ""),
            sync_source=data.get("sync_source", "facebook"),
        )

    def to_facebook_json(self) -> dict[str, Any]:
        """导出为 CreativeRepository 兼容的 facebook.json 格式。"""
        return {
            "creative_asset_id": self.creative_asset_id,
            "legacy_id": self.legacy_id,
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "ad_name": self.ad_name,
            "creative_type": self.creative_type.value,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "adset_id": self.adset_id,
            "adset_name": self.adset_name,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "video_id": self.video_id,
            "duration": self.duration,
            "resolution": self.resolution,
            "primary_text": self.primary_text,
            "headline": self.headline,
            "description": self.description,
            "call_to_action": self.call_to_action,
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": self.ctr,
            "cpc": self.cpc,
            "cpm": self.cpm,
            "installs": self.installs,
            "status": self.status,
            "created_time": self.created_time,
            "updated_time": self.updated_time,
        }

    def __repr__(self) -> str:
        return (
            f"FacebookCreativeEntity(id={self.creative_asset_id!r}, "
            f"type={self.creative_type.value}, "
            f"ad={self.ad_name!r})"
        )