"""E11.2.1 — Asset Binding Materializer (E11.2.2 升级版)。

将 assets.json 中的资产绑定数据写入 CreativeEntity.asset（entity.json），
使 CreativeEntity 成为唯一资产入口。

E11.2.2 升级：
  - 集成 IdentityResolver，将 creative_id 映射为 creative_asset_id
  - entity.json 写入正确的 CreativeStorage 目录（creative_asset_id）
  - 同时写入 identity.json 作为 ID 映射持久化

流程：
  assets.json (AssetBindingRepository, key=creative_id)
        │
        │ 读取 CreativeAssetReference
        ▼
  IdentityResolver
        │
        │ creative_id → creative_asset_id
        ▼
  entity.json (CreativeStorage, key=creative_asset_id)
        │
        │ 更新 asset 字段
        ▼
  CreativeEntity.asset  ← 单一事实源

Usage:
    resolver = IdentityResolver("data/creatives")
    materializer = AssetBindingMaterializer("data/creatives", resolver)
    report = materializer.materialize_all()
    print(report["summary"])
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .asset_reference import CreativeAssetReference, AssetType

if TYPE_CHECKING:
    from .identity_resolver import IdentityResolver


class AssetBindingMaterializer:
    """将 AssetBindingRepository 的 assets.json 写入 CreativeEntity 的 entity.json。

    E11.2.2 升级：通过 IdentityResolver 统一 ID 空间，
    entity.json 写入 creative_asset_id 目录（而非 creative_id 目录）。
    """

    def __init__(
        self,
        creative_storage_root: str = "data/creatives",
        identity_resolver: IdentityResolver | None = None,
    ) -> None:
        self._root = Path(creative_storage_root)
        self._errors: list[str] = []

        # 延迟导入避免循环引用
        if identity_resolver is None:
            from .identity_resolver import IdentityResolver
            identity_resolver = IdentityResolver(creative_storage_root)

        self._resolver = identity_resolver

    # ── Public API ───────────────────────────────────────

    def materialize(self, creative_id: str) -> bool:
        """将单个 creative_id 的 assets.json 写入 entity.json。

        通过 IdentityResolver 将 creative_id 映射为 creative_asset_id，
        写入正确的 CreativeStorage 目录。

        Args:
            creative_id: Facebook creative_id (e.g., "2453146861847495")

        Returns:
            True if materialized successfully
        """
        # 定位 assets.json（在 creative_id 目录下）
        asset_path = self._root / creative_id / "assets.json"
        if not asset_path.exists():
            return False

        try:
            # 读取 AssetReference
            with open(asset_path, "r", encoding="utf-8") as f:
                asset_data = json.load(f)
            ref = CreativeAssetReference.from_dict(asset_data)

            # 解析 creative_asset_id
            asset_id = self._resolver.resolve_asset_id(creative_id)
            entity_path = self._root / asset_id / "entity.json"

            # 读取或创建 entity.json
            if entity_path.exists():
                with open(entity_path, "r", encoding="utf-8") as f:
                    entity_data = json.load(f)
            else:
                entity_data = {
                    "creative_asset_id": asset_id,
                    "identity": {"type": ref.asset_type.value},
                    "sources": {"facebook_id": creative_id},
                    "created_at": datetime.now().isoformat(),
                }

            # 更新 asset 字段
            asset_update = ref.to_creative_asset()
            entity_data.setdefault("asset", {})
            entity_data["asset"] = {
                **entity_data["asset"],
                **asset_update,
            }

            # 标记来源
            entity_data.setdefault("synced_sources", [])
            if "eagle" not in entity_data["synced_sources"]:
                entity_data["synced_sources"].append("eagle")

            entity_data["updated_at"] = datetime.now().isoformat()

            # 写入 entity.json
            entity_path.parent.mkdir(parents=True, exist_ok=True)
            with open(entity_path, "w", encoding="utf-8") as f:
                json.dump(entity_data, f, indent=2, ensure_ascii=False)

            # 写入 identity.json（ID 映射持久化）
            self._write_identity_json(asset_id, creative_id, ref)

            return True

        except Exception as e:
            self._errors.append(f"Materialize error for {creative_id}: {e}")
            return False

    def materialize_all(self) -> dict[str, Any]:
        """批量 materialize 所有已有 assets.json 的 creative。

        遍历所有 creative_id 目录，通过 IdentityResolver 解析后写入
        对应的 creative_asset_id 目录。

        Returns:
            {
                "summary": str,
                "total": int,
                "materialized": int,
                "skipped": int,
                "resolved": int,       # 通过映射解析的
                "fallback": int,        # 使用 creative_id 作为 fallback 的
                "errors": int,
                "error_details": list[str],
                "elapsed_seconds": float,
            }
        """
        self._errors = []
        started = datetime.now()

        total = 0
        materialized = 0
        skipped = 0
        resolved = 0
        fallback = 0

        if not self._root.exists():
            return self._build_report(0, 0, 0, 0, 0, started)

        for entity_dir in sorted(self._root.iterdir()):
            if not entity_dir.is_dir():
                continue

            asset_path = entity_dir / "assets.json"
            if not asset_path.exists():
                continue

            creative_id = entity_dir.name
            total += 1

            if self._resolver.has_mapping(creative_id):
                resolved += 1
            else:
                fallback += 1

            if self.materialize(creative_id):
                materialized += 1
            else:
                skipped += 1

        return self._build_report(total, materialized, skipped, resolved, fallback, started)

    def verify(self) -> dict[str, Any]:
        """验证所有 entity.json 的 asset 字段完整性。

        检查项：
          - entity.json 是否存在
          - asset 字段是否完整 (eagle_path, source_type, match_method)
          - 本地文件路径是否可访问

        Returns:
            {
                "summary": str,
                "total_entities": int,
                "with_asset": int,
                "with_eagle_path": int,
                "with_source_type": int,
                "missing_entity": int,
                "missing_asset": int,
                "path_accessible": int,
                "path_inaccessible": int,
            }
        """
        total_entities = 0
        with_asset = 0
        with_eagle_path = 0
        with_source_type = 0
        missing_entity = 0
        missing_asset = 0
        path_accessible = 0
        path_inaccessible = 0

        if not self._root.exists():
            return self._build_verify_report(0, 0, 0, 0, 0, 0, 0, 0)

        for entity_dir in sorted(self._root.iterdir()):
            if not entity_dir.is_dir():
                continue

            entity_path = entity_dir / "entity.json"
            if not entity_path.exists():
                continue

            total_entities += 1

            try:
                with open(entity_path, "r", encoding="utf-8") as f:
                    entity_data = json.load(f)
            except Exception:
                missing_entity += 1
                continue

            asset = entity_data.get("asset", {})
            if not asset:
                missing_asset += 1
                continue

            with_asset += 1

            eagle_path = asset.get("eagle_path", "")
            if eagle_path:
                with_eagle_path += 1

            source_type = asset.get("source_type", "")
            if source_type:
                with_source_type += 1

            if eagle_path and os.path.exists(eagle_path):
                path_accessible += 1
            elif eagle_path:
                path_inaccessible += 1

        return self._build_verify_report(
            total_entities, with_asset, with_eagle_path,
            with_source_type, missing_entity, missing_asset,
            path_accessible, path_inaccessible,
        )

    def verify_one(self, creative_id: str) -> dict[str, Any]:
        """验证单个 creative 的 entity.json asset 字段。

        通过 IdentityResolver 找到正确的 entity.json 路径。

        Returns:
            {
                "creative_id": str,
                "asset_id": str,        # 解析后的 creative_asset_id
                "resolved": bool,       # 是否通过映射解析
                "has_entity": bool,
                "has_asset": bool,
                "eagle_path": str,
                "source_type": str,
                "match_method": str,
                "confidence": float,
                "path_accessible": bool,
                "path_exists": bool,
            }
        """
        asset_id = self._resolver.resolve_asset_id(creative_id)
        resolved = self._resolver.has_mapping(creative_id)

        entity_path = self._root / asset_id / "entity.json"
        result = {
            "creative_id": creative_id,
            "asset_id": asset_id,
            "resolved": resolved,
            "has_entity": entity_path.exists(),
            "has_asset": False,
            "eagle_path": "",
            "source_type": "",
            "match_method": "",
            "confidence": 0.0,
            "path_accessible": False,
            "path_exists": False,
        }

        if not entity_path.exists():
            return result

        try:
            with open(entity_path, "r", encoding="utf-8") as f:
                entity_data = json.load(f)
        except Exception:
            return result

        asset = entity_data.get("asset", {})
        if asset:
            result["has_asset"] = True
            result["eagle_path"] = asset.get("eagle_path", "")
            result["source_type"] = asset.get("source_type", "")
            result["match_method"] = asset.get("match_method", "")
            result["confidence"] = asset.get("matched_confidence", 0.0)

            eagle_path = result["eagle_path"]
            if eagle_path:
                result["path_exists"] = os.path.exists(eagle_path)
                result["path_accessible"] = result["path_exists"]

        return result

    # ── Internal ────────────────────────────────────────

    def _write_identity_json(
        self, asset_id: str, creative_id: str, ref: CreativeAssetReference
    ) -> None:
        """写入 identity.json 持久化 ID 映射。"""
        identity_path = self._root / asset_id / "identity.json"

        if identity_path.exists():
            with open(identity_path, "r", encoding="utf-8") as f:
                identity_data = json.load(f)
        else:
            identity_data = {}

        identity_data.setdefault("creative_asset_id", asset_id)
        identity_data.setdefault("facebook_creative_id", creative_id)
        identity_data.setdefault("legacy_ids", [])

        if ref.a_number and ref.a_number not in identity_data.get("legacy_ids", []):
            identity_data["legacy_ids"].append(ref.a_number)

        identity_data["updated_at"] = datetime.now().isoformat()

        with open(identity_path, "w", encoding="utf-8") as f:
            json.dump(identity_data, f, indent=2, ensure_ascii=False)

    def _build_report(
        self,
        total: int,
        materialized: int,
        skipped: int,
        resolved: int,
        fallback: int,
        started: datetime,
    ) -> dict[str, Any]:
        elapsed = (datetime.now() - started).total_seconds()

        lines = [
            "=" * 60,
            "  Asset Binding Materialization Report (E11.2.2)",
            "=" * 60,
            "",
            f"  Total assets.json found:  {total}",
            f"  Materialized to entity:  {materialized}",
            f"  Resolved via mapping:    {resolved}",
            f"  Fallback (no mapping):   {fallback}",
            f"  Skipped / errors:       {skipped}",
            f"  Errors:                 {len(self._errors)}",
            f"  Elapsed:                {elapsed:.1f}s",
            f"  Resolver mappings:      {self._resolver.mapping_count}",
            "",
        ]
        if self._errors:
            lines.append("  Errors:")
            for err in self._errors[:10]:
                lines.append(f"    - {err}")
            lines.append("")
        lines.append("=" * 60)

        return {
            "summary": "\n".join(lines),
            "total": total,
            "materialized": materialized,
            "skipped": skipped,
            "resolved": resolved,
            "fallback": fallback,
            "errors": len(self._errors),
            "error_details": self._errors[:],
            "elapsed_seconds": round(elapsed, 1),
        }

    def _build_verify_report(
        self,
        total_entities: int,
        with_asset: int,
        with_eagle_path: int,
        with_source_type: int,
        missing_entity: int,
        missing_asset: int,
        path_accessible: int,
        path_inaccessible: int,
    ) -> dict[str, Any]:
        lines = [
            "=" * 60,
            "  Asset Binding Verification Report (E11.2.2)",
            "=" * 60,
            "",
            f"  Total entity.json found:   {total_entities}",
            f"  With asset section:       {with_asset}",
            f"  With eagle_path:          {with_eagle_path}",
            f"  With source_type:         {with_source_type}",
            f"  Missing entity.json:      {missing_entity}",
            f"  Missing asset section:    {missing_asset}",
            f"  Path accessible (local):  {path_accessible}",
            f"  Path inaccessible (Y:):   {path_inaccessible}",
            "",
            "=" * 60,
        ]

        return {
            "summary": "\n".join(lines),
            "total_entities": total_entities,
            "with_asset": with_asset,
            "with_eagle_path": with_eagle_path,
            "with_source_type": with_source_type,
            "missing_entity": missing_entity,
            "missing_asset": missing_asset,
            "path_accessible": path_accessible,
            "path_inaccessible": path_inaccessible,
        }

    @property
    def error_count(self) -> int:
        return len(self._errors)

    def __repr__(self) -> str:
        return (
            f"AssetBindingMaterializer(root={self._root}, "
            f"mappings={self._resolver.mapping_count})"
        )