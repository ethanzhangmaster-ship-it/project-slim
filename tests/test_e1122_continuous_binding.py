"""E11.2.2 — Continuous Asset Binding Pipeline 测试。

测试范围：
  - EagleScanner: 增量扫描 + 变更检测
  - ANumberMatcher: A-number 匹配规则
  - AssetLifecycleManager: 状态机
  - BindingScheduler: 管线编排
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from market_ops.creative_asset_binding.eagle_scanner import EagleScanner
from market_ops.creative_asset_binding.a_number_matcher import ANumberMatcher
from market_ops.creative_asset_binding.asset_lifecycle import (
    AssetLifecycleManager,
    AssetLifecycleStatus,
)
from market_ops.creative_asset_binding.binding_scheduler import BindingScheduler
from market_ops.creative_repository.assets.asset_reference import (
    CreativeAssetReference,
    AssetSource,
    AssetType,
    MatchMethod,
)
from market_ops.creative_repository.assets.asset_binding_repository import AssetBindingRepository


# ════════════════════════════════════════════════════════════════════
# EagleScanner
# ════════════════════════════════════════════════════════════════════

class TestEagleScanner:
    """EagleScanner 增量扫描测试。"""

    @pytest.fixture
    def eagle_dir(self, tmp_path):
        """创建模拟 Eagle 目录。"""
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        # 创建模拟文件
        for name in ["P4-v2601536-mg-2d.mp4", "P4-v2601537-mg-2d.mp4"]:
            (eagle / name).write_text("dummy")
        return eagle

    def test_scan_full(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))
        result = scanner.scan_full()

        assert result["total"] == 2
        assert result["video_count"] == 2
        assert result["new_count"] == 2
        assert index_path.exists()

    def test_scan_incremental_no_changes(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))

        scanner.scan_full()  # first scan
        result = scanner.scan_incremental()

        assert result["new_count"] == 0
        assert result["changed_count"] == 0
        assert result["removed_count"] == 0

    def test_scan_incremental_new_file(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))

        scanner.scan_full()
        # 添加新文件
        (eagle_dir / "P4-v2601538-new.mp4").write_text("new content")

        result = scanner.scan_incremental()
        assert result["new_count"] == 1
        assert len(result["new_assets"]) == 1

    def test_scan_incremental_removed_file(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))

        scanner.scan_full()
        # 删除文件
        (eagle_dir / "P4-v2601536-mg-2d.mp4").unlink()

        result = scanner.scan_incremental()
        assert result["removed_count"] == 1

    def test_find_by_v_number(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))
        scanner.scan_full()

        asset = scanner.find_by_v_number("v2601536")
        assert asset is not None
        assert "P4-v2601536" in asset.filename

    def test_find_by_v_number_numeric(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))
        scanner.scan_full()

        asset = scanner.find_by_v_number("2601536")
        assert asset is not None

    def test_is_available(self, eagle_dir, tmp_path):
        scanner = EagleScanner(str(eagle_dir))
        assert scanner.is_available

    def test_is_not_available(self, tmp_path):
        scanner = EagleScanner(str(tmp_path / "nonexistent"))
        assert not scanner.is_available

    def test_get_new_assets(self, eagle_dir, tmp_path):
        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle_dir), index_path=str(index_path))
        scanner.scan_full()

        (eagle_dir / "P4-v2601539-extra.mp4").write_text("extra")
        new = scanner.get_new_assets()
        assert len(new) == 1


# ════════════════════════════════════════════════════════════════════
# ANumberMatcher
# ════════════════════════════════════════════════════════════════════

class TestANumberMatcher:
    """ANumberMatcher 匹配规则测试。"""

    def test_extract_a_number(self):
        assert ANumberMatcher.extract_a_number("P4-IOS-T1-A536-0707") == "A536"
        assert ANumberMatcher.extract_a_number("P04-AND-T1-A800-0722") == "A800"
        assert ANumberMatcher.extract_a_number("P4-IOS-T1-A1-0707") == "A1"
        assert ANumberMatcher.extract_a_number("no_a_number") is None

    def test_extract_numeric_a(self):
        assert ANumberMatcher.extract_numeric_a("P4-IOS-T1-A536-0707") == "536"
        assert ANumberMatcher.extract_numeric_a("P4-IOS-T1-A800-0722") == "800"

    def test_extract_v_number(self):
        assert ANumberMatcher.extract_v_number("P4-v2601536-mg-2d.mp4") == "v2601536"
        assert ANumberMatcher.extract_v_number("P4-v2601800-dragon-rescue-en.mp4") == "v2601800"

    def test_extract_numeric_v(self):
        assert ANumberMatcher.extract_numeric_v("P4-v2601536-mg-2d.mp4") == "2601536"
        assert ANumberMatcher.extract_numeric_v("P4-v2601800-dragon-rescue-en.mp4") == "2601800"

    def test_match_success(self):
        m = ANumberMatcher()
        is_match, conf = m.match(
            ad_name="P4-IOS-T1-A536-0707",
            eagle_filename="P4-v2601536-mg-2d-juesezhanshi-en-42s-9X16.mp4",
        )
        assert is_match
        assert conf == 1.0

    def test_match_success_short(self):
        m = ANumberMatcher()
        is_match, conf = m.match("P4-A1-test", "P4-v1234-test.mp4")
        assert is_match
        assert conf == 1.0  # "1" in "1234"

    def test_match_fail(self):
        m = ANumberMatcher()
        is_match, conf = m.match("P4-A536-test", "P4-v999999-test.mp4")
        assert not is_match
        assert conf == 0.0

    def test_match_no_a_number(self):
        m = ANumberMatcher()
        is_match, conf = m.match("no_a_number", "P4-v2601536.mp4")
        assert not is_match

    def test_match_no_v_number(self):
        m = ANumberMatcher()
        is_match, conf = m.match("P4-A536-test", "no_v_number.mp4")
        assert not is_match

    def test_match_to_asset(self, tmp_path):
        # 创建 Eagle 目录
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        (eagle / "P4-v2601536-mg-2d.mp4").write_text("dummy")

        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle), index_path=str(index_path))
        scanner.scan_full()

        m = ANumberMatcher()
        ref = m.match_to_asset(
            creative_id="111",
            ad_name="P4-IOS-T1-A536-0707",
            scanner=scanner,
        )
        assert ref is not None
        assert ref.creative_id == "111"
        assert ref.match_method == MatchMethod.A_NUMBER
        assert ref.confidence == 1.0
        assert ref.a_number == "A536"
        assert ref.eagle_v_number == "v2601536"

    def test_match_to_asset_no_match(self, tmp_path):
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        (eagle / "test.mp4").write_text("dummy")

        index_path = tmp_path / "index.json"
        scanner = EagleScanner(str(eagle), index_path=str(index_path))
        scanner.scan_full()

        m = ANumberMatcher()
        ref = m.match_to_asset("111", "P4-A999-test", scanner)
        assert ref is None


# ════════════════════════════════════════════════════════════════════
# AssetLifecycleManager
# ════════════════════════════════════════════════════════════════════

class TestAssetLifecycleManager:
    """AssetLifecycleManager 状态机测试。"""

    @pytest.fixture
    def mgr(self, tmp_path):
        state_path = tmp_path / "lifecycle.json"
        return AssetLifecycleManager(str(state_path))

    def test_new_asset_starts_new(self, mgr):
        assert mgr.get_status("v2601536") is None

    def test_transition_new_to_matched(self, mgr):
        assert mgr.transition("v2601536", AssetLifecycleStatus.MATCHED)
        assert mgr.get_status("v2601536") == AssetLifecycleStatus.MATCHED

    def test_transition_invalid(self, mgr):
        # 不能从 NEW 直接跳到 WINNER
        assert not mgr.transition("v2601536", AssetLifecycleStatus.WINNER)
        # _get_or_create 会创建 NEW 条目，但转换失败后状态保持 NEW
        assert mgr.get_status("v2601536") == AssetLifecycleStatus.NEW

    def test_full_lifecycle(self, mgr):
        assert mgr.transition("v1", AssetLifecycleStatus.MATCHED)
        assert mgr.transition("v1", AssetLifecycleStatus.TESTING)
        assert mgr.transition("v1", AssetLifecycleStatus.WINNER)
        assert mgr.transition("v1", AssetLifecycleStatus.DNA_ANALYZED)
        assert mgr.transition("v1", AssetLifecycleStatus.MUTATED)
        assert mgr.get_status("v1") == AssetLifecycleStatus.MUTATED

    def test_mark_failed(self, mgr):
        mgr.transition("v1", AssetLifecycleStatus.MATCHED)
        mgr.transition("v1", AssetLifecycleStatus.TESTING)
        assert mgr.mark_failed("v1", "low_roas")
        assert mgr.get_status("v1") == AssetLifecycleStatus.FAILED

    def test_get_by_status(self, mgr):
        mgr.transition("v1", AssetLifecycleStatus.MATCHED)
        mgr.transition("v2", AssetLifecycleStatus.MATCHED)
        mgr.transition("v3", AssetLifecycleStatus.MATCHED)
        mgr.transition("v3", AssetLifecycleStatus.TESTING)
        mgr.transition("v3", AssetLifecycleStatus.WINNER)

        matched = mgr.get_by_status(AssetLifecycleStatus.MATCHED)
        assert len(matched) == 2
        assert "v1" in matched
        assert "v2" in matched

        winners = mgr.get_winners()
        assert winners == ["v3"]

    def test_count_by_status(self, mgr):
        mgr.transition("v1", AssetLifecycleStatus.MATCHED)
        mgr.transition("v2", AssetLifecycleStatus.MATCHED)
        mgr.transition("v2", AssetLifecycleStatus.TESTING)
        mgr.transition("v2", AssetLifecycleStatus.WINNER)
        mgr.transition("v3", AssetLifecycleStatus.MATCHED)

        counts = mgr.count_by_status()
        assert counts["MATCHED"] == 2
        assert counts["WINNER"] == 1

    def test_import_from_mapping(self, mgr):
        refs = [
            CreativeAssetReference(
                creative_id="111",
                eagle_v_number="v2601536",
                eagle_filename="P4-v2601536.mp4",
                local_path="Y:\\Eagle\\P4-v2601536.mp4",
            ),
            CreativeAssetReference(
                creative_id="222",
                eagle_v_number="v2601537",
                eagle_filename="P4-v2601537.mp4",
                local_path="Y:\\Eagle\\P4-v2601537.mp4",
            ),
        ]
        count = mgr.import_from_mapping(refs)
        assert count == 2
        assert mgr.get_status("v2601536") == AssetLifecycleStatus.MATCHED

    def test_to_summary(self, mgr):
        mgr.transition("v1", AssetLifecycleStatus.MATCHED)
        summary = mgr.to_summary()
        assert "MATCHED" in summary
        assert "1" in summary

    def test_persistence(self, tmp_path):
        state_path = tmp_path / "lifecycle.json"
        mgr1 = AssetLifecycleManager(str(state_path))
        mgr1.transition("v1", AssetLifecycleStatus.MATCHED)

        # 重新加载
        mgr2 = AssetLifecycleManager(str(state_path))
        assert mgr2.get_status("v1") == AssetLifecycleStatus.MATCHED

    def test_archive(self, mgr):
        mgr.transition("v1", AssetLifecycleStatus.MATCHED)
        assert mgr.mark_archived("v1")
        assert mgr.get_status("v1") == AssetLifecycleStatus.ARCHIVED


# ════════════════════════════════════════════════════════════════════
# BindingScheduler
# ════════════════════════════════════════════════════════════════════

class TestBindingScheduler:
    """BindingScheduler 管线编排测试。"""

    @pytest.fixture
    def scheduler(self, tmp_path):
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        for name in ["P4-v2601536-mg-2d.mp4", "P4-v2601537-mg-2d.mp4"]:
            (eagle / name).write_text("dummy")

        creative_root = tmp_path / "creatives"
        creative_root.mkdir()

        return BindingScheduler(
            eagle_root=str(eagle),
            creative_storage_root=str(creative_root),
            eagle_index_path=str(tmp_path / "eagle_index.json"),
            lifecycle_path=str(tmp_path / "lifecycle.json"),
            report_dir=str(tmp_path / "reports"),
        )

    def test_run_incremental(self, scheduler):
        report = scheduler.run_incremental()

        assert "eagle_scan" in report
        assert "bindings" in report
        assert "lifecycle" in report
        assert report["eagle_scan"]["total"] == 2

    def test_get_pipeline_status(self, scheduler):
        status = scheduler.get_pipeline_status()
        assert "eagle_available" in status
        assert "repository_count" in status
        assert "lifecycle" in status

    def test_run_full_historical(self, scheduler, tmp_path):
        # 创建 creative_mapping_v2.json
        mapping = {
            "total_fb_videos": 2,
            "matched": 2,
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
                    "eagle_filepath": str(tmp_path / "eagle" / "P4-v2601536-mg-2d.mp4"),
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
                    "eagle_filepath": str(tmp_path / "eagle" / "P4-v2601537-mg-2d.mp4"),
                    "match_method": "A-number",
                    "confidence": 1.0,
                    "spend": 200.0,
                    "revenue": 400.0,
                    "roas": 2.0,
                    "impressions": 10000,
                    "clicks": 300,
                    "installs": 20,
                },
            ],
        }
        mapping_path = tmp_path / "creative_mapping_v2.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        report = scheduler.run_full_historical(str(mapping_path))

        assert report["migration"]["total"] == 2
        assert report["migration"]["written"] == 2
        assert report["lifecycle"]["imported"] == 2

    def test_repr(self, scheduler):
        assert "BindingScheduler" in repr(scheduler)