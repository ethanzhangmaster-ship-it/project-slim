"""FacebookCreativeIngester — 单元测试 (v1.4)。

覆盖:
  - IngestionResult 数据结构
  - ingest_creatives() dry_run 模式
  - ingest() 真实 API 模式（mock client）
  - 增量过滤（跳过 MATCHED/REVIEW_APPROVED）
  - duration/resolution 补全（_enrich_video_metadata）
  - 错误处理（API 失败、match 异常）
  - _to_match_input 格式转换
  - API 端点（ingest + ingest-dry-run）
  - FacebookCreativeEntity duration/resolution 字段
  - FacebookClient.get_video() fields 扩展
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.market_ops.creative_mapping_engine import (
    CreativeMappingEngine,
    FacebookCreativeIngester,
    IngestionResult,
)
from src.market_ops.creative_mapping_engine.models import MappingStatus


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _create_solid_image(path: Path, color: tuple = (255, 0, 0)):
    """创建纯色图片。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64), color)
    img.save(path)


def _make_engine(tmp_path: Path, eagle_assets: list[dict] | None = None) -> CreativeMappingEngine:
    """创建临时 CreativeMappingEngine。"""
    engine = CreativeMappingEngine(
        data_dir=str(tmp_path / "creative_mapping"),
        eagle_index_path=str(tmp_path / "eagle_scan_index.json"),
    )
    if eagle_assets is not None:
        engine.set_eagle_assets(eagle_assets)
    return engine


def _make_creative(
    creative_id: str = "536123456789",
    name: str = "MW_VIDEO_260721_000123",
    video_id: str = "",
    duration: float = 0.0,
    resolution: str = "",
    thumbnail_url: str = "",
    file_hash: str = "",
) -> dict:
    """构造创意数据。"""
    return {
        "facebook_creative_id": creative_id,
        "facebook_creative_name": name,
        "facebook_account_id": "act_123456",
        "thumbnail_url": thumbnail_url,
        "video_id": video_id,
        "duration": duration,
        "resolution": resolution,
        "creation_time": "2026-07-24T10:00:00+0000",
        "file_hash": file_hash,
    }


def _make_eagle_assets(tmp_path: Path | None = None) -> list[dict]:
    """构造 Eagle 素材索引。tmp_path 用于创建本地图片。"""
    eagle_path = ""
    if tmp_path is not None:
        eagle_img = tmp_path / "eagle_asset.jpg"
        _create_solid_image(eagle_img, color=(255, 0, 0))
        eagle_path = str(eagle_img)
    return [
        {
            "filename": "MW_VIDEO_260721_000123.mp4",
            "path": eagle_path or "D:/eagle/MW_VIDEO_260721_000123.mp4",
            "duration": 32.5,
            "resolution": "1080x1920",
            "file_hash": "abc123",
            "created_at": "2026-07-24T10:30:00Z",
        },
    ]


def _make_mock_facebook_client(
    ads: list[dict] | None = None,
    videos: dict[str, dict] | None = None,
) -> MagicMock:
    """构造 mock FacebookClient。"""
    client = MagicMock()
    client._account_id = "123456"
    client.get_ads.return_value = ads or []
    client.get_video.side_effect = lambda vid: (videos or {}).get(vid)
    return client


# ═══════════════════════════════════════════════════════════════
# IngestionResult 数据结构测试
# ═══════════════════════════════════════════════════════════════


class TestIngestionResult:
    """IngestionResult 数据结构测试。"""

    def test_default_values(self):
        """默认值全为零/空。"""
        result = IngestionResult()
        assert result.total_fetched == 0
        assert result.total_mapped == 0
        assert result.total_skipped == 0
        assert result.total_errors == 0
        assert result.mappings == []
        assert result.elapsed_seconds == 0.0
        assert result.dry_run is False

    def test_to_dict_keys(self):
        """to_dict 包含所有字段。"""
        result = IngestionResult(total_fetched=5, total_mapped=3)
        d = result.to_dict()
        assert "total_fetched" in d
        assert "total_mapped" in d
        assert "total_skipped" in d
        assert "total_errors" in d
        assert "mappings" in d
        assert "elapsed_seconds" in d
        assert "dry_run" in d

    def test_to_dict_elapsed_rounded(self):
        """elapsed_seconds 保留 3 位小数。"""
        result = IngestionResult(elapsed_seconds=1.23456789)
        assert result.to_dict()["elapsed_seconds"] == 1.235

    def test_dry_run_flag(self):
        """dry_run 标志传递。"""
        result = IngestionResult(dry_run=True)
        assert result.dry_run is True
        assert result.to_dict()["dry_run"] is True


# ═══════════════════════════════════════════════════════════════
# ingest_creatives() dry_run 模式测试
# ═══════════════════════════════════════════════════════════════


class TestIngestCreativesDryRun:
    """ingest_creatives() dry_run 模式测试。"""

    def test_empty_creatives(self, tmp_path: Path):
        """空列表 → total_fetched=0。"""
        engine = _make_engine(tmp_path)
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        result = ingester.ingest_creatives([])
        assert result.total_fetched == 0
        assert result.total_mapped == 0
        assert result.dry_run is True

    def test_single_creative_maps_successfully(self, tmp_path: Path):
        """单条创意 → 自动映射成功。"""
        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets())
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        creative = _make_creative(
            name="MW_VIDEO_260721_000123",
            duration=32.5,
            resolution="1080x1920",
        )
        result = ingester.ingest_creatives([creative])
        assert result.total_fetched == 1
        assert result.total_mapped == 1
        assert result.total_errors == 0
        assert len(result.mappings) == 1
        assert result.dry_run is True

    def test_auto_map_false_skips_mapping(self, tmp_path: Path):
        """auto_map=False → 不映射，只统计 fetched。"""
        engine = _make_engine(tmp_path)
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        result = ingester.ingest_creatives([_make_creative()], auto_map=False)
        assert result.total_fetched == 1
        assert result.total_mapped == 0
        assert result.mappings == []

    def test_no_eagle_assets_returns_no_match(self, tmp_path: Path):
        """Eagle 索引为空 → 映射结果为 NO_MATCH。"""
        engine = _make_engine(tmp_path, eagle_assets=[])
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        result = ingester.ingest_creatives([_make_creative()])
        assert result.total_mapped == 1
        assert result.mappings[0]["status"] == "no_match"

    def test_elapsed_seconds_positive(self, tmp_path: Path):
        """elapsed_seconds > 0。"""
        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets())
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        result = ingester.ingest_creatives([_make_creative()])
        assert result.elapsed_seconds >= 0.0


# ═══════════════════════════════════════════════════════════════
# 增量过滤测试
# ═══════════════════════════════════════════════════════════════


class TestIncrementalSkip:
    """增量过滤测试。"""

    def test_skip_matched(self, tmp_path: Path):
        """已有 MATCHED 记录 → 跳过。"""
        # 创建本地 thumbnail 图片（与 eagle 相同颜色 → frame_similarity 高分）
        thumb_path = tmp_path / "thumb.jpg"
        _create_solid_image(thumb_path, color=(255, 0, 0))

        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets(tmp_path))
        creative = _make_creative(
            name="MW_VIDEO_260721_000123",
            duration=32.5,
            resolution="1080x1920",
            file_hash="abc123",
            thumbnail_url=str(thumb_path),
        )

        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        # 第一次映射 → MATCHED
        result1 = ingester.ingest_creatives([creative])
        assert result1.total_mapped == 1
        assert result1.mappings[0]["status"] == "matched"

        # 第二次 → 跳过
        result2 = ingester.ingest_creatives([creative])
        assert result2.total_skipped == 1
        assert result2.total_mapped == 0

    def test_skip_review_approved(self, tmp_path: Path):
        """已有 REVIEW_APPROVED 记录 → 跳过。"""
        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets())
        creative = _make_creative(name="MW_VIDEO_260721_000123")

        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        # 第一次映射
        result1 = ingester.ingest_creatives([creative])
        assert result1.total_mapped == 1

        # 手动审核通过
        records = engine.list_records()
        if records:
            mapping_id = records[0].mapping_id
            review_tasks = engine.list_review_queue()
            # 直接通过 store 修改状态
            record = engine.get_record(mapping_id)
            if record:
                record.status = MappingStatus.REVIEW_APPROVED
                engine._store.save_record(record)

        # 第二次 → 跳过
        result2 = ingester.ingest_creatives([creative])
        assert result2.total_skipped == 1

    def test_remap_needs_review(self, tmp_path: Path):
        """已有 NEEDS_REVIEW 记录 → 重新映射。"""
        engine = _make_engine(tmp_path, eagle_assets=[])
        creative = _make_creative()

        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        # 第一次 → NO_MATCH（无 Eagle 素材）
        result1 = ingester.ingest_creatives([creative])
        assert result1.total_mapped == 1
        assert result1.mappings[0]["status"] == "no_match"

        # 第二次 → 重新映射（不跳过）
        result2 = ingester.ingest_creatives([creative])
        assert result2.total_skipped == 0
        assert result2.total_mapped == 1

    def test_mixed_skipped_and_new(self, tmp_path: Path):
        """混合：1 条已映射 + 1 条新创意。"""
        # 创建本地 thumbnail 图片（与 eagle 相同颜色 → frame_similarity 高分）
        thumb_path = tmp_path / "thumb.jpg"
        _create_solid_image(thumb_path, color=(255, 0, 0))

        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets(tmp_path))
        creative1 = _make_creative(
            creative_id="536111",
            name="MW_VIDEO_260721_000123",
            duration=32.5,
            resolution="1080x1920",
            file_hash="abc123",
            thumbnail_url=str(thumb_path),
        )
        creative2 = _make_creative(
            creative_id="536222", name="MW_VIDEO_260721_000456",
        )

        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        # 先映射 creative1
        ingester.ingest_creatives([creative1])

        # 混合：creative1（跳过）+ creative2（新）
        result = ingester.ingest_creatives([creative1, creative2])
        assert result.total_skipped == 1
        assert result.total_mapped == 1


# ═══════════════════════════════════════════════════════════════
# ingest() 真实 API 模式测试（mock client）
# ═══════════════════════════════════════════════════════════════


class TestIngestWithMockClient:
    """ingest() 使用 mock FacebookClient 测试。"""

    def test_no_client_returns_error(self, tmp_path: Path):
        """无 client → total_errors=1。"""
        engine = _make_engine(tmp_path)
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=None)
        result = ingester.ingest()
        assert result.total_errors == 1
        assert result.total_fetched == 0

    def test_successful_ingest(self, tmp_path: Path):
        """成功拉取 + 映射。"""
        # 创建本地 thumbnail 图片（与 eagle 相同颜色 → frame_similarity 高分）
        thumb_path = tmp_path / "thumb.jpg"
        _create_solid_image(thumb_path, color=(255, 0, 0))

        ads = [
            {
                "id": "ad_001",
                "name": "MW_VIDEO_260721_000123",
                "creative": {
                    "id": "536123456789",
                    "name": "MW_VIDEO_260721_000123",
                    "thumbnail_url": str(thumb_path),
                    "video_id": "vid_001",
                },
                "created_time": "2026-07-24T10:00:00+0000",
            },
        ]
        videos = {
            "vid_001": {"id": "vid_001", "length": 32.5, "width": 1080, "height": 1920},
        }
        client = _make_mock_facebook_client(ads=ads, videos=videos)
        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets(tmp_path))
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        result = ingester.ingest(ad_account_id="act_123456")
        assert result.total_fetched == 1
        assert result.total_mapped == 1
        assert result.total_errors == 0
        assert result.mappings[0]["status"] == "matched"

    def test_video_enrichment(self, tmp_path: Path):
        """视频元数据补全：duration 和 resolution。"""
        ads = [
            {
                "id": "ad_001",
                "name": "test",
                "creative": {
                    "id": "536001",
                    "name": "test",
                    "thumbnail_url": "",
                    "video_id": "vid_001",
                },
                "created_time": "",
            },
        ]
        videos = {
            "vid_001": {"length": 45.0, "width": 720, "height": 1280},
        }
        client = _make_mock_facebook_client(ads=ads, videos=videos)
        engine = _make_engine(tmp_path, eagle_assets=[])
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        creatives = ingester._fetch_and_enrich("", 7)
        assert len(creatives) == 1
        assert creatives[0]["duration"] == 45.0
        assert creatives[0]["resolution"] == "720x1280"

    def test_video_enrichment_no_video_id(self, tmp_path: Path):
        """IMAGE 类型（无 video_id）→ duration=0.0, resolution=''。"""
        ads = [
            {
                "id": "ad_001",
                "name": "test",
                "creative": {
                    "id": "536002",
                    "name": "test",
                    "thumbnail_url": "https://thumb.jpg",
                    "video_id": "",
                },
                "created_time": "",
            },
        ]
        client = _make_mock_facebook_client(ads=ads)
        engine = _make_engine(tmp_path, eagle_assets=[])
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        creatives = ingester._fetch_and_enrich("", 7)
        assert len(creatives) == 1
        assert creatives[0]["duration"] == 0.0
        assert creatives[0]["resolution"] == ""

    def test_video_enrichment_failure_graceful(self, tmp_path: Path):
        """get_video() 失败 → 降级为空值，不中断。"""
        ads = [
            {
                "id": "ad_001",
                "name": "test",
                "creative": {
                    "id": "536003",
                    "name": "test",
                    "thumbnail_url": "",
                    "video_id": "vid_bad",
                },
                "created_time": "",
            },
        ]
        client = _make_mock_facebook_client(ads=ads)
        client.get_video.side_effect = RuntimeError("API error")
        engine = _make_engine(tmp_path, eagle_assets=[])
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        creatives = ingester._fetch_and_enrich("", 7)
        assert len(creatives) == 1
        assert creatives[0]["duration"] == 0.0
        assert creatives[0]["resolution"] == ""

    def test_api_failure_returns_error(self, tmp_path: Path):
        """get_ads() 抛出异常 → total_errors=1。"""
        client = _make_mock_facebook_client()
        client.get_ads.side_effect = RuntimeError("API unreachable")
        engine = _make_engine(tmp_path)
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        result = ingester.ingest()
        assert result.total_errors == 1
        assert result.total_fetched == 0

    def test_ad_without_creative_skipped(self, tmp_path: Path):
        """无 creative 字段的广告 → 跳过。"""
        ads = [
            {"id": "ad_001", "name": "no_creative"},
            {
                "id": "ad_002",
                "name": "with_creative",
                "creative": {"id": "536004", "name": "test"},
                "created_time": "",
            },
        ]
        client = _make_mock_facebook_client(ads=ads)
        engine = _make_engine(tmp_path, eagle_assets=[])
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        creatives = ingester._fetch_and_enrich("", 7)
        assert len(creatives) == 1  # 只有一条有效创意
        assert creatives[0]["facebook_creative_id"] == "536004"

    def test_account_id_from_client(self, tmp_path: Path):
        """ad_account_id 为空时从 client 获取。"""
        ads = [
            {
                "id": "ad_001",
                "name": "test",
                "creative": {"id": "536005", "name": "test"},
                "created_time": "",
            },
        ]
        client = _make_mock_facebook_client(ads=ads)
        engine = _make_engine(tmp_path, eagle_assets=[])
        ingester = FacebookCreativeIngester(engine=engine, facebook_client=client)

        creatives = ingester._fetch_and_enrich("", 7)
        assert creatives[0]["facebook_account_id"] == "act_123456"


# ═══════════════════════════════════════════════════════════════
# _to_match_input 格式转换测试
# ═══════════════════════════════════════════════════════════════


class TestToMatchInput:
    """_to_match_input 格式转换测试。"""

    def test_all_fields_present(self):
        """所有字段正确映射。"""
        creative = _make_creative(
            creative_id="123",
            name="test_creative",
            duration=30.0,
            resolution="1080x1920",
            thumbnail_url="https://thumb.jpg",
        )
        match_input = FacebookCreativeIngester._to_match_input(creative)
        assert match_input["facebook_creative_id"] == "123"
        assert match_input["facebook_creative_name"] == "test_creative"
        assert match_input["duration"] == 30.0
        assert match_input["resolution"] == "1080x1920"
        assert match_input["thumbnail_url"] == "https://thumb.jpg"

    def test_missing_fields_default(self):
        """缺失字段 → 默认值。"""
        match_input = FacebookCreativeIngester._to_match_input({})
        assert match_input["facebook_creative_id"] == ""
        assert match_input["duration"] == 0.0
        assert match_input["resolution"] == ""


# ═══════════════════════════════════════════════════════════════
# 错误处理测试
# ═══════════════════════════════════════════════════════════════


class TestErrorHandling:
    """错误处理测试。"""

    def test_empty_creative_id_counts_as_error(self, tmp_path: Path):
        """creative_id 为空 → total_errors += 1。"""
        engine = _make_engine(tmp_path)
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)
        result = ingester.ingest_creatives([{"facebook_creative_id": ""}])
        assert result.total_errors == 1
        assert result.total_mapped == 0

    def test_match_exception_counts_as_error(self, tmp_path: Path):
        """match() 抛出异常 → total_errors += 1。"""
        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets())
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)

        with patch.object(engine, "match", side_effect=RuntimeError("match error")):
            result = ingester.ingest_creatives([_make_creative()])
        assert result.total_errors == 1
        assert result.total_mapped == 0

    def test_partial_failure_continues(self, tmp_path: Path):
        """部分失败不中断后续处理。"""
        engine = _make_engine(tmp_path, eagle_assets=_make_eagle_assets())
        ingester = FacebookCreativeIngester(engine=engine, dry_run=True)

        call_count = {"n": 0}
        original_match = engine.match

        def mock_match(data):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("first fails")
            return original_match(data)

        with patch.object(engine, "match", side_effect=mock_match):
            result = ingester.ingest_creatives([
                _make_creative(creative_id="536_fail"),
                _make_creative(creative_id="536_ok", name="MW_VIDEO_260721_000123"),
            ])
        assert result.total_errors == 1
        assert result.total_mapped == 1


# ═══════════════════════════════════════════════════════════════
# FacebookCreativeEntity duration/resolution 字段测试
# ═══════════════════════════════════════════════════════════════


class TestFacebookCreativeEntityFields:
    """FacebookCreativeEntity duration/resolution 字段测试。"""

    def test_default_duration_zero(self):
        """默认 duration=0.0。"""
        from src.market_ops.facebook_ingestion.models import (
            FacebookCreativeEntity,
        )
        entity = FacebookCreativeEntity()
        assert entity.duration == 0.0
        assert entity.resolution == ""

    def test_duration_in_to_dict(self):
        """to_dict 包含 duration 和 resolution。"""
        from src.market_ops.facebook_ingestion.models import (
            FacebookCreativeEntity,
        )
        entity = FacebookCreativeEntity(duration=32.5, resolution="1080x1920")
        d = entity.to_dict()
        assert d["duration"] == 32.5
        assert d["resolution"] == "1080x1920"

    def test_duration_from_dict(self):
        """from_dict 正确解析 duration 和 resolution。"""
        from src.market_ops.facebook_ingestion.models import (
            FacebookCreativeEntity,
        )
        data = {
            "creative_id": "123",
            "duration": 45.0,
            "resolution": "720x1280",
        }
        entity = FacebookCreativeEntity.from_dict(data)
        assert entity.duration == 45.0
        assert entity.resolution == "720x1280"

    def test_duration_in_to_facebook_json(self):
        """to_facebook_json 包含 duration 和 resolution。"""
        from src.market_ops.facebook_ingestion.models import (
            FacebookCreativeEntity,
        )
        entity = FacebookCreativeEntity(duration=15.0, resolution="1920x1080")
        d = entity.to_facebook_json()
        assert d["duration"] == 15.0
        assert d["resolution"] == "1920x1080"

    def test_roundtrip_dict(self):
        """to_dict → from_dict 往返保持一致。"""
        from src.market_ops.facebook_ingestion.models import (
            FacebookCreativeEntity,
        )
        entity = FacebookCreativeEntity(
            creative_id="123",
            duration=42.0,
            resolution="1080x1920",
        )
        data = entity.to_dict()
        restored = FacebookCreativeEntity.from_dict(data)
        assert restored.duration == 42.0
        assert restored.resolution == "1080x1920"


# ═══════════════════════════════════════════════════════════════
# FacebookClient.get_video() fields 扩展测试
# ═══════════════════════════════════════════════════════════════


class TestFacebookClientVideoFields:
    """FacebookClient.get_video() fields 扩展测试。"""

    def test_get_video_fields_include_width_height(self):
        """get_video() 的 fields 参数包含 width,height。"""
        import inspect

        from src.market_ops.facebook_ingestion.facebook_client import (
            FacebookClient,
        )
        source = inspect.getsource(FacebookClient.get_video)
        assert "width" in source
        assert "height" in source


# ═══════════════════════════════════════════════════════════════
# API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestFacebookIngestAPI:
    """Facebook 创意映射 API 端点测试。"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path: Path):
        """临时 client。"""
        from fastapi.testclient import TestClient

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        if hasattr(app_module._get_creative_mapping_engine, "_instance"):
            monkeypatch.delattr(app_module._get_creative_mapping_engine, "_instance")

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_ingest_dry_run_success(self, client: TestClient, tmp_path: Path):
        """POST /facebook/ingest-dry-run — 成功映射。"""
        # 先写入 Eagle 索引
        eagle_index = tmp_path / "data" / "eagle_scan_index.json"
        eagle_index.parent.mkdir(parents=True, exist_ok=True)
        eagle_index.write_text(json.dumps({
            "assets": _make_eagle_assets(),
        }), encoding="utf-8")

        response = client.post(
            "/api/creative-mapping/facebook/ingest-dry-run",
            json={
                "creatives": [
                    _make_creative(name="MW_VIDEO_260721_000123"),
                ],
                "auto_map": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_fetched"] == 1
        assert data["total_mapped"] == 1
        assert data["dry_run"] is True
        assert len(data["mappings"]) == 1

    def test_ingest_dry_run_missing_creatives(self, client: TestClient):
        """POST /facebook/ingest-dry-run — 缺少 creatives → 400。"""
        response = client.post(
            "/api/creative-mapping/facebook/ingest-dry-run",
            json={},
        )
        assert response.status_code == 400

    def test_ingest_dry_run_empty_list(self, client: TestClient):
        """POST /facebook/ingest-dry-run — 空列表 → 400。"""
        response = client.post(
            "/api/creative-mapping/facebook/ingest-dry-run",
            json={"creatives": []},
        )
        assert response.status_code == 400

    def test_ingest_dry_run_auto_map_false(self, client: TestClient):
        """POST /facebook/ingest-dry-run — auto_map=False → 不映射。"""
        response = client.post(
            "/api/creative-mapping/facebook/ingest-dry-run",
            json={
                "creatives": [_make_creative()],
                "auto_map": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_fetched"] == 1
        assert data["total_mapped"] == 0
        assert data["mappings"] == []

    def test_ingest_no_credentials_returns_503(self, client: TestClient, monkeypatch):
        """POST /facebook/ingest — 无凭据 → 503。"""
        monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("FB_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
        monkeypatch.delenv("FACEBOOK_AD_ACCOUNT_ID", raising=False)

        response = client.post(
            "/api/creative-mapping/facebook/ingest",
            json={"ad_account_id": "", "lookback_days": 7},
        )
        assert response.status_code == 503

    def test_ingest_dry_run_elapsed_seconds(self, client: TestClient, tmp_path: Path):
        """POST /facebook/ingest-dry-run — elapsed_seconds 为数值。"""
        eagle_index = tmp_path / "data" / "eagle_scan_index.json"
        eagle_index.parent.mkdir(parents=True, exist_ok=True)
        eagle_index.write_text(json.dumps({"assets": _make_eagle_assets()}), encoding="utf-8")

        response = client.post(
            "/api/creative-mapping/facebook/ingest-dry-run",
            json={"creatives": [_make_creative(name="MW_VIDEO_260721_000123")]},
        )
        data = response.json()
        assert isinstance(data["elapsed_seconds"], (int, float))
        assert data["elapsed_seconds"] >= 0
