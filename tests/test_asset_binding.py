"""E11 Phase 3 — Creative Asset Binding Tests。

测试覆盖：
  1. EagleIndexer: 索引构建、ID 提取、文件扫描
  2. VideoMatcher: 3 级匹配（精确 ID → 文件名 → Hash）
  3. ImageMatcher: Lovart 图片匹配
  4. AssetBindingEngine: 完整绑定流程
  5. AssetBindingValidator: 质量验证
  6. CreativeAsset 扩展字段
  7. 模型序列化
  8. 异常/边界处理
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from market_ops.creative_repository import CreativeEntity
from market_ops.creative_repository.models.creative_entity import (
    CreativeType,
    CreativeIdentity,
    CreativeSources,
    CreativeAsset,
    CreativePerformance,
    CreativeAnalysis,
    AcquisitionData,
    RevenueData,
)
from market_ops.creative_asset_binding import (
    EagleAsset,
    LovartAsset,
    AssetBindingResult,
    BindingMethod,
    AssetSourceType,
    EagleIndexer,
    EagleIndex,
    VideoMatcher,
    VideoMatchResult,
    ImageMatcher,
    ImageMatchResult,
    AssetBindingEngine,
    AssetBindingReport,
    AssetBindingValidator,
    AssetBindingQualityReport,
)


# ═══════════════════════════════════════════════════════════
# Helper: 创建临时 Eagle 素材目录
# ═══════════════════════════════════════════════════════════

def _make_eagle_dir(files: list[str]) -> Path:
    """创建临时 Eagle 素材目录。"""
    tmp = tempfile.mkdtemp(prefix="test_eagle_")
    root = Path(tmp)
    for f in files:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"mock content for {f}")
    return root


def _make_entity(
    creative_asset_id: str,
    media_type: CreativeType = CreativeType.VIDEO,
    creative_name: str = "test_creative",
    lovart_id: str = "",
) -> CreativeEntity:
    """创建测试用 CreativeEntity。"""
    return CreativeEntity(
        creative_asset_id=creative_asset_id,
        identity=CreativeIdentity(name=creative_name, type=media_type),
        sources=CreativeSources(facebook_id="fb_001", lovart_id=lovart_id),
        asset=CreativeAsset(),
        performance=CreativePerformance(
            acquisition=AcquisitionData(),
            revenue=RevenueData(),
        ),
        analysis=CreativeAnalysis(),
        synced_sources={"facebook"},
    )


# ═══════════════════════════════════════════════════════════
# Test 1: EagleIndexer
# ═══════════════════════════════════════════════════════════

class TestEagleIndexer:
    """测试 Eagle 索引构建。"""

    def test_build_index_empty_dir(self):
        root = _make_eagle_dir([])
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.total == 0

    def test_build_index_with_videos(self):
        files = [
            "MW_VIDEO_260721_000123.mp4",
            "MW_VIDEO_260721_000124.mp4",
            "MW_VIDEO_260721_000125.mp4",
        ]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.total == 3
        assert index.video_count == 3

    def test_build_index_mixed_media(self):
        files = [
            "MW_VIDEO_260721_000123.mp4",
            "MW_IMG_260721_000125.png",
            "MW_VIDEO_260721_000126.mov",
        ]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.total == 3

    def test_extract_creative_id(self):
        files = ["MW_VIDEO_260721_000123.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        asset = index.find_by_id("MW_VIDEO_260721_000123")
        assert asset is not None
        assert asset.creative_asset_id == "MW_VIDEO_260721_000123"
        assert asset.filename == "MW_VIDEO_260721_000123.mp4"

    def test_extract_creative_id_case_insensitive(self):
        files = ["mw_video_260721_000123.MP4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        asset = index.find_by_id("MW_VIDEO_260721_000123")
        assert asset is not None

    def test_find_by_id_miss(self):
        files = ["MW_VIDEO_260721_000123.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.find_by_id("MW_VIDEO_260721_999999") is None

    def test_find_by_filename(self):
        files = ["MW_VIDEO_260721_000123.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.find_by_filename("MW_VIDEO_260721_000123.mp4") is not None
        assert index.find_by_filename("nonexistent.mp4") is None

    def test_find_by_id_fuzzy(self):
        files = ["MW_VIDEO_260721_000123.mp4", "MW_VIDEO_260721_000124.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        results = index.find_by_id_fuzzy("000123")
        assert len(results) == 1

    def test_scan_directory_subdir(self):
        files = ["videos/MW_VIDEO_260721_000123.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.scan_directory("videos")
        assert index.total == 1

    def test_ignores_non_media_files(self):
        files = [
            "MW_VIDEO_260721_000123.mp4",
            "readme.txt",
            "config.json",
            "thumbnails/thumb.jpg",
        ]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.total == 2  # .mp4 + .jpg (not .txt, .json)

    def test_find_by_id_returns_correct_asset(self):
        files = ["MW_VIDEO_260721_000123.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        asset = indexer.find_by_id("MW_VIDEO_260721_000123")
        assert asset is not None
        assert "MW_VIDEO_260721_000123.mp4" in asset.path

    def test_nonexistent_dir_returns_empty(self):
        indexer = EagleIndexer("/nonexistent/path")
        index = indexer.build_index()
        assert index.total == 0

    def test_eagle_index_to_dict_from_dict(self):
        files = ["MW_VIDEO_260721_000123.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        d = index.to_dict()
        index2 = EagleIndex.from_dict(d)
        assert index2.total == 1
        assert index2.find_by_id("MW_VIDEO_260721_000123") is not None


# ═══════════════════════════════════════════════════════════
# Test 2: VideoMatcher
# ═══════════════════════════════════════════════════════════

class TestVideoMatcher:
    """测试视频匹配器。"""

    @pytest.fixture
    def eagle_index(self):
        files = [
            "MW_VIDEO_260721_000123.mp4",
            "MW_VIDEO_260721_000124.mp4",
            "dragon_rescue_000125.mp4",
        ]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        return indexer.build_index()

    def test_exact_id_match(self, eagle_index):
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("MW_VIDEO_260721_000123")
        assert result.matched is True
        assert result.best_result is not None
        assert result.best_result.method == BindingMethod.EXACT_ID
        assert result.best_result.confidence == 1.0
        assert "MW_VIDEO_260721_000123.mp4" in result.best_result.asset_path

    def test_exact_id_match_not_found(self, eagle_index):
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("MW_VIDEO_260721_999999")
        assert result.matched is False

    def test_filename_match(self, eagle_index):
        """通过序列号 000125 匹配 dragon_rescue_000125.mp4。"""
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("MW_VIDEO_260721_000125", creative_name="dragon_rescue_000125")
        # 精确 ID 不匹配，回退到文件名匹配
        assert result.matched is True
        assert result.best_result is not None
        assert result.best_result.method == BindingMethod.FILENAME
        assert result.best_result.confidence >= 0.95

    def test_filename_match_via_creative_name(self, eagle_index):
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("custom_id_001", creative_name="dragon_rescue_000125")
        assert result.matched is True
        assert result.best_result.method == BindingMethod.FILENAME

    def test_visual_hash_fallback(self, eagle_index):
        """无精确 ID 匹配且无序列号匹配时，回退到视觉 Hash。"""
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("UNKNOWN_ID_999999")
        # 没有序列号可提取，但 visual_hash 会模糊搜索
        # 这里无法匹配（无序列号）
        assert result.matched is False

    def test_match_batch(self, eagle_index):
        matcher = VideoMatcher(eagle_index)
        ids = {
            "MW_VIDEO_260721_000123": "video_123",
            "MW_VIDEO_260721_000124": "video_124",
            "MW_VIDEO_260721_999999": "missing",
        }
        results = matcher.match_batch(ids)
        assert len(results) == 3
        assert results[0].matched is True
        assert results[1].matched is True
        assert results[2].matched is False

    def test_no_match_returns_unmatched(self, eagle_index):
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("MW_VIDEO_260721_999999")
        assert result.matched is False
        assert result.best_result is None
        assert len(result.results) == 1
        assert result.results[0].matched is False

    def test_video_match_result_to_dict(self, eagle_index):
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("MW_VIDEO_260721_000123")
        d = result.to_dict()
        assert d["creative_asset_id"] == "MW_VIDEO_260721_000123"
        assert d["matched"] is True
        assert d["best_result"] is not None


# ═══════════════════════════════════════════════════════════
# Test 3: ImageMatcher
# ═══════════════════════════════════════════════════════════

class TestImageMatcher:
    """测试图片匹配器。"""

    @pytest.fixture
    def lovart_assets(self):
        return [
            LovartAsset(
                generation_id="lovart_gen_001",
                image_path="D:/lovart/outputs/img_000125.png",
                prompt="A witch merging two dragons in a dark forest",
                seed=42,
                model="sdxl",
            ),
            LovartAsset(
                generation_id="lovart_gen_002",
                image_path="D:/lovart/outputs/img_000126.png",
                prompt="A dragon flying over a castle",
                seed=43,
                model="sdxl",
            ),
        ]

    def test_match_by_generation_id(self, lovart_assets):
        matcher = ImageMatcher(lovart_assets)
        result = matcher.match(
            "MW_IMG_260721_000125",
            lovart_generation_id="lovart_gen_001",
        )
        assert result.matched is True
        assert result.best_result.method == BindingMethod.EXACT_ID
        assert result.best_result.confidence == 1.0
        assert result.lovart_asset is not None
        assert result.lovart_asset.generation_id == "lovart_gen_001"

    def test_match_by_serial(self, lovart_assets):
        matcher = ImageMatcher(lovart_assets)
        result = matcher.match("MW_IMG_260721_000125")
        assert result.matched is True
        assert result.best_result.method == BindingMethod.FILENAME
        assert result.lovart_asset is not None

    def test_match_by_serial_via_creative_name(self, lovart_assets):
        matcher = ImageMatcher(lovart_assets)
        result = matcher.match("custom_id", creative_name="dragon_000126")
        assert result.matched is True
        assert result.lovart_asset.generation_id == "lovart_gen_002"

    def test_visual_fallback(self):
        """无序列号匹配时回退到视觉匹配。"""
        assets = [LovartAsset(
            generation_id="gen_001",
            image_path="D:/lovart/outputs/special.png",
        )]
        matcher = ImageMatcher(assets)
        result = matcher.match("MW_IMG_260721_999999")
        assert result.matched is True
        assert result.best_result.method == BindingMethod.VISUAL_HASH
        assert result.best_result.confidence == 0.85

    def test_no_match(self):
        matcher = ImageMatcher([])
        result = matcher.match("MW_IMG_260721_999999")
        assert result.matched is False

    def test_add_lovart_asset(self):
        matcher = ImageMatcher([])
        assert matcher.total_lovart_assets == 0
        matcher.add_lovart_asset(LovartAsset(
            generation_id="new_gen",
            image_path="D:/lovart/outputs/new_000127.png",
        ))
        assert matcher.total_lovart_assets == 1
        result = matcher.match("MW_IMG_260721_000127")
        assert result.matched is True

    def test_match_batch(self, lovart_assets):
        matcher = ImageMatcher(lovart_assets)
        ids = {
            "MW_IMG_260721_000125": "img_125",
            "MW_IMG_260721_999999": "missing",
        }
        results = matcher.match_batch(ids)
        assert len(results) == 2
        assert results[0].matched is True
        assert results[1].matched is False

    def test_image_match_result_to_dict(self, lovart_assets):
        matcher = ImageMatcher(lovart_assets)
        result = matcher.match("MW_IMG_260721_000125")
        d = result.to_dict()
        assert d["creative_asset_id"] == "MW_IMG_260721_000125"
        assert d["matched"] is True


# ═══════════════════════════════════════════════════════════
# Test 4: CreativeAsset 扩展字段
# ═══════════════════════════════════════════════════════════

class TestCreativeAssetExtension:
    """测试 CreativeAsset Phase 3 扩展字段。"""

    def test_has_eagle(self):
        asset = CreativeAsset(eagle_path="D:/eagle/video.mp4")
        assert asset.has_eagle is True
        assert asset.has_lovart is False

    def test_has_lovart(self):
        asset = CreativeAsset(lovart_generation_id="lovart_gen_001")
        assert asset.has_lovart is True
        assert asset.has_eagle is False

    def test_source_type(self):
        asset = CreativeAsset(source_type="EAGLE", matched_confidence=0.95)
        assert asset.source_type == "EAGLE"
        assert asset.matched_confidence == 0.95

    def test_to_dict_includes_new_fields(self):
        asset = CreativeAsset(
            eagle_path="D:/eagle/video.mp4",
            lovart_generation_id="lovart_gen_001",
            source_type="EAGLE",
            matched_confidence=1.0,
        )
        d = asset.to_dict()
        assert d["eagle_path"] == "D:/eagle/video.mp4"
        assert d["lovart_generation_id"] == "lovart_gen_001"
        assert d["source_type"] == "EAGLE"
        assert d["matched_confidence"] == 1.0

    def test_from_dict_backward_compat(self):
        """旧格式（无新字段）仍可正常加载。"""
        d = {"image_url": "http://example.com/img.jpg"}
        asset = CreativeAsset.from_dict(d)
        assert asset.eagle_path == ""
        assert asset.source_type == ""
        assert asset.matched_confidence == 0.0


# ═══════════════════════════════════════════════════════════
# Test 5: AssetBindingEngine
# ═══════════════════════════════════════════════════════════

class TestAssetBindingEngine:
    """测试绑定引擎。"""

    @pytest.fixture
    def eagle_root(self):
        files = [
            "MW_VIDEO_260721_000123.mp4",
            "MW_VIDEO_260721_000124.mp4",
            "MW_IMG_260721_000125.png",
        ]
        return _make_eagle_dir(files)

    @pytest.fixture
    def lovart_assets(self):
        return [
            LovartAsset(
                generation_id="lovart_gen_001",
                image_path="D:/lovart/outputs/img_000125.png",
            ),
        ]

    def test_bind_video_exact_match(self, eagle_root):
        engine = AssetBindingEngine(eagle_root=str(eagle_root))
        entity = _make_entity("MW_VIDEO_260721_000123", CreativeType.VIDEO)

        # Manually bind
        engine._ensure_initialized()
        result = engine._video_matcher.match(entity.creative_asset_id, entity.identity.name)
        engine._apply_video_binding(entity, result)

        assert entity.asset.has_eagle is True
        assert "MW_VIDEO_260721_000123.mp4" in entity.asset.eagle_path
        assert entity.asset.source_type == "EAGLE"
        assert entity.asset.matched_confidence == 1.0

    def test_bind_image_serial_match(self, eagle_root, lovart_assets):
        engine = AssetBindingEngine(
            eagle_root=str(eagle_root),
            lovart_assets=lovart_assets,
        )
        entity = _make_entity("MW_IMG_260721_000125", CreativeType.IMAGE)

        engine._ensure_initialized()
        result = engine._image_matcher.match(entity.creative_asset_id, entity.identity.name)
        engine._apply_image_binding(entity, result)

        assert entity.asset.has_lovart is True
        assert entity.asset.source_type == "LOVART"
        assert entity.asset.lovart_generation_id == "lovart_gen_001"

    def test_bind_all_report(self, eagle_root, lovart_assets):
        """测试 bind_all() 生成报告。"""
        engine = AssetBindingEngine(
            eagle_root=str(eagle_root),
            lovart_assets=lovart_assets,
        )
        report = engine.bind_all()
        assert isinstance(report, AssetBindingReport)
        assert report.total_entities >= 0

    def test_bind_all_no_entities(self, eagle_root):
        engine = AssetBindingEngine(eagle_root=str(eagle_root))
        report = engine.bind_all()
        assert report.total_entities == 0
        assert "No CreativeEntities" in report.errors[0]

    def test_report_to_summary(self, eagle_root):
        report = AssetBindingReport(
            total_entities=10,
            total_matched=9,
            total_missing=1,
            video_total=7,
            video_matched=7,
            video_match_rate=1.0,
            image_total=3,
            image_matched=2,
            image_match_rate=0.6667,
            by_method={"exact_id": 7, "filename": 2},
        )
        summary = report.to_summary()
        assert "10" in summary
        assert "9" in summary
        assert "100.0%" in summary

    def test_report_to_dict(self):
        report = AssetBindingReport(
            total_entities=5,
            total_matched=4,
            total_missing=1,
            video_total=3,
            video_matched=3,
            image_total=2,
            image_matched=1,
            by_method={"exact_id": 3, "filename": 1},
        )
        d = report.to_dict()
        assert d["total_entities"] == 5
        assert d["total_matched"] == 4


# ═══════════════════════════════════════════════════════════
# Test 6: AssetBindingValidator
# ═══════════════════════════════════════════════════════════

class TestAssetBindingValidator:
    """测试绑定质量验证器。"""

    def test_validate_good_report(self):
        report = AssetBindingReport(
            total_entities=100,
            total_matched=95,
            total_missing=5,
            video_total=70,
            video_matched=68,
            video_match_rate=0.9714,
            image_total=30,
            image_matched=27,
            image_match_rate=0.9,
            by_method={
                "exact_id": 80,
                "filename": 10,
                "visual_hash": 5,
            },
            results=[
                AssetBindingResult(
                    creative_asset_id="MW_VID_001",
                    matched=True,
                    confidence=1.0,
                    method=BindingMethod.EXACT_ID,
                ),
                AssetBindingResult(
                    creative_asset_id="MW_VID_002",
                    matched=True,
                    confidence=0.5,
                    method=BindingMethod.VISUAL_HASH,
                ),
            ],
        )
        validator = AssetBindingValidator()
        quality = validator.validate(report)
        assert quality.total_entities == 100
        assert quality.total_matched == 95
        assert quality.exact_id_count == 80
        assert quality.filename_count == 10
        assert quality.visual_hash_count == 5
        assert quality.high_confidence_count == 1
        assert quality.low_confidence_count == 1

    def test_validate_low_match_rate_critical(self):
        report = AssetBindingReport(
            total_entities=100,
            total_matched=50,
            total_missing=50,
            by_method={"exact_id": 30, "visual_hash": 20},
            results=[
                AssetBindingResult(
                    creative_asset_id="X",
                    matched=True,
                    confidence=1.0,
                    method=BindingMethod.EXACT_ID,
                ),
            ],
        )
        validator = AssetBindingValidator()
        quality = validator.validate(report)
        assert len(quality.critical) > 0

    def test_validate_too_many_fallback_warning(self):
        report = AssetBindingReport(
            total_entities=100,
            total_matched=90,
            by_method={"exact_id": 20, "filename": 30, "visual_hash": 40},
            results=[
                AssetBindingResult(
                    creative_asset_id="X",
                    matched=True,
                    confidence=1.0,
                    method=BindingMethod.EXACT_ID,
                )
                for _ in range(90)
            ],
        )
        validator = AssetBindingValidator()
        quality = validator.validate(report)
        assert len(quality.warnings) > 0

    def test_quality_report_to_summary(self):
        report = AssetBindingReport(
            total_entities=10,
            total_matched=9,
            total_missing=1,
            by_method={"exact_id": 9},
            results=[
                AssetBindingResult(
                    creative_asset_id="MW_VID_001",
                    matched=True,
                    confidence=1.0,
                    method=BindingMethod.EXACT_ID,
                ),
            ],
        )
        validator = AssetBindingValidator()
        quality = validator.validate(report)
        summary = quality.to_summary()
        assert "10" in summary
        assert "9" in summary

    def test_quality_report_to_dict(self):
        report = AssetBindingReport(
            total_entities=5,
            total_matched=5,
            by_method={"exact_id": 5},
            results=[],
        )
        validator = AssetBindingValidator()
        quality = validator.validate(report)
        d = quality.to_dict()
        assert d["total_entities"] == 5
        assert d["total_matched"] == 5


# ═══════════════════════════════════════════════════════════
# Test 7: 模型序列化
# ═══════════════════════════════════════════════════════════

class TestModelSerialization:
    """测试数据模型序列化。"""

    def test_eagle_asset_to_dict_from_dict(self):
        asset = EagleAsset(
            filename="test.mp4",
            path="D:/eagle/test.mp4",
            creative_asset_id="MW_VID_001",
            duration=30.5,
            resolution="1080x1920",
            file_hash="abc123",
            file_size=1024000,
        )
        d = asset.to_dict()
        a2 = EagleAsset.from_dict(d)
        assert a2.filename == "test.mp4"
        assert a2.creative_asset_id == "MW_VID_001"
        assert a2.duration == 30.5

    def test_lovart_asset_to_dict_from_dict(self):
        asset = LovartAsset(
            generation_id="gen_001",
            image_path="D:/lovart/img.png",
            image_url="http://example.com/img.png",
            prompt="A dragon",
            seed=42,
            model="sdxl",
        )
        d = asset.to_dict()
        a2 = LovartAsset.from_dict(d)
        assert a2.generation_id == "gen_001"
        assert a2.seed == 42

    def test_asset_binding_result_to_dict_from_dict(self):
        result = AssetBindingResult(
            creative_asset_id="MW_VID_001",
            source=AssetSourceType.EAGLE,
            matched=True,
            confidence=1.0,
            method=BindingMethod.EXACT_ID,
            asset_path="D:/eagle/test.mp4",
            asset_filename="test.mp4",
        )
        d = result.to_dict()
        r2 = AssetBindingResult.from_dict(d)
        assert r2.creative_asset_id == "MW_VID_001"
        assert r2.matched is True
        assert r2.confidence == 1.0

    def test_binding_result_confidence_properties(self):
        high = AssetBindingResult(matched=True, confidence=0.95)
        possible = AssetBindingResult(matched=True, confidence=0.7)
        low = AssetBindingResult(matched=True, confidence=0.3)
        unmatched = AssetBindingResult(matched=False, confidence=0.0)

        assert high.is_high_confidence is True
        assert possible.is_possible_match is True
        assert possible.is_high_confidence is False
        assert low.is_low_confidence is True
        assert unmatched.is_high_confidence is False


# ═══════════════════════════════════════════════════════════
# Test 8: 异常/边界处理
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:
    """测试异常和边界情况。"""

    def test_empty_eagle_dir(self):
        root = _make_eagle_dir([])
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        matcher = VideoMatcher(index)
        result = matcher.match("MW_VIDEO_260721_000123")
        assert result.matched is False

    def test_corrupt_filename_no_pattern(self):
        files = ["random_file.mp4", "no_pattern_here.mov"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        assert index.total == 2
        # 没有 creative_asset_id，但仍被索引
        assert index.find_by_id("random_file") is None

    def test_empty_image_matcher(self):
        matcher = ImageMatcher([])
        result = matcher.match("any_id")
        assert result.matched is False
        assert result.best_result is None

    def test_creative_asset_has_no_video_initially(self):
        entity = _make_entity("MW_VID_001", CreativeType.VIDEO)
        assert entity.asset.has_eagle is False
        assert entity.asset.has_video is False

    def test_entity_identity_type_affects_is_video(self):
        video_entity = _make_entity("MW_VID_001", CreativeType.VIDEO)
        image_entity = _make_entity("MW_IMG_001", CreativeType.IMAGE)
        assert video_entity.is_video is True
        assert video_entity.is_image is False
        assert image_entity.is_video is False
        assert image_entity.is_image is True

    def test_eagle_asset_repr(self):
        indexer = EagleIndexer("D:/eagle")
        assert "EagleIndexer" in repr(indexer)

    def test_video_matcher_repr(self):
        files = ["MW_VID_001.mp4"]
        root = _make_eagle_dir(files)
        indexer = EagleIndexer(str(root))
        index = indexer.build_index()
        matcher = VideoMatcher(index)
        assert "VideoMatcher" in repr(matcher)

    def test_image_matcher_repr(self):
        matcher = ImageMatcher([])
        assert "ImageMatcher" in repr(matcher)

    def test_asset_binding_engine_repr(self):
        engine = AssetBindingEngine(eagle_root="D:/eagle")
        assert "AssetBindingEngine" in repr(engine)