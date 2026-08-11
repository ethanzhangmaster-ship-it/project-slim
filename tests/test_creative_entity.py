"""E11 Phase 2 — Creative Entity & Adjust Tests。

测试覆盖：
  1. CreativeEntity 创建和序列化（Phase 2 升级）
  2. AcquisitionData / RevenueData 子模型
  3. merge_facebook_data() — Facebook 数据合并
  4. merge_adjust_data() — Adjust 收入数据合并（Phase 2 升级）
  5. merge_eagle_data() / merge_lovart_data()
  6. FacebookCreativeEntity.to_creative_entity()
  7. AdParser 新 ID 格式
  8. Storage entity.json 双文件保存
  9. DataQualityValidator
  10. AdjustRevenueEntity 模型
  11. AdjustCreativeMatcher 4级匹配
  12. AdjustStorage adjust.json 保存
  13. AdjustDataQualityValidator 质量检查
  14. AdjustClient / AdjustFetcher — API 数据抓取
  15. RevenueCalculator — CPI/ARPU/ROAS/LTV 计算
  16. AdjustSyncEngine — 完整同步流程
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from market_ops.creative_repository import (
    CreativeEntity,
    CreativeIdentity,
    CreativeSources,
    AcquisitionData,
    RevenueData,
    CreativePerformance,
    CreativeAsset,
    CreativeAnalysis,
    CreativeType,
)

from market_ops.facebook_ingestion import (
    FacebookCreativeEntity,
    AdParser,
    CreativeStorage,
    DataQualityValidator,
)

from market_ops.adjust_ingestion import (
    AdjustRevenueEntity,
    AdjustCreativeMatcher,
    AdjustStorage,
    AdjustDataQualityValidator,
    AdjustClient,
    AdjustFetcher,
    RevenueCalculator,
    AdjustSyncEngine,
)


# ═══════════════════════════════════════════════════════════
# Test 1 — CreativeEntity 创建和序列化（Phase 2）
# ═══════════════════════════════════════════════════════════

def test_creative_entity_creation():
    """CreativeEntity 基本创建。"""
    entity = CreativeEntity(
        creative_asset_id="MW_IMG_260721_000123",
        legacy_id="000123",
        identity=CreativeIdentity(name="witch_merge", type=CreativeType.IMAGE, product="MW"),
    )
    assert entity.creative_asset_id == "MW_IMG_260721_000123"
    assert entity.legacy_id == "000123"
    assert entity.is_image
    assert not entity.is_video
    assert entity.display_name == "witch_merge"


def test_creative_entity_serialization_roundtrip():
    """CreativeEntity 序列化往返（Phase 2 新结构）。"""
    entity = CreativeEntity(
        creative_asset_id="MW_VID_260721_000456",
        legacy_id="000456",
        identity=CreativeIdentity(name="dragon_video", type=CreativeType.VIDEO, product="MW"),
        sources=CreativeSources(facebook_id="cr_001"),
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=5000.0, impressions=120000, clicks=8000, ctr=6.67, installs=1200),
            revenue=RevenueData(iap_d30=10000.0, ad_d30=2000.0, purchases=300, payer_count=50, payer_rate=0.05),
        ),
        asset=CreativeAsset(video_url="vid_123"),
        analysis=CreativeAnalysis(hook_type="rescue", reward_type="evolution"),
        synced_sources=["facebook", "adjust"],
    )

    restored = CreativeEntity.from_dict(entity.to_dict())
    assert restored.creative_asset_id == entity.creative_asset_id
    assert restored.legacy_id == entity.legacy_id
    assert restored.identity.name == "dragon_video"
    assert restored.sources.facebook_id == "cr_001"
    assert restored.performance.acquisition.spend == 5000.0
    assert restored.performance.revenue.iap_d30 == 10000.0
    assert restored.performance.roas_d30 == 2.4  # 12000/5000
    assert restored.asset.video_url == "vid_123"
    assert restored.analysis.hook_type == "rescue"
    assert restored.synced_sources == ["facebook", "adjust"]


def test_creative_entity_properties():
    """CreativeEntity Phase 2 便捷属性。"""
    img = CreativeEntity(identity=CreativeIdentity(type=CreativeType.IMAGE))
    assert img.is_image
    assert not img.is_video
    assert not img.has_performance
    assert not img.has_revenue

    vid = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        identity=CreativeIdentity(type=CreativeType.VIDEO),
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=100.0, impressions=1000),
        ),
    )
    assert vid.is_video
    assert vid.has_performance
    assert not vid.has_revenue
    assert vid.performance.roas_d30_str == "N/A"
    assert vid.performance.roi == 0.0


# ═══════════════════════════════════════════════════════════
# Test 2 — AcquisitionData / RevenueData
# ═══════════════════════════════════════════════════════════

def test_acquisition_data():
    """AcquisitionData 基本属性。"""
    acq = AcquisitionData(spend=5000.0, impressions=120000, clicks=8000, installs=2000)
    assert acq.has_data
    assert acq.cpi == 2.5  # 5000/2000
    assert acq.cpi == 0.0 if acq.installs == 0 else 2.5

    acq2 = AcquisitionData()
    assert not acq2.has_data
    assert acq2.cpi == 0.0


def test_revenue_data():
    """RevenueData 基本属性。"""
    rev = RevenueData(
        iap_d1=800.0, iap_d7=3000.0, iap_d30=10000.0,
        ad_d1=200.0, ad_d7=500.0, ad_d30=2000.0,
        purchases=300, payer_count=50, payer_rate=0.05,
    )
    assert rev.total_iap == 10000.0
    assert rev.total_ad == 2000.0
    assert rev.total_revenue == 12000.0
    assert rev.has_data

    rev2 = RevenueData()
    assert not rev2.has_data
    assert rev2.total_revenue == 0.0


def test_acquisition_serialization():
    """AcquisitionData 序列化往返。"""
    acq = AcquisitionData(spend=5000.0, impressions=120000, clicks=8000, ctr=6.67, cpc=0.625, cpm=41.67, installs=2000)
    restored = AcquisitionData.from_dict(acq.to_dict())
    assert restored.spend == 5000.0
    assert restored.impressions == 120000
    assert restored.installs == 2000


def test_revenue_serialization():
    """RevenueData 序列化往返。"""
    rev = RevenueData(iap_d1=800.0, iap_d7=3000.0, iap_d30=10000.0, ad_d30=2000.0)
    restored = RevenueData.from_dict(rev.to_dict())
    assert restored.iap_d30 == 10000.0
    assert restored.ad_d30 == 2000.0


def test_creative_performance_metrics_computed():
    """CreativePerformance ROAS/CPI 为计算属性。"""
    perf = CreativePerformance(
        acquisition=AcquisitionData(spend=5000.0, installs=2000),
        revenue=RevenueData(iap_d1=500.0, iap_d7=2000.0, iap_d30=10000.0, ad_d30=2000.0),
    )
    assert perf.cpi == 2.5
    assert perf.roas_d1 == 0.1    # 500/5000
    assert perf.roas_d7 == 0.4    # 2000/5000
    assert perf.roas_d30 == 2.4   # 12000/5000
    assert perf.roi == 2.4
    assert perf.roas_d30_str == "240.00%"
    assert perf.has_acquisition
    assert perf.has_revenue


def test_creative_performance_serialization():
    """CreativePerformance 序列化往返（Phase 2）。"""
    perf = CreativePerformance(
        acquisition=AcquisitionData(spend=5000.0, impressions=120000, clicks=8000, ctr=6.67, installs=2000),
        revenue=RevenueData(iap_d30=10000.0, ad_d30=2000.0, purchases=300, payer_count=50),
    )
    restored = CreativePerformance.from_dict(perf.to_dict())
    assert restored.acquisition.spend == 5000.0
    assert restored.acquisition.installs == 2000
    assert restored.revenue.iap_d30 == 10000.0
    assert restored.revenue.ad_d30 == 2000.0
    # metrics 是计算属性，不参与序列化
    assert restored.roas_d30 == 2.4


def test_creative_performance_from_dict_old_format():
    """旧格式兼容：flat structure → CreativePerformance。"""
    old_data = {
        "spend": 5000.0,
        "impressions": 120000,
        "clicks": 8000,
        "installs": 2000,
        "revenue": 12000.0,
    }
    perf = CreativePerformance.from_dict(old_data)
    assert perf.acquisition.spend == 5000.0
    assert perf.acquisition.installs == 2000
    # 旧格式没有 D1/D7/D30 拆分，revenue 回退到 0
    assert perf.revenue.iap_d30 == 0.0


# ═══════════════════════════════════════════════════════════
# Test 3 — merge_facebook_data() Phase 2
# ═══════════════════════════════════════════════════════════

def test_merge_facebook_data():
    """merge_facebook_data() 写入 acquisition 子结构。"""
    entity = CreativeEntity(
        creative_asset_id="MW_IMG_000001",
        identity=CreativeIdentity(type=CreativeType.IMAGE, product="MW"),
    )

    fb_entity = FacebookCreativeEntity(
        creative_asset_id="MW_IMG_000001",
        legacy_id="000001",
        creative_id="cr_001",
        ad_name="witch_image_000001",
        creative_type=CreativeType.IMAGE,
        spend=150.50,
        impressions=5000,
        clicks=300,
        ctr=6.0,
        cpc=0.50,
        cpm=30.10,
        installs=50,
        image_url="https://fb.com/img.jpg",
        thumbnail_url="https://fb.com/thumb.jpg",
    )

    entity.merge_facebook_data(fb_entity)

    assert entity.sources.facebook_id == "cr_001"
    assert entity.identity.name == "witch_image_000001"
    assert entity.performance.acquisition.spend == 150.50
    assert entity.performance.acquisition.impressions == 5000
    assert entity.performance.acquisition.clicks == 300
    assert entity.performance.acquisition.ctr == 6.0
    assert entity.performance.acquisition.installs == 50
    assert entity.asset.image_url == "https://fb.com/img.jpg"
    assert "facebook" in entity.synced_sources


# ═══════════════════════════════════════════════════════════
# Test 4 — merge_adjust_data() Phase 2
# ═══════════════════════════════════════════════════════════

def test_merge_adjust_data():
    """merge_adjust_data() 写入 revenue 子结构（D1/D7/D30）。"""
    entity = CreativeEntity(
        creative_asset_id="MW_VID_000002",
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=5000.0),
        ),
    )

    adjust_data = {
        "adjust_id": "adj_001",
        "iap_d1": 800.0,
        "iap_d7": 3000.0,
        "iap_d30": 10000.0,
        "ad_d1": 200.0,
        "ad_d7": 500.0,
        "ad_d30": 2000.0,
        "purchases": 300,
        "payer_count": 50,
        "payer_rate": 0.05,
    }

    entity.merge_adjust_data(adjust_data)

    assert entity.sources.adjust_id == "adj_001"
    assert entity.performance.revenue.iap_d1 == 800.0
    assert entity.performance.revenue.iap_d7 == 3000.0
    assert entity.performance.revenue.iap_d30 == 10000.0
    assert entity.performance.revenue.ad_d30 == 2000.0
    assert entity.performance.revenue.purchases == 300
    assert entity.performance.revenue.payer_count == 50
    assert entity.performance.revenue.total_revenue == 12000.0
    assert entity.performance.roas_d30 == 2.4  # 12000/5000
    assert entity.has_revenue
    assert "adjust" in entity.synced_sources


# ═══════════════════════════════════════════════════════════
# Test 5 — merge_eagle_data / merge_lovart_data
# ═══════════════════════════════════════════════════════════

def test_merge_eagle_data():
    """merge_eagle_data() 正确写入素材路径。"""
    entity = CreativeEntity(creative_asset_id="MW_VID_000003")
    entity.merge_eagle_data({"eagle_path": "/eagle/000003.mp4", "video_path": "/local/000003.mp4"})
    assert entity.sources.eagle_path == "/eagle/000003.mp4"
    assert entity.asset.video_path == "/local/000003.mp4"
    assert "eagle" in entity.synced_sources


def test_merge_lovart_data():
    """merge_lovart_data() 正确写入 DNA 分析数据。"""
    entity = CreativeEntity(creative_asset_id="MW_VID_000004")
    entity.merge_lovart_data({
        "lovart_id": "lov_001",
        "video_dna": {"hook": "rescue", "reward": "evolution"},
        "hook_type": "rescue",
        "reward_type": "evolution",
        "emotion": "excited",
        "style": "gameplay",
    })
    assert entity.sources.lovart_id == "lov_001"
    assert entity.analysis.hook_type == "rescue"
    assert entity.analysis.video_dna == {"hook": "rescue", "reward": "evolution"}
    assert "lovart" in entity.synced_sources


# ═══════════════════════════════════════════════════════════
# Test 6 — to_creative_entity() Phase 2
# ═══════════════════════════════════════════════════════════

def test_to_creative_entity():
    """FacebookCreativeEntity → CreativeEntity（Phase 2 新结构）。"""
    fb = FacebookCreativeEntity(
        legacy_id="000001",
        creative_id="cr_001",
        ad_name="witch_image_000001",
        creative_type=CreativeType.IMAGE,
        spend=150.50,
        impressions=5000,
        clicks=300,
        ctr=6.0,
        cpc=0.50,
        cpm=30.10,
        installs=50,
        image_url="https://fb.com/img.jpg",
        created_time="2026-07-01T00:00:00+0000",
    )

    ce = fb.to_creative_entity(product="MW")
    assert ce.creative_asset_id.startswith("MW_IMG_")
    assert ce.legacy_id == "000001"
    assert ce.performance.acquisition.spend == 150.50
    assert ce.performance.acquisition.impressions == 5000
    assert ce.performance.acquisition.installs == 50
    assert ce.asset.image_url == "https://fb.com/img.jpg"
    assert "facebook" in ce.synced_sources


def test_to_creative_entity_video():
    """视频类型使用 VID 前缀。"""
    fb = FacebookCreativeEntity(
        legacy_id="000456",
        creative_id="cr_002",
        creative_type=CreativeType.VIDEO,
        ad_name="dragon_video_000456",
        video_id="vid_123",
        spend=5000.0,
        impressions=120000,
        created_time="2026-07-21T00:00:00+0000",
    )
    ce = fb.to_creative_entity(product="MW")
    assert ce.creative_asset_id.startswith("MW_VID_")
    assert ce.asset.video_url == "vid_123"


# ═══════════════════════════════════════════════════════════
# Test 7 — AdParser 新 ID 格式
# ═══════════════════════════════════════════════════════════

def test_ad_parser_new_format():
    """AdParser 生成新格式 ID。"""
    parser = AdParser(product="MW")

    img = FacebookCreativeEntity(
        ad_name="witch_image_000001", creative_id="cr_001",
        creative_type=CreativeType.IMAGE, created_time="2026-07-01T00:00:00+0000",
    )
    parsed = parser.parse(img)
    assert parsed.creative_asset_id == "MW_IMG_260701_000001"
    assert parsed.legacy_id == "000001"

    vid = FacebookCreativeEntity(
        ad_name="dragon_video_000456", creative_id="cr_002",
        creative_type=CreativeType.VIDEO, created_time="2026-07-21T00:00:00+0000",
    )
    parsed = parser.parse(vid)
    assert parsed.creative_asset_id == "MW_VID_260721_000456"
    assert parsed.legacy_id == "000456"


def test_ad_parser_fallback():
    """无编号时 fallback 到 FB_{creative_id}。"""
    parser = AdParser(product="MW")
    entity = FacebookCreativeEntity(
        ad_name="no_number", creative_id="cr_888", creative_type=CreativeType.IMAGE,
    )
    parsed = parser.parse(entity)
    assert parsed.legacy_id == "FB_cr_888"
    assert "FB_cr_888" in parsed.creative_asset_id


# ═══════════════════════════════════════════════════════════
# Test 8 — Storage entity.json + facebook.json
# ═══════════════════════════════════════════════════════════

def test_storage_saves_entity_json():
    """Storage.save() 同时保存 entity.json 和 facebook.json。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        entity = FacebookCreativeEntity(
            ad_name="test_000001", creative_id="cr_001",
            creative_type=CreativeType.IMAGE, spend=100.0, impressions=1000,
            created_time="2026-07-01T00:00:00+0000",
        )
        parsed = parser.parse(entity)
        storage.save(parsed)

        creative_dir = Path(tmpdir) / parsed.creative_asset_id
        assert (creative_dir / "facebook.json").exists()
        assert (creative_dir / "entity.json").exists()
        assert (creative_dir / "metadata.json").exists()

        entity_data = json.loads((creative_dir / "entity.json").read_text())
        assert entity_data["performance"]["acquisition"]["spend"] == 100.0
        assert entity_data["performance"]["acquisition"]["installs"] == 0


def test_storage_load_entity():
    """Storage.load_entity() 正确加载 CreativeEntity。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        entity = FacebookCreativeEntity(
            ad_name="test_000002", creative_id="cr_002",
            creative_type=CreativeType.VIDEO, spend=200.0, impressions=2000,
            created_time="2026-07-02T00:00:00+0000",
        )
        parsed = parser.parse(entity)
        storage.save(parsed)

        ce = storage.load_entity(parsed.creative_asset_id)
        assert ce is not None
        assert ce.performance.acquisition.spend == 200.0


# ═══════════════════════════════════════════════════════════
# Test 9 — DataQualityValidator
# ═══════════════════════════════════════════════════════════

def test_validator_basic():
    """DataQualityValidator 基本检查。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        entity = FacebookCreativeEntity(
            ad_name="test_000001", creative_id="cr_001",
            creative_type=CreativeType.IMAGE, campaign_id="camp_001",
            adset_id="adset_001", spend=100.0, impressions=1000, clicks=50, ctr=5.0,
            created_time="2026-07-01T00:00:00+0000",
        )
        storage.save(parser.parse(entity))

        validator = DataQualityValidator(storage)
        report = validator.validate()
        assert report.completeness.total_entities == 1
        assert "Data Quality Report" in report.to_summary()


# ═══════════════════════════════════════════════════════════
# Test 10 — AdjustRevenueEntity 模型
# ═══════════════════════════════════════════════════════════

def test_adjust_entity_creation():
    """AdjustRevenueEntity 基本创建。"""
    entity = AdjustRevenueEntity(
        creative_asset_id="MW_VID_260721_000123",
        adjust_creative_id="adj_001",
        installs=2000,
        sessions=5000,
        purchasers=120,
        iap_d1=800.0,
        iap_d7=3000.0,
        iap_d30=10000.0,
        ad_d1=200.0,
        ad_d7=500.0,
        ad_d30=2000.0,
    )
    assert entity.creative_asset_id == "MW_VID_260721_000123"
    assert entity.total_revenue == 12000.0
    assert entity.total_iap == 10000.0
    assert entity.total_ad == 2000.0
    assert entity.has_revenue
    assert entity.has_iap
    assert entity.has_users


def test_adjust_entity_serialization():
    """AdjustRevenueEntity 序列化往返。"""
    entity = AdjustRevenueEntity(
        creative_asset_id="MW_VID_000001",
        adjust_creative_id="adj_001",
        legacy_id="000001",
        campaign="Campaign A",
        installs=1000,
        purchasers=50,
        iap_d30=5000.0,
        ad_d30=1000.0,
    )
    restored = AdjustRevenueEntity.from_dict(entity.to_dict())
    assert restored.creative_asset_id == "MW_VID_000001"
    assert restored.legacy_id == "000001"
    assert restored.campaign == "Campaign A"
    assert restored.total_revenue == 6000.0


def test_adjust_entity_empty():
    """空 AdjustRevenueEntity。"""
    entity = AdjustRevenueEntity()
    assert not entity.has_revenue
    assert not entity.has_iap
    assert not entity.has_users
    assert entity.total_revenue == 0.0


# ═══════════════════════════════════════════════════════════
# Test 11 — AdjustCreativeMatcher 4级匹配
# ═══════════════════════════════════════════════════════════

def test_matcher_level1_exact_id():
    """Level 1: creative_asset_id 精确匹配。"""
    creative = CreativeEntity(
        creative_asset_id="MW_VID_260721_000123",
        legacy_id="000123",
        identity=CreativeIdentity(name="dragon_video_000123", type=CreativeType.VIDEO),
        performance=CreativePerformance(acquisition=AcquisitionData(spend=5000.0)),
    )

    adjust = AdjustRevenueEntity(
        creative_asset_id="MW_VID_260721_000123",
        adjust_creative_id="adj_001",
        iap_d30=10000.0,
        ad_d30=2000.0,
    )

    matcher = AdjustCreativeMatcher()
    report = matcher.match([creative], [adjust])

    assert report.matched == 1
    assert report.match_rate == 1.0
    assert report.by_level.get(1, 0) == 1

    # 验证 CreativeEntity 已更新
    assert creative.sources.adjust_id == "adj_001"
    assert creative.performance.revenue.iap_d30 == 10000.0
    assert creative.performance.roas_d30 == 2.4  # 12000/5000
    assert "adjust" in creative.synced_sources


def test_matcher_level2_legacy_id():
    """Level 2: legacy_id 匹配。"""
    creative = CreativeEntity(
        creative_asset_id="MW_VID_260721_000123",
        legacy_id="000123",
        identity=CreativeIdentity(name="dragon_video", type=CreativeType.VIDEO),
        performance=CreativePerformance(acquisition=AcquisitionData(spend=5000.0)),
    )

    adjust = AdjustRevenueEntity(
        creative_asset_id="",  # 无新格式 ID
        legacy_id="000123",
        adjust_creative_id="adj_002",
        iap_d30=8000.0,
    )

    matcher = AdjustCreativeMatcher()
    report = matcher.match([creative], [adjust])

    assert report.matched == 1
    assert report.by_level.get(2, 0) == 1
    assert creative.sources.adjust_id == "adj_002"
    assert creative.performance.revenue.iap_d30 == 8000.0


def test_matcher_level3_name_match():
    """Level 3: creative name 匹配。"""
    creative = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        legacy_id="",
        identity=CreativeIdentity(name="dragon_video_000123", type=CreativeType.VIDEO),
    )

    adjust = AdjustRevenueEntity(
        creative_asset_id="",
        legacy_id="",
        creative="dragon_video_000123",  # 通过 name 匹配
        adjust_creative_id="adj_003",
        iap_d30=5000.0,
    )

    matcher = AdjustCreativeMatcher()
    report = matcher.match([creative], [adjust])

    assert report.matched == 1
    assert report.by_level.get(3, 0) == 1


def test_matcher_unmatched():
    """无法匹配时报告 unmatched。"""
    creative = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        legacy_id="000001",
        identity=CreativeIdentity(name="dragon_video", type=CreativeType.VIDEO),
    )

    adjust = AdjustRevenueEntity(
        creative_asset_id="MW_VID_999999",  # 不匹配
        legacy_id="999999",
        creative="completely_different",
        adjust_creative_id="adj_999",
    )

    matcher = AdjustCreativeMatcher()
    report = matcher.match([creative], [adjust])

    assert report.matched == 0
    assert report.unmatched == 1
    assert report.match_rate == 0.0


def test_matcher_mixed_levels():
    """混合匹配：不同级别各命中。"""
    creatives = [
        CreativeEntity(
            creative_asset_id="MW_IMG_000001",
            legacy_id="000001",
            identity=CreativeIdentity(name="image_000001", type=CreativeType.IMAGE),
        ),
        CreativeEntity(
            creative_asset_id="MW_VID_000002",
            legacy_id="000002",
            identity=CreativeIdentity(name="video_000002", type=CreativeType.VIDEO),
        ),
        CreativeEntity(
            creative_asset_id="MW_VID_000003",
            legacy_id="",
            identity=CreativeIdentity(name="special_video", type=CreativeType.VIDEO),
        ),
    ]

    adjust_entities = [
        AdjustRevenueEntity(creative_asset_id="MW_IMG_000001", iap_d30=1000.0),  # Level 1
        AdjustRevenueEntity(legacy_id="000002", iap_d30=2000.0),                  # Level 2
        AdjustRevenueEntity(creative="special_video", iap_d30=3000.0),             # Level 3
        AdjustRevenueEntity(creative_asset_id="MW_XXX", legacy_id="999", creative="no_match"),  # Unmatched
    ]

    matcher = AdjustCreativeMatcher()
    report = matcher.match(creatives, adjust_entities)

    assert report.matched == 3
    assert report.unmatched == 1
    assert report.match_rate == 0.75
    assert report.by_level.get(1, 0) == 1
    assert report.by_level.get(2, 0) == 1
    assert report.by_level.get(3, 0) == 1


def test_matcher_report_summary():
    """AdjustMatchReport.to_summary() 生成可读摘要。"""
    matcher = AdjustCreativeMatcher()
    creative = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        legacy_id="000001",
        identity=CreativeIdentity(name="test", type=CreativeType.VIDEO),
    )
    adjust = AdjustRevenueEntity(creative_asset_id="MW_VID_000001", iap_d30=5000.0)

    report = matcher.match([creative], [adjust])
    summary = report.to_summary()

    assert "Match Report" in summary
    assert "Match Rate: 100.0%" in summary
    assert "Level 1: 1" in summary


# ═══════════════════════════════════════════════════════════
# Test 12 — AdjustStorage
# ═══════════════════════════════════════════════════════════

def test_adjust_storage_save():
    """AdjustStorage.save() 保存 adjust.json。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        entity = AdjustRevenueEntity(
            creative_asset_id="MW_VID_000001",
            adjust_creative_id="adj_001",
            installs=1000,
            purchasers=50,
            iap_d30=5000.0,
            ad_d30=1000.0,
        )
        storage.save(entity)

        creative_dir = Path(tmpdir) / "MW_VID_000001"
        assert (creative_dir / "adjust.json").exists()

        # 验证 adjust.json 内容
        data = json.loads((creative_dir / "adjust.json").read_text())
        assert data["iap_d30"] == 5000.0
        assert data["ad_d30"] == 1000.0
        assert data["installs"] == 1000

        # 验证 metadata.json
        meta = json.loads((creative_dir / "metadata.json").read_text())
        assert meta["has_adjust"] is True
        assert meta["adjust_total_revenue"] == 6000.0


def test_adjust_storage_load():
    """AdjustStorage.load() 正确加载。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        entity = AdjustRevenueEntity(
            creative_asset_id="MW_VID_000002",
            iap_d30=8000.0,
            ad_d30=2000.0,
        )
        storage.save(entity)

        loaded = storage.load("MW_VID_000002")
        assert loaded is not None
        assert loaded.total_revenue == 10000.0
        assert loaded.iap_d30 == 8000.0


def test_adjust_storage_batch():
    """AdjustStorage.save_batch() 批量保存。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        entities = [
            AdjustRevenueEntity(creative_asset_id=f"MW_VID_{i:06d}", iap_d30=1000.0 * i)
            for i in range(1, 4)
        ]
        stats = storage.save_batch(entities)
        assert stats["created"] == 3
        assert storage.count() == 3

        # 重复保存
        stats2 = storage.save_batch(entities)
        assert stats2["updated"] == 3


def test_adjust_storage_exists():
    """AdjustStorage.exists() 检查。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)
        assert not storage.exists("MW_VID_000001")

        entity = AdjustRevenueEntity(creative_asset_id="MW_VID_000001")
        storage.save(entity)
        assert storage.exists("MW_VID_000001")


def test_adjust_storage_load_nonexistent():
    """加载不存在的实体返回 None。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)
        assert storage.load("nonexistent") is None


def test_adjust_storage_save_empty_id():
    """空 creative_asset_id 时抛异常。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)
        entity = AdjustRevenueEntity(creative_asset_id="")
        with pytest.raises(ValueError, match="cannot be empty"):
            storage.save(entity)


# ═══════════════════════════════════════════════════════════
# Test 13 — AdjustDataQualityValidator
# ═══════════════════════════════════════════════════════════

def test_adjust_validator_revenue_completeness():
    """AdjustDataQualityValidator 检查收入完整率。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        # 全部有 D1，部分有 D7/D30
        entities = [
            AdjustRevenueEntity(creative_asset_id="MW_VID_000001", iap_d1=100.0, iap_d7=500.0, iap_d30=1000.0),
            AdjustRevenueEntity(creative_asset_id="MW_VID_000002", iap_d1=200.0, iap_d7=1000.0),  # 无 D30
            AdjustRevenueEntity(creative_asset_id="MW_VID_000003", iap_d1=300.0),  # 无 D7/D30
        ]
        storage.save_batch(entities)

        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()

        assert report.total_adjust == 3
        assert report.revenue_completeness["d1"] == 1.0
        assert report.revenue_completeness["d7"] == pytest.approx(2 / 3, abs=0.01)
        assert report.revenue_completeness["d30"] == pytest.approx(1 / 3, abs=0.01)


def test_adjust_validator_top_revenue():
    """AdjustDataQualityValidator 按收入排序 Top N。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        revenues = [5000.0, 3000.0, 1000.0, 500.0, 100.0]
        for i, rev in enumerate(revenues):
            entity = AdjustRevenueEntity(
                creative_asset_id=f"MW_VID_{i:06d}",
                iap_d30=rev * 0.8,
                ad_d30=rev * 0.2,
                installs=1000 + i * 100,
            )
            storage.save(entity)

        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()

        assert len(report.top_revenue) == 5
        assert report.top_revenue[0]["revenue"] == 5000.0
        assert report.top_revenue[0]["rank"] == 1


def test_adjust_validator_anomalies():
    """AdjustDataQualityValidator 检测异常数据。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        # 异常：有收入但 0 installs
        entity = AdjustRevenueEntity(
            creative_asset_id="MW_VID_000001",
            iap_d30=5000.0,
            installs=0,
        )
        storage.save(entity)

        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()

        assert len(report.anomalies) > 0
        assert any("0 installs" in a for a in report.anomalies)


def test_adjust_validator_warnings():
    """AdjustDataQualityValidator 生成告警。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        # 只有 1 个实体，可能匹配率低
        entity = AdjustRevenueEntity(creative_asset_id="MW_VID_000001")
        storage.save(entity)

        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()

        # 无 creative_storage 时不计算匹配率
        assert report.match_rate == 0.0
        assert len(report.warnings) > 0  # 低 D30 覆盖率


def test_adjust_validator_empty():
    """空存储时 validator 不报错。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)
        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()

        assert report.total_adjust == 0
        assert len(report.warnings) > 0


def test_adjust_validator_report_summary():
    """AdjustQualityReport.to_summary() 生成可读摘要。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AdjustStorage(root_dir=tmpdir)

        entity = AdjustRevenueEntity(
            creative_asset_id="MW_VID_000001",
            iap_d1=100.0, iap_d7=500.0, iap_d30=1000.0,
            installs=100,
        )
        storage.save(entity)

        validator = AdjustDataQualityValidator(storage)
        report = validator.validate()
        summary = report.to_summary()

        assert "Adjust Data Quality Report" in summary
        assert "Revenue Completeness" in summary
        assert "D1: 100.0%" in summary


# ═══════════════════════════════════════════════════════════
# Test — 子模型序列化
# ═══════════════════════════════════════════════════════════

def test_creative_identity_serialization():
    """CreativeIdentity 序列化。"""
    identity = CreativeIdentity(
        name="test", type=CreativeType.VIDEO, product="MW",
        language="en", country="US", tags=["gameplay"],
    )
    restored = CreativeIdentity.from_dict(identity.to_dict())
    assert restored.name == "test"
    assert restored.tags == ["gameplay"]


def test_creative_sources_serialization():
    """CreativeSources 序列化。"""
    sources = CreativeSources(
        facebook_id="fb_001", adjust_id="adj_001",
        eagle_path="/eagle/001.mp4", lovart_id="lov_001",
    )
    restored = CreativeSources.from_dict(sources.to_dict())
    assert restored.has_facebook
    assert restored.has_adjust
    assert restored.has_eagle
    assert restored.has_lovart


def test_creative_asset_serialization():
    """CreativeAsset 序列化。"""
    asset = CreativeAsset(
        image_url="https://fb.com/img.jpg",
        video_path="/local/vid.mp4",
        thumbnail_url="https://fb.com/thumb.jpg",
    )
    restored = CreativeAsset.from_dict(asset.to_dict())
    assert restored.image_url == "https://fb.com/img.jpg"
    assert restored.has_image
    assert restored.has_video


def test_creative_analysis_serialization():
    """CreativeAnalysis 序列化。"""
    analysis = CreativeAnalysis(
        image_dna={"colors": ["red"]},
        video_dna={"hook": "rescue"},
        hook_type="rescue",
        reward_type="evolution",
        emotion="excited",
        style="gameplay",
        notes="test note",
    )
    restored = CreativeAnalysis.from_dict(analysis.to_dict())
    assert restored.video_dna == {"hook": "rescue"}
    assert restored.hook_type == "rescue"
    assert restored.emotion == "excited"


# ═══════════════════════════════════════════════════════════
# Test — FacebookCreativeEntity 序列化含 legacy_id
# ═══════════════════════════════════════════════════════════

def test_facebook_entity_serialization_with_legacy():
    """FacebookCreativeEntity 序列化含 legacy_id。"""
    entity = FacebookCreativeEntity(
        creative_asset_id="MW_IMG_260701_000001",
        legacy_id="000001",
        creative_id="cr_001",
        ad_name="test_000001",
        creative_type=CreativeType.IMAGE,
        spend=100.0,
    )
    restored = FacebookCreativeEntity.from_dict(entity.to_dict())
    assert restored.creative_asset_id == "MW_IMG_260701_000001"
    assert restored.legacy_id == "000001"


def test_facebook_entity_to_facebook_json_with_legacy():
    """to_facebook_json 包含 legacy_id。"""
    entity = FacebookCreativeEntity(
        creative_asset_id="MW_IMG_260701_000001",
        legacy_id="000001",
        creative_type=CreativeType.IMAGE,
        spend=100.0,
    )
    fb_json = entity.to_facebook_json()
    assert fb_json["legacy_id"] == "000001"


# ═══════════════════════════════════════════════════════════
# Test 14 — AdjustClient / AdjustFetcher
# ═══════════════════════════════════════════════════════════

def test_adjust_client_fetch_revenue():
    """AdjustClient Mock 返回 Adjust 收入数据。"""
    client = AdjustClient(api_token="mock_token", app_token="mock_app")
    records = client.fetch_revenue(start_date="2026-07-01", end_date="2026-07-21")

    assert len(records) == 3
    assert records[0]["creative_name"] == "dragon_video_000123"
    assert records[0]["cohort_revenue_iap_d30"] == 10000.0
    assert records[0]["installs"] == 2000


def test_adjust_fetcher_parse():
    """AdjustFetcher 解析 API 数据为 AdjustRevenueEntity 列表。"""
    client = AdjustClient(api_token="mock_token", app_token="mock_app")
    fetcher = AdjustFetcher(client)

    entities = fetcher.fetch(start_date="2026-07-01", end_date="2026-07-21")

    assert len(entities) == 3
    assert entities[0].adjust_creative_id == "adj_001"
    assert entities[0].creative == "dragon_video_000123"
    assert entities[0].iap_d30 == 10000.0
    assert entities[0].ad_d30 == 2000.0
    assert entities[0].total_revenue == 12000.0
    assert entities[0].installs == 2000
    assert entities[0].purchasers == 120


# ═══════════════════════════════════════════════════════════
# Test 15 — RevenueCalculator
# ═══════════════════════════════════════════════════════════

def test_revenue_calculator_single():
    """RevenueCalculator 计算单个 CreativeEntity 的指标。"""
    entity = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=5000.0, installs=2000),
            revenue=RevenueData(iap_d30=10000.0, ad_d30=2000.0),
        ),
    )

    calc = RevenueCalculator()
    metrics = calc.calculate(entity)

    assert metrics.cpi == 2.5  # 5000/2000
    assert metrics.arpu == 6.0  # 12000/2000
    assert metrics.ltv_d30 == 6.0
    assert metrics.roas_d30 == 2.4  # 12000/5000
    assert metrics.profit == 7000.0  # 12000-5000
    assert metrics.is_profitable
    assert metrics.roas_d30_pct == "240.00%"


def test_revenue_calculator_roas_from_creativity():
    """ROAS 计算 = revenue / spend。"""
    entity = CreativeEntity(
        creative_asset_id="MW_VID_000002",
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=5000.0, installs=2000),
            revenue=RevenueData(iap_d30=8000.0, ad_d30=4000.0),
        ),
    )

    calc = RevenueCalculator()
    metrics = calc.calculate(entity)

    assert metrics.roas_d30 == 2.4  # 12000/5000
    assert metrics.arpu == 6.0  # 12000/2000
    assert metrics.cpi == 2.5  # 5000/2000


def test_revenue_calculator_batch():
    """RevenueCalculator 批量计算。"""
    entities = [
        CreativeEntity(
            creative_asset_id=f"MW_VID_{i:06d}",
            performance=CreativePerformance(
                acquisition=AcquisitionData(spend=1000.0 * (i + 1), installs=100 * (i + 1)),
                revenue=RevenueData(iap_d30=2000.0 * (i + 1)),
            ),
        )
        for i in range(3)
    ]

    calc = RevenueCalculator()
    result = calc.calculate_batch(entities)

    assert len(result) == 3
    assert result["MW_VID_000000"].roas_d30 == 2.0  # 2000/1000
    assert result["MW_VID_000001"].roas_d30 == 2.0  # 4000/2000


def test_revenue_calculator_summary():
    """RevenueCalculator 计算汇总统计。"""
    entities = [
        CreativeEntity(
            creative_asset_id="MW_VID_000001",
            performance=CreativePerformance(
                acquisition=AcquisitionData(spend=5000.0, installs=2000),
                revenue=RevenueData(iap_d30=10000.0, ad_d30=2000.0),
            ),
        ),
        CreativeEntity(
            creative_asset_id="MW_VID_000002",
            performance=CreativePerformance(
                acquisition=AcquisitionData(spend=3000.0, installs=1000),
                revenue=RevenueData(iap_d30=2000.0),
            ),
        ),
    ]

    calc = RevenueCalculator()
    summary = calc.calculate_summary(entities)

    assert summary["total_creatives"] == 2
    assert summary["total_spend"] == 8000.0
    assert summary["total_revenue"] == 14000.0
    assert summary["total_installs"] == 3000
    assert summary["overall_roas"] == 1.75  # 14000/8000
    assert summary["total_profit"] == 6000.0
    assert summary["profitable_count"] == 1  # 只有 entity 1 盈利


def test_revenue_calculator_not_profitable():
    """不盈利的情况。"""
    entity = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=5000.0, installs=2000),
            revenue=RevenueData(iap_d30=2000.0),  # 只有 2000
        ),
    )

    calc = RevenueCalculator()
    metrics = calc.calculate(entity)

    assert metrics.profit == -3000.0
    assert not metrics.is_profitable
    assert metrics.roas_d30 == 0.4


def test_revenue_calculator_zero_installs():
    """0 installs 时指标为 0。"""
    entity = CreativeEntity(
        creative_asset_id="MW_VID_000001",
        performance=CreativePerformance(
            acquisition=AcquisitionData(spend=5000.0, installs=0),
            revenue=RevenueData(iap_d30=10000.0),
        ),
    )

    calc = RevenueCalculator()
    metrics = calc.calculate(entity)

    assert metrics.cpi == 0.0
    assert metrics.arpu == 0.0
    assert metrics.ltv_d30 == 0.0


# ═══════════════════════════════════════════════════════════
# Test 16 — AdjustSyncEngine
# ═══════════════════════════════════════════════════════════

def test_sync_engine_full_flow():
    """AdjustSyncEngine 完整同步流程。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 准备 CreativeEntity（先同步 Facebook 数据）
        creative_storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        fb_entity = FacebookCreativeEntity(
            ad_name="dragon_video_000123",
            creative_id="cr_123",
            creative_type=CreativeType.VIDEO,
            spend=5000.0,
            impressions=120000,
            clicks=8000,
            ctr=6.67,
            installs=2000,
            created_time="2026-07-01T00:00:00+0000",
        )
        parsed = parser.parse(fb_entity)
        creative_storage.save(parsed)

        # 2. 同步 Adjust 数据
        client = AdjustClient(api_token="mock_token", app_token="mock_app")
        engine = AdjustSyncEngine(client, creative_storage)

        result = engine.sync(start_date="2026-07-01", end_date="2026-07-21")

        # 验证结果
        assert result.total_records == 3
        assert result.creative_entities_loaded == 1
        assert result.match_report is not None
        assert result.match_report.matched >= 1  # 至少匹配到 1 个

        # 验证 entity.json 已更新
        ce = creative_storage.load_entity(parsed.creative_asset_id)
        assert ce is not None
        assert "adjust" in ce.synced_sources
        assert ce.performance.revenue.iap_d30 > 0


def test_sync_engine_result_summary():
    """AdjustSyncResult.to_summary() 生成可读摘要。"""
    client = AdjustClient(api_token="mock", app_token="mock")
    with tempfile.TemporaryDirectory() as tmpdir:
        creative_storage = CreativeStorage(root_dir=tmpdir)
        parser = AdParser(product="MW")

        fb = FacebookCreativeEntity(
            ad_name="test_000001",
            creative_id="cr_001",
            creative_type=CreativeType.IMAGE,
            spend=100.0,
            impressions=1000,
            created_time="2026-07-01T00:00:00+0000",
        )
        creative_storage.save(parser.parse(fb))

        engine = AdjustSyncEngine(client, creative_storage)
        result = engine.sync(start_date="2026-07-01", end_date="2026-07-21")

        summary = result.to_summary()
        assert "Adjust Sync Completed" in summary
        assert "Records:" in summary
        assert "Match Rate:" in summary
        assert "Total Spend:" in summary
        assert "Total Revenue:" in summary
        assert "Overall ROAS:" in summary


def test_sync_engine_empty_creatives():
    """无 CreativeEntity 时仍正常完成。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        creative_storage = CreativeStorage(root_dir=tmpdir)
        client = AdjustClient(api_token="mock", app_token="mock")
        engine = AdjustSyncEngine(client, creative_storage)

        result = engine.sync(start_date="2026-07-01", end_date="2026-07-21")

        assert result.total_records == 3
        assert result.creative_entities_loaded == 0
        assert result.creative_entities_updated == 0


def test_creative_performance_arpu_ltv():
    """CreativePerformance arpu/ltv_d30 计算属性。"""
    perf = CreativePerformance(
        acquisition=AcquisitionData(spend=5000.0, installs=2000),
        revenue=RevenueData(iap_d30=10000.0, ad_d30=2000.0),
    )
    assert perf.arpu == 6.0  # 12000/2000
    assert perf.ltv_d30 == 6.0
    # metrics 序列化包含 arpu/ltv
    d = perf.to_dict()
    assert d["metrics"]["arpu"] == 6.0
    assert d["metrics"]["ltv_d30"] == 6.0