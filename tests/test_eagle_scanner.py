"""EagleScanner — 单元测试。

覆盖:
  - 全量扫描: 递归收集视频/图片文件
  - 增量扫描: 检测新增/变更/删除
  - 元数据提取: filename, path, creative_asset_id, file_hash, file_size, created_at
  - ffprobe 降级: 不可用时返回空值
  - 索引持久化: 写入和加载
  - 统计查询: get_index / get_stats
  - API 端点: 4 个端点集成测试
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.market_ops.creative_mapping_engine import EagleScanner


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _create_video_file(path: Path, content: bytes = b"fake_video_content_12345"):
    """创建测试用视频文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _create_image_file(path: Path, content: bytes = b"fake_image_content"):
    """创建测试用图片文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


# ═══════════════════════════════════════════════════════════════
# EagleScanner 单元测试
# ═══════════════════════════════════════════════════════════════


class TestEagleScannerScanFull:
    """全量扫描测试。"""

    def test_scan_full_with_video_files(self, tmp_path: Path):
        """全量扫描 — 收集视频文件。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")
        _create_video_file(eagle_root / "MW_VIDEO_260721_000456.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["status"] == "ok"
        assert report["total"] == 2
        assert report["video_count"] == 2
        assert report["image_count"] == 0
        assert report["new_count"] == 2
        assert report["elapsed_seconds"] >= 0

    def test_scan_full_with_image_files(self, tmp_path: Path):
        """全量扫描 — 收集图片文件。"""
        eagle_root = tmp_path / "eagle"
        _create_image_file(eagle_root / "MW_IMG_260721_000125.png")
        _create_image_file(eagle_root / "banner.jpg")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["total"] == 2
        assert report["video_count"] == 0
        assert report["image_count"] == 2

    def test_scan_full_mixed_files(self, tmp_path: Path):
        """全量扫描 — 混合视频和图片。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")
        _create_image_file(eagle_root / "MW_IMG_260721_000125.png")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["total"] == 2
        assert report["video_count"] == 1
        assert report["image_count"] == 1

    def test_scan_full_recursive(self, tmp_path: Path):
        """全量扫描 — 递归子目录。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")
        _create_video_file(eagle_root / "subdir" / "MW_VIDEO_260721_000456.mp4")
        _create_image_file(eagle_root / "subdir" / "deep" / "image.png")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["total"] == 3

    def test_scan_full_empty_directory(self, tmp_path: Path):
        """全量扫描 — 空目录。"""
        eagle_root = tmp_path / "eagle"
        eagle_root.mkdir()

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["total"] == 0
        assert report["video_count"] == 0
        assert report["image_count"] == 0

    def test_scan_full_nonexistent_directory(self, tmp_path: Path):
        """全量扫描 — 目录不存在。"""
        scanner = EagleScanner(
            eagle_root=str(tmp_path / "nonexistent"),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["total"] == 0
        assert not scanner.is_available

    def test_scan_full_ignores_non_media_files(self, tmp_path: Path):
        """全量扫描 — 忽略非媒体文件。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")
        (eagle_root / "readme.txt").write_text("not a media file")
        (eagle_root / "config.json").write_text("{}")
        (eagle_root / "script.py").write_text("# script")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_full()

        assert report["total"] == 1


class TestEagleScannerMetadata:
    """元数据提取测试。"""

    def test_extract_creative_id(self, tmp_path: Path):
        """提取 creative_asset_id — MW_VIDEO 格式。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["creative_asset_id"] == "MW_VIDEO_260721_000123"

    def test_extract_creative_id_img_format(self, tmp_path: Path):
        """提取 creative_asset_id — MW_IMG 格式。"""
        eagle_root = tmp_path / "eagle"
        _create_image_file(eagle_root / "MW_IMG_260721_000125.png")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["creative_asset_id"] == "MW_IMG_260721_000125"

    def test_creative_id_empty_for_non_matching_filename(self, tmp_path: Path):
        """无统一编号的文件 → creative_asset_id 为空。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "random_video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["creative_asset_id"] == ""

    def test_file_hash_extracted(self, tmp_path: Path):
        """提取 file_hash。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4", b"unique_content")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["file_hash"] != ""
        assert len(asset["file_hash"]) == 32  # MD5 hexdigest

    def test_file_hash_differs_for_different_content(self, tmp_path: Path):
        """不同内容 → 不同 file_hash。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video1.mp4", b"content_a")
        _create_video_file(eagle_root / "video2.mp4", b"content_b")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        hashes = {a["file_hash"] for a in index["assets"]}
        assert len(hashes) == 2

    def test_file_size_extracted(self, tmp_path: Path):
        """提取 file_size。"""
        eagle_root = tmp_path / "eagle"
        content = b"exactly_20_bytes!!"
        _create_video_file(eagle_root / "video.mp4", content)

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["file_size"] == len(content)

    def test_created_at_extracted(self, tmp_path: Path):
        """提取 created_at (ISO 格式)。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["created_at"] != ""
        assert "T" in asset["created_at"]  # ISO 格式

    def test_path_is_absolute(self, tmp_path: Path):
        """path 为绝对路径。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert Path(asset["path"]).is_absolute()


class TestEagleScannerFfprobe:
    """ffprobe 降级测试。"""

    def test_ffprobe_disabled_returns_empty_metadata(self, tmp_path: Path):
        """extract_metadata=False → duration/resolution 为空。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["duration"] == 0.0
        assert asset["resolution"] == ""

    def test_ffprobe_unavailable_graceful_degradation(self, tmp_path: Path, monkeypatch):
        """ffprobe 不可用时优雅降级。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=True,
        )
        # 模拟 ffprobe 不可用
        monkeypatch.setattr(scanner, "_ffprobe_available", False)
        scanner.scan_full()
        index = scanner.get_index()

        asset = index["assets"][0]
        assert asset["duration"] == 0.0
        assert asset["resolution"] == ""


class TestEagleScannerIncremental:
    """增量扫描测试。"""

    def test_incremental_detects_new_files(self, tmp_path: Path):
        """增量扫描 — 检测新增文件。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video1.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()

        # 新增文件
        _create_video_file(eagle_root / "video2.mp4")
        report = scanner.scan_incremental()

        assert report["new_count"] == 1
        assert report["total"] == 2
        assert report["changed_count"] == 0
        assert report["removed_count"] == 0

    def test_incremental_detects_changed_files(self, tmp_path: Path):
        """增量扫描 — 检测变更文件。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4", b"original_content")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()

        # 修改文件内容
        _create_video_file(eagle_root / "video.mp4", b"modified_content")
        report = scanner.scan_incremental()

        assert report["changed_count"] == 1
        assert report["new_count"] == 0
        assert report["removed_count"] == 0

    def test_incremental_detects_removed_files(self, tmp_path: Path):
        """增量扫描 — 检测删除文件。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video1.mp4")
        _create_video_file(eagle_root / "video2.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()

        # 删除文件
        (eagle_root / "video2.mp4").unlink()
        report = scanner.scan_incremental()

        assert report["removed_count"] == 1
        assert report["total"] == 1
        assert report["new_count"] == 0

    def test_incremental_no_changes(self, tmp_path: Path):
        """增量扫描 — 无变更。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        report = scanner.scan_incremental()

        assert report["new_count"] == 0
        assert report["changed_count"] == 0
        assert report["removed_count"] == 0

    def test_incremental_first_run_treats_all_as_new(self, tmp_path: Path):
        """增量扫描 — 首次运行（无历史索引）全部视为新增。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video1.mp4")
        _create_video_file(eagle_root / "video2.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        report = scanner.scan_incremental()

        assert report["new_count"] == 2
        assert report["total"] == 2


class TestEagleScannerPersistence:
    """索引持久化测试。"""

    def test_index_file_created(self, tmp_path: Path):
        """扫描后生成索引文件。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        index_path = tmp_path / "index.json"
        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(index_path),
            extract_metadata=False,
        )
        scanner.scan_full()

        assert index_path.exists()

    def test_index_file_format(self, tmp_path: Path):
        """索引文件格式正确。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")

        index_path = tmp_path / "index.json"
        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(index_path),
            extract_metadata=False,
        )
        scanner.scan_full()

        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert "scanned_at" in data
        assert "root_dir" in data
        assert "total" in data
        assert "video_count" in data
        assert "image_count" in data
        assert "assets" in data
        assert isinstance(data["assets"], list)
        assert len(data["assets"]) == 1

    def test_scan_log_appended(self, tmp_path: Path):
        """扫描日志追加写入。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        scanner.scan_incremental()

        log_path = tmp_path / "eagle_scan_log.jsonl"
        assert log_path.exists()
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) >= 2

        entries = [json.loads(l) for l in lines]
        assert entries[0]["type"] == "full_scan"
        assert entries[1]["type"] == "incremental_scan"


class TestEagleScannerQuery:
    """索引查询测试。"""

    def test_get_index_empty(self, tmp_path: Path):
        """无索引文件 → 返回空索引。"""
        scanner = EagleScanner(
            eagle_root=str(tmp_path / "eagle"),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        index = scanner.get_index()

        assert index["total"] == 0
        assert index["assets"] == []
        assert index["scanned_at"] == ""

    def test_get_index_after_scan(self, tmp_path: Path):
        """扫描后查询索引。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video.mp4")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        index = scanner.get_index()

        assert index["total"] == 1
        assert len(index["assets"]) == 1
        assert index["scanned_at"] != ""

    def test_get_stats(self, tmp_path: Path):
        """查询统计摘要。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")
        _create_image_file(eagle_root / "MW_IMG_260721_000125.png")

        scanner = EagleScanner(
            eagle_root=str(eagle_root),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        scanner.scan_full()
        stats = scanner.get_stats()

        assert stats["total"] == 2
        assert stats["video_count"] == 1
        assert stats["image_count"] == 1
        assert stats["with_creative_id"] == 2
        assert stats["scanned_at"] != ""

    def test_get_stats_empty(self, tmp_path: Path):
        """无索引 → 统计全为 0。"""
        scanner = EagleScanner(
            eagle_root=str(tmp_path / "eagle"),
            index_path=str(tmp_path / "index.json"),
            extract_metadata=False,
        )
        stats = scanner.get_stats()

        assert stats["total"] == 0
        assert stats["video_count"] == 0
        assert stats["image_count"] == 0


# ═══════════════════════════════════════════════════════════════
# Eagle Scanner API 集成测试
# ═══════════════════════════════════════════════════════════════


class TestEagleScannerAPI:
    """Eagle Scanner API 端点测试。"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path: Path):
        """临时 client。"""
        from fastapi.testclient import TestClient

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        # 重置单例
        if hasattr(app_module._get_creative_mapping_engine, "_instance"):
            monkeypatch.delattr(app_module._get_creative_mapping_engine, "_instance")

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_scan_full_api(self, client: TestClient, tmp_path: Path):
        """POST /eagle/scan — 全量扫描。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")

        response = client.post("/api/creative-mapping/eagle/scan", json={
            "eagle_root": str(eagle_root),
            "extract_metadata": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["total"] == 1
        assert data["video_count"] == 1

    def test_scan_full_missing_eagle_root(self, client: TestClient):
        """POST /eagle/scan — 缺少 eagle_root → 400。"""
        response = client.post("/api/creative-mapping/eagle/scan", json={
            "extract_metadata": False,
        })
        assert response.status_code == 400

    def test_scan_full_nonexistent_root(self, client: TestClient, tmp_path: Path):
        """POST /eagle/scan — 目录不存在 → 404。"""
        response = client.post("/api/creative-mapping/eagle/scan", json={
            "eagle_root": str(tmp_path / "nonexistent"),
            "extract_metadata": False,
        })
        assert response.status_code == 404

    def test_scan_incremental_api(self, client: TestClient, tmp_path: Path):
        """POST /eagle/scan-incremental — 增量扫描。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "video1.mp4")

        # 先全量扫描
        client.post("/api/creative-mapping/eagle/scan", json={
            "eagle_root": str(eagle_root),
            "extract_metadata": False,
        })

        # 新增文件后增量扫描
        _create_video_file(eagle_root / "video2.mp4")
        response = client.post("/api/creative-mapping/eagle/scan-incremental", json={
            "eagle_root": str(eagle_root),
            "extract_metadata": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["new_count"] == 1
        assert data["total"] == 2

    def test_get_index_api(self, client: TestClient, tmp_path: Path):
        """GET /eagle/index — 查询索引。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")

        client.post("/api/creative-mapping/eagle/scan", json={
            "eagle_root": str(eagle_root),
            "extract_metadata": False,
        })

        response = client.get("/api/creative-mapping/eagle/index")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["assets"]) == 1

    def test_get_index_empty_api(self, client: TestClient):
        """GET /eagle/index — 无索引 → 空结果。"""
        response = client.get("/api/creative-mapping/eagle/index")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["assets"] == []

    def test_get_index_stats_api(self, client: TestClient, tmp_path: Path):
        """GET /eagle/index/stats — 查询统计。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")
        _create_image_file(eagle_root / "MW_IMG_260721_000125.png")

        client.post("/api/creative-mapping/eagle/scan", json={
            "eagle_root": str(eagle_root),
            "extract_metadata": False,
        })

        response = client.get("/api/creative-mapping/eagle/index/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["video_count"] == 1
        assert data["image_count"] == 1
        assert data["with_creative_id"] == 2

    def test_scan_then_match_integration(self, client: TestClient, tmp_path: Path):
        """扫描后触发匹配 — 验证引擎缓存刷新。"""
        eagle_root = tmp_path / "eagle"
        _create_video_file(eagle_root / "MW_VIDEO_260721_000123.mp4")

        # 先扫描
        client.post("/api/creative-mapping/eagle/scan", json={
            "eagle_root": str(eagle_root),
            "extract_metadata": False,
        })

        # 再匹配 — 应能找到素材
        response = client.post("/api/creative-mapping/match", json={
            "facebook_creative_id": "fb_scan_test_001",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 0.0,
            "resolution": "",
            "creation_time": "",
            "file_hash": "abc123",
        })
        assert response.status_code == 200
        data = response.json()
        # name_similarity 应为 1.0 (序列号匹配)
        assert data["scores"]["name_similarity"] == 1.0
