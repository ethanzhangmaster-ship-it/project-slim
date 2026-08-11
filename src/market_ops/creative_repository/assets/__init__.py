"""E11.2 — Asset Binding Layer。

将 CreativeEntity 与本地素材资产（Eagle/Lovart/Facebook）绑定。

模块结构：
  asset_reference.py           — CreativeAssetReference 数据模型
  asset_binding_repository.py  — 资产绑定存储层（读写 asset.json）
  creative_mapping_loader.py   — 从 creative_mapping_v2.json 迁移数据
  asset_materializer.py        — 将 assets.json 写入 entity.json (E11.2.1)
"""

from .asset_reference import (
    CreativeAssetReference,
    AssetSource,
    MatchMethod,
    AssetType,
)
from .asset_binding_repository import AssetBindingRepository
from .creative_mapping_loader import CreativeMappingLoader
from .asset_materializer import AssetBindingMaterializer
from .identity_resolver import IdentityResolver

__all__ = [
    "CreativeAssetReference",
    "AssetSource",
    "MatchMethod",
    "AssetType",
    "AssetBindingRepository",
    "CreativeMappingLoader",
    "AssetBindingMaterializer",
    "IdentityResolver",
]