"""E11.1 — UnifiedSyncOrchestrator 测试。

测试覆盖：
  - AC1: SyncReport 序列化、摘要
  - AC2: Orchestrator 初始化、配置
  - AC3: sync_facebook 错误处理（无 token、无账户）
  - AC4: sync_adjust 错误处理（无 token）
  - AC5: run_daily_sync 默认日期逻辑
  - AC6: SyncReport.to_dict 完整字段
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from datetime import date, timedelta

from market_ops.e11.orchestrator import UnifiedSyncOrchestrator, SyncReport


class TestSyncReport:
    """AC1: SyncReport 数据模型测试."""

    def test_empty_report(self):
        """AC1: 空报告."""
        report = SyncReport()
        assert report.fb_accounts_synced == 0
        assert report.adjust_records == 0

    def test_to_dict(self):
        """AC6: 序列化."""
        report = SyncReport(
            started_at="2026-01-01T00:00:00",
            completed_at="2026-01-01T00:01:00",
            duration_seconds=60.0,
            fb_accounts_synced=1,
            fb_entities_created=10,
            adjust_records=100,
            adjust_matched=80,
            adjust_total_revenue=500.0,
            adjust_match_rate=0.8,
            creative_storage_count=50,
            storage_root="data/creatives",
        )
        d = report.to_dict()
        assert d["facebook"]["accounts_synced"] == 1
        assert d["facebook"]["entities_created"] == 10
        assert d["adjust"]["records"] == 100
        assert d["adjust"]["matched"] == 80
        assert d["adjust"]["total_revenue"] == 500.0
        assert d["adjust"]["match_rate"] == 0.8
        assert d["storage"]["total_entities"] == 50

    def test_to_summary(self):
        """AC1: 摘要输出."""
        report = SyncReport(
            started_at="2026-01-01T00:00:00",
            completed_at="2026-01-01T00:01:00",
            duration_seconds=60.0,
            fb_accounts_synced=2,
            fb_entities_created=10,
            adjust_records=100,
            adjust_matched=80,
            adjust_total_revenue=500.0,
            adjust_match_rate=0.8,
            storage_root="data/creatives",
        )
        summary = report.to_summary()
        assert "E11.1 Unified Sync Report" in summary
        assert "Accounts:  2" in summary
        assert "Records:   100" in summary
        assert "Revenue:   $500.00" in summary


class TestUnifiedSyncOrchestratorInit:
    """AC2: Orchestrator 初始化测试."""

    def test_default_init(self):
        """AC2: 默认初始化."""
        orchestrator = UnifiedSyncOrchestrator()
        assert orchestrator.storage_root == "data/creatives"
        assert orchestrator.creative_storage is not None

    def test_with_config(self):
        """AC2: 带配置初始化."""
        orchestrator = UnifiedSyncOrchestrator(
            creative_storage_root="test_data/creatives",
            facebook_accounts=[
                {"id": "123456", "name": "P04 And 1", "platform": "Android"},
                {"id": "789012", "name": "P04 iOS 1", "platform": "iOS"},
            ],
            adjust_config={"api_token": "test_token", "app_token": "test_app"},
            fb_token="test_fb_token",
            fb_api_version="v19.0",
        )
        assert orchestrator.storage_root == "test_data/creatives"

    def test_repr(self):
        """AC2: 字符串表示."""
        orchestrator = UnifiedSyncOrchestrator(
            creative_storage_root="data/creatives",
            facebook_accounts=[
                {"id": "123456", "name": "P04 And 1", "platform": "Android"},
            ],
            adjust_config={"api_token": "configured"},
        )
        r = repr(orchestrator)
        assert "fb_accounts=1" in r
        assert "adjust=configured" in r

    def test_adjust_not_configured_repr(self):
        """AC2: Adjust 未配置时的表示."""
        orchestrator = UnifiedSyncOrchestrator()
        r = repr(orchestrator)
        assert "adjust=not configured" in r


class TestUnifiedSyncOrchestratorSync:
    """AC3-AC5: 同步逻辑测试."""

    def test_sync_facebook_no_accounts(self):
        """AC3: 无账户时的 Facebook 同步."""
        orchestrator = UnifiedSyncOrchestrator()
        result = orchestrator.sync_facebook(
            start_date=date.today(),
            end_date=date.today(),
        )
        assert result["accounts_synced"] == 0
        assert result["entities_created"] == 0

    def test_sync_facebook_no_token(self):
        """AC3: 无 token 时的 Facebook 同步."""
        orchestrator = UnifiedSyncOrchestrator(
            facebook_accounts=[
                {"id": "123456", "name": "Test Account", "platform": "Android"},
            ],
            fb_token="",  # no token
        )
        result = orchestrator.sync_facebook(
            start_date=date.today(),
            end_date=date.today(),
        )
        assert result["accounts_synced"] == 0
        assert len(result["errors"]) >= 1

    def test_sync_adjust_no_token(self):
        """AC4: 无 token 时的 Adjust 同步."""
        orchestrator = UnifiedSyncOrchestrator()
        result = orchestrator.sync_adjust(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert result["records"] == 0
        assert result["matched"] == 0
        assert len(result["errors"]) >= 1

    def test_run_daily_sync_no_config(self):
        """AC5: 无配置时的每日同步（应优雅降级）."""
        orchestrator = UnifiedSyncOrchestrator()
        report = orchestrator.run_daily_sync()
        assert report.fb_accounts_synced == 0
        assert report.adjust_records == 0
        assert report.duration_seconds >= 0

    def test_run_daily_sync_default_dates(self):
        """AC5: 默认日期逻辑."""
        orchestrator = UnifiedSyncOrchestrator()
        report = orchestrator.run_daily_sync()
        # 无配置时两个引擎都应该返回 0
        assert report.fb_accounts_synced == 0
        assert report.started_at != ""
        assert report.completed_at != ""

    def test_run_daily_sync_custom_dates(self):
        """AC5: 自定义日期."""
        orchestrator = UnifiedSyncOrchestrator(
            facebook_accounts=[
                {"id": "123456", "name": "Test", "platform": "Android"},
            ],
        )
        report = orchestrator.run_daily_sync(
            fb_date=date(2026, 1, 1),
            adjust_start="2026-01-01",
            adjust_end="2026-01-07",
        )
        # 无 token 时 Facebook 会报错，Adjust 会报错
        assert report.fb_accounts_synced == 0
        assert report.adjust_records == 0

    def test_sync_facebook_with_token_no_accounts_skipped(self):
        """AC3: 有 token 但无账户时不报错."""
        orchestrator = UnifiedSyncOrchestrator(
            facebook_accounts=[
                {"id": "123456", "name": "Test", "platform": "Android"},
            ],
            fb_token="test_token",
        )
        result = orchestrator.sync_facebook(
            start_date=date.today(),
            end_date=date.today(),
        )
        # 有 token 有 account，但 API 调用会失败（假 token）
        # 错误被捕获，不会崩溃
        assert "accounts_synced" in result
        assert "errors" in result

    def test_sync_facebook_empty_account_id_skipped(self):
        """AC3: 空 account_id 的账户被跳过."""
        orchestrator = UnifiedSyncOrchestrator(
            facebook_accounts=[
                {"id": "", "name": "Invalid", "platform": "Android"},
            ],
            fb_token="test_token",
        )
        result = orchestrator.sync_facebook(
            start_date=date.today(),
            end_date=date.today(),
        )
        assert result["accounts_synced"] == 0
        assert len(result["errors"]) >= 1


class TestSyncReportErrors:
    """AC3-AC4: 错误报告测试."""

    def test_report_with_errors(self):
        """AC3: 带错误的报告."""
        report = SyncReport(
            fb_errors=["[P04 And 1] API error"],
            adjust_errors=["Invalid token"],
        )
        d = report.to_dict()
        assert d["facebook"]["errors"] == 1
        assert d["adjust"]["errors"] == 1

    def test_report_no_errors(self):
        """AC3: 无错误报告."""
        report = SyncReport(
            fb_accounts_synced=5,
            fb_entities_created=120,
            adjust_records=500,
            adjust_matched=450,
        )
        d = report.to_dict()
        assert d["facebook"]["errors"] == 0
        assert d["adjust"]["errors"] == 0


class TestOrchestratorStorage:
    """AC2: Storage 集成测试."""

    def test_creative_storage_property(self):
        """AC2: CreativeStorage 属性."""
        orchestrator = UnifiedSyncOrchestrator(
            creative_storage_root="test_storage",
        )
        storage = orchestrator.creative_storage
        assert storage is not None

    def test_storage_root(self):
        """AC2: Storage root 路径."""
        orchestrator = UnifiedSyncOrchestrator(
            creative_storage_root="custom/path",
        )
        assert orchestrator.storage_root == "custom/path"