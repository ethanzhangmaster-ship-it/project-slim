"""E11 Phase 1.5 — Storage (升级版)。

将 FacebookCreativeEntity 保存到文件系统，同时生成 entity.json。

Phase 1.5 升级：
  - 新增 entity.json：FacebookCreativeEntity → CreativeEntity 统一格式
  - 目录结构：{creative_asset_id}/entity.json + facebook.json + metadata.json

目录结构：
  data/creatives/
    MW_IMG_260721_000123/
      entity.json      ← 统一 CreativeEntity 格式
      facebook.json    ← Facebook 原始数据
      metadata.json    ← 同步元数据
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import FacebookCreativeEntity

if TYPE_CHECKING:
    from market_ops.creative_repository.models.creative_entity import CreativeEntity


class CreativeStorage:
    """Creative Entity 文件存储（Phase 1.5 升级版）。

    同时保存 facebook.json 和 entity.json。

    Usage:
        storage = CreativeStorage("data/creatives")
        storage.save(entity)  # 自动生成 facebook.json + entity.json
        all_entities = storage.list_all()
    """

    def __init__(self, root_dir: str | Path = "data/creatives") -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    # ── Save ────────────────────────────────────────────

    def save(self, entity: FacebookCreativeEntity) -> str:
        """保存一个 Creative Entity。

        同时保存 facebook.json 和 entity.json。
        如果已存在，则更新全部文件。

        Returns:
            保存目录路径
        """
        asset_id = entity.creative_asset_id
        if not asset_id:
            raise ValueError("creative_asset_id cannot be empty")

        creative_dir = self._root / asset_id
        creative_dir.mkdir(parents=True, exist_ok=True)

        # 保存 facebook.json
        self._save_json(creative_dir / "facebook.json", entity.to_facebook_json())

        # 保存 entity.json（统一 CreativeEntity 格式）
        creative_entity = entity.to_creative_entity()
        self._save_json(creative_dir / "entity.json", creative_entity.to_dict())

        # 保存 metadata.json
        existing_meta = self._load_json(creative_dir / "metadata.json")
        metadata = self._build_metadata(entity, existing_meta)
        self._save_json(creative_dir / "metadata.json", metadata)

        return str(creative_dir)

    def save_batch(self, entities: list[FacebookCreativeEntity]) -> dict[str, int]:
        """批量保存。

        Returns:
            {"created": N, "updated": N}
        """
        created = 0
        updated = 0
        for entity in entities:
            asset_dir = self._root / entity.creative_asset_id
            if asset_dir.exists():
                updated += 1
            else:
                created += 1
            self.save(entity)
        return {"created": created, "updated": updated}

    # ── Load ────────────────────────────────────────────

    def load(self, creative_asset_id: str) -> FacebookCreativeEntity | None:
        """加载单个 FacebookCreativeEntity（从 facebook.json）。"""
        creative_dir = self._root / creative_asset_id
        data = self._load_json(creative_dir / "facebook.json")
        if data:
            return FacebookCreativeEntity.from_dict(data)
        return None

    def load_entity(self, creative_asset_id: str) -> CreativeEntity | None:
        """加载单个 CreativeEntity（从 entity.json）。"""
        from market_ops.creative_repository.models.creative_entity import CreativeEntity

        creative_dir = self._root / creative_asset_id
        data = self._load_json(creative_dir / "entity.json")
        if data:
            return CreativeEntity.from_dict(data)
        return None

    def exists(self, creative_asset_id: str) -> bool:
        """检查是否已存在。"""
        return (self._root / creative_asset_id).exists()

    def list_all(self) -> list[FacebookCreativeEntity]:
        """列出所有已存储的 FacebookCreativeEntity。"""
        entities: list[FacebookCreativeEntity] = []
        for d in sorted(self._root.iterdir()):
            if d.is_dir():
                entity = self.load(d.name)
                if entity:
                    entities.append(entity)
        return entities

    def list_all_creative_entities(self) -> list[CreativeEntity]:
        """列出所有已存储的 CreativeEntity（从 entity.json）。"""
        from market_ops.creative_repository.models.creative_entity import CreativeEntity

        entities: list[CreativeEntity] = []
        for d in sorted(self._root.iterdir()):
            if d.is_dir():
                ce = self.load_entity(d.name)
                if ce:
                    entities.append(ce)
        return entities

    def save_existing_entity(self, entity: CreativeEntity) -> None:
        """保存已存在的 CreativeEntity（更新 entity.json）。

        用于 Adjust 匹配后回写更新后的 CreativeEntity。
        """
        asset_id = entity.creative_asset_id
        if not asset_id:
            raise ValueError("creative_asset_id cannot be empty")

        creative_dir = self._root / asset_id
        creative_dir.mkdir(parents=True, exist_ok=True)

        self._save_json(creative_dir / "entity.json", entity.to_dict())

    def list_by_type(self, creative_type: str) -> list[FacebookCreativeEntity]:
        """按类型列出。"""
        return [e for e in self.list_all() if e.creative_type.value == creative_type]

    def count(self) -> int:
        """统计总数。"""
        return len([d for d in self._root.iterdir() if d.is_dir()])

    # ── Helpers ─────────────────────────────────────────

    def _build_metadata(
        self,
        entity: FacebookCreativeEntity,
        existing: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """构建 metadata.json。"""
        now = datetime.now().isoformat()

        if existing:
            # 更新现有 metadata
            existing["updated_at"] = now
            existing["last_synced_at"] = now
            existing["sync_count"] = existing.get("sync_count", 0) + 1
            existing["has_entity"] = True
            return existing

        # 新建 metadata
        return {
            "creative_asset_id": entity.creative_asset_id,
            "legacy_id": entity.legacy_id,
            "source": "facebook",
            "type": entity.creative_type.value,
            "ad_name": entity.ad_name,
            "account_id": entity.account_id,
            "created_at": entity.created_time or now,
            "first_synced_at": now,
            "last_synced_at": now,
            "sync_count": 1,
            "has_entity": True,
            "has_adjust": False,
            "has_eagle": False,
            "has_dna": False,
        }

    def _save_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                pass
        return None

    @property
    def root_dir(self) -> Path:
        return self._root

    def __repr__(self) -> str:
        return f"CreativeStorage(root={self._root}, count={self.count()})"