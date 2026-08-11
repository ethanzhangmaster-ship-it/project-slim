"""E11 Phase 3 — Creative Asset Reality Binding Layer。

将 Facebook 广告实体绑定到真实素材资产：
  - Eagle 视频：通过 EagleIndexer 扫描本地素材库 + VideoMatcher 3 级匹配
  - Lovart 图片：通过 ImageMatcher 匹配 Facebook 缩略图 ↔ Lovart 生成图
  - AssetBindingEngine：编排完整绑定流程
  - AssetBindingValidator：绑定质量验证

模块结构：
  eagle_indexer.py        — Eagle 素材库扫描，构建索引
  video_matcher.py        — 3 级匹配（精确 ID → 文件名 → 视觉 Hash）
  image_matcher.py        — Facebook 图片 ↔ Lovart 图片匹配
  asset_binding_engine.py — 绑定流程编排器
  models.py               — 数据模型
  validator.py            — 绑定质量验证器
"""

from .models import (
    EagleAsset,
    LovartAsset,
    AssetBindingResult,
    BindingMethod,
    AssetSourceType,
)
from .eagle_indexer import (
    EagleIndexer,
    EagleIndex,
)
from .video_matcher import (
    VideoMatcher,
    VideoMatchResult,
)
from .image_matcher import (
    ImageMatcher,
    ImageMatchResult,
)
from .asset_binding_engine import (
    AssetBindingEngine,
    AssetBindingReport,
)
from .validator import (
    AssetBindingValidator,
    AssetBindingQualityReport,
)

__all__ = [
    # Models
    "EagleAsset",
    "LovartAsset",
    "AssetBindingResult",
    "BindingMethod",
    "AssetSourceType",
    # Indexer
    "EagleIndexer",
    "EagleIndex",
    # Matchers
    "VideoMatcher",
    "VideoMatchResult",
    "ImageMatcher",
    "ImageMatchResult",
    # Engine
    "AssetBindingEngine",
    "AssetBindingReport",
    # Validator
    "AssetBindingValidator",
    "AssetBindingQualityReport",
]