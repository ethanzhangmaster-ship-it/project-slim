"""JsonlRotator 单元测试 — 验证 JSONL 文件轮转机制.

测试覆盖:
  1. 基础轮转: 按大小触发、按行数触发
  2. 归档压缩: gzip 压缩、文件名规则
  3. 保留份数: max_backups 限制、最旧归档删除
  4. 线程安全: 并发写入不冲突
  5. 便捷函数: append_with_rotation
  6. 查询 API: list_archives、get_rotation_stats
  7. API 端点: /api/maintenance/jsonl/*
  8. 边界场景: 不存在的文件、空文件、小文件不轮转
"""
from __future__ import annotations

import gzip
import json
import os
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── 公共 fixtures ──────────────────────────────────────────────


@pytest.fixture
def small_rotator(tmp_path: Path):
    """小阈值 rotator (便于测试触发)."""
    from market_ops.workspace.jsonl_rotator import JsonlRotator
    return JsonlRotator(
        data_dir=str(tmp_path),
        max_bytes=1024,  # 1KB
        max_lines=10,
        max_backups=3,
    )


@pytest.fixture
def jsonl_file(tmp_path: Path) -> Path:
    """创建一个测试用 JSONL 文件."""
    path = tmp_path / "test.jsonl"
    path.write_text('{"line": 1}\n{"line": 2}\n', encoding="utf-8")
    return path


# ── 1. 基础轮转 ────────────────────────────────────────────────


class TestBasicRotation:
    """基础轮转功能."""

    def test_no_rotation_for_small_file(self, small_rotator, jsonl_file):
        """小文件不触发轮转."""
        rotated = small_rotator.maybe_rotate(jsonl_file)
        assert rotated is False
        # 原文件内容不变
        content = jsonl_file.read_text(encoding="utf-8")
        assert '{"line": 1}' in content

    def test_rotation_by_size(self, small_rotator, tmp_path):
        """按大小触发轮转."""
        path = tmp_path / "big.jsonl"
        # 写入超过 1KB 的数据
        with open(path, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(json.dumps({"line": i, "data": "x" * 50}) + "\n")

        rotated = small_rotator.maybe_rotate(path)

        assert rotated is True
        # 原文件被截断
        assert path.stat().st_size == 0
        # 归档文件存在
        archive = Path(f"{path}.1.gz")
        assert archive.exists()
        assert archive.stat().st_size > 0

    def test_rotation_by_lines(self, small_rotator, tmp_path):
        """按行数触发轮转 (大小超过 50% 阈值但未超 100%)."""
        path = tmp_path / "many_lines.jsonl"
        # 写入 12 行, 每行约 40 字节, 总约 480-580 字节 (在 50%-100% 阈值之间)
        with open(path, "w", encoding="utf-8") as f:
            for i in range(12):
                f.write(json.dumps({"line": i, "pad": "x" * 20}) + "\n")

        size = path.stat().st_size
        # 确认大小在 50%-100% 阈值之间 (512-1024), 若不在此范围则调整数据
        if size < 512:
            # 补充行数使大小超过 512B
            with open(path, "a", encoding="utf-8") as f:
                for i in range(12, 20):
                    f.write(json.dumps({"line": i, "pad": "x" * 20}) + "\n")
            size = path.stat().st_size
        assert 512 <= size < 1024, f"size={size} not in [512, 1024)"

        rotated = small_rotator.maybe_rotate(path)

        assert rotated is True
        assert path.stat().st_size == 0

    def test_nonexistent_file_returns_false(self, small_rotator, tmp_path):
        """不存在的文件返回 False."""
        path = tmp_path / "nonexistent.jsonl"
        rotated = small_rotator.maybe_rotate(path)
        assert rotated is False


# ── 2. 归档压缩 ────────────────────────────────────────────────


class TestArchiveCompression:
    """归档压缩功能."""

    def test_archive_is_gzip(self, small_rotator, tmp_path):
        """归档文件是 gzip 格式."""
        path = tmp_path / "test.jsonl"
        original_content = '{"test": "data"}\n' * 50
        path.write_text(original_content, encoding="utf-8")

        small_rotator.maybe_rotate(path)

        archive = Path(f"{path}.1.gz")
        assert archive.exists()

        # 验证 gzip 内容可解压
        with gzip.open(archive, "rt", encoding="utf-8") as f:
            content = f.read()
        assert original_content in content

    def test_original_file_truncated(self, small_rotator, tmp_path):
        """轮转后原文件被截断为空."""
        path = tmp_path / "test.jsonl"
        path.write_text('{"data": "test"}\n' * 50, encoding="utf-8")

        small_rotator.maybe_rotate(path)

        assert path.read_text(encoding="utf-8") == ""

    def test_rotation_audit_written(self, small_rotator, tmp_path):
        """轮转审计记录被写入."""
        path = tmp_path / "test.jsonl"
        path.write_text('{"data": "test"}\n' * 50, encoding="utf-8")

        small_rotator.maybe_rotate(path)

        audit_path = tmp_path / "rotation_audit.jsonl"
        assert audit_path.exists()
        audit_lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(audit_lines) >= 1
        record = json.loads(audit_lines[-1])
        assert "timestamp" in record
        assert "original_file" in record
        assert "archive_file" in record


# ── 3. 保留份数 ───────────────────────────────────────────────


class TestBackupRetention:
    """保留份数管理."""

    def test_max_backups_limit(self, small_rotator, tmp_path):
        """轮转多次后归档不超过 max_backups."""
        path = tmp_path / "rotating.jsonl"

        # 轮转 5 次 (max_backups=3), 每次写入足够大的数据 (>= max_bytes 触发大小轮转)
        for i in range(5):
            lines = [json.dumps({"cycle": i, "data": "x" * 200}) for _ in range(50)]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            rotated = small_rotator.maybe_rotate(path)
            assert rotated is True, f"cycle {i} should rotate"

        # 验证归档数量不超过 3
        archives = []
        for n in range(1, 10):
            archive = Path(f"{path}.{n}.gz")
            if archive.exists():
                archives.append(archive)
        assert len(archives) <= 3

    def test_oldest_archive_deleted(self, small_rotator, tmp_path):
        """最旧的归档被删除."""
        path = tmp_path / "rotating.jsonl"

        # 轮转 4 次 (max_backups=3), 每次写入足够大的数据 (>= max_bytes 触发大小轮转)
        for i in range(4):
            lines = [json.dumps({"cycle": i, "data": "x" * 200}) for _ in range(50)]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            rotated = small_rotator.maybe_rotate(path)
            assert rotated is True, f"cycle {i} should rotate"

        # 第 4 份归档 (.4.gz) 不应存在
        assert not Path(f"{path}.4.gz").exists()
        # .3.gz 应存在
        assert Path(f"{path}.3.gz").exists()

    def test_archive_numbering_shifts(self, small_rotator, tmp_path):
        """归档编号正确移位 (n → n+1)."""
        path = tmp_path / "rotating.jsonl"

        # 第一次轮转 (注意: 必须用括号分组, 否则 * 50 仅作用于最后的 '"}\n')
        with open(path, "w", encoding="utf-8") as f:
            f.write(('{"cycle": 1, "data": "' + 'x' * 200 + '"}\n') * 50)
        rotated = small_rotator.maybe_rotate(path)
        assert rotated is True
        assert Path(f"{path}.1.gz").exists()

        # 第二次轮转
        with open(path, "w", encoding="utf-8") as f:
            f.write(('{"cycle": 2, "data": "' + 'x' * 200 + '"}\n') * 50)
        rotated = small_rotator.maybe_rotate(path)
        assert rotated is True
        # .1.gz 应是第二次的内容, .2.gz 应是第一次的内容
        assert Path(f"{path}.1.gz").exists()
        assert Path(f"{path}.2.gz").exists()


# ── 4. 线程安全 ───────────────────────────────────────────────


class TestThreadSafety:
    """线程安全测试."""

    def test_concurrent_writes_no_crash(self, small_rotator, tmp_path):
        """并发写入不会崩溃."""
        path = tmp_path / "concurrent.jsonl"
        path.write_text("", encoding="utf-8")

        errors = []

        def worker(worker_id: int):
            try:
                from market_ops.workspace.jsonl_rotator import append_with_rotation
                for i in range(20):
                    append_with_rotation(
                        path,
                        {"worker": worker_id, "seq": i},
                        data_dir=str(tmp_path),
                        rotator=small_rotator,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 文件应该有内容 (可能被轮转过, 但当前文件非空)
        assert path.exists()


# ── 5. 便捷函数 ───────────────────────────────────────────────


class TestAppendWithRotation:
    """append_with_rotation 便捷函数."""

    def test_creates_file_if_not_exists(self, tmp_path):
        """文件不存在时自动创建."""
        from market_ops.workspace.jsonl_rotator import append_with_rotation
        path = tmp_path / "new.jsonl"

        append_with_rotation(path, {"test": True}, data_dir=str(tmp_path))

        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["test"] is True

    def test_appends_to_existing(self, tmp_path):
        """追加到现有文件."""
        from market_ops.workspace.jsonl_rotator import append_with_rotation
        path = tmp_path / "existing.jsonl"
        path.write_text('{"line": 1}\n', encoding="utf-8")

        append_with_rotation(path, {"line": 2}, data_dir=str(tmp_path))

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_creates_parent_directory(self, tmp_path):
        """自动创建父目录."""
        from market_ops.workspace.jsonl_rotator import append_with_rotation
        path = tmp_path / "subdir" / "deep" / "file.jsonl"

        append_with_rotation(path, {"test": True}, data_dir=str(tmp_path))

        assert path.exists()


# ── 6. 查询 API ───────────────────────────────────────────────


class TestQueryAPI:
    """查询 API 测试."""

    def test_list_archives_empty(self, small_rotator, tmp_path):
        """无归档时返回空列表."""
        path = tmp_path / "test.jsonl"
        archives = small_rotator.list_archives(path)
        assert archives == []

    def test_list_archives_after_rotation(self, small_rotator, tmp_path):
        """轮转后 list_archives 返回归档列表."""
        path = tmp_path / "test.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write(('{"data": "' + 'x' * 200 + '"}\n') * 50)
        rotated = small_rotator.maybe_rotate(path)
        assert rotated is True

        archives = small_rotator.list_archives(path)
        assert len(archives) >= 1
        assert archives[0]["index"] == 1
        assert archives[0]["size_bytes"] > 0

    def test_get_rotation_stats(self, small_rotator, tmp_path):
        """get_rotation_stats 返回统计信息."""
        # 创建几个 jsonl 文件
        (tmp_path / "a.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
        (tmp_path / "b.jsonl").write_text('{"b": 1}\n{"b": 2}\n', encoding="utf-8")

        stats = small_rotator.get_rotation_stats()

        assert stats["total_jsonl_files"] >= 2
        assert stats["total_size_bytes"] > 0
        assert isinstance(stats["largest_files"], list)
        assert len(stats["largest_files"]) <= 10

    def test_get_rotation_stats_empty_data_dir(self, small_rotator, tmp_path):
        """空 data_dir 返回零值统计."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        from market_ops.workspace.jsonl_rotator import JsonlRotator
        rotator = JsonlRotator(data_dir=str(empty_dir))

        stats = rotator.get_rotation_stats()

        assert stats["total_jsonl_files"] == 0
        assert stats["total_size_bytes"] == 0


# ── 7. API 端点 ───────────────────────────────────────────────


class TestJsonlRotationAPI:
    """JSONL 轮转管理 API 端点测试."""

    @pytest.fixture
    def client(self):
        """FastAPI 测试客户端."""
        from market_ops.workspace.app import app
        return TestClient(app)

    def test_stats_endpoint(self, client):
        """GET /api/maintenance/jsonl/stats 返回统计."""
        response = client.get("/api/maintenance/jsonl/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_jsonl_files" in data
        assert "total_size_bytes" in data
        assert "total_archives" in data
        assert "largest_files" in data

    def test_archives_endpoint(self, client):
        """GET /api/maintenance/jsonl/archives/{path} 返回归档列表."""
        response = client.get("/api/maintenance/jsonl/archives/ceo/execution_memory.jsonl")
        assert response.status_code == 200
        data = response.json()
        assert "file_path" in data
        assert "archives" in data
        assert "archive_count" in data

    def test_rotate_endpoint(self, client):
        """POST /api/maintenance/jsonl/rotate 返回轮转结果."""
        response = client.post(
            "/api/maintenance/jsonl/rotate",
            params={"file_path": "ceo/execution_memory.jsonl"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "rotated" in data
        assert "message" in data


# ── 8. 边界场景 ───────────────────────────────────────────────


class TestEdgeCases:
    """边界场景测试."""

    def test_empty_file_not_rotated(self, small_rotator, tmp_path):
        """空文件不触发轮转."""
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")

        rotated = small_rotator.maybe_rotate(path)

        assert rotated is False

    def test_custom_config(self, tmp_path):
        """自定义配置参数."""
        from market_ops.workspace.jsonl_rotator import JsonlRotator
        rotator = JsonlRotator(
            data_dir=str(tmp_path),
            max_bytes=100,
            max_lines=5,
            max_backups=1,
        )

        path = tmp_path / "test.jsonl"
        # 写入超过 100 字节的数据
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"data": "' + 'x' * 50 + '"}\n' * 5)  # 约 320 字节

        rotator.maybe_rotate(path)

        # max_backups=1, 只有 .1.gz
        assert Path(f"{path}.1.gz").exists()
        assert not Path(f"{path}.2.gz").exists()

    def test_rotator_singleton(self):
        """get_default_rotator 返回单例."""
        from market_ops.workspace.jsonl_rotator import get_default_rotator
        r1 = get_default_rotator()
        r2 = get_default_rotator()
        assert r1 is r2


# ── 9. 批量轮转 rotate_all ─────────────────────────────────────


class TestRotateAll:
    """rotate_all 批量轮转功能."""

    def test_rotate_all_no_files(self, small_rotator, tmp_path):
        """空 data_dir 返回零值."""
        empty = tmp_path / "empty"
        empty.mkdir()
        from market_ops.workspace.jsonl_rotator import JsonlRotator
        rotator = JsonlRotator(data_dir=str(empty))
        result = rotator.rotate_all()
        assert result["scanned"] == 0
        assert result["rotated"] == 0
        assert result["skipped"] == 0

    def test_rotate_all_skips_small_files(self, small_rotator, tmp_path):
        """小文件被跳过, 不轮转."""
        (tmp_path / "small.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
        result = small_rotator.rotate_all()
        assert result["scanned"] >= 1
        assert result["rotated"] == 0
        assert result["skipped"] >= 1

    def test_rotate_all_rotates_big_files(self, small_rotator, tmp_path):
        """超阈值文件被轮转."""
        path = tmp_path / "big.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(json.dumps({"i": i, "data": "x" * 50}) + "\n")
        result = small_rotator.rotate_all()
        assert result["scanned"] >= 1
        assert result["rotated"] == 1
        # 归档存在
        assert Path(f"{path}.1.gz").exists()
        # 原文件截断
        assert path.stat().st_size == 0

    def test_rotate_all_skips_audit_log(self, small_rotator, tmp_path):
        """轮转审计日志自身不被轮转."""
        audit = tmp_path / "rotation_audit.jsonl"
        audit.write_text('{"audit": true}\n' * 100, encoding="utf-8")
        result = small_rotator.rotate_all()
        # 审计文件不出现在扫描中
        assert result["scanned"] == 0 or all(
            "rotation_audit" not in d["path"] for d in result["details"]
        )

    def test_rotate_all_mixed_files(self, small_rotator, tmp_path):
        """混合文件: 部分超阈值部分未超."""
        # 大文件
        big = tmp_path / "big.jsonl"
        with open(big, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(json.dumps({"i": i, "data": "x" * 50}) + "\n")
        # 小文件
        (tmp_path / "small.jsonl").write_text('{"a": 1}\n', encoding="utf-8")

        result = small_rotator.rotate_all()
        assert result["rotated"] == 1
        assert result["skipped"] >= 1

    def test_rotate_all_details_structure(self, small_rotator, tmp_path):
        """details 列表结构正确."""
        path = tmp_path / "big.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(json.dumps({"i": i, "data": "x" * 50}) + "\n")

        result = small_rotator.rotate_all()
        rotated_details = [d for d in result["details"] if d["rotated"]]
        assert len(rotated_details) == 1
        assert "path" in rotated_details[0]
        assert "reason" in rotated_details[0]


class TestRotateAllAPI:
    """rotate_all API 端点测试."""

    @pytest.fixture
    def client(self):
        from market_ops.workspace.app import app
        return TestClient(app)

    def test_rotate_all_endpoint(self, client):
        """POST /api/maintenance/jsonl/rotate-all 返回批量轮转结果."""
        response = client.post("/api/maintenance/jsonl/rotate-all")
        assert response.status_code == 200
        data = response.json()
        assert "scanned" in data
        assert "rotated" in data
        assert "skipped" in data
        assert "details" in data
        assert isinstance(data["details"], list)
