"""JSONL 文件轮转器 — 防止 append-only 文件无限膨胀.

设计原则:
  - 非侵入式: 在追加写入前检查, 不修改读取逻辑
  - 轻量触发: 仅 stat 检查文件大小, 不读取文件内容
  - 可配置: 支持按大小/行数触发, 可配置保留份数
  - 压缩归档: 历史文件 gzip 压缩, 节省磁盘空间
  - 线程安全: 文件锁保护轮转操作

轮转策略:
  1. 文件大小 >= max_bytes (默认 10MB) → 触发轮转
  2. 文件行数 >= max_lines (默认 50000) → 触发轮转
  3. 轮转时: file.jsonl → file.jsonl.1.gz → file.jsonl.2.gz → ... → 删除最旧
  4. 保留份数: max_backups (默认 5)

用法:
    from .jsonl_rotator import JsonlRotator

    rotator = JsonlRotator(data_dir="data")
    rotator.maybe_rotate("data/ceo/execution_memory.jsonl")
    # 然后正常 append 写入

    # 或使用便捷函数
    from .jsonl_rotator import append_with_rotation
    append_with_rotation("data/ceo/execution_memory.jsonl", record_dict, data_dir="data")
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 默认配置 ──────────────────────────────────────────────────
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_LINES = 50_000  # 5 万行
DEFAULT_MAX_BACKUPS = 5  # 保留 5 份历史归档


class JsonlRotator:
    """JSONL 文件轮转器 — 按大小/行数触发轮转, gzip 压缩归档.

    线程安全: 使用全局锁保护同一文件的轮转操作.
    """

    # 全局锁池: 每个文件路径一把锁, 防止并发轮转冲突
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(
        self,
        data_dir: str = "data",
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_lines: int = DEFAULT_MAX_LINES,
        max_backups: int = DEFAULT_MAX_BACKUPS,
    ) -> None:
        """初始化轮转器.

        Args:
            data_dir: 数据目录根路径 (用于日志和统计)
            max_bytes: 单文件最大字节数, 超过则轮转 (默认 10MB)
            max_lines: 单文件最大行数, 超过则轮转 (默认 50000)
            max_backups: 保留的历史归档份数 (默认 5)
        """
        self.data_dir = Path(data_dir)
        self.max_bytes = max_bytes
        self.max_lines = max_lines
        self.max_backups = max_backups

    @classmethod
    def _get_lock(cls, path: str) -> threading.Lock:
        """获取文件级锁 (每个路径一把锁)."""
        with cls._locks_guard:
            if path not in cls._locks:
                cls._locks[path] = threading.Lock()
            return cls._locks[path]

    def maybe_rotate(self, file_path: str | Path) -> bool:
        """检查并可能触发轮转.

        在 append 写入前调用. 仅 stat 检查大小, 不读取文件内容.
        如果文件大小未超阈值, 立即返回 (无 IO 开销).

        Args:
            file_path: JSONL 文件路径

        Returns:
            True=已轮转; False=未轮转 (文件未超阈值或不存在)
        """
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            stat = path.stat()
        except OSError:
            return False

        # 按大小触发 (轻量, 仅 stat)
        if stat.st_size < self.max_bytes:
            # 大小未超, 再按行数触发 (需要读取, 但仅在大小接近时才检查)
            # 优化: 仅当大小超过 50% 阈值时才检查行数, 避免每次都读文件
            if stat.st_size < self.max_bytes * 0.5:
                return False
            # 检查行数
            line_count = self._count_lines(path)
            if line_count < self.max_lines:
                return False
            logger.info(
                "JsonlRotator: rotating %s (lines=%d >= %d)",
                path.name, line_count, self.max_lines,
            )
        else:
            logger.info(
                "JsonlRotator: rotating %s (size=%d bytes >= %d)",
                path.name, stat.st_size, self.max_bytes,
            )

        # 获取文件级锁, 执行轮转
        lock = self._get_lock(str(path.resolve()))
        with lock:
            # 双重检查: 拿到锁后再次确认 (可能其他线程已轮转)
            try:
                current_size = path.stat().st_size
            except OSError:
                return False
            if current_size < self.max_bytes and current_size < self.max_bytes * 0.5:
                return False

            self._do_rotate(path)
            return True

    def _count_lines(self, path: Path) -> int:
        """快速统计文件行数 (二进制模式, 避免解码开销)."""
        try:
            with open(path, "rb") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    def _do_rotate(self, path: Path) -> None:
        """执行轮转操作 (已持有锁).

        步骤:
          1. 删除最旧的归档 (file.jsonl.{max_backups}.gz)
          2. 从旧到新依次重命名: file.jsonl.{n}.gz → file.jsonl.{n+1}.gz
          3. 压缩当前文件: file.jsonl → file.jsonl.1.gz
          4. 创建新的空文件 (保持文件存在, 避免下游报错)
        """
        base = str(path)

        # 1. 删除最旧归档
        oldest = Path(f"{base}.{self.max_backups}.gz")
        if oldest.exists():
            try:
                oldest.unlink()
            except OSError as exc:
                logger.warning("JsonlRotator: failed to delete %s: %s", oldest, exc)

        # 2. 从旧到新依次重命名 (n-1 → n, 从 max_backups-1 到 1)
        for n in range(self.max_backups - 1, 0, -1):
            src = Path(f"{base}.{n}.gz")
            dst = Path(f"{base}.{n + 1}.gz")
            if src.exists():
                try:
                    shutil.move(str(src), str(dst))
                except OSError as exc:
                    logger.warning("JsonlRotator: failed to move %s → %s: %s", src, dst, exc)

        # 3. 压缩当前文件为 .1.gz
        archive_path = Path(f"{base}.1.gz")
        try:
            self._gzip_file(path, archive_path)
        except Exception as exc:
            logger.error("JsonlRotator: gzip failed for %s: %s", path, exc)
            return  # 压缩失败, 不截断原文件

        # 4. 截断原文件 (创建新的空文件)
        try:
            # 清空原文件 (而非删除, 避免下游 open 失败)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
        except OSError as exc:
            logger.warning("JsonlRotator: failed to truncate %s: %s", path, exc)

        # 5. 写入轮转审计记录 (到单独的轮转日志)
        self._write_rotation_audit(path, archive_path)

        logger.info(
            "JsonlRotator: rotated %s → %s (backups=%d)",
            path.name, archive_path.name, self.max_backups,
        )

    def _gzip_file(self, src: Path, dst: Path) -> None:
        """gzip 压缩文件."""
        with open(src, "rb") as f_in:
            with gzip.open(dst, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _write_rotation_audit(self, original: Path, archive: Path) -> None:
        """写入轮转审计记录."""
        audit_path = self.data_dir / "rotation_audit.jsonl"
        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original_file": str(original),
                "archive_file": str(archive),
                "original_size": original.stat().st_size if original.exists() else 0,
                "archive_size": archive.stat().st_size if archive.exists() else 0,
                "max_bytes": self.max_bytes,
                "max_lines": self.max_lines,
                "max_backups": self.max_backups,
            }
            with open(audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("JsonlRotator: failed to write audit: %s", exc)

    def list_archives(self, file_path: str | Path) -> list[dict[str, Any]]:
        """列出某文件的所有归档 (用于查询/管理 API)."""
        base = str(file_path)
        archives = []
        for n in range(1, self.max_backups + 1):
            archive = Path(f"{base}.{n}.gz")
            if archive.exists():
                try:
                    stat = archive.stat()
                    archives.append({
                        "index": n,
                        "path": str(archive),
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    })
                except OSError:
                    continue
        return archives

    def get_rotation_stats(self) -> dict[str, Any]:
        """获取轮转统计信息 (扫描 data_dir 下所有 .jsonl 文件)."""
        stats = {
            "total_jsonl_files": 0,
            "total_size_bytes": 0,
            "total_archives": 0,
            "archive_size_bytes": 0,
            "files_near_limit": 0,  # 大小超过 80% 阈值的文件
            "largest_files": [],
        }

        if not self.data_dir.exists():
            return stats

        file_sizes: list[tuple[str, int]] = []

        for path in self.data_dir.rglob("*.jsonl"):
            if path.name == "rotation_audit.jsonl":
                continue
            try:
                stat = path.stat()
                stats["total_jsonl_files"] += 1
                stats["total_size_bytes"] += stat.st_size
                file_sizes.append((str(path), stat.st_size))
                if stat.st_size >= self.max_bytes * 0.8:
                    stats["files_near_limit"] += 1
            except OSError:
                continue

        # 统计归档文件
        for path in self.data_dir.rglob("*.jsonl.*.gz"):
            try:
                stat = path.stat()
                stats["total_archives"] += 1
                stats["archive_size_bytes"] += stat.st_size
            except OSError:
                continue

        # Top 10 最大文件
        file_sizes.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = [
            {"path": p, "size_mb": round(s / (1024 * 1024), 2)}
            for p, s in file_sizes[:10]
        ]

        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
        stats["archive_size_mb"] = round(stats["archive_size_bytes"] / (1024 * 1024), 2)

        return stats

    def rotate_all(self) -> dict[str, Any]:
        """批量扫描 data_dir 下所有 JSONL 文件, 轮转超阈值的文件.

        非侵入式运维操作: 不修改任何模块的写入路径, 仅对已超阈值的文件
        执行 gzip 归档 + 截断. 适用于 append-only 文件定期清理.

        Returns:
            dict: {scanned, rotated, skipped, details: [{path, rotated, reason}]}
        """
        result: dict[str, Any] = {
            "scanned": 0,
            "rotated": 0,
            "skipped": 0,
            "details": [],
        }

        if not self.data_dir.exists():
            return result

        for path in self.data_dir.rglob("*.jsonl"):
            # 跳过轮转审计日志自身
            if path.name == "rotation_audit.jsonl":
                continue
            result["scanned"] += 1
            try:
                rotated = self.maybe_rotate(path)
            except Exception as exc:
                logger.warning("JsonlRotator: rotate_all failed for %s: %s", path, exc)
                result["skipped"] += 1
                result["details"].append({
                    "path": str(path.relative_to(self.data_dir)),
                    "rotated": False,
                    "reason": f"error: {exc}",
                })
                continue

            if rotated:
                result["rotated"] += 1
                result["details"].append({
                    "path": str(path.relative_to(self.data_dir)),
                    "rotated": True,
                    "reason": "exceeded threshold",
                })
            else:
                result["skipped"] += 1

        logger.info(
            "JsonlRotator: rotate_all done — scanned=%d rotated=%d skipped=%d",
            result["scanned"], result["rotated"], result["skipped"],
        )
        return result


# ── 模块级单例 + 便捷函数 ─────────────────────────────────────

_default_rotator: JsonlRotator | None = None
_default_rotator_lock = threading.Lock()


def get_default_rotator(data_dir: str = "data") -> JsonlRotator:
    """获取默认的 JsonlRotator 单例."""
    global _default_rotator
    with _default_rotator_lock:
        if _default_rotator is None:
            _default_rotator = JsonlRotator(data_dir=data_dir)
        return _default_rotator


def append_with_rotation(
    file_path: str | Path,
    record: dict[str, Any],
    data_dir: str = "data",
    rotator: JsonlRotator | None = None,
) -> None:
    """带轮转的 JSONL 追加写入.

    在追加前检查文件大小, 超阈值时自动轮转.
    这是 _append_jsonl 的轮转增强版.

    Args:
        file_path: JSONL 文件路径
        record: 要写入的记录 dict
        data_dir: 数据目录 (用于初始化默认 rotator)
        rotator: 自定义 rotator (None 则使用默认单例)
    """
    if rotator is None:
        rotator = get_default_rotator(data_dir=data_dir)

    # 轮转检查 (轻量, 仅 stat)
    rotator.maybe_rotate(file_path)

    # 确保目录存在
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 追加写入
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
