"""E11.3.1 — Vision Asset Validator。

进入 Vision Pipeline 前验证 VisionAsset 的完整性。

检查项：
  1. 文件存在性：video_path 文件是否存在
  2. 视频格式：mp4 / mov / webm
  3. 元数据完整：creative_id, eagle_filename, video_path 非空
  4. 性能数据：spend, impressions 非空（可选，仅警告）

Usage:
    validator = VisionAssetValidator()
    ok, errors = validator.validate(asset)
    if not ok:
        print(errors)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .models import VisionAsset

logger = logging.getLogger(__name__)

# 支持的视频格式
SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

# 元数据必填字段
REQUIRED_METADATA_FIELDS = ["creative_id", "eagle_filename", "video_path"]


class VisionAssetValidator:
    """VisionAsset 进入 Vision Pipeline 前的验证器。

    验证规则：
      - 文件存在：Path(video_path).exists()
      - 格式支持：后缀名在 SUPPORTED_VIDEO_FORMATS 中
      - 元数据完整：creative_id, eagle_filename, video_path 非空
      - 文件大小：> 0 bytes
    """

    def __init__(
        self,
        check_files: bool = True,
        check_performance: bool = False,
    ) -> None:
        self._check_files = check_files
        self._check_performance = check_performance

    # ── Public API ───────────────────────────────────────

    def validate(self, asset: VisionAsset) -> tuple[bool, list[str]]:
        """验证 VisionAsset。

        Args:
            asset: VisionAsset 对象

        Returns:
            (is_valid, errors)
        """
        errors: list[str] = []

        # 1. 元数据完整性
        metadata_errors = self._check_metadata(asset)
        errors.extend(metadata_errors)

        # 2. 文件验证
        if self._check_files:
            file_errors = self._check_file(asset.video_path)
            errors.extend(file_errors)

        # 3. 性能数据（可选，仅警告）
        if self._check_performance:
            perf_warnings = self._check_performance_data(asset)
            for w in perf_warnings:
                logger.warning(f"VisionAssetValidator: {asset.asset_id}: {w}")

        return len(errors) == 0, errors

    def validate_path(self, video_path: str) -> tuple[bool, list[str]]:
        """仅验证视频文件路径。

        Args:
            video_path: 视频文件路径

        Returns:
            (is_valid, errors)
        """
        errors = self._check_file(video_path)
        return len(errors) == 0, errors

    def is_valid_video(self, video_path: str) -> bool:
        """快速检查视频文件是否有效。"""
        errors = self._check_file(video_path)
        return len(errors) == 0

    def is_supported_format(self, video_path: str) -> bool:
        """检查视频格式是否支持。"""
        suffix = Path(video_path).suffix.lower()
        return suffix in SUPPORTED_VIDEO_FORMATS

    # ── Internal ────────────────────────────────────────

    def _check_file(self, video_path: str) -> list[str]:
        """检查视频文件是否存在、格式支持、大小 > 0。"""
        errors: list[str] = []

        if not video_path:
            errors.append("video_path is empty")
            return errors

        path = Path(video_path)

        # 文件存在
        if not path.exists():
            errors.append(f"file not found: {video_path}")
            return errors

        if not path.is_file():
            errors.append(f"not a file: {video_path}")
            return errors

        # 格式支持
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_VIDEO_FORMATS:
            errors.append(f"unsupported format: {suffix}")

        # 文件大小
        size = path.stat().st_size
        if size == 0:
            errors.append("file is empty (0 bytes)")

        return errors

    def _check_metadata(self, asset: VisionAsset) -> list[str]:
        """检查元数据完整性。"""
        errors: list[str] = []

        if not asset.creative_id and not asset.creative_asset_id:
            errors.append("missing creative_id / creative_asset_id")

        if not asset.video_path:
            errors.append("missing video_path")

        if not asset.eagle_filename:
            errors.append("missing eagle_filename")

        return errors

    def _check_performance_data(self, asset: VisionAsset) -> list[str]:
        """检查性能数据完整性（非阻塞）。"""
        warnings: list[str] = []

        if not asset.performance:
            warnings.append("no performance data")
            return warnings

        if asset.spend == 0 and asset.impressions == 0:
            warnings.append("no spend or impressions data")

        return warnings

    def __repr__(self) -> str:
        return f"VisionAssetValidator(check_files={self._check_files})"