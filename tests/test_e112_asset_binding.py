"""E11.2 — Asset Binding Layer 测试。

测试范围：
  - CreativeAssetReference 模型（to_dict/from_dict/属性）
  - AssetBindingRepository CRUD
  - CreativeMappingLoader 加载/迁移
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from market_ops.creative_repository.assets import (
    CreativeAssetReference,
    AssetSource,
    AssetType,
    MatchMethod,
    AssetBindingRepository,
    CreativeMappingLoader,
    AssetBindingMaterializer,
    IdentityResolver,
)


# ════════════════════════════════════════════════════════════════════
# CreativeAssetReference
# ════════════════════════════════════════════════════════════════════

class TestCreativeAssetReference:
    """CreativeAssetReference 数据模型测试。"""

    def test_default_construction(self):
        ref = CreativeAssetReference()
        assert ref.creative_id == ""
        assert ref.asset_type == AssetType.VIDEO
        assert ref.source == AssetSource.EAGLE
        assert ref.confidence == 0.0
        assert ref.is_bound is False

    def test_binding_with_a_number(self):
        ref = CreativeAssetReference(
            creative_id="2453146861847495",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="P4-v2601536-mg-2d.mp4",
            local_path="Y:\\Eagle\\images\\P4-v2601536-mg-2d.mp4",
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
            a_number="536",
            eagle_v_number="v2601536",
        )
        assert ref.is_bound
        assert ref.is_high_confidence
        assert ref.is_eagle

    def test_low_confidence_not_bound(self):
        ref = CreativeAssetReference(
            creative_id="123",
            local_path="Y:\\Eagle\\test.mp4",
            confidence=0.5,
        )
        assert ref.is_bound is False

    def test_zero_confidence_not_bound(self):
        ref = CreativeAssetReference(
            creative_id="123",
            local_path="Y:\\Eagle\\test.mp4",
            confidence=0.0,
        )
        assert ref.is_bound is False

    def test_to_dict_roundtrip(self):
        ref = CreativeAssetReference(
            creative_id="123456",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="test.mp4",
            local_path="Y:\\Eagle\\test.mp4",
            match_method=MatchMethod.A_NUMBER,
            confidence=0.95,
            spend=100.0,
            revenue=200.0,
            roas=2.0,
            impressions=5000,
            clicks=150,
            installs=10,
            ad_name="P4-IOS-T1-A536-0707",
            a_number="536",
            eagle_v_number="v2601536",
            bound_at="2026-01-01T00:00:00",
        )
        d = ref.to_dict()
        ref2 = CreativeAssetReference.from_dict(d)

        assert ref2.creative_id == ref.creative_id
        assert ref2.asset_type == ref.asset_type
        assert ref2.source == ref.source
        assert ref2.eagle_filename == ref.eagle_filename
        assert ref2.local_path == ref.local_path
        assert ref2.match_method == ref.match_method
        assert ref2.confidence == ref.confidence
        assert ref2.spend == ref.spend
        assert ref2.revenue == ref.revenue
        assert ref2.roas == ref.roas
        assert ref2.a_number == "536"
        assert ref2.eagle_v_number == "v2601536"

    def test_to_creative_asset_video(self):
        ref = CreativeAssetReference(
            creative_id="123",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="test.mp4",
            local_path="Y:\\Eagle\\test.mp4",
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
        )
        asset = ref.to_creative_asset()
        assert asset["eagle_path"] == "Y:\\Eagle\\test.mp4"
        assert asset["eagle_filename"] == "test.mp4"
        assert asset["source_type"] == "EAGLE"
        assert asset["matched_confidence"] == 1.0
        assert asset["match_method"] == "a_number"
        assert asset["video_path"] == "Y:\\Eagle\\test.mp4"

    def test_to_creative_asset_image_no_video_path(self):
        ref = CreativeAssetReference(
            creative_id="123",
            asset_type=AssetType.IMAGE,
            source=AssetSource.EAGLE,
            eagle_filename="test.png",
            local_path="Y:\\Eagle\\test.png",
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
        )
        asset = ref.to_creative_asset()
        assert "video_path" not in asset

    def test_is_high_confidence_boundary(self):
        assert CreativeAssetReference(confidence=0.95).is_high_confidence
        assert not CreativeAssetReference(confidence=0.94).is_high_confidence

    def test_repr(self):
        ref = CreativeAssetReference(
            creative_id="123",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            confidence=0.95,
        )
        r = repr(ref)
        assert "123" in r
        assert "video" in r
        assert "eagle" in r


# ════════════════════════════════════════════════════════════════════
# AssetBindingRepository
# ════════════════════════════════════════════════════════════════════

class TestAssetBindingRepository:
    """AssetBindingRepository 存储层测试。"""

    @pytest.fixture
    def repo(self):
        with tempfile.TemporaryDirectory() as td:
            yield AssetBindingRepository(td)

    def test_save_and_load(self, repo):
        ref = CreativeAssetReference(
            creative_id="123",
            confidence=1.0,
            local_path="/tmp/test.mp4",
        )
        repo.save(ref)

        loaded = repo.load("123")
        assert loaded is not None
        assert loaded.creative_id == "123"
        assert loaded.confidence == 1.0
        assert loaded.is_bound

    def test_load_nonexistent(self, repo):
        assert repo.load("nonexistent") is None

    def test_exists(self, repo):
        ref = CreativeAssetReference(creative_id="456")
        assert not repo.exists("456")
        repo.save(ref)
        assert repo.exists("456")

    def test_count(self, repo):
        assert repo.count() == 0
        for i in range(5):
            repo.save(CreativeAssetReference(creative_id=str(i)))
        assert repo.count() == 5

    def test_delete(self, repo):
        ref = CreativeAssetReference(creative_id="789")
        repo.save(ref)
        assert repo.exists("789")
        repo.delete("789")
        assert not repo.exists("789")

    def test_save_batch(self, repo):
        refs = [CreativeAssetReference(creative_id=str(i)) for i in range(10)]
        count = repo.save_batch(refs)
        assert count == 10
        assert repo.count() == 10

    def test_load_all(self, repo):
        for i in range(3):
            repo.save(CreativeAssetReference(creative_id=str(i)))
        all_refs = repo.load_all()
        assert len(all_refs) == 3

    def test_load_all_by_source(self, repo):
        repo.save(CreativeAssetReference(creative_id="1", source=AssetSource.EAGLE))
        repo.save(CreativeAssetReference(creative_id="2", source=AssetSource.FACEBOOK))
        repo.save(CreativeAssetReference(creative_id="3", source=AssetSource.EAGLE))

        eagle = repo.load_all_by_source("eagle")
        assert len(eagle) == 2

    def test_load_all_by_confidence(self, repo):
        repo.save(CreativeAssetReference(creative_id="1", confidence=0.9))
        repo.save(CreativeAssetReference(creative_id="2", confidence=0.7))
        repo.save(CreativeAssetReference(creative_id="3", confidence=1.0))

        high = repo.load_all_by_confidence(0.85)
        assert len(high) == 2

    def test_save_without_creative_id(self, repo):
        ref = CreativeAssetReference()
        with pytest.raises(ValueError, match="creative_id"):
            repo.save(ref)

    def test_to_summary(self, repo):
        repo.save(CreativeAssetReference(
            creative_id="1", confidence=1.0, match_method=MatchMethod.A_NUMBER
        ))
        repo.save(CreativeAssetReference(
            creative_id="2", confidence=0.8, match_method=MatchMethod.FILENAME
        ))
        summary = repo.to_summary()
        assert summary["total"] == 2
        assert summary["by_source"]["eagle"] == 2
        assert summary["by_method"]["a_number"] == 1
        assert summary["by_method"]["filename"] == 1
        assert summary["high_confidence"] == 1

    def test_repr(self, repo):
        assert "AssetBindingRepository" in repr(repo)


# ════════════════════════════════════════════════════════════════════
# CreativeMappingLoader
# ════════════════════════════════════════════════════════════════════

class TestCreativeMappingLoader:
    """CreativeMappingLoader 迁移测试。"""

    @pytest.fixture
    def sample_mapping(self):
        """创建一个最小 creative_mapping_v2.json 结构。"""
        return {
            "total_fb_videos": 3,
            "matched": 3,
            "unmatched": 0,
            "unique_eagle_matched": 2,
            "matched_spend": 300.0,
            "unmatched_spend": 0.0,
            "match_records": [
                {
                    "creative_id": "111",
                    "creative_type": "video",
                    "ad_name": "P4-IOS-T1-A536-0707",
                    "a_number": "536",
                    "eagle_v_number": "v2601536",
                    "eagle_filename": "P4-v2601536-mg-2d.mp4",
                    "eagle_filepath": "Y:\\Eagle\\images\\P4-v2601536-mg-2d.mp4",
                    "match_method": "A-number",
                    "confidence": 1.0,
                    "spend": 100.0,
                    "revenue": 200.0,
                    "roas": 2.0,
                    "impressions": 5000,
                    "clicks": 150,
                    "installs": 10,
                },
                {
                    "creative_id": "222",
                    "creative_type": "video",
                    "ad_name": "P4-AND-T1-A537-0707",
                    "a_number": "537",
                    "eagle_v_number": "v2601537",
                    "eagle_filename": "P4-v2601537-mg-2d.mp4",
                    "eagle_filepath": "Y:\\Eagle\\images\\P4-v2601537-mg-2d.mp4",
                    "match_method": "A-number",
                    "confidence": 1.0,
                    "spend": 200.0,
                    "revenue": 400.0,
                    "roas": 2.0,
                    "impressions": 10000,
                    "clicks": 300,
                    "installs": 20,
                },
                {
                    "creative_id": "333",
                    "creative_type": "video",
                    "ad_name": "P4-video2-0707",
                    "a_number": "",
                    "eagle_v_number": "",
                    "eagle_filename": "P4-video2.mp4",
                    "eagle_filepath": "Y:\\Eagle\\images\\P4-video2.mp4",
                    "match_method": "video_number",
                    "confidence": 0.8,
                    "spend": 0,
                    "revenue": 0,
                    "roas": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "installs": 0,
                },
            ],
        }

    def test_load_parses_a_number_method(self, sample_mapping, tmp_path):
        mapping_path = tmp_path / "creative_mapping_v2.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(sample_mapping, f)

        loader = CreativeMappingLoader()
        refs = loader.load(str(mapping_path))

        assert len(refs) == 3
        assert loader.error_count == 0

        # A-number record
        ref1 = refs[0]
        assert ref1.creative_id == "111"
        assert ref1.match_method == MatchMethod.A_NUMBER
        assert ref1.a_number == "536"
        assert ref1.eagle_v_number == "v2601536"
        assert ref1.confidence == 1.0
        assert ref1.spend == 100.0
        assert ref1.revenue == 200.0
        assert ref1.roas == 2.0
        assert ref1.is_bound

        # video_number record
        ref3 = refs[2]
        assert ref3.match_method == MatchMethod.VIDEO_NUMBER
        assert ref3.confidence == 0.8
        assert ref3.is_bound is False  # confidence < 0.85

    def test_load_missing_file(self):
        loader = CreativeMappingLoader()
        refs = loader.load("nonexistent.json")
        assert len(refs) == 0
        assert loader.error_count == 1

    def test_migrate_dry_run(self, sample_mapping, tmp_path):
        mapping_path = tmp_path / "creative_mapping_v2.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(sample_mapping, f)

        repo_dir = tmp_path / "creatives"
        repo = AssetBindingRepository(str(repo_dir))
        loader = CreativeMappingLoader()

        report = loader.migrate(str(mapping_path), repo, dry_run=True)
        assert report["total"] == 3
        assert report["written"] == 0  # dry run
        assert repo.count() == 0

    def test_migrate_write(self, sample_mapping, tmp_path):
        mapping_path = tmp_path / "creative_mapping_v2.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(sample_mapping, f)

        repo_dir = tmp_path / "creatives"
        repo = AssetBindingRepository(str(repo_dir))
        loader = CreativeMappingLoader()

        report = loader.migrate(str(mapping_path), repo, dry_run=False)
        assert report["total"] == 3
        assert report["written"] == 3
        assert report["errors"] == 0
        assert repo.count() == 3

        # Verify one record
        loaded = repo.load("111")
        assert loaded is not None
        assert loaded.match_method == MatchMethod.A_NUMBER
        assert loaded.a_number == "536"

    def test_migrate_skip_existing(self, sample_mapping, tmp_path):
        mapping_path = tmp_path / "creative_mapping_v2.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(sample_mapping, f)

        repo_dir = tmp_path / "creatives"
        repo = AssetBindingRepository(str(repo_dir))
        loader = CreativeMappingLoader()

        # First migration
        report1 = loader.migrate(str(mapping_path), repo)
        assert report1["written"] == 3

        # Second migration should skip all
        report2 = loader.migrate(str(mapping_path), repo)
        assert report2["written"] == 0
        assert report2["skipped"] == 3

    def test_parse_unknow_match_method(self, tmp_path):
        mapping = {
            "total_fb_videos": 1,
            "matched": 0,
            "unmatched": 1,
            "unique_eagle_matched": 0,
            "matched_spend": 0.0,
            "unmatched_spend": 50.0,
            "match_records": [
                {
                    "creative_id": "999",
                    "creative_type": "video",
                    "ad_name": "unknown",
                    "a_number": "",
                    "eagle_v_number": "",
                    "eagle_filename": "",
                    "eagle_filepath": "",
                    "match_method": "",
                    "confidence": 0.0,
                    "spend": 50.0,
                    "revenue": 0,
                    "roas": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "installs": 0,
                }
            ],
        }
        mapping_path = tmp_path / "mapping.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        loader = CreativeMappingLoader()
        refs = loader.load(str(mapping_path))
        assert len(refs) == 1
        assert refs[0].match_method == MatchMethod.UNKNOWN
        assert refs[0].confidence == 0.0
        assert refs[0].is_bound is False


# ════════════════════════════════════════════════════════════════════
# AssetSource / MatchMethod / AssetType Enums
# ════════════════════════════════════════════════════════════════════

class TestAssetEnums:
    def test_asset_source_values(self):
        assert AssetSource.FACEBOOK.value == "facebook"
        assert AssetSource.EAGLE.value == "eagle"
        assert AssetSource.LOVART.value == "lovart"

    def test_match_method_values(self):
        assert MatchMethod.A_NUMBER.value == "a_number"
        assert MatchMethod.FILENAME.value == "filename"
        assert MatchMethod.EXACT_ID.value == "exact_id"
        assert MatchMethod.LEGACY_ID.value == "legacy_id"
        assert MatchMethod.VIDEO_NUMBER.value == "video_number"
        assert MatchMethod.UNKNOWN.value == "unknown"

    def test_asset_type_values(self):
        assert AssetType.VIDEO.value == "video"
        assert AssetType.IMAGE.value == "image"


# ════════════════════════════════════════════════════════════════════
# IdentityResolver
# ════════════════════════════════════════════════════════════════════

class TestIdentityResolver:
    """IdentityResolver ID 映射测试。"""

    @pytest.fixture
    def storage_with_entity(self, tmp_path):
        """创建包含 entity.json 的 CreativeStorage 目录。"""
        root = tmp_path / "creatives"
        asset_dir = root / "MW_IMG_260721_000123"
        asset_dir.mkdir(parents=True)
        with open(asset_dir / "entity.json", "w", encoding="utf-8") as f:
            json.dump({
                "creative_asset_id": "MW_IMG_260721_000123",
                "sources": {
                    "facebook_id": "2453146861847495",
                    "adjust_id": "adjust_536",
                },
                "legacy_id": "000123",
            }, f)
        return root

    def test_resolve_asset_id(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.resolve_asset_id("2453146861847495") == "MW_IMG_260721_000123"

    def test_resolve_facebook_id(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.resolve_facebook_id("MW_IMG_260721_000123") == "2453146861847495"

    def test_resolve_from_adjust(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.resolve_from_adjust("adjust_536") == "MW_IMG_260721_000123"

    def test_resolve_from_legacy(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.resolve_from_legacy("000123") == "MW_IMG_260721_000123"

    def test_has_mapping(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.has_mapping("2453146861847495")
        assert not r.has_mapping("nonexistent")

    def test_fallback_when_no_mapping(self, tmp_path):
        r = IdentityResolver(str(tmp_path))
        assert r.resolve_asset_id("unknown_id") == "unknown_id"
        assert r.resolve_facebook_id("unknown_id") == "unknown_id"

    def test_empty_storage(self, tmp_path):
        r = IdentityResolver(str(tmp_path))
        assert r.mapping_count == 0
        assert r.to_summary()["facebook_to_asset"] == 0

    def test_mapping_count(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.mapping_count == 1

    def test_get_identity(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        identity = r.get_identity("MW_IMG_260721_000123")
        assert identity is not None
        assert identity["creative_asset_id"] == "MW_IMG_260721_000123"
        assert identity["facebook_creative_id"] == "2453146861847495"
        assert identity["adjust_creative_id"] == "adjust_536"
        assert "000123" in identity["legacy_ids"]

    def test_get_identity_missing(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert r.get_identity("nonexistent") is None

    def test_build_identity_json(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        data = r.build_identity_json("MW_IMG_260721_000123")
        assert data is not None
        assert data["creative_asset_id"] == "MW_IMG_260721_000123"

    def test_index_from_facebook_json(self, tmp_path):
        """测试从 facebook.json 补充映射。"""
        root = tmp_path / "creatives"
        asset_dir = root / "MW_VIDEO_260721_000456"
        asset_dir.mkdir(parents=True)
        # 只有 facebook.json，没有 entity.json
        with open(asset_dir / "facebook.json", "w", encoding="utf-8") as f:
            json.dump({"creative_id": "9999999999999999"}, f)

        r = IdentityResolver(str(root))
        assert r.resolve_asset_id("9999999999999999") == "MW_VIDEO_260721_000456"

    def test_to_summary(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        s = r.to_summary()
        assert s["facebook_to_asset"] == 1
        assert s["adjust_to_asset"] == 1
        assert s["legacy_to_asset"] == 1

    def test_repr(self, storage_with_entity):
        r = IdentityResolver(str(storage_with_entity))
        assert "IdentityResolver" in repr(r)
        assert "mappings=1" in repr(r)


# ════════════════════════════════════════════════════════════════════
# AssetBindingMaterializer (E11.2.2 upgraded)
# ════════════════════════════════════════════════════════════════════

class TestAssetBindingMaterializer:
    """AssetBindingMaterializer 测试（E11.2.2 升级版）。"""

    @pytest.fixture
    def populated_repo(self, tmp_path):
        """创建包含 assets.json 的 repository 目录。"""
        repo = AssetBindingRepository(str(tmp_path / "creatives"))
        ref = CreativeAssetReference(
            creative_id="111",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="test.mp4",
            local_path="Y:\\Eagle\\test.mp4",
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
        )
        repo.save(ref)
        return tmp_path / "creatives"

    def test_materialize_creates_entity_json(self, populated_repo):
        m = AssetBindingMaterializer(str(populated_repo))
        assert m.materialize("111")

        # 无映射时 fallback 到 creative_id
        entity_path = populated_repo / "111" / "entity.json"
        assert entity_path.exists()

        with open(entity_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["asset"]["eagle_path"] == "Y:\\Eagle\\test.mp4"
        assert data["asset"]["eagle_filename"] == "test.mp4"
        assert data["asset"]["source_type"] == "EAGLE"
        assert data["asset"]["match_method"] == "a_number"
        assert data["asset"]["matched_confidence"] == 1.0
        assert data["asset"]["video_path"] == "Y:\\Eagle\\test.mp4"
        assert "eagle" in data["synced_sources"]
        # sources 包含 facebook_id
        assert data["sources"]["facebook_id"] == "111"

    def test_materialize_creates_identity_json(self, populated_repo):
        m = AssetBindingMaterializer(str(populated_repo))
        m.materialize("111")

        identity_path = populated_repo / "111" / "identity.json"
        assert identity_path.exists()

        with open(identity_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["creative_asset_id"] == "111"
        assert data["facebook_creative_id"] == "111"

    def test_materialize_with_resolver(self, populated_repo):
        """测试有 IdentityResolver 时的映射行为。"""
        # 创建 entity.json 模拟 sync 已跑过（建立映射）
        asset_dir = populated_repo / "MW_IMG_260721_000111"
        asset_dir.mkdir(parents=True)
        with open(asset_dir / "entity.json", "w", encoding="utf-8") as f:
            json.dump({
                "creative_asset_id": "MW_IMG_260721_000111",
                "sources": {"facebook_id": "111"},
                "identity": {"type": "video"},
            }, f)

        resolver = IdentityResolver(str(populated_repo))
        m = AssetBindingMaterializer(str(populated_repo), resolver)

        # resolver 应该已建立映射
        assert resolver.has_mapping("111")

        assert m.materialize("111")

        # entity.json 应该写入正确的 creative_asset_id 目录
        entity_path = populated_repo / "MW_IMG_260721_000111" / "entity.json"
        with open(entity_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["asset"]["eagle_path"] == "Y:\\Eagle\\test.mp4"
        assert data["sources"]["facebook_id"] == "111"
        assert "eagle" in data["synced_sources"]

    def test_materialize_updates_existing_entity_json(self, populated_repo):
        # 先创建 entity.json（模拟 sync 已跑过）
        entity_path = populated_repo / "111" / "entity.json"
        entity_path.parent.mkdir(parents=True, exist_ok=True)
        with open(entity_path, "w", encoding="utf-8") as f:
            json.dump({
                "creative_asset_id": "111",
                "identity": {"type": "video", "name": "P4-test"},
                "performance": {"acquisition": {"spend": 100}},
                "asset": {"image_url": "http://fb.com/img.jpg"},
                "synced_sources": ["facebook"],
            }, f)

        m = AssetBindingMaterializer(str(populated_repo))
        assert m.materialize("111")

        with open(entity_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 原有字段保留
        assert data["identity"]["name"] == "P4-test"
        assert data["performance"]["acquisition"]["spend"] == 100
        assert data["asset"]["image_url"] == "http://fb.com/img.jpg"

        # 新增 asset 字段
        assert data["asset"]["eagle_path"] == "Y:\\Eagle\\test.mp4"
        assert data["asset"]["source_type"] == "EAGLE"

        # synced_sources 合并
        assert "facebook" in data["synced_sources"]
        assert "eagle" in data["synced_sources"]

    def test_materialize_missing_assets_json(self, tmp_path):
        m = AssetBindingMaterializer(str(tmp_path))
        assert not m.materialize("nonexistent")

    def test_materialize_all(self, populated_repo):
        # 添加第二个 creative
        repo = AssetBindingRepository(str(populated_repo))
        repo.save(CreativeAssetReference(
            creative_id="222",
            asset_type=AssetType.IMAGE,
            source=AssetSource.EAGLE,
            eagle_filename="test2.png",
            local_path="Y:\\Eagle\\test2.png",
            match_method=MatchMethod.A_NUMBER,
            confidence=0.9,
        ))

        m = AssetBindingMaterializer(str(populated_repo))
        report = m.materialize_all()

        assert report["total"] == 2
        assert report["materialized"] == 2
        assert report["errors"] == 0
        assert report["resolved"] == 0  # 无映射，全部 fallback
        assert report["fallback"] == 2

    def test_materialize_all_with_resolver(self, populated_repo):
        """测试有映射时的 materialize_all 统计。"""
        # 创建 entity.json 建立映射
        asset_dir = populated_repo / "MW_IMG_111"
        asset_dir.mkdir(parents=True)
        with open(asset_dir / "entity.json", "w", encoding="utf-8") as f:
            json.dump({
                "creative_asset_id": "MW_IMG_111",
                "sources": {"facebook_id": "111"},
            }, f)

        resolver = IdentityResolver(str(populated_repo))
        m = AssetBindingMaterializer(str(populated_repo), resolver)

        report = m.materialize_all()
        assert report["resolved"] == 1
        assert report["fallback"] == 0

    def test_materialize_all_empty(self, tmp_path):
        m = AssetBindingMaterializer(str(tmp_path))
        report = m.materialize_all()
        assert report["total"] == 0

    def test_verify(self, populated_repo):
        m = AssetBindingMaterializer(str(populated_repo))
        m.materialize("111")

        result = m.verify()
        assert result["total_entities"] == 1
        assert result["with_asset"] == 1
        assert result["with_eagle_path"] == 1
        assert result["with_source_type"] == 1
        assert result["path_inaccessible"] == 1
        assert result["path_accessible"] == 0

    def test_verify_one(self, populated_repo):
        m = AssetBindingMaterializer(str(populated_repo))
        m.materialize("111")

        result = m.verify_one("111")
        assert result["has_entity"] is True
        assert result["has_asset"] is True
        assert result["eagle_path"] == "Y:\\Eagle\\test.mp4"
        assert result["source_type"] == "EAGLE"
        assert result["match_method"] == "a_number"
        assert result["confidence"] == 1.0
        # 无映射时 fallback
        assert result["asset_id"] == "111"
        assert result["resolved"] is False

    def test_verify_one_with_resolver(self, populated_repo):
        """测试有映射时的 verify_one 行为。"""
        # 建立映射
        asset_dir = populated_repo / "MW_IMG_111"
        asset_dir.mkdir(parents=True)
        with open(asset_dir / "entity.json", "w", encoding="utf-8") as f:
            json.dump({
                "creative_asset_id": "MW_IMG_111",
                "sources": {"facebook_id": "111"},
            }, f)

        resolver = IdentityResolver(str(populated_repo))
        m = AssetBindingMaterializer(str(populated_repo), resolver)
        m.materialize("111")

        result = m.verify_one("111")
        assert result["asset_id"] == "MW_IMG_111"
        assert result["resolved"] is True

    def test_verify_one_missing(self, tmp_path):
        m = AssetBindingMaterializer(str(tmp_path))
        result = m.verify_one("nonexistent")
        assert result["has_entity"] is False
        assert result["has_asset"] is False

    def test_verify_empty(self, tmp_path):
        m = AssetBindingMaterializer(str(tmp_path))
        result = m.verify()
        assert result["total_entities"] == 0

    def test_verify_idempotent(self, populated_repo):
        """验证 materialize 是幂等的。"""
        m = AssetBindingMaterializer(str(populated_repo))

        for _ in range(3):
            assert m.materialize("111")

        result = m.verify_one("111")
        assert result["has_asset"] is True

    def test_repr(self, tmp_path):
        m = AssetBindingMaterializer(str(tmp_path))
        assert "AssetBindingMaterializer" in repr(m)