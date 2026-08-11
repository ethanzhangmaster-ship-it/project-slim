"""E11.3.1 — Vision Asset Loader 测试。

测试范围：
  - VisionAsset: 数据模型 + 序列化
  - VisionAssetValidator: 文件/格式/元数据验证
  - VisionAssetLoader: CreativeEntity → VisionAsset 转换
  - 加载规则: video_path/source_type/confidence 过滤
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_ops.creative_vision_runtime.vision_asset.models import (
    VisionAsset,
    VisionAssetStatus,
)
from market_ops.creative_vision_runtime.vision_asset.validator import (
    VisionAssetValidator,
    SUPPORTED_VIDEO_FORMATS,
)
from market_ops.creative_vision_runtime.vision_asset.loader import (
    VisionAssetLoader,
)
from market_ops.creative_repository.models.creative_entity import (
    CreativeEntity,
    CreativeIdentity,
    CreativeSources,
    CreativePerformance,
    CreativeAsset,
    CreativeType,
    AcquisitionData,
    RevenueData,
)


# ════════════════════════════════════════════════════════════════════
# VisionAsset
# ════════════════════════════════════════════════════════════════════

class TestVisionAsset:
    """VisionAsset 数据模型测试。"""

    def test_create_minimal(self):
        asset = VisionAsset(
            creative_id="111",
            video_path="Y:/Eagle/P4-v2601536.mp4",
            eagle_filename="P4-v2601536.mp4",
            source_type="EAGLE",
        )
        assert asset.creative_id == "111"
        assert asset.video_path == "Y:/Eagle/P4-v2601536.mp4"
        assert asset.source_type == "EAGLE"
        assert asset.status == VisionAssetStatus.PENDING.value
        assert asset.asset_id.startswith("va_")

    def test_create_full(self):
        asset = VisionAsset(
            creative_id="111",
            creative_asset_id="MW_VID_260721_000001",
            video_path="Y:/Eagle/P4-v2601536.mp4",
            eagle_filename="P4-v2601536.mp4",
            source_type="EAGLE",
            match_method="a_number",
            match_confidence=1.0,
            performance={
                "spend": 500,
                "revenue": 1500,
                "roas": 3.0,
                "impressions": 5000,
            },
            lifecycle_status="WINNER",
        )
        assert asset.is_winner
        assert asset.is_eagle_source
        assert asset.has_video
        assert asset.roas == 3.0
        assert asset.spend == 500
        assert asset.impressions == 5000

    def test_to_dict(self):
        asset = VisionAsset(
            creative_id="111",
            video_path="Y:/Eagle/test.mp4",
            eagle_filename="test.mp4",
            source_type="EAGLE",
            match_confidence=1.0,
        )
        d = asset.to_dict()
        assert d["creative_id"] == "111"
        assert d["video_path"] == "Y:/Eagle/test.mp4"
        assert d["match_confidence"] == 1.0

    def test_from_dict(self):
        data = {
            "asset_id": "va_test",
            "creative_id": "222",
            "video_path": "Y:/Eagle/test.mp4",
            "eagle_filename": "test.mp4",
            "source_type": "EAGLE",
            "match_confidence": 0.9,
            "performance": {"roas": 2.0},
            "lifecycle_status": "WINNER",
            "status": "validated",
        }
        asset = VisionAsset.from_dict(data)
        assert asset.creative_id == "222"
        assert asset.match_confidence == 0.9
        assert asset.is_winner
        assert asset.status == "validated"

    def test_properties_no_performance(self):
        asset = VisionAsset(
            creative_id="111",
            video_path="Y:/Eagle/test.mp4",
            eagle_filename="test.mp4",
            source_type="EAGLE",
        )
        assert asset.roas == 0.0
        assert asset.spend == 0.0
        assert asset.has_performance is False

    def test_not_eagle_source(self):
        asset = VisionAsset(
            source_type="FACEBOOK",
        )
        assert asset.is_eagle_source is False

    def test_repr(self):
        asset = VisionAsset(
            creative_id="111",
            source_type="EAGLE",
        )
        r = repr(asset)
        assert "111" in r
        assert "EAGLE" in r

    def test_vision_asset_status_values(self):
        assert VisionAssetStatus.PENDING.value == "pending"
        assert VisionAssetStatus.VALIDATED.value == "validated"
        assert VisionAssetStatus.INVALID.value == "invalid"
        assert VisionAssetStatus.FRAMES_EXTRACTED.value == "frames_extracted"
        assert VisionAssetStatus.DNA_READY.value == "dna_ready"


# ════════════════════════════════════════════════════════════════════
# VisionAssetValidator
# ════════════════════════════════════════════════════════════════════

class TestVisionAssetValidator:
    """VisionAssetValidator 验证测试。"""

    @pytest.fixture
    def validator(self):
        return VisionAssetValidator(check_files=True)

    def test_valid_asset(self, validator, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("fake video content")

        asset = VisionAsset(
            creative_id="111",
            video_path=str(video),
            eagle_filename="test.mp4",
            source_type="EAGLE",
        )
        ok, errors = validator.validate(asset)
        assert ok is True
        assert len(errors) == 0

    def test_missing_metadata(self, validator):
        asset = VisionAsset()
        ok, errors = validator.validate(asset)
        assert ok is False
        assert len(errors) >= 2  # missing creative_id, missing video_path, missing eagle_filename

    def test_file_not_found(self, validator):
        asset = VisionAsset(
            creative_id="111",
            video_path="Z:/nonexistent/file.mp4",
            eagle_filename="file.mp4",
            source_type="EAGLE",
        )
        ok, errors = validator.validate(asset)
        assert ok is False
        assert any("file not found" in e for e in errors)

    def test_empty_file(self, validator, tmp_path):
        video = tmp_path / "empty.mp4"
        video.write_text("")  # empty file

        asset = VisionAsset(
            creative_id="111",
            video_path=str(video),
            eagle_filename="empty.mp4",
            source_type="EAGLE",
        )
        ok, errors = validator.validate(asset)
        assert ok is False
        assert any("empty" in e for e in errors)

    def test_unsupported_format(self, validator, tmp_path):
        video = tmp_path / "test.txt"
        video.write_text("not a video")

        asset = VisionAsset(
            creative_id="111",
            video_path=str(video),
            eagle_filename="test.txt",
            source_type="EAGLE",
        )
        ok, errors = validator.validate(asset)
        assert ok is False
        assert any("format" in e for e in errors)

    def test_validate_path(self, validator, tmp_path):
        video = tmp_path / "good.mp4"
        video.write_text("content")

        ok, _ = validator.validate_path(str(video))
        assert ok is True

    def test_is_valid_video(self, validator, tmp_path):
        video = tmp_path / "good.mp4"
        video.write_text("content")

        assert validator.is_valid_video(str(video)) is True
        assert validator.is_valid_video("Z:/nonexistent.mp4") is False

    def test_is_supported_format(self, validator):
        assert validator.is_supported_format("test.mp4") is True
        assert validator.is_supported_format("test.mov") is True
        assert validator.is_supported_format("test.webm") is True
        assert validator.is_supported_format("test.txt") is False
        assert validator.is_supported_format("test.jpg") is False

    def test_supported_formats_complete(self):
        assert ".mp4" in SUPPORTED_VIDEO_FORMATS
        assert ".mov" in SUPPORTED_VIDEO_FORMATS
        assert ".webm" in SUPPORTED_VIDEO_FORMATS
        assert ".avi" in SUPPORTED_VIDEO_FORMATS
        assert ".mkv" in SUPPORTED_VIDEO_FORMATS

    def test_skip_file_check(self):
        validator = VisionAssetValidator(check_files=False)
        asset = VisionAsset(
            creative_id="111",
            video_path="Z:/nonexistent.mp4",
            eagle_filename="test.mp4",
            source_type="EAGLE",
        )
        ok, errors = validator.validate(asset)
        assert ok is True  # 跳过文件检查，只检查元数据

    def test_repr(self, validator):
        assert "VisionAssetValidator" in repr(validator)


# ════════════════════════════════════════════════════════════════════
# VisionAssetLoader
# ════════════════════════════════════════════════════════════════════

class TestVisionAssetLoader:
    """VisionAssetLoader 加载测试。"""

    @pytest.fixture
    def loader(self, tmp_path):
        creative_root = tmp_path / "creatives"
        creative_root.mkdir()
        return VisionAssetLoader(
            creative_storage_root=str(creative_root),
            index_path=str(tmp_path / "vision_asset_index.json"),
        )

    def _create_entity(self, loader, creative_asset_id, video_path="", **kwargs):
        """创建 CreativeEntity 并写入磁盘。"""
        entity_dir = loader._root / creative_asset_id
        entity_dir.mkdir(parents=True, exist_ok=True)

        entity = CreativeEntity(
            creative_asset_id=creative_asset_id,
            identity=CreativeIdentity(
                name=kwargs.get("name", f"test_{creative_asset_id}"),
                type=CreativeType.VIDEO,
            ),
            sources=CreativeSources(
                facebook_id=kwargs.get("creative_id", "111"),
            ),
            performance=CreativePerformance(
                acquisition=AcquisitionData(
                    spend=kwargs.get("spend", 500),
                    impressions=kwargs.get("impressions", 5000),
                    installs=kwargs.get("installs", 200),
                ),
                revenue=RevenueData(
                    iap_d7=kwargs.get("iap_d7", 1000),
                    iap_d30=kwargs.get("iap_d30", 3000),
                ),
            ),
            asset=CreativeAsset(
                video_path=video_path or kwargs.get("eagle_path", ""),
                eagle_filename=kwargs.get("eagle_filename", f"P4-{creative_asset_id}.mp4"),
                source_type=kwargs.get("source_type", "EAGLE"),
                match_method=kwargs.get("match_method", "a_number"),
                matched_confidence=kwargs.get("confidence", 1.0),
            ),
        )

        entity_path = entity_dir / "entity.json"
        with open(entity_path, "w", encoding="utf-8") as f:
            json.dump(entity.to_dict(), f, indent=2)

        return entity

    def test_load_valid_entity(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("fake video")

        entity = self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path=str(video),
            eagle_filename="P4-v2601536.mp4",
        )
        asset = loader.load(entity)
        assert asset is not None
        assert asset.creative_asset_id == "MW_VID_260721_000001"
        assert asset.eagle_filename == "P4-v2601536.mp4"
        assert asset.source_type == "EAGLE"
        assert asset.match_method == "a_number"
        assert asset.status == VisionAssetStatus.VALIDATED.value
        assert asset.roas > 0

    def test_load_skip_no_video_path(self, loader):
        entity = self._create_entity(
            loader,
            "MW_VID_260721_000002",
            video_path="",  # 无视频路径
        )
        asset = loader.load(entity)
        assert asset is None

    def test_load_skip_non_eagle_source(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("fake")

        entity = self._create_entity(
            loader,
            "MW_VID_260721_000003",
            video_path=str(video),
            source_type="FACEBOOK",  # 非 EAGLE
        )
        asset = loader.load(entity)
        assert asset is None

    def test_load_skip_low_confidence(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("fake")

        entity = self._create_entity(
            loader,
            "MW_VID_260721_000004",
            video_path=str(video),
            confidence=0.3,  # < 0.5
        )
        asset = loader.load(entity)
        assert asset is None

    def test_load_invalid_file(self, loader):
        entity = self._create_entity(
            loader,
            "MW_VID_260721_000005",
            video_path="Z:/nonexistent.mp4",
        )
        asset = loader.load(entity)
        assert asset is not None  # 仍然加载，但标记为 invalid
        assert asset.status == VisionAssetStatus.INVALID.value
        assert "file not found" in asset.error_message

    def test_load_from_entity_json(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("content")

        self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path=str(video),
            eagle_filename="P4-v2601536.mp4",
        )

        entity_dir = loader._root / "MW_VID_260721_000001"
        asset = loader.load_from_entity_json(entity_dir)
        assert asset is not None
        assert asset.creative_asset_id == "MW_VID_260721_000001"

    def test_load_all(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("content")

        for i in range(3):
            self._create_entity(
                loader,
                f"MW_VID_260721_00000{i}",
                video_path=str(video),
                eagle_filename=f"P4-v260153{i}.mp4",
            )

        assets = loader.load_all()
        assert len(assets) == 3
        assert loader.loaded_count == 3

    def test_load_all_saves_index(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("content")

        self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path=str(video),
            eagle_filename="P4-v2601536.mp4",
        )

        loader.load_all()
        index_path = loader._index_path
        assert index_path.exists()

        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        assert index["total"] == 1

    def test_load_empty_root(self, loader):
        assets = loader.load_all()
        assert len(assets) == 0

    def test_get_index(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("content")

        entity = self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path=str(video),
            eagle_filename="P4-v2601536.mp4",
        )
        loader.load(entity)

        index = loader.get_index()
        assert "MW_VID_260721_000001" in index
        assert index["MW_VID_260721_000001"]["is_valid"] is True

    def test_get_valid_assets(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("content")

        self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path=str(video),
            eagle_filename="P4-v2601536.mp4",
        )

        valid = loader.get_valid_assets()
        assert len(valid) == 1

    def test_get_invalid_assets(self, loader, tmp_path):
        self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path="Z:/nonexistent.mp4",
            eagle_filename="P4-v2601536.mp4",
        )

        invalid = loader.get_invalid_assets()
        assert len(invalid) == 1

    def test_performance_extraction(self, loader, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("content")

        entity = self._create_entity(
            loader,
            "MW_VID_260721_000001",
            video_path=str(video),
            eagle_filename="P4-v2601536.mp4",
            spend=1000,
            impressions=10000,
            installs=400,
            iap_d7=2000,
            iap_d30=5000,
        )
        asset = loader.load(entity)
        assert asset is not None
        assert asset.performance["spend"] == 1000
        assert asset.performance["impressions"] == 10000
        assert asset.performance["installs"] == 400
        assert asset.performance["revenue_d7"] > 0
        assert asset.performance["revenue_d30"] > 0

    def test_repr(self, loader):
        assert "VisionAssetLoader" in repr(loader)


# ════════════════════════════════════════════════════════════════════
# Integration: Loader + Validator
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Loader + Validator 集成测试。"""

    def test_full_load_validate_flow(self, tmp_path):
        """完整流程：CreativeEntity → VisionAsset → 验证 → 索引。"""
        creative_root = tmp_path / "creatives"
        creative_root.mkdir()

        video = tmp_path / "test.mp4"
        video.write_text("fake video content")

        loader = VisionAssetLoader(
            creative_storage_root=str(creative_root),
            index_path=str(tmp_path / "index.json"),
        )

        # 创建 entity
        entity_dir = creative_root / "MW_VID_260721_000001"
        entity_dir.mkdir()
        entity = CreativeEntity(
            creative_asset_id="MW_VID_260721_000001",
            identity=CreativeIdentity(name="test", type=CreativeType.VIDEO),
            performance=CreativePerformance(
                acquisition=AcquisitionData(spend=500, impressions=5000, installs=200),
            ),
            asset=CreativeAsset(
                video_path=str(video),
                eagle_filename="P4-v2601536.mp4",
                source_type="EAGLE",
                match_method="a_number",
                matched_confidence=1.0,
            ),
        )
        with open(entity_dir / "entity.json", "w", encoding="utf-8") as f:
            json.dump(entity.to_dict(), f, indent=2)

        # 加载
        asset = loader.load(entity)
        assert asset is not None
        assert asset.status == VisionAssetStatus.VALIDATED.value
        assert asset.creative_asset_id == "MW_VID_260721_000001"
        assert asset.eagle_filename == "P4-v2601536.mp4"
        assert asset.spend == 500
        assert asset.impressions == 5000

        # 索引
        index = loader.get_index()
        assert "MW_VID_260721_000001" in index
        assert index["MW_VID_260721_000001"]["is_valid"] is True

        # 验证有效资产
        valid = loader.get_valid_assets()
        assert len(valid) == 1