"""E11.2 — Asset Binding Repository。

读写 CreativeAssetReference 到 data/creatives/{creative_id}/assets.json

Usage:
    repo = AssetBindingRepository("data/creatives")
    repo.save(reference)
    ref = repo.load("2453146861847495")
    all_refs = repo.load_all()
    print(f"Total bound: {repo.count()}")
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .asset_reference import CreativeAssetReference


class AssetBindingRepository:
    """资产绑定存储层。

    每个 CreativeEntity 的资产绑定信息存储为独立的 assets.json 文件。
    目录结构：
      data/creatives/{creative_id}/
        ├── entity.json
        ├── facebook.json
        └── assets.json    ← 本模块管理
    """

    def __init__(self, creative_storage_root: str = "data/creatives") -> None:
        self._root = Path(creative_storage_root)

    # ── Public API ───────────────────────────────────────

    def save(self, reference: CreativeAssetReference) -> str:
        """保存资产绑定记录。

        Args:
            reference: CreativeAssetReference

        Returns:
            写入的文件路径
        """
        if not reference.creative_id:
            raise ValueError("creative_id is required")

        reference.bound_at = datetime.now().isoformat()
        filepath = self._asset_path(reference.creative_id)
        os.makedirs(filepath.parent, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(reference.to_dict(), f, indent=2, ensure_ascii=False)

        return str(filepath)

    def save_batch(self, references: list[CreativeAssetReference]) -> int:
        """批量保存。

        Returns:
            成功保存数量
        """
        count = 0
        for ref in references:
            try:
                self.save(ref)
                count += 1
            except Exception:
                pass
        return count

    def load(self, creative_id: str) -> CreativeAssetReference | None:
        """加载单个资产绑定记录。"""
        filepath = self._asset_path(creative_id)
        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return CreativeAssetReference.from_dict(data)

    def load_all(self) -> list[CreativeAssetReference]:
        """加载所有资产绑定记录。"""
        refs: list[CreativeAssetReference] = []

        if not self._root.exists():
            return refs

        for entity_dir in self._root.iterdir():
            if not entity_dir.is_dir():
                continue
            asset_file = entity_dir / "assets.json"
            if not asset_file.exists():
                continue
            try:
                with open(asset_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                refs.append(CreativeAssetReference.from_dict(data))
            except Exception:
                pass

        return refs

    def load_all_by_source(self, source: str) -> list[CreativeAssetReference]:
        """按来源加载所有绑定记录。"""
        return [r for r in self.load_all() if r.source.value == source]

    def load_all_by_confidence(self, min_confidence: float = 0.85) -> list[CreativeAssetReference]:
        """按最低置信度加载。"""
        return [r for r in self.load_all() if r.confidence >= min_confidence]

    def exists(self, creative_id: str) -> bool:
        """检查是否已绑定。"""
        return self._asset_path(creative_id).exists()

    def delete(self, creative_id: str) -> bool:
        """删除绑定记录。"""
        filepath = self._asset_path(creative_id)
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def count(self) -> int:
        """已绑定数量。"""
        if not self._root.exists():
            return 0
        return sum(
            1 for d in self._root.iterdir()
            if d.is_dir() and (d / "assets.json").exists()
        )

    def to_summary(self) -> dict[str, Any]:
        """生成绑定统计摘要。"""
        refs = self.load_all()
        by_source: dict[str, int] = {}
        by_method: dict[str, int] = {}
        high_conf = 0

        for r in refs:
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_method[r.match_method.value] = by_method.get(r.match_method.value, 0) + 1
            if r.is_high_confidence:
                high_conf += 1

        return {
            "total": len(refs),
            "by_source": by_source,
            "by_method": by_method,
            "high_confidence": high_conf,
            "high_confidence_rate": round(high_conf / len(refs), 4) if refs else 0.0,
        }

    # ── Internal ────────────────────────────────────────

    def _asset_path(self, creative_id: str) -> Path:
        return self._root / creative_id / "assets.json"

    def __repr__(self) -> str:
        return f"AssetBindingRepository(root={self._root})"