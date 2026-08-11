"""E11 Phase 3 — Eagle Asset Indexer。

扫描 Eagle 素材库，构建索引。

输入：
  Eagle Library/
   ├── MW_VIDEO_260721_000123.mp4
   ├── MW_VIDEO_260721_000124.mp4
   ├── MW_IMG_260721_000125.png

输出：
  EagleIndex 对象，包含所有 EagleAsset 记录
  支持按 creative_asset_id 和 filename 快速查询
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import EagleAsset


# 统一编号正则：MW_VIDEO_YYMMDD_6位序列号
CREATIVE_ID_PATTERN = re.compile(
    r"(MW_[A-Z]+_\d{6}_\d{6})",
    re.IGNORECASE,
)

# 支持的文件扩展名
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


@dataclass
class EagleIndex:
    """Eagle 素材索引。

    Usage:
        index = EagleIndex()
        index.add(asset)
        result = index.find_by_id("MW_VIDEO_260721_000123")
    """

    assets: list[EagleAsset] = field(default_factory=list)
    _by_id: dict[str, EagleAsset] = field(default_factory=dict, repr=False)
    _by_filename: dict[str, EagleAsset] = field(default_factory=dict, repr=False)

    def add(self, asset: EagleAsset) -> None:
        self.assets.append(asset)
        if asset.creative_asset_id:
            self._by_id[asset.creative_asset_id] = asset
        self._by_filename[asset.filename.lower()] = asset

    def find_by_id(self, creative_asset_id: str) -> EagleAsset | None:
        return self._by_id.get(creative_asset_id)

    def find_by_filename(self, filename: str) -> EagleAsset | None:
        return self._by_filename.get(filename.lower())

    def find_by_id_fuzzy(self, pattern: str) -> list[EagleAsset]:
        """模糊搜索：creative_asset_id 包含 pattern。"""
        return [a for a in self.assets if pattern.lower() in a.creative_asset_id.lower()]

    @property
    def total(self) -> int:
        return len(self.assets)

    @property
    def video_count(self) -> int:
        return sum(
            1 for a in self.assets
            if Path(a.filename).suffix.lower() in VIDEO_EXTENSIONS
        )

    @property
    def image_count(self) -> int:
        return self.total - self.video_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "assets": [a.to_dict() for a in self.assets],
            "total": self.total,
            "video_count": self.video_count,
            "image_count": self.image_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EagleIndex:
        index = cls()
        for a in data.get("assets", []):
            index.add(EagleAsset.from_dict(a))
        return index


class EagleIndexer:
    """Eagle 素材库扫描器。

    扫描指定目录，递归收集所有视频/图片文件，提取元数据。

    Usage:
        indexer = EagleIndexer("D:/eagle")
        index = indexer.build_index()
        print(f"Found {index.total} assets")
        print(f"  Videos: {index.video_count}")
        print(f"  Images: {index.image_count}")
    """

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir)

    # ── Public API ───────────────────────────────────────

    def build_index(self) -> EagleIndex:
        """扫描素材库，构建完整索引。"""
        index = EagleIndex()

        if not self._root.exists():
            return index

        for file_path in self._root.rglob("*"):
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext not in VIDEO_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                continue

            asset = self._parse_file(file_path)
            if asset:
                index.add(asset)

        return index

    def scan_directory(self, subdir: str = "") -> EagleIndex:
        """扫描指定子目录。"""
        target = self._root / subdir if subdir else self._root
        index = EagleIndex()

        if not target.exists():
            return index

        for file_path in target.iterdir():
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext not in VIDEO_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                continue

            asset = self._parse_file(file_path)
            if asset:
                index.add(asset)

        return index

    def find_by_id(self, creative_asset_id: str) -> EagleAsset | None:
        """按 creative_asset_id 搜索单个文件。"""
        index = self.build_index()
        return index.find_by_id(creative_asset_id)

    # ── Internal ────────────────────────────────────────

    def _parse_file(self, file_path: Path) -> EagleAsset | None:
        """解析单个文件为 EagleAsset。"""
        filename = file_path.name
        creative_id = self._extract_creative_id(filename) or ""

        ext = file_path.suffix.lower()
        is_video = ext in VIDEO_EXTENSIONS

        # 获取文件哈希
        file_hash = self._compute_hash(file_path)

        return EagleAsset(
            filename=filename,
            path=str(file_path.resolve()),
            creative_asset_id=creative_id,
            duration=0.0,  # 实际项目需用 ffprobe 获取
            resolution="",  # 实际项目需用 ffprobe 获取
            file_hash=file_hash,
            file_size=file_path.stat().st_size if file_path.exists() else 0,
            created_at="",
        )

    def _extract_creative_id(self, filename: str) -> str | None:
        """从文件名提取统一编号。

        匹配模式：MW_类型_日期_序列号
        例如：MW_VIDEO_260721_000123, MW_IMG_260721_000125
        """
        match = CREATIVE_ID_PATTERN.search(filename)
        if match:
            return match.group(1).upper()  # 统一转大写
        return None

    def _compute_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """计算文件哈希（快速采样）。"""
        if not file_path.exists():
            return ""
        try:
            h = hashlib.md5()
            with open(file_path, "rb") as f:
                # 读取前 1KB + 中间 1KB + 后 1KB 作为快速哈希
                file_size = file_path.stat().st_size
                h.update(f.read(min(chunk_size, file_size)))
                if file_size > chunk_size * 2:
                    f.seek(file_size // 2)
                    h.update(f.read(min(chunk_size, file_size - file_size // 2)))
                if file_size > chunk_size:
                    f.seek(max(0, file_size - chunk_size))
                    h.update(f.read(min(chunk_size, file_size)))
            return h.hexdigest()
        except (IOError, OSError):
            return ""

    def __repr__(self) -> str:
        return f"EagleIndexer(root={self._root})"