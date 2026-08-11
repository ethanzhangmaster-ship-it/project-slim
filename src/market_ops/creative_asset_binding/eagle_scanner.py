"""E11.2.2 — Eagle Asset Scanner（增量扫描 + 变更检测）。

定期扫描 Eagle 素材库，支持增量更新（仅检测新文件/变更文件）。

与 EagleIndexer 的区别：
  - EagleIndexer: 全量扫描，每次重建索引
  - EagleScanner:  增量扫描，持久化索引，检测变更

Usage:
    scanner = EagleScanner("Y:\\Eagle\\公司-市场部门库.library")
    report = scanner.scan_incremental()
    print(f"New assets: {report['new_count']}")
    print(f"Changed:    {report['changed_count']}")
    print(f"Removed:    {report['removed_count']}")
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .eagle_indexer import EagleIndexer, EagleIndex, EagleAsset
from .models import EagleAsset as EagleAssetModel


class EagleScanner:
    """Eagle 素材库增量扫描器。

    持久化索引到磁盘，每次扫描对比上次结果，检测新增/变更/删除。

    持久化文件：
      data/eagle_scan_index.json  — 上次扫描的完整索引
      data/eagle_scan_log.jsonl  — 扫描日志
    """

    # 支持的文件类型
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def __init__(
        self,
        eagle_root: str,
        index_path: str = "data/eagle_scan_index.json",
        log_path: str = "data/eagle_scan_log.jsonl",
    ) -> None:
        self._root = Path(eagle_root)
        self._index_path = Path(index_path)
        self._log_path = Path(log_path)
        self._indexer = EagleIndexer(eagle_root)

    # ── Public API ───────────────────────────────────────

    def scan_full(self) -> dict[str, Any]:
        """全量扫描（首次运行或重建索引）。

        Returns:
            {
                "total": int,
                "video_count": int,
                "image_count": int,
                "new_count": int,
                "index": EagleIndex,
                "elapsed_seconds": float,
            }
        """
        started = datetime.now()

        index = self._indexer.build_index()
        self._save_index(index)
        self._log("full_scan", {"total": index.total})

        elapsed = (datetime.now() - started).total_seconds()

        return {
            "total": index.total,
            "video_count": index.video_count,
            "image_count": index.image_count,
            "new_count": index.total,
            "index": index,
            "elapsed_seconds": round(elapsed, 1),
        }

    def scan_incremental(self) -> dict[str, Any]:
        """增量扫描（对比上次索引，检测变更）。

        Returns:
            {
                "total": int,
                "new_count": int,
                "changed_count": int,
                "removed_count": int,
                "new_assets": list[EagleAsset],
                "changed_assets": list[EagleAsset],
                "removed_paths": list[str],
                "index": EagleIndex,
                "elapsed_seconds": float,
            }
        """
        started = datetime.now()

        # 加载上次索引
        previous = self._load_index()
        previous_paths = {a.path: a for a in previous.assets} if previous else {}

        # 构建当前索引
        current = self._indexer.build_index()
        current_paths = {a.path: a for a in current.assets}

        # 检测变更
        new_assets: list[EagleAsset] = []
        changed_assets: list[EagleAsset] = []
        removed_paths: list[str] = []

        for path, asset in current_paths.items():
            if path not in previous_paths:
                new_assets.append(asset)
            elif previous_paths[path].file_hash != asset.file_hash:
                changed_assets.append(asset)

        for path in previous_paths:
            if path not in current_paths:
                removed_paths.append(path)

        # 保存当前索引
        self._save_index(current)

        elapsed = (datetime.now() - started).total_seconds()

        summary = {
            "total": current.total,
            "new_count": len(new_assets),
            "changed_count": len(changed_assets),
            "removed_count": len(removed_paths),
            "new_assets": new_assets,
            "changed_assets": changed_assets,
            "removed_paths": removed_paths,
            "index": current,
            "elapsed_seconds": round(elapsed, 1),
        }

        self._log("incremental_scan", {
            "total": current.total,
            "new": len(new_assets),
            "changed": len(changed_assets),
            "removed": len(removed_paths),
        })

        return summary

    def get_new_assets(self) -> list[EagleAsset]:
        """获取上次扫描后新增的素材。"""
        result = self.scan_incremental()
        return result["new_assets"]

    def find_by_filename(self, filename: str) -> EagleAsset | None:
        """按文件名搜索（需要先 scan）。"""
        index = self._load_index()
        if index:
            return index.find_by_filename(filename)
        return None

    def find_by_v_number(self, v_number: str) -> EagleAsset | None:
        """按 v 号搜索（v2601536 → 匹配文件名包含 v2601536 的素材）。

        Args:
            v_number: e.g., "v2601536" or "2601536"
        """
        index = self._load_index()
        if not index:
            return None
        search = v_number.replace("v", "").replace("V", "")
        for asset in index.assets:
            if search in asset.filename:
                return asset
        return None

    @property
    def is_available(self) -> bool:
        """检查 Eagle 库是否可访问。"""
        return self._root.exists()

    # ── Internal ────────────────────────────────────────

    def _save_index(self, index: EagleIndex) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        data = index.to_dict()
        data["scanned_at"] = datetime.now().isoformat()
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_index(self) -> EagleIndex | None:
        if not self._index_path.exists():
            return None
        with open(self._index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return EagleIndex.from_dict(data)

    def _log(self, scan_type: str, summary: dict[str, Any]) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "type": scan_type,
            **summary,
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def __repr__(self) -> str:
        return f"EagleScanner(root={self._root})"