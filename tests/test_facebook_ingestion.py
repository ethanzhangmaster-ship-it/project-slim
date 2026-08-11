"""E11 Phase 1 — Facebook Ingestion Tests (Phase 1.5 升级)。

17 tests:
  Test 1: API Mock → CreativeEntity 生成 (新格式 ID)
  Test 2: 图片素材 → creative_type=image, image_url 存在
  Test 3: 视频素材 → creative_type=video, video_id 存在
  Test 4: 编号解析 → 新格式 MW_IMG_260701_000123 + legacy 兼容
  Test 5: 重复同步 → 第一次新增，第二次更新
  Tests 6-17: 序列化、存储、类型分布等
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from market_ops.facebook_ingestion import (
    FacebookCreativeEntity,
    CreativeType,
    FacebookClient,
    CreativeFetcher,
    AdParser,
    CreativeStorage,
    SyncEngine,
    SyncResult,
    DataQualityValidator,
)


# ═══════════════════════════════════════════════════════════
# Mock Data
# ═══════════════════════════════════════════════════════════

MOCK_IMAGE_AD = {
    "id": "ad_001",
    "name": "witch_image_000001",
    "status": "ACTIVE",
    "created_time": "2026-07-01T00:00:00+0000",
    "updated_time": "2026-07-20T00:00:00+0000",
    "campaign_id": "camp_001",
    "campaign": {"id": "camp_001", "name": "Campaign A"},
    "adset_id": "adset_001",
    "adset": {"id": "adset_001", "name": "Adset A"},
    "creative": {
        "id": "cr_001",
        "image_url": "https://fb.com/image_001.jpg",
        "thumbnail_url": "https://fb.com/thumb_001.jpg",
        "body": "Play now!",
        "title": "Merge Witches",
        "call_to_action_type": "INSTALL_MOBILE_APP",
    },
}

MOCK_VIDEO_AD = {
    "id": "ad_002",
    "name": "dragon_video_000002",
    "status": "ACTIVE",
    "created_time": "2026-07-02T00:00:00+0000",
    "updated_time": "2026-07-21T00:00:00+0000",
    "campaign_id": "camp_002",
    "campaign": {"id": "camp_002", "name": "Campaign B"},
    "adset_id": "adset_002",
    "adset": {"id": "adset_002", "name": "Adset B"},
    "creative": {
        "id": "cr_002",
        "video_id": "vid_123456",
        "thumbnail_url": "https://fb.com/thumb_002.jpg",
        "body": "Rescue the dragon!",
        "title": "Merge Dragons",
        "call_to_action_type": "INSTALL_MOBILE_APP",
    },
}

MOCK_INSIGHTS_IMAGE = {
    "ad_id": "ad_001",
    "ad_name": "witch_image_000001",
    "campaign_id": "camp_001",
    "campaign_name": "Campaign A",
    "adset_id": "adset_001",
    "adset_name": "Adset A",
    "spend": "150.50",
    "impressions": "5000",
    "clicks": "300",
    "ctr": "6.0",
    "cpc": "0.50",
    "cpm": "30.10",
    "actions": [
        {"action_type": "app_custom_event.fb_mobile_app_install", "value": "50"},
    ],
    "date_start": "2026-07-01",
    "date_stop": "2026-07-20",
}

MOCK_INSIGHTS_VIDEO = {
    "ad_id": "ad_002",
    "ad_name": "dragon_video_000002",
    "campaign_id": "camp_002",
    "campaign_name": "Campaign B",
    "adset_id": "adset_002",
    "adset_name": "Adset B",
    "spend": "5000.00",
    "impressions": "120000",
    "clicks": "8000",
    "ctr": "6.67",
    "cpc": "0.625",
    "cpm": "41.67",
    "actions": [
        {"action_type": "app_custom_event.fb_mobile_app_install", "value": "1200"},
    ],
    "date_start": "2026-07-02",
    "date_stop": "2026-07-21",
}

MOCK_ADS_LIST = [MOCK_IMAGE_AD, MOCK_VIDEO_AD]
MOCK_INSIGHTS_LIST = [MOCK_INSIGHTS_IMAGE, MOCK_INSIGHTS_VIDEO]


# ═══════════════════════════════════════════════════════════
# Test 1 — API Mock → CreativeEntity 生成 (新格式 ID)
# ═══════════════════════════════════════════════════════════

def test1_api_mock_success():
    """Test 1: Mock Facebook API → 生成 CreativeEntity (新格式 ID)。"""
    client = FacebookClient(access_token="test_token", ad_account_id="act_123")

    with patch.object(client, "get_ads", return_value=MOCK_ADS_LIST):
        with patch.object(client, "get_insights", return_value=MOCK_INSIGHTS_LIST):
            fetcher = CreativeFetcher(client)
            parser = AdParser(product="MW")

            entities = fetcher.fetch_all(date(2026, 7, 1), date(2026, 7, 21))
            entities = parser.parse_batch(entities)

            assert len(entities) == 2

            # Image entity — 新格式 ID
            img = entities[0]
            assert img.creative_asset_id == "MW_IMG_260701_000001"
            assert img.legacy_id == "000001"
            assert img.creative_type == CreativeType.IMAGE
            assert img.ad_name == "witch_image_000001"
            assert img.spend == 150.50
            assert img.impressions == 5000

            # Video entity — 新格式 ID
            vid = entities[1]
            assert vid.creative_asset_id == "MW_VID_260702_000002"
            assert vid.legacy_id == "000002"
            assert vid.creative_type == CreativeType.VIDEO
            assert vid.ad_name == "dragon_video_000002"
            assert vid.spend == 5000.00
            assert vid.impressions == 120000


# ═══════════════════════════════════════════════════════════
# Test 2 — 图片素材
# ═══════════════════════════════════════════════════════════

def test2_image_creative():
    """Test 2: 图片素材 → creative_type=image, image_url 存在。"""
    client = FacebookClient(access_token="test_token", ad_account_id="act_123")

    with patch.object(client, "get_ads", return_value=[MOCK_IMAGE_AD]):
        with patch.object(client, "get_insights", return_value=[MOCK_INSIGHTS_IMAGE]):
            fetcher = CreativeFetcher(client)
            parser = AdParser(product="MW")

            entities = fetcher.fetch_all(date(2026, 7, 1), date(2026, 7, 21))
            entities = parser.parse_batch(entities)

            assert len(entities) == 1
            entity = entities[0]

            assert entity.creative_type == CreativeType.IMAGE
            assert entity.is_image
            assert not entity.is_video
            assert entity.image_url == "https://fb.com/image_001.jpg"
            assert entity.thumbnail_url == "https://fb.com/thumb_001.jpg"
            assert entity.video_id == ""
            assert entity.has_asset_id
            assert entity.has_performance
            assert entity.creative_asset_id.startswith("MW_IMG_")
            assert entity.legacy_id == "000001"


# ═══════════════════════════════════════════════════════════
# Test 3 — 视频素材
# ═══════════════════════════════════════════════════════════

def test3_video_creative():
    """Test 3: 视频素材 → creative_type=video, video_id 存在。"""
    client = FacebookClient(access_token="test_token", ad_account_id="act_123")

    with patch.object(client, "get_ads", return_value=[MOCK_VIDEO_AD]):
        with patch.object(client, "get_insights", return_value=[MOCK_INSIGHTS_VIDEO]):
            fetcher = CreativeFetcher(client)
            parser = AdParser(product="MW")

            entities = fetcher.fetch_all(date(2026, 7, 2), date(2026, 7, 21))
            entities = parser.parse_batch(entities)

            assert len(entities) == 1
            entity = entities[0]

            assert entity.creative_type == CreativeType.VIDEO
            assert entity.is_video
            assert not entity.is_image
            assert entity.video_id == "vid_123456"
            assert entity.thumbnail_url == "https://fb.com/thumb_002.jpg"
            assert entity.image_url == ""
            assert entity.has_asset_id
            assert entity.has_performance
            assert entity.installs == 1200
            assert entity.creative_asset_id.startswith("MW_VID_")
            assert entity.legacy_id == "000002"


# ═══════════════════════════════════════════════════════════
# Test 4 — 编号解析 (新格式)
# ═══════════════════════════════════════════════════════════

def test4_asset_id_parsing():
    """Test 4: 新格式 ID 生成 + legacy 兼容。"""
    parser = AdParser(product="MW")

    # 标准 6 位数字 → 新格式
    entity = FacebookCreativeEntity(
        ad_name="dragon_video_000123",
        creative_id="cr_123",
        creative_type=CreativeType.VIDEO,
        created_time="2026-07-21T00:00:00+0000",
    )
    parsed = parser.parse(entity)
    assert parsed.creative_asset_id == "MW_VID_260721_000123"
    assert parsed.legacy_id == "000123"

    # 图片类型
    entity2 = FacebookCreativeEntity(
        ad_name="witch_image_000456",
        creative_id="cr_456",
        creative_type=CreativeType.IMAGE,
        created_time="2026-07-01T00:00:00+0000",
    )
    parsed2 = parser.parse(entity2)
    assert parsed2.creative_asset_id == "MW_IMG_260701_000456"
    assert parsed2.legacy_id == "000456"

    # 提取 legacy_id
    assert parser.extract_legacy_id("merge_hook_999999") == "999999"
    assert parser.extract_legacy_id("my_ad_000001_something") == "000001"

    # 无编号 → fallback
    assert parser.extract_legacy_id("no_number_here", creative_id="cr_999") == "FB_cr_999"
    assert parser.extract_legacy_id("") == ""
    assert parser.extract_legacy_id("no_id", creative_id="") == ""

    # get_legacy_id_from_name
    assert parser.get_legacy_id_from_name("ad_000789") == "000789"
    assert parser.get_legacy_id_from_name("no_number") is None


def test4b_fallback_asset_id():
    """Test 4b: 无编号时 fallback 到 FB_{creative_id}，新格式仍生成。"""
    parser = AdParser(product="MW")

    entity = FacebookCreativeEntity(
        ad_name="no_number_here",
        creative_id="cr_888",
        creative_type=CreativeType.IMAGE,
    )
    parsed = parser.parse(entity)
    assert parsed.legacy_id == "FB_cr_888"
    assert "FB_cr_888" in parsed.creative_asset_id
    assert parsed.creative_asset_id.startswith("MW_IMG_")


# ═══════════════════════════════════════════════════════════
# Test 5 — 重复同步 (新格式 ID)
# ═══════════════════════════════════════════════════════════

def test5_deduplication():
    """Test 5: 重复同步 → 第一次新增，第二次更新，不重复创建。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        # 第一次同步
        entity = FacebookCreativeEntity(
            creative_asset_id="",
            creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            ad_name="test_000001",
            ad_id="ad_001",
            spend=100.0,
            impressions=1000,
            created_time="2026-07-01T00:00:00+0000",
        )
        entity = parser.parse(entity)
        asset_id = entity.creative_asset_id  # 新格式 ID
        stats1 = storage.save_batch([entity])
        assert stats1["created"] == 1
        assert stats1["updated"] == 0
        assert storage.count() == 1

        # 第二次同步（同一素材，spend 更新）
        entity2 = FacebookCreativeEntity(
            creative_asset_id="",
            creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            ad_name="test_000001",
            ad_id="ad_001",
            spend=200.0,
            impressions=2000,
            created_time="2026-07-01T00:00:00+0000",
        )
        entity2 = parser.parse(entity2)
        # 同一个 legacy_id → 同一个新格式 ID
        assert entity2.creative_asset_id == asset_id
        stats2 = storage.save_batch([entity2])
        assert stats2["created"] == 0
        assert stats2["updated"] == 1
        assert storage.count() == 1

        # 验证数据已更新
        loaded = storage.load(asset_id)
        assert loaded is not None
        assert loaded.spend == 200.0
        assert loaded.impressions == 2000

        # 验证 entity.json 也存在
        ce = storage.load_entity(asset_id)
        assert ce is not None
        assert ce.performance.acquisition.spend == 200.0


# ═══════════════════════════════════════════════════════════
# Additional Tests — Serialization & Storage
# ═══════════════════════════════════════════════════════════

def test_entity_serialization_roundtrip():
    """FacebookCreativeEntity 序列化往返（含 legacy_id）。"""
    entity = FacebookCreativeEntity(
        creative_asset_id="MW_VID_260701_000001",
        legacy_id="000001",
        creative_type=CreativeType.VIDEO,
        creative_id="cr_001",
        ad_name="test_000001",
        spend=100.0,
        impressions=1000,
        clicks=50,
        ctr=5.0,
        cpc=2.0,
        cpm=100.0,
        installs=10,
    )
    restored = FacebookCreativeEntity.from_dict(entity.to_dict())
    assert restored.creative_asset_id == entity.creative_asset_id
    assert restored.legacy_id == entity.legacy_id
    assert restored.creative_type == entity.creative_type
    assert restored.spend == entity.spend
    assert restored.impressions == entity.impressions
    assert restored.installs == entity.installs


def test_entity_to_facebook_json():
    """to_facebook_json 导出兼容格式（含 legacy_id）。"""
    entity = FacebookCreativeEntity(
        creative_asset_id="MW_IMG_260701_000001",
        legacy_id="000001",
        creative_type=CreativeType.IMAGE,
        creative_id="cr_001",
        image_url="https://fb.com/img.jpg",
        spend=150.0,
    )
    fb_json = entity.to_facebook_json()
    assert fb_json["creative_asset_id"] == "MW_IMG_260701_000001"
    assert fb_json["legacy_id"] == "000001"
    assert fb_json["creative_type"] == "image"
    assert fb_json["image_url"] == "https://fb.com/img.jpg"
    assert fb_json["spend"] == 150.0


def test_storage_list_by_type():
    """按类型列出 Entity。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        image_entity = FacebookCreativeEntity(
            ad_name="img_000001",
            creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            ad_id="ad_001",
            created_time="2026-07-01T00:00:00+0000",
        )
        video_entity = FacebookCreativeEntity(
            ad_name="vid_000002",
            creative_id="cr_002",
            creative_type=CreativeType.VIDEO,
            ad_id="ad_002",
            created_time="2026-07-01T00:00:00+0000",
        )
        storage.save(parser.parse(image_entity))
        storage.save(parser.parse(video_entity))

        images = storage.list_by_type("image")
        videos = storage.list_by_type("video")
        assert len(images) == 1
        assert len(videos) == 1


def test_storage_exists():
    """exists 检查。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")
        assert not storage.exists("MW_IMG_000001")

        entity = FacebookCreativeEntity(
            ad_name="test_000001",
            creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            ad_id="ad_001",
            created_time="2026-07-01T00:00:00+0000",
        )
        parsed = parser.parse(entity)
        storage.save(parsed)
        assert storage.exists(parsed.creative_asset_id)


def test_storage_metadata():
    """metadata.json 正确生成和更新（含 legacy_id + has_entity）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        entity = FacebookCreativeEntity(
            ad_name="test_000001",
            creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            ad_id="ad_001",
            created_time="2026-07-01T00:00:00+0000",
        )
        parsed = parser.parse(entity)
        storage.save(parsed)

        asset_dir = Path(tmpdir) / parsed.creative_asset_id
        meta_path = asset_dir / "metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["source"] == "facebook"
        assert meta["type"] == "image"
        assert meta["sync_count"] == 1
        assert meta["has_entity"] is True
        assert meta["has_adjust"] is False
        assert meta["has_eagle"] is False
        assert meta["legacy_id"] == "000001"


def test_sync_result():
    """SyncResult 统计正确。"""
    result = SyncResult()
    result.account_id = "act_123"
    result.total_ads = 100
    result.entities_created = 50
    result.entities_updated = 30
    result.duration_seconds = 120.5

    d = result.to_dict()
    assert d["total_ads"] == 100
    assert d["created"] == 50
    assert d["updated"] == 30

    log = result.to_log()
    assert "Ads: 100" in log
    assert "New Creative: 50" in log


def test_creative_type_enum():
    """CreativeType 枚举值正确。"""
    assert CreativeType.IMAGE.value == "image"
    assert CreativeType.VIDEO.value == "video"
    assert CreativeType.UNKNOWN.value == "unknown"


def test_entity_properties():
    """Entity 便捷属性。"""
    entity = FacebookCreativeEntity(
        creative_asset_id="",
        creative_type=CreativeType.IMAGE,
        spend=0.0,
        impressions=0,
    )
    assert not entity.has_asset_id
    assert not entity.has_performance

    entity2 = FacebookCreativeEntity(
        creative_asset_id="MW_VID_000001",
        creative_type=CreativeType.VIDEO,
        spend=100.0,
        impressions=1000,
    )
    assert entity2.has_asset_id
    assert entity2.has_performance


def test_ad_parser_batch():
    """AdParser 批量解析新格式。"""
    parser = AdParser(product="MW")
    entities = [
        FacebookCreativeEntity(
            ad_name="ad_000001", creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            created_time="2026-07-01T00:00:00+0000",
        ),
        FacebookCreativeEntity(
            ad_name="ad_000002", creative_id="cr_002",
            creative_type=CreativeType.VIDEO,
            created_time="2026-07-02T00:00:00+0000",
        ),
        FacebookCreativeEntity(
            ad_name="no_number", creative_id="cr_003",
            creative_type=CreativeType.IMAGE,
        ),
    ]
    parsed = parser.parse_batch(entities)
    assert parsed[0].creative_asset_id == "MW_IMG_260701_000001"
    assert parsed[0].legacy_id == "000001"
    assert parsed[1].creative_asset_id == "MW_VID_260702_000002"
    assert parsed[1].legacy_id == "000002"
    assert "FB_cr_003" in parsed[2].creative_asset_id
    assert parsed[2].legacy_id == "FB_cr_003"


def test_storage_load_nonexistent():
    """加载不存在的 Entity 返回 None。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        assert storage.load("nonexistent") is None
        assert storage.load_entity("nonexistent") is None


def test_storage_save_empty_asset_id():
    """保存空 asset_id 的 Entity 抛异常。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        entity = FacebookCreativeEntity(creative_asset_id="")
        with pytest.raises(ValueError, match="cannot be empty"):
            storage.save(entity)