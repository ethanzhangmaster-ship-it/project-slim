"""E11 — Creative Repository。

统一的创意素材管理中心。

Phase 1.5: 建立 Creative Core Entity Layer，作为所有数据源（Facebook/Adjust/Eagle/Lovart）的聚合视图。

架构：
  CreativeEntity（核心聚合对象）
    ├── identity:     名称/类型/产品/国家
    ├── sources:      Facebook/Adjust/Eagle/Lovart 外部 ID
    ├── performance:  投放效果 + 收入数据
    ├── asset:        素材文件路径
    └── analysis:     DNA/分析数据

数据源到字段的映射：
  Facebook → sources.facebook,  performance (acquisition),  asset (urls)
  Adjust   → sources.adjust,    performance (revenue)
  Eagle    → sources.eagle,     asset (local paths)
  Lovart   → sources.lovart,    analysis (DNA)

Usage:
    from creative_repository import CreativeEntity, CreativeIdentity, CreativeSources

    entity = CreativeEntity(
        creative_asset_id="MW_IMG_260721_000123",
        identity=CreativeIdentity(name="witch_merge", type=CreativeType.IMAGE),
    )
    entity.merge_facebook_data(fb_entity)
    entity.merge_adjust_data(adjust_data)
"""

from .models.creative_entity import (
    CreativeType,
    CreativeIdentity,
    CreativeSources,
    AcquisitionData,
    RevenueData,
    CreativePerformance,
    CreativeAsset,
    CreativeAnalysis,
    CreativeEntity,
)

__all__ = [
    "CreativeType",
    "CreativeIdentity",
    "CreativeSources",
    "AcquisitionData",
    "RevenueData",
    "CreativePerformance",
    "CreativeAsset",
    "CreativeAnalysis",
    "CreativeEntity",
]