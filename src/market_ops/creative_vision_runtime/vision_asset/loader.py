"""E11.3.1 — Vision Asset Loader。

从 CreativeEntity.asset 读取资产数据，转换为 VisionAsset 对象。

支持：
  - 单个加载：load(entity) → VisionAsset
  - 批量加载 Winner：load_winners() → list[VisionAsset]
  - 批量加载全部：load_all() → list[VisionAsset]

加载规则：
  - 必须有 video_path
  - source_type == EAGLE
  - match_confidence >= 0.5

Usage:
    loader = VisionAssetLoader(creative_storage_root="data/creatives")
    asset = loader.load(entity)
    winners = loader.load_winners()
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.creative_repository.models.creative_entity import CreativeEntity

from .models import VisionAsset, VisionAssetStatus
from .validator import VisionAssetValidator

logger = logging.getLogger(__name__)


class VisionAssetLoader:
    """CreativeEntity → VisionAsset 转换器。

    从 CreativeStorage 读取 entity.json，转换为 VisionAsset。
    同时维护 asset_index.json 缓存（快速查找）。

    Attributes:
        creative_storage_root: CreativeEntity 存储根目录
        index_path:           asset_index.json 缓存路径
    """

    def __init__(
        self,
        creative_storage_root: str = "data/creatives",
        index_path: str = "data/vision_asset_index.json",
    ) -> None:
        self._root = Path(creative_storage_root)
        self._index_path = Path(index_path)
        self._validator = VisionAssetValidator()

        self._loaded_count: int = 0
        self._index: dict[str, dict[str, Any]] = {}  # creative_asset_id → summary

    # ── Public API ───────────────────────────────────────

    def load(self, entity: CreativeEntity) -> VisionAsset | None:
        """从 CreativeEntity 加载单个 VisionAsset。

        Args:
            entity: CreativeEntity 对象

        Returns:
            VisionAsset 或 None（不符合加载规则）
        """
        # 规则 1: 必须有视频路径
        video_path = entity.asset.video_path or entity.asset.eagle_path
        if not video_path:
            logger.debug(f"VisionAssetLoader: skip {entity.creative_asset_id} — no video_path")
            return None

        # 规则 2: source_type 必须是 EAGLE
        source_type = entity.asset.source_type or "EAGLE"
        if source_type.upper() != "EAGLE":
            logger.debug(f"VisionAssetLoader: skip {entity.creative_asset_id} — source={source_type}")
            return None

        # 规则 3: 匹配置信度 >= 阈值
        confidence = entity.asset.matched_confidence
        if confidence < 0.5:
            logger.debug(f"VisionAssetLoader: skip {entity.creative_asset_id} — confidence={confidence}")
            return None

        # 构建 VisionAsset
        asset = VisionAsset(
            creative_id=entity.sources.facebook_id,
            creative_asset_id=entity.creative_asset_id,
            video_path=video_path,
            eagle_filename=entity.asset.eagle_filename,
            source_type=source_type,
            match_method=entity.asset.match_method,
            match_confidence=confidence,
            performance={
                "spend": entity.performance.acquisition.spend,
                "impressions": entity.performance.acquisition.impressions,
                "clicks": entity.performance.acquisition.clicks,
                "installs": entity.performance.acquisition.installs,
                "ctr": entity.performance.acquisition.ctr,
                "cpi": entity.performance.cpi,
                "revenue": entity.performance.revenue.total_revenue,
                "revenue_d7": entity.performance.revenue.iap_d7 + entity.performance.revenue.ad_d7,
                "revenue_d30": entity.performance.revenue.iap_d30 + entity.performance.revenue.ad_d30,
                "roas": entity.performance.roas_d30,
                "roas_d7": entity.performance.roas_d7,
                "roas_d30": entity.performance.roas_d30,
                "payer_count": entity.performance.revenue.payer_count,
                "payer_rate": entity.performance.revenue.payer_rate,
            },
            metadata={
                "identity_name": entity.identity.name,
                "creative_type": entity.identity.type.value,
                "product": entity.identity.product,
                "synced_sources": entity.synced_sources,
            },
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

        # 文件验证
        is_valid, errors = self._validator.validate(asset)
        if not is_valid:
            asset.status = VisionAssetStatus.INVALID.value
            asset.error_message = "; ".join(errors)
            logger.warning(f"VisionAssetLoader: invalid asset {asset.creative_asset_id}: {asset.error_message}")
        else:
            asset.status = VisionAssetStatus.VALIDATED.value

        # 更新索引
        self._index[entity.creative_asset_id] = {
            "asset_id": asset.asset_id,
            "creative_id": asset.creative_id,
            "video_path": asset.video_path,
            "eagle_filename": asset.eagle_filename,
            "status": asset.status,
            "is_valid": is_valid,
        }

        self._loaded_count += 1
        return asset

    def load_from_entity_json(self, entity_dir: Path) -> VisionAsset | None:
        """从磁盘 entity.json 加载 VisionAsset。

        Args:
            entity_dir: CreativeEntity 目录（如 data/creatives/MW_VID_260721_000001）

        Returns:
            VisionAsset 或 None
        """
        entity_path = entity_dir / "entity.json"
        if not entity_path.exists():
            return None

        with open(entity_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entity = CreativeEntity.from_dict(data)
        return self.load(entity)

    def load_all(self) -> list[VisionAsset]:
        """批量加载所有 CreativeEntity 目录下的 VisionAsset。

        Returns:
            VisionAsset 列表
        """
        assets: list[VisionAsset] = []

        if not self._root.exists():
            logger.warning(f"VisionAssetLoader: root not found: {self._root}")
            return assets

        for entity_dir in sorted(self._root.iterdir()):
            if not entity_dir.is_dir():
                continue

            asset = self.load_from_entity_json(entity_dir)
            if asset is not None:
                assets.append(asset)

        logger.info(f"VisionAssetLoader: loaded {len(assets)} from {self._root}")
        self._save_index()
        return assets

    def load_winners(self) -> list[VisionAsset]:
        """批量加载所有 WINNER 状态的 VisionAsset。

        从 asset_lifecycle.json 读取 WINNER 列表，然后加载对应 entity.json。

        Returns:
            WINNER VisionAsset 列表
        """
        from market_ops.creative_asset_binding.asset_lifecycle import (
            AssetLifecycleManager,
            AssetLifecycleStatus,
        )

        # 读取 lifecycle 数据
        lifecycle_path = self._root.parent / "asset_lifecycle.json"
        if not lifecycle_path.exists():
            logger.warning(f"VisionAssetLoader: lifecycle not found: {lifecycle_path}")
            return []

        mgr = AssetLifecycleManager(str(lifecycle_path))
        winner_ids = mgr.get_winners()

        assets: list[VisionAsset] = []
        for asset_id in winner_ids:
            # 尝试通过 asset_id 查找 entity 目录
            # asset_id 格式可能是 "v2601536" 或 "MW_VID_260721_000001"
            entity_dir = self._find_entity_dir(asset_id)
            if entity_dir is None:
                # 尝试遍历所有目录查找匹配的 creative_asset_id
                for d in self._root.iterdir():
                    if d.is_dir() and (d.name == asset_id or asset_id in d.name):
                        entity_dir = d
                        break

            if entity_dir is None:
                continue

            asset = self.load_from_entity_json(entity_dir)
            if asset is not None:
                asset.lifecycle_status = "WINNER"
                assets.append(asset)

        logger.info(f"VisionAssetLoader: loaded {len(assets)} winners")
        return assets

    def load_by_status(self, status: str) -> list[VisionAsset]:
        """按生命周期状态加载 VisionAsset。

        Args:
            status: NEW, MATCHED, TESTING, WINNER, FAILED, etc.

        Returns:
            匹配的 VisionAsset 列表
        """
        from market_ops.creative_asset_binding.asset_lifecycle import AssetLifecycleManager

        lifecycle_path = self._root.parent / "asset_lifecycle.json"
        if not lifecycle_path.exists():
            return []

        mgr = AssetLifecycleManager(str(lifecycle_path))
        asset_ids = mgr.get_by_status(status)

        assets: list[VisionAsset] = []
        for asset_id in asset_ids:
            entity_dir = self._find_entity_dir(asset_id)
            if entity_dir is None:
                continue
            asset = self.load_from_entity_json(entity_dir)
            if asset is not None:
                asset.lifecycle_status = status
                assets.append(asset)

        return assets

    # ── Query ────────────────────────────────────────────

    def get_index(self) -> dict[str, dict[str, Any]]:
        return dict(self._index)

    def get_valid_assets(self) -> list[VisionAsset]:
        """获取所有验证通过的资产（需要重新加载）。"""
        all_assets = self.load_all()
        return [a for a in all_assets if a.status == VisionAssetStatus.VALIDATED.value]

    def get_invalid_assets(self) -> list[VisionAsset]:
        """获取所有验证失败的资产。"""
        all_assets = self.load_all()
        return [a for a in all_assets if a.status == VisionAssetStatus.INVALID.value]

    def save_index(self) -> None:
        """持久化索引到磁盘。"""
        self._save_index()

    @property
    def loaded_count(self) -> int:
        return self._loaded_count

    # ── Internal ────────────────────────────────────────

    def _find_entity_dir(self, asset_id: str) -> Path | None:
        """查找 asset_id 对应的 entity 目录。"""
        # 直接匹配
        direct = self._root / asset_id
        if direct.is_dir() and (direct / "entity.json").exists():
            return direct

        # 遍历查找
        for d in self._root.iterdir():
            if d.is_dir() and d.name == asset_id:
                return d

        return None

    def _save_index(self) -> None:
        """保存索引到磁盘。"""
        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": datetime.now().isoformat(),
                    "total": len(self._index),
                    "assets": self._index,
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"VisionAssetLoader: failed to save index: {e}")

    def __repr__(self) -> str:
        return f"VisionAssetLoader(root={self._root}, loaded={self._loaded_count})"