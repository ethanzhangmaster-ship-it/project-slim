"""EagleScanner — Eagle 素材库自动索引扫描器。

扫描指定目录，递归收集视频/图片文件，提取元数据并生成索引文件，
供 CreativeMappingEngine 使用。

功能：
  - 全量扫描：递归扫描目录，构建完整索引
  - 增量扫描：对比上次索引，检测新增/变更/删除
  - 元数据提取：filename, path, creative_asset_id, file_hash, file_size, created_at
  - ffprobe 可选：提取 duration/resolution（不可用时降级为空值）
  - 持久化：索引写入 data/eagle_scan_index.json

Usage::

    scanner = EagleScanner(
        eagle_root="D:/eagle/library",
        index_path="data/eagle_scan_index.json",
    )
    report = scanner.scan_full()
    print(f"Total: {report['total']}, New: {report['new_count']}")
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 支持的文件扩展名
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
ALL_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS

# 统一编号正则：MW_类型_日期_6位序列号
CREATIVE_ID_PATTERN = re.compile(
    r"(MW_[A-Z]+_\d{6}_\d{6})",
    re.IGNORECASE,
)


class EagleScanner:
    """Eagle 素材库扫描器 — 自动生成索引。

    扫描指定目录，递归收集视频/图片文件，提取元数据，
    持久化到 ``index_path``，供 CreativeMappingEngine 加载。

    Args:
        eagle_root: Eagle 素材库根目录
        index_path: 索引文件输出路径 (默认 data/eagle_scan_index.json)
        extract_metadata: 是否使用 ffprobe 提取 duration/resolution
    """

    def __init__(
        self,
        eagle_root: str | Path,
        index_path: str | Path = "data/eagle_scan_index.json",
        extract_metadata: bool = True,
    ) -> None:
        self._root = Path(eagle_root)
        self._index_path = Path(index_path)
        self._extract_metadata = extract_metadata
        self._ffprobe_available: bool | None = None

    # ── Public API ───────────────────────────────────────

    def scan_full(self) -> dict[str, Any]:
        """全量扫描 — 重建完整索引。

        Returns:
            扫描报告字典，包含 total/video_count/image_count/new_count/elapsed_seconds
        """
        started = datetime.now()

        assets = self._collect_assets()
        self._save_index(assets)
        self._log_scan("full_scan", len(assets))

        elapsed = (datetime.now() - started).total_seconds()
        return {
            "status": "ok",
            "scanned_at": datetime.now().isoformat(),
            "root_dir": str(self._root),
            "total": len(assets),
            "video_count": sum(1 for a in assets if self._is_video(a["filename"])),
            "image_count": sum(1 for a in assets if not self._is_video(a["filename"])),
            "new_count": len(assets),
            "changed_count": 0,
            "removed_count": 0,
            "elapsed_seconds": round(elapsed, 3),
        }

    def scan_incremental(self) -> dict[str, Any]:
        """增量扫描 — 对比上次索引，检测变更。

        Returns:
            扫描报告字典，包含 new_count/changed_count/removed_count
        """
        started = datetime.now()

        previous = self._load_index()
        previous_paths = {a["path"]: a for a in previous} if previous else {}

        current = self._collect_assets()
        current_paths = {a["path"]: a for a in current}

        new_assets = []
        changed_assets = []
        removed_paths = []

        for path, asset in current_paths.items():
            if path not in previous_paths:
                new_assets.append(asset)
            elif previous_paths[path].get("file_hash", "") != asset.get("file_hash", ""):
                changed_assets.append(asset)

        for path in previous_paths:
            if path not in current_paths:
                removed_paths.append(path)

        self._save_index(current)
        self._log_scan(
            "incremental_scan",
            len(current),
            new=len(new_assets),
            changed=len(changed_assets),
            removed=len(removed_paths),
        )

        elapsed = (datetime.now() - started).total_seconds()
        return {
            "status": "ok",
            "scanned_at": datetime.now().isoformat(),
            "root_dir": str(self._root),
            "total": len(current),
            "video_count": sum(1 for a in current if self._is_video(a["filename"])),
            "image_count": sum(1 for a in current if not self._is_video(a["filename"])),
            "new_count": len(new_assets),
            "changed_count": len(changed_assets),
            "removed_count": len(removed_paths),
            "elapsed_seconds": round(elapsed, 3),
        }

    def get_index(self) -> dict[str, Any]:
        """加载当前索引（不触发扫描）。"""
        assets = self._load_index()
        if assets is None:
            return {
                "scanned_at": "",
                "root_dir": str(self._root),
                "total": 0,
                "video_count": 0,
                "image_count": 0,
                "assets": [],
            }
        return {
            "scanned_at": self._get_index_meta().get("scanned_at", ""),
            "root_dir": self._get_index_meta().get("root_dir", str(self._root)),
            "total": len(assets),
            "video_count": sum(1 for a in assets if self._is_video(a["filename"])),
            "image_count": sum(1 for a in assets if not self._is_video(a["filename"])),
            "assets": assets,
        }

    def get_stats(self) -> dict[str, Any]:
        """查询索引统计摘要。"""
        assets = self._load_index() or []
        meta = self._get_index_meta()
        return {
            "scanned_at": meta.get("scanned_at", ""),
            "root_dir": meta.get("root_dir", str(self._root)),
            "total": len(assets),
            "video_count": sum(1 for a in assets if self._is_video(a["filename"])),
            "image_count": sum(1 for a in assets if not self._is_video(a["filename"])),
            "with_creative_id": sum(1 for a in assets if a.get("creative_asset_id")),
            "with_duration": sum(1 for a in assets if a.get("duration", 0) > 0),
            "with_resolution": sum(1 for a in assets if a.get("resolution")),
        }

    @property
    def is_available(self) -> bool:
        """检查 Eagle 库是否可访问。"""
        return self._root.exists()

    # ── 内部方法 ──────────────────────────────────────────

    def _collect_assets(self) -> list[dict[str, Any]]:
        """递归扫描目录，收集所有素材文件。"""
        assets: list[dict[str, Any]] = []
        if not self._root.exists():
            logger.warning("Eagle root not found: %s", self._root)
            return assets

        for file_path in sorted(self._root.rglob("*")):
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            if ext not in ALL_EXTENSIONS:
                continue
            asset = self._parse_file(file_path)
            if asset:
                assets.append(asset)

        return assets

    def _parse_file(self, file_path: Path) -> dict[str, Any] | None:
        """解析单个文件，提取元数据。"""
        try:
            filename = file_path.name
            creative_id = self._extract_creative_id(filename)
            file_hash = self._compute_hash(file_path)
            file_size = file_path.stat().st_size if file_path.exists() else 0
            created_at = self._get_created_at(file_path)

            asset: dict[str, Any] = {
                "filename": filename,
                "path": str(file_path.resolve()),
                "creative_asset_id": creative_id,
                "duration": 0.0,
                "resolution": "",
                "file_hash": file_hash,
                "file_size": file_size,
                "created_at": created_at,
            }

            # 可选：使用 ffprobe 提取视频元数据
            if self._extract_metadata and self._is_video(filename):
                duration, resolution = self._ffprobe_extract(file_path)
                asset["duration"] = duration
                asset["resolution"] = resolution

            return asset
        except (OSError, IOError) as exc:
            logger.warning("Failed to parse file %s: %s", file_path, exc)
            return None

    def _extract_creative_id(self, filename: str) -> str:
        """从文件名提取统一编号 (MW_类型_日期_序列号)。"""
        match = CREATIVE_ID_PATTERN.search(filename)
        if match:
            return match.group(1).upper()
        return ""

    def _compute_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """计算文件哈希（采样：前1KB + 中1KB + 后1KB）。"""
        if not file_path.exists():
            return ""
        try:
            h = hashlib.md5()
            file_size = file_path.stat().st_size
            with open(file_path, "rb") as f:
                h.update(f.read(min(chunk_size, file_size)))
                if file_size > chunk_size * 2:
                    f.seek(file_size // 2)
                    h.update(f.read(min(chunk_size, file_size - file_size // 2)))
                if file_size > chunk_size:
                    f.seek(max(0, file_size - chunk_size))
                    h.update(f.read(min(chunk_size, file_size)))
            return h.hexdigest()
        except (IOError, OSError) as exc:
            logger.warning("Failed to hash %s: %s", file_path, exc)
            return ""

    def _get_created_at(self, file_path: Path) -> str:
        """获取文件创建时间（ISO 格式）。"""
        try:
            stat = file_path.stat()
            # Windows: st_cttime 是创建时间；Unix: st_mtime 是最后修改时间
            ts = getattr(stat, "st_ctime", stat.st_mtime)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (OSError, IOError):
            return ""

    def _ffprobe_extract(self, file_path: Path) -> tuple[float, str]:
        """使用 ffprobe 提取视频 duration 和 resolution。

        Returns:
            (duration_seconds, "WxH") 或 (0.0, "") 如果不可用
        """
        if not self._check_ffprobe():
            return 0.0, ""

        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return 0.0, ""

            data = json.loads(result.stdout)
            duration = float(data.get("format", {}).get("duration", 0))

            # 查找视频流获取分辨率
            resolution = ""
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    width = stream.get("width", 0)
                    height = stream.get("height", 0)
                    if width and height:
                        resolution = f"{width}x{height}"
                    break

            return round(duration, 3), resolution
        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            logger.debug("ffprobe failed for %s: %s", file_path, exc)
            return 0.0, ""

    def _check_ffprobe(self) -> bool:
        """检查 ffprobe 是否可用（结果缓存）。"""
        if self._ffprobe_available is None:
            self._ffprobe_available = shutil.which("ffprobe") is not None
            if not self._ffprobe_available:
                logger.info("ffprobe not available, duration/resolution will be empty")
        return self._ffprobe_available

    @staticmethod
    def _is_video(filename: str) -> bool:
        """判断文件是否为视频。"""
        return Path(filename).suffix.lower() in VIDEO_EXTENSIONS

    def _save_index(self, assets: list[dict[str, Any]]) -> None:
        """持久化索引到文件。"""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "scanned_at": datetime.now().isoformat(),
            "root_dir": str(self._root),
            "total": len(assets),
            "video_count": sum(1 for a in assets if self._is_video(a["filename"])),
            "image_count": sum(1 for a in assets if not self._is_video(a["filename"])),
            "assets": assets,
        }
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_index(self) -> list[dict[str, Any]] | None:
        """加载上次扫描的索引。"""
        if not self._index_path.exists():
            return None
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("assets", [])
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load index: %s", exc)
        return None

    def _get_index_meta(self) -> dict[str, Any]:
        """获取索引文件元数据（scanned_at, root_dir）。"""
        if not self._index_path.exists():
            return {}
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {
                    "scanned_at": data.get("scanned_at", ""),
                    "root_dir": data.get("root_dir", ""),
                }
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _log_scan(self, scan_type: str, total: int, **extra: Any) -> None:
        """记录扫描日志。"""
        log_path = self._index_path.parent / "eagle_scan_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "type": scan_type,
            "total": total,
            **extra,
        }
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to write scan log: %s", exc)

    def __repr__(self) -> str:
        return f"EagleScanner(root={self._root})"


__all__ = ["EagleScanner"]
