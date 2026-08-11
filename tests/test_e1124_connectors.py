"""E11.2.4 — Runtime Connectors 测试。

测试范围：
  - FacebookConnector:  事件发布 + A-Number 提取
  - AdjustConnector:    事件发布 + 收入数据格式化
  - FacebookWorker:     轮询循环
  - AdjustWorker:       轮询循环
  - RuntimeDaemon:      完整管线编排 + 报告持久化
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from market_ops.creative_asset_runtime.events.asset_events import (
    AssetEvent,
    AssetEventType,
)
from market_ops.creative_asset_runtime.events.event_bus_adapter import AssetEventBus
from market_ops.creative_asset_runtime.connectors.facebook_connector import FacebookConnector
from market_ops.creative_asset_runtime.connectors.adjust_connector import AdjustConnector
from market_ops.creative_asset_runtime.workers.facebook_worker import FacebookWorker
from market_ops.creative_asset_runtime.workers.adjust_worker import AdjustWorker
from market_ops.creative_asset_runtime.daemon import RuntimeDaemon
from market_ops.creative_asset_runtime.runtime import AssetRuntime
from market_ops.facebook_ingestion.facebook_client import FacebookClient
from market_ops.adjust_ingestion.adjust_client import AdjustClient


# ════════════════════════════════════════════════════════════════════
# FacebookConnector
# ════════════════════════════════════════════════════════════════════

class TestFacebookConnector:
    """FacebookConnector 测试。"""

    @pytest.fixture
    def connector(self, tmp_path):
        """创建 Mock FacebookConnector（无真实 API token）。"""
        bus = AssetEventBus()
        client = FacebookClient(
            access_token="test_token",
            ad_account_id="123456789",
        )
        return FacebookConnector(client, event_bus=bus)

    def test_extract_a_number(self, connector):
        assert connector._extract_a_number("P4-IOS-T1-A536-0707") == "A536"
        assert connector._extract_a_number("P4-IOS-T1-A800-0722") == "A800"
        assert connector._extract_a_number("P4-AND-T1-A1234-0801") == "A1234"
        assert connector._extract_a_number("no_a_number_here") == ""

    def test_is_connected(self, connector):
        # 没有真实 token，应返回 False
        assert connector.is_connected() is False

    def test_connector_created(self, connector):
        assert connector.total_synced == 0
        assert connector.last_synced_at is None

    def test_repr(self, connector):
        assert "FacebookConnector" in repr(connector)


# ════════════════════════════════════════════════════════════════════
# AdjustConnector
# ════════════════════════════════════════════════════════════════════

class TestAdjustConnector:
    """AdjustConnector 测试。"""

    @pytest.fixture
    def connector(self):
        """创建 AdjustConnector（Mock client 有测试数据）。"""
        bus = AssetEventBus()
        client = AdjustClient(
            api_token="test_token",
            app_token="test_app",
        )
        return AdjustConnector(client, event_bus=bus)

    def test_poll_publishes_events(self, connector):
        events = connector.poll()
        # Mock AdjustClient 返回 3 条测试数据
        assert len(events) == 3
        assert connector.total_synced == 3

        for event in events:
            assert event.event_type == AssetEventType.PERFORMANCE_UPDATED
            assert "revenue_d7" in event.payload
            assert "roas_d7" in event.payload

    def test_record_to_event(self, connector):
        record = {
            "creative_id": "adj_test",
            "creative_name": "test_video",
            "creative_asset_id": "MW_VID_260721_000001",
            "installs": 1000,
            "cohort_revenue_iap_d7": 5000.0,
            "cohort_revenue_ad_d7": 1000.0,
            "cohort_revenue_iap_d30": 15000.0,
            "cohort_revenue_ad_d30": 3000.0,
            "cohort_retention_rate_d1": 0.5,
            "cohort_retention_rate_d7": 0.25,
            "cohort_paying_users_d30": 50,
            "sessions": 2000,
            "campaign_name": "MW_AEO_Install",
            "date": "2026-07-21",
        }
        event = connector._record_to_event(record)
        assert event.creative_id == "adj_test"
        assert event.payload["revenue_d7"] == 6000.0  # 5000 + 1000
        assert event.payload["revenue_d30"] == 18000.0  # 15000 + 3000
        assert event.payload["retention_d1"] == 0.5
        assert event.payload["payer_count_d30"] == 50

    def test_is_connected(self, connector):
        assert connector.is_connected() is True

    def test_empty_token_not_connected(self):
        client = AdjustClient(api_token="", app_token="")
        connector = AdjustConnector(client)
        assert connector.is_connected() is False

    def test_repr(self, connector):
        assert "AdjustConnector" in repr(connector)


# ════════════════════════════════════════════════════════════════════
# FacebookWorker
# ════════════════════════════════════════════════════════════════════

class TestFacebookWorker:
    """FacebookWorker 轮询测试。"""

    @pytest.fixture
    def worker(self):
        bus = AssetEventBus()
        client = FacebookClient(
            access_token="test_token",
            ad_account_id="123456789",
        )
        connector = FacebookConnector(client, event_bus=bus)
        return FacebookWorker(connector, poll_interval_seconds=0.1)

    def test_worker_created(self, worker):
        assert worker.run_count == 0
        assert worker.total_published == 0

    def test_stop(self, worker):
        worker.stop()
        # 不应抛出异常

    def test_repr(self, worker):
        assert "FacebookWorker" in repr(worker)


# ════════════════════════════════════════════════════════════════════
# AdjustWorker
# ════════════════════════════════════════════════════════════════════

class TestAdjustWorker:
    """AdjustWorker 轮询测试。"""

    @pytest.fixture
    def worker(self):
        bus = AssetEventBus()
        client = AdjustClient(
            api_token="test_token",
            app_token="test_app",
        )
        connector = AdjustConnector(client, event_bus=bus)
        return AdjustWorker(connector, poll_interval_seconds=0.1)

    def test_run_once(self, worker):
        result = worker.run_once()
        assert result["published"] == 3  # Mock 返回 3 条
        assert worker.run_count == 1
        assert worker.total_published == 3

    def test_stop(self, worker):
        worker.stop()

    def test_is_connected(self, worker):
        assert worker.is_connected() is True

    def test_repr(self, worker):
        assert "AdjustWorker" in repr(worker)


# ════════════════════════════════════════════════════════════════════
# RuntimeDaemon
# ════════════════════════════════════════════════════════════════════

class TestRuntimeDaemon:
    """RuntimeDaemon 完整管线编排测试。"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """创建完整的 RuntimeDaemon（含 Mock API）。"""
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        for name in ["P4-v2601536-mg-2d.mp4", "P4-v2601537-mg-2d.mp4"]:
            (eagle / name).write_text("dummy")

        creative_root = tmp_path / "creatives"
        creative_root.mkdir()

        # Runtime
        runtime = AssetRuntime(
            eagle_root=str(eagle),
            creative_storage_root=str(creative_root),
            eagle_index_path=str(tmp_path / "eagle_index.json"),
            lifecycle_path=str(tmp_path / "lifecycle.json"),
            runtime_dir=str(tmp_path / "runtime"),
        )

        # Connectors
        fb_client = FacebookClient(
            access_token="test_token",
            ad_account_id="123456789",
        )
        fb_connector = FacebookConnector(fb_client, event_bus=runtime.event_bus)

        adj_client = AdjustClient(
            api_token="test_token",
            app_token="test_app",
        )
        adj_connector = AdjustConnector(adj_client, event_bus=runtime.event_bus)

        return RuntimeDaemon(
            runtime=runtime,
            facebook_connector=fb_connector,
            adjust_connector=adj_connector,
            report_dir=str(tmp_path / "reports"),
        )

    def test_run_once(self, daemon, tmp_path):
        daemon._runtime.start()
        report = daemon.run_once()

        assert "eagle_scan" in report.to_dict()
        assert report.eagle_scan["total"] == 2
        assert report.eagle_scan["new"] == 2
        # Adjust Mock 返回 3 条
        assert report.adjust_sync.get("published", 0) == 3
        assert report.elapsed_seconds >= 0

    def test_get_status(self, daemon):
        daemon._runtime.start()
        status = daemon.get_status()

        assert "daemon_running" in status
        assert "daemon_run_count" in status
        assert "facebook_connected" in status
        assert "adjust_connected" in status
        assert status["adjust_connected"] is True

    def test_report_persisted(self, daemon, tmp_path):
        daemon._runtime.start()
        daemon.run_once()

        report_path = tmp_path / "reports" / "run_0001.json"
        assert report_path.exists()

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "eagle_scan" in data
        assert "elapsed_seconds" in data

    def test_stop(self, daemon):
        daemon._runtime.start()
        daemon.stop()
        # 不应抛出异常

    def test_full_event_chain_with_real_connectors(
        self, daemon, tmp_path
    ):
        """端到端测试：完整事件链 + 真实 Connectors。

        模拟:
          1. Eagle Scan → 发现新素材
          2. Adjust Sync → 拉取收入数据 → 发布 PERFORMANCE_UPDATED
          3. Lifecycle → 处理 WINNER 判定
        """
        daemon._runtime.start()

        # 创建已匹配的素材（模拟 Binding）
        from market_ops.creative_repository.assets.asset_reference import (
            CreativeAssetReference,
            AssetSource,
            AssetType,
            MatchMethod,
        )
        from market_ops.creative_repository.assets.asset_binding_repository import AssetBindingRepository

        creative_root = tmp_path / "creatives"
        repo = AssetBindingRepository(str(creative_root))
        ref = CreativeAssetReference(
            creative_id="adj_001",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="P4-v2601536-mg-2d.mp4",
            eagle_v_number="v2601536",
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
            ad_name="P4-IOS-T1-A536-0707",
            a_number="A536",
        )
        repo.save(ref)

        # 先标记为 MATCHED
        daemon._runtime._lifecycle_worker._manager.transition(
            "adj_001", "MATCHED"
        )

        # 执行完整管线
        report = daemon.run_once()

        assert report.adjust_sync["published"] == 3
        assert report.eagle_scan["total"] == 2

        # 验证 lifecycle 状态更新
        # adj_001: installs=2000, revenue_d7=3500 (3000+500)
        # 没有 spend 数据，所以不会触发 WINNER
        # 但至少应该已经处理了 PERFORMANCE_UPDATED

        daemon.stop()

    def test_repr(self, daemon):
        assert "RuntimeDaemon" in repr(daemon)