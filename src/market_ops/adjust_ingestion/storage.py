"""E11 Phase 2 — Adjust Storage。

将 AdjustRevenueEntity 保存到 CreativeRepository 目录下。

目录结构：
  data/creatives/{creative_asset_id}/
    entity.json       ← 已存在（Phase 1.5）
    facebook.json     ← 已存在（Phase 1）
    adjust.json       ← 新增（Phase 2）
    metadata.json     ← 更新 has_adjust=True
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import AdjustRevenueEntity


class AdjustStorage:
    """Adjust 数据存储。

    将 AdjustRevenueEntity 保存为 adjust.json，
    同时更新 metadata.json 标记 has_adjust=True。

    Usage:
        storage = AdjustStorage("data/creatives")
        storage.save(adjust_entity)
    """

    def __init__(self, root_dir: str | Path = "data/creatives") -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, entity: AdjustRevenueEntity) -> str:
        """保存 AdjustRevenueEntity 到对应 creative 目录。

        Returns:
            保存目录路径
        """
        asset_id = entity.creative_asset_id
        if not asset_id:
            raise ValueError("creative_asset_id cannot be empty")

        creative_dir = self._root / asset_id
        creative_dir.mkdir(parents=True, exist_ok=True)

        # 保存 adjust.json
        self._save_json(creative_dir / "adjust.json", entity.to_dict())

        # 更新 metadata.json
        existing_meta = self._load_json(creative_dir / "metadata.json")
        metadata = self._build_metadata(entity, existing_meta)
        self._save_json(creative_dir / "metadata.json", metadata)

        return str(creative_dir)

    def save_batch(self, entities: list[AdjustRevenueEntity]) -> dict[str, int]:
        """批量保存。

        Returns:
            {"created": N, "updated": N}
        """
        created = 0
        updated = 0
        for entity in entities:
            adj_path = self._root / entity.creative_asset_id / "adjust.json"
            if adj_path.exists():
                updated += 1
            else:
                created += 1
            self.save(entity)
        return {"created": created, "updated": updated}

    def load(self, creative_asset_id: str) -> AdjustRevenueEntity | None:
        """加载单个 AdjustRevenueEntity。"""
        creative_dir = self._root / creative_asset_id
        data = self._load_json(creative_dir / "adjust.json")
        if data:
            return AdjustRevenueEntity.from_dict(data)
        return None

    def exists(self, creative_asset_id: str) -> bool:
        """检查是否已有 adjust.json。"""
        return (self._root / creative_asset_id / "adjust.json").exists()

    def list_all(self) -> list[AdjustRevenueEntity]:
        """列出所有已存储的 AdjustRevenueEntity。"""
        entities: list[AdjustRevenueEntity] = []
        for d in sorted(self._root.iterdir()):
            if d.is_dir():
                entity = self.load(d.name)
                if entity:
                    entities.append(entity)
        return entities

    def count(self) -> int:
        """统计已保存的 Adjust 实体数。"""
        return len([d for d in self._root.iterdir()
                    if d.is_dir() and (d / "adjust.json").exists()])

    # ── Helpers ─────────────────────────────────────────

    def _build_metadata(
        self,
        entity: AdjustRevenueEntity,
        existing: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """构建/更新 metadata.json。"""
        now = datetime.now().isoformat()

        if existing:
            existing["updated_at"] = now
            existing["has_adjust"] = True
            existing["last_adjust_sync"] = now
            existing["adjust_installs"] = entity.installs
            existing["adjust_purchasers"] = entity.purchasers
            existing["adjust_total_revenue"] = entity.total_revenue
            return existing

        return {
            "creative_asset_id": entity.creative_asset_id,
            "source": "adjust",
            "has_adjust": True,
            "first_adjust_sync": now,
            "last_adjust_sync": now,
            "adjust_installs": entity.installs,
            "adjust_purchasers": entity.purchasers,
            "adjust_total_revenue": entity.total_revenue,
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
        return f"AdjustStorage(root={self._root}, count={self.count()})"