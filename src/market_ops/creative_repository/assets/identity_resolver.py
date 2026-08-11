"""E11.2.2 — Creative Identity Resolver。

统一 Facebook creative_id、creative_asset_id、adjust_creative_id 等所有 ID 空间，
建立双向映射表，解决 AssetBindingRepository 和 CreativeStorage 的 ID 空间分裂问题。

问题：
  AssetBindingRepository 使用 creative_id (Facebook creative_id) 作为目录键
  CreativeStorage 使用 creative_asset_id (自定义 ID) 作为目录键
  → 同一个创意存在两个 entity.json

解决方案：
  IdentityResolver 扫描 CreativeStorage 的 entity.json，建立映射表。
  Materializer 通过 Resolver 找到正确的 creative_asset_id 目录，写入 entity.json。

Usage:
    resolver = IdentityResolver("data/creatives")
    asset_id = resolver.resolve_asset_id("2453146861847495")
    # → "MW_IMG_260721_000123"

    fb_id = resolver.resolve_facebook_id("MW_IMG_260721_000123")
    # → "2453146861847495"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class IdentityResolver:
    """创意 ID 双向映射表。

    索引来源：
      1. entity.json 中的 sources.facebook_id → creative_asset_id (目录名)
      2. entity.json 中的 sources.adjust_id → creative_asset_id
      3. facebook.json 中的 creative_id → creative_asset_id

    在没有 entity.json 时（sync 未跑），使用 creative_id 作为 fallback。
    """

    def __init__(self, creative_storage_root: str = "data/creatives") -> None:
        self._root = Path(creative_storage_root)
        self._fb_to_asset: dict[str, str] = {}   # facebook_creative_id → creative_asset_id
        self._asset_to_fb: dict[str, str] = {}   # creative_asset_id → facebook_creative_id
        self._adjust_to_asset: dict[str, str] = {}  # adjust_creative_id → creative_asset_id
        self._legacy_to_asset: dict[str, str] = {}  # legacy_id → creative_asset_id
        self._build_index()

    # ── Public API ───────────────────────────────────────

    def resolve_asset_id(self, creative_id: str) -> str:
        """将 Facebook creative_id 解析为 creative_asset_id。

        Args:
            creative_id: Facebook creative_id (e.g., "2453146861847495")

        Returns:
            creative_asset_id (e.g., "MW_IMG_260721_000123")
            如果未找到映射，返回 creative_id 本身作为 fallback
        """
        return self._fb_to_asset.get(creative_id, creative_id)

    def resolve_facebook_id(self, asset_id: str) -> str:
        """将 creative_asset_id 解析为 Facebook creative_id。

        Args:
            asset_id: creative_asset_id (e.g., "MW_IMG_260721_000123")

        Returns:
            Facebook creative_id，如果未找到返回 asset_id 本身
        """
        return self._asset_to_fb.get(asset_id, asset_id)

    def resolve_from_adjust(self, adjust_id: str) -> str:
        """将 Adjust creative_id 解析为 creative_asset_id。"""
        return self._adjust_to_asset.get(adjust_id, "")

    def resolve_from_legacy(self, legacy_id: str) -> str:
        """将 legacy_id 解析为 creative_asset_id。"""
        return self._legacy_to_asset.get(legacy_id, "")

    def has_mapping(self, creative_id: str) -> bool:
        """检查是否存在映射。"""
        return creative_id in self._fb_to_asset

    def get_identity(self, asset_id: str) -> dict[str, Any] | None:
        """获取完整的 identity 信息。

        Returns:
            {
                "creative_asset_id": str,
                "facebook_creative_id": str,
                "facebook_ad_id": str,
                "adjust_creative_id": str,
                "legacy_ids": [str, ...],
            }
        """
        if not self._root.exists():
            return None

        entity_path = self._root / asset_id / "entity.json"
        if not entity_path.exists():
            return None

        try:
            with open(entity_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None

        sources = data.get("sources", {})
        identity_data = data.get("identity", {})

        fb_id = sources.get("facebook_id", "")
        fb_ad_id = identity_data.get("facebook_ad_id", "")
        legacy_id = data.get("legacy_id", "")

        legacy_ids = [legacy_id] if legacy_id else []

        return {
            "creative_asset_id": asset_id,
            "facebook_creative_id": fb_id,
            "facebook_ad_id": fb_ad_id,
            "adjust_creative_id": sources.get("adjust_id", ""),
            "legacy_ids": legacy_ids,
        }

    def build_identity_json(self, asset_id: str) -> dict[str, Any] | None:
        """构建 identity.json 内容。

        输出格式：
        {
            "creative_asset_id": "MW_IMG_260721_000123",
            "facebook_creative_id": "2453146861847495",
            "facebook_ad_id": "123456789",
            "adjust_creative_id": "A536",
            "legacy_ids": ["536"]
        }
        """
        return self.get_identity(asset_id)

    @property
    def mapping_count(self) -> int:
        return len(self._fb_to_asset)

    def to_summary(self) -> dict[str, Any]:
        """生成映射统计摘要。"""
        return {
            "facebook_to_asset": len(self._fb_to_asset),
            "asset_to_facebook": len(self._asset_to_fb),
            "adjust_to_asset": len(self._adjust_to_asset),
            "legacy_to_asset": len(self._legacy_to_asset),
        }

    # ── Internal ────────────────────────────────────────

    def _build_index(self) -> None:
        """扫描 CreativeStorage 中的 entity.json 和 facebook.json 建立映射表。"""
        if not self._root.exists():
            return

        for entity_dir in self._root.iterdir():
            if not entity_dir.is_dir():
                continue

            asset_id = entity_dir.name

            # 从 entity.json 读取
            self._index_from_entity(entity_dir, asset_id)

            # 从 facebook.json 读取（补充）
            self._index_from_facebook(entity_dir, asset_id)

    def _index_from_entity(self, entity_dir: Path, asset_id: str) -> None:
        """从 entity.json 提取映射。"""
        entity_path = entity_dir / "entity.json"
        if not entity_path.exists():
            return

        try:
            with open(entity_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        sources = data.get("sources", {})
        fb_id = sources.get("facebook_id", "")
        adjust_id = sources.get("adjust_id", "")
        legacy_id = data.get("legacy_id", "")

        if fb_id:
            self._fb_to_asset[fb_id] = asset_id
            self._asset_to_fb[asset_id] = fb_id

        if adjust_id:
            self._adjust_to_asset[adjust_id] = asset_id

        if legacy_id:
            self._legacy_to_asset[legacy_id] = asset_id

    def _index_from_facebook(self, entity_dir: Path, asset_id: str) -> None:
        """从 facebook.json 提取映射（补充 entity.json 可能缺失的）。"""
        fb_path = entity_dir / "facebook.json"
        if not fb_path.exists():
            return

        try:
            with open(fb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        fb_id = data.get("creative_id", "")
        if fb_id and fb_id not in self._fb_to_asset:
            self._fb_to_asset[fb_id] = asset_id
            self._asset_to_fb[asset_id] = fb_id

    def __repr__(self) -> str:
        return (
            f"IdentityResolver(root={self._root}, "
            f"mappings={len(self._fb_to_asset)})"
        )