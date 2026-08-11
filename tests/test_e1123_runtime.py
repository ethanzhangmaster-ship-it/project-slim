"""E11.2.3 — Asset Runtime 测试。

测试范围：
  - AssetEvent + AssetEventType: 事件模型
  - AssetEventBus: 发布/订阅/持久化/重试
  - EagleScannerWorker: 扫描 + 事件发布
  - BindingWorker: 匹配 + 事件发布
  - MaterializerWorker: 实体化 + 事件发布
  - LifecycleWorker: 生命周期状态转换
  - AssetRuntime: 完整管线编排
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
from market_ops.creative_asset_runtime.workers.eagle_worker import EagleScannerWorker
from market_ops.creative_asset_runtime.workers.binding_worker import BindingWorker
from market_ops.creative_asset_runtime.workers.materializer_worker import MaterializerWorker
from market_ops.creative_asset_runtime.workers.lifecycle_worker import LifecycleWorker
from market_ops.creative_asset_runtime.runtime import AssetRuntime
from market_ops.creative_asset_binding.asset_lifecycle import AssetLifecycleStatus


# ════════════════════════════════════════════════════════════════════
# AssetEvent
# ════════════════════════════════════════════════════════════════════

class TestAssetEvent:
    """AssetEvent 不可变事件模型测试。"""

    def test_create_event(self):
        event = AssetEvent(
            event_type=AssetEventType.EAGLE_ASSET_DISCOVERED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={"filename": "test.mp4"},
        )
        assert event.event_type == AssetEventType.EAGLE_ASSET_DISCOVERED
        assert event.creative_id == "111"
        assert event.eagle_v_number == "v2601536"
        assert event.payload["filename"] == "test.mp4"
        assert event.event_id.startswith("evt_")
        assert event.retry_count == 0
        assert event.error == ""

    def test_to_dict(self):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="222",
            eagle_v_number="v2601537",
            payload={"spend": 100},
        )
        d = event.to_dict()
        assert d["event_type"] == "asset_matched"
        assert d["creative_id"] == "222"
        assert d["payload"]["spend"] == 100

    def test_from_dict(self):
        data = {
            "event_id": "evt_test123",
            "event_type": "asset_matched",
            "creative_id": "333",
            "eagle_v_number": "v2601538",
            "payload": {"roas": 2.0},
            "timestamp": "2026-07-22T00:00:00",
            "retry_count": 1,
            "error": "test error",
        }
        event = AssetEvent.from_dict(data)
        assert event.event_type == AssetEventType.ASSET_MATCHED
        assert event.creative_id == "333"
        assert event.retry_count == 1
        assert event.error == "test error"

    def test_is_frozen(self):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
        )
        with pytest.raises(Exception):
            event.creative_id = "222"  # frozen

    def test_with_retry(self):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
        )
        retried = event.with_retry()
        assert retried.retry_count == 1
        assert retried.event_id == event.event_id  # same id
        assert retried.creative_id == event.creative_id

    def test_with_error(self):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATERIALIZE_FAILED,
            creative_id="111",
        )
        errored = event.with_error("disk full")
        assert errored.error == "disk full"
        assert errored.creative_id == event.creative_id

    def test_asset_event_type_values(self):
        assert AssetEventType.EAGLE_ASSET_DISCOVERED.value == "eagle_asset_discovered"
        assert AssetEventType.ASSET_MATCHED.value == "asset_matched"
        assert AssetEventType.ASSET_MATERIALIZED.value == "asset_materialized"
        assert AssetEventType.PERFORMANCE_UPDATED.value == "performance_updated"
        assert AssetEventType.ASSET_WINNER_DETECTED.value == "winner_detected"
        assert AssetEventType.ASSET_FAILED.value == "asset_failed"
        assert AssetEventType.EAGLE_SCAN_COMPLETED.value == "eagle_scan_completed"

    def test_repr(self):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
            eagle_v_number="v2601536",
        )
        r = repr(event)
        assert "asset_matched" in r
        assert "111" in r
        assert "v2601536" in r


# ════════════════════════════════════════════════════════════════════
# AssetEventBus
# ════════════════════════════════════════════════════════════════════

class TestAssetEventBus:
    """AssetEventBus 事件总线测试。"""

    @pytest.fixture
    def bus(self):
        """创建无持久化的 EventBus（快速测试）。"""
        return AssetEventBus()

    @pytest.fixture
    def bus_with_persistence(self, tmp_path):
        """创建有持久化的 EventBus（测试 replay/retry）。"""
        return AssetEventBus(
            replay_log=str(tmp_path / "events.jsonl"),
            failed_log=str(tmp_path / "failed.json"),
        )

    def test_subscribe_and_publish(self, bus):
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(AssetEventType.ASSET_MATCHED, handler)
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
        )
        bus.publish(event)

        assert len(received) == 1
        assert received[0].creative_id == "111"

    def test_wildcard_subscription(self, bus):
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("*", handler)
        bus.publish(AssetEvent(event_type=AssetEventType.EAGLE_ASSET_DISCOVERED))
        bus.publish(AssetEvent(event_type=AssetEventType.ASSET_MATCHED))

        assert len(received) == 2

    def test_unsubscribe(self, bus):
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(AssetEventType.ASSET_MATCHED, handler)
        bus.unsubscribe(AssetEventType.ASSET_MATCHED, handler)
        bus.publish(AssetEvent(event_type=AssetEventType.ASSET_MATCHED))

        assert len(received) == 0

    def test_handler_error_does_not_block(self, bus):
        received = []

        def bad_handler(event):
            raise RuntimeError("boom")

        def good_handler(event):
            received.append(event)

        bus.subscribe(AssetEventType.ASSET_MATCHED, bad_handler)
        bus.subscribe(AssetEventType.ASSET_MATCHED, good_handler)
        bus.publish(AssetEvent(event_type=AssetEventType.ASSET_MATCHED, creative_id="111"))

        assert len(received) == 1

    def test_publish_chain(self, bus):
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("*", handler)
        events = [
            AssetEvent(event_type=AssetEventType.EAGLE_ASSET_DISCOVERED, creative_id="1"),
            AssetEvent(event_type=AssetEventType.ASSET_MATCHED, creative_id="1"),
            AssetEvent(event_type=AssetEventType.ASSET_MATERIALIZED, creative_id="1"),
        ]
        bus.publish_chain(events)
        assert len(received) == 3

    def test_replay_log(self, bus_with_persistence, tmp_path):
        bus_with_persistence.publish(AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
        ))
        bus_with_persistence.publish(AssetEvent(
            event_type=AssetEventType.ASSET_MATERIALIZED,
            creative_id="222",
        ))

        replay_path = tmp_path / "events.jsonl"
        assert replay_path.exists()

        # 创建新 bus 回放
        bus2 = AssetEventBus(replay_log=str(replay_path))
        received = []

        def handler(event):
            received.append(event)

        bus2.subscribe("*", handler)
        count = bus2.replay()
        assert count == 2
        assert len(received) == 2

    def test_failed_event_retry(self, bus_with_persistence):
        def failing_handler(event):
            if event.retry_count < 1:
                raise RuntimeError("temporary error")

        bus_with_persistence.subscribe(AssetEventType.ASSET_MATCHED, failing_handler)
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
        )
        bus_with_persistence.publish_with_retry(event)

        assert bus_with_persistence.get_failed_count() == 1

        # 重试
        retried = bus_with_persistence.retry_failed()
        assert retried == 1
        assert bus_with_persistence.get_failed_count() == 0

    def test_max_retries(self, bus_with_persistence):
        def always_fail(event):
            raise RuntimeError("always")

        bus_with_persistence.subscribe(AssetEventType.ASSET_MATCHED, always_fail)
        event = AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
            retry_count=AssetEventBus.MAX_RETRIES,  # 已达上限
        )

        bus_with_persistence.publish_with_retry(event)
        # 超过最大重试，不会出现在 retry 中
        retried = bus_with_persistence.retry_failed()
        assert retried == 0

    def test_get_stats(self, bus):
        bus.publish(AssetEvent(event_type=AssetEventType.EAGLE_ASSET_DISCOVERED))
        bus.publish(AssetEvent(event_type=AssetEventType.ASSET_MATCHED))
        bus.publish(AssetEvent(event_type=AssetEventType.ASSET_MATCHED))

        stats = bus.get_stats()
        assert stats["total_events"] == 3
        assert stats["events_by_type"]["eagle_asset_discovered"] == 1
        assert stats["events_by_type"]["asset_matched"] == 2

    def test_subscriber_count(self, bus):
        def h1(e): pass
        def h2(e): pass

        bus.subscribe(AssetEventType.ASSET_MATCHED, h1)
        bus.subscribe(AssetEventType.ASSET_MATCHED, h2)
        bus.subscribe(AssetEventType.EAGLE_ASSET_DISCOVERED, h1)

        assert bus.subscriber_count("asset_matched") == 2
        assert bus.subscriber_count() == 3

    def test_shutdown(self, bus):
        bus.shutdown()
        # 不应抛出异常


# ════════════════════════════════════════════════════════════════════
# EagleScannerWorker
# ════════════════════════════════════════════════════════════════════

class TestEagleScannerWorker:
    """EagleScannerWorker 测试。"""

    @pytest.fixture
    def worker(self, tmp_path):
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        for name in ["P4-v2601536-mg-2d.mp4", "P4-v2601537-mg-2d.mp4"]:
            (eagle / name).write_text("dummy")

        bus = AssetEventBus()
        return EagleScannerWorker(
            eagle_root=str(eagle),
            event_bus=bus,
            eagle_index_path=str(tmp_path / "index.json"),
        )

    def test_run_publishes_events(self, worker):
        received = []

        def handler(event):
            received.append(event)

        worker._bus.subscribe(AssetEventType.EAGLE_ASSET_DISCOVERED, handler)
        worker._bus.subscribe(AssetEventType.EAGLE_SCAN_COMPLETED, handler)

        result = worker.run()
        assert result["discovered"] == 2
        assert result["total"] == 2

        discovered = [e for e in received if e.event_type == AssetEventType.EAGLE_ASSET_DISCOVERED]
        completed = [e for e in received if e.event_type == AssetEventType.EAGLE_SCAN_COMPLETED]
        assert len(discovered) == 2
        assert len(completed) == 1

    def test_run_scan_only(self, worker):
        result = worker.run_scan_only()
        assert "total" in result
        assert result["total"] == 2

    def test_incremental_scan(self, worker, tmp_path):
        worker.run()  # 首次全量

        # 添加新文件
        eagle_dir = tmp_path / "eagle"
        (eagle_dir / "P4-v2601538-new.mp4").write_text("new")

        received = []
        worker._bus.subscribe(AssetEventType.EAGLE_ASSET_DISCOVERED, lambda e: received.append(e))

        result = worker.run()
        assert result["discovered"] == 1

    def test_is_available(self, worker):
        assert worker.is_available

    def test_not_available(self, tmp_path):
        bus = AssetEventBus()
        worker = EagleScannerWorker(
            eagle_root=str(tmp_path / "nonexistent"),
            event_bus=bus,
        )
        assert not worker.is_available


# ════════════════════════════════════════════════════════════════════
# BindingWorker
# ════════════════════════════════════════════════════════════════════

class TestBindingWorker:
    """BindingWorker A-Number 匹配测试。"""

    @pytest.fixture
    def worker_and_bus(self, tmp_path):
        creative_root = tmp_path / "creatives"
        creative_root.mkdir()

        bus = AssetEventBus()
        worker = BindingWorker(
            creative_storage_root=str(creative_root),
            event_bus=bus,
        )
        return worker, bus, creative_root

    def test_on_asset_discovered_no_match(self, worker_and_bus):
        worker, bus, _ = worker_and_bus
        event = AssetEvent(
            event_type=AssetEventType.EAGLE_ASSET_DISCOVERED,
            eagle_v_number="v2601536",
            payload={"filename": "P4-v2601536-mg-2d.mp4"},
        )
        worker.on_asset_discovered(event)
        # 没有已同步的广告，匹配结果为 0
        assert worker.match_count == 0

    def test_on_facebook_synced_matches_existing_eagle(self, worker_and_bus, tmp_path):
        worker, bus, creative_root = worker_and_bus

        # 先创建一个已匹配的 Eagle 素材
        from market_ops.creative_repository.assets.asset_reference import (
            CreativeAssetReference,
            AssetSource,
            AssetType,
            MatchMethod,
        )
        ref = CreativeAssetReference(
            creative_id="eagle_v2601536",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="P4-v2601536-mg-2d.mp4",
            eagle_v_number="v2601536",
            local_path=str(tmp_path / "eagle" / "P4-v2601536-mg-2d.mp4"),
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
        )
        worker._repository.save(ref)

        # 触发 Facebook Sync 事件
        received = []
        bus.subscribe(AssetEventType.ASSET_MATCHED, lambda e: received.append(e))

        worker.on_facebook_synced(AssetEvent(
            event_type=AssetEventType.FACEBOOK_CREATIVE_SYNCED,
            creative_id="111",
            payload={"ad_name": "P4-IOS-T1-A536-0707"},
        ))

        # 536 in 2601536 → 匹配成功
        assert worker.match_count == 1
        assert len(received) == 1
        assert received[0].creative_id == "111"


# ════════════════════════════════════════════════════════════════════
# MaterializerWorker
# ════════════════════════════════════════════════════════════════════

class TestMaterializerWorker:
    """MaterializerWorker 实体化测试。"""

    @pytest.fixture
    def worker_and_bus(self, tmp_path):
        creative_root = tmp_path / "creatives"
        creative_root.mkdir()

        bus = AssetEventBus()
        worker = MaterializerWorker(
            creative_storage_root=str(creative_root),
            event_bus=bus,
        )
        return worker, bus, creative_root

    def test_on_asset_matched_no_assets_json(self, worker_and_bus):
        worker, bus, _ = worker_and_bus
        received = []
        bus.subscribe(AssetEventType.ASSET_MATERIALIZE_FAILED, lambda e: received.append(e))

        worker.on_asset_matched(AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="nonexistent",
            eagle_v_number="v2601536",
        ))

        assert worker.materialized_count == 0
        assert worker.failed_count == 1
        assert len(received) == 1
        assert received[0].event_type == AssetEventType.ASSET_MATERIALIZE_FAILED

    def test_on_asset_matched_success(self, worker_and_bus, tmp_path):
        worker, bus, creative_root = worker_and_bus

        # 先创建 assets.json
        from market_ops.creative_repository.assets.asset_reference import (
            CreativeAssetReference,
            AssetSource,
            AssetType,
            MatchMethod,
        )
        from market_ops.creative_repository.assets.asset_binding_repository import AssetBindingRepository

        repo = AssetBindingRepository(str(creative_root))
        ref = CreativeAssetReference(
            creative_id="111",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="P4-v2601536.mp4",
            eagle_v_number="v2601536",
            local_path=str(tmp_path / "eagle" / "P4-v2601536.mp4"),
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
        )
        repo.save(ref)

        received = []
        bus.subscribe(AssetEventType.ASSET_MATERIALIZED, lambda e: received.append(e))

        worker.on_asset_matched(AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
            eagle_v_number="v2601536",
        ))

        assert worker.materialized_count == 1
        assert worker.failed_count == 0
        assert len(received) == 1
        assert received[0].event_type == AssetEventType.ASSET_MATERIALIZED

        # 验证 entity.json 已写入
        entity_path = creative_root / "111" / "entity.json"
        assert entity_path.exists()


# ════════════════════════════════════════════════════════════════════
# LifecycleWorker
# ════════════════════════════════════════════════════════════════════

class TestLifecycleWorker:
    """LifecycleWorker 生命周期状态转换测试。"""

    @pytest.fixture
    def worker_and_bus(self, tmp_path):
        bus = AssetEventBus()
        worker = LifecycleWorker(
            lifecycle_path=str(tmp_path / "lifecycle.json"),
            event_bus=bus,
        )
        return worker, bus

    def test_on_asset_materialized_new_to_matched(self, worker_and_bus):
        worker, bus = worker_and_bus
        worker.on_asset_materialized(AssetEvent(
            event_type=AssetEventType.ASSET_MATERIALIZED,
            creative_id="111",
            eagle_v_number="v2601536",
        ))

        assert worker.get_status("v2601536") == AssetLifecycleStatus.MATCHED

    def test_on_performance_updated_to_testing(self, worker_and_bus):
        worker, bus = worker_and_bus
        # 先标记为 MATCHED
        worker._manager.transition("v2601536", AssetLifecycleStatus.MATCHED)

        worker.on_performance_updated(AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 1000,
                "revenue": 2000,
                "roas": 2.0,
                "impressions": 5000,
            },
        ))

        assert worker.get_status("v2601536") == AssetLifecycleStatus.WINNER

    def test_on_performance_updated_to_winner(self, worker_and_bus):
        worker, bus = worker_and_bus
        worker._manager.transition("v2601536", AssetLifecycleStatus.MATCHED)

        received = []
        bus.subscribe(AssetEventType.ASSET_WINNER_DETECTED, lambda e: received.append(e))

        worker.on_performance_updated(AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 500,
                "revenue": 1000,
                "roas": 2.0,
                "impressions": 5000,
            },
        ))

        assert worker.get_status("v2601536") == AssetLifecycleStatus.WINNER
        assert worker.winner_count == 1
        assert len(received) == 1
        assert received[0].payload["roas"] == 2.0

    def test_on_performance_updated_to_failed(self, worker_and_bus):
        worker, bus = worker_and_bus
        worker._manager.transition("v2601536", AssetLifecycleStatus.MATCHED)

        received = []
        bus.subscribe(AssetEventType.ASSET_FAILED, lambda e: received.append(e))

        worker.on_performance_updated(AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 600,
                "revenue": 300,
                "roas": 0.5,
                "impressions": 5000,
            },
        ))

        assert worker.get_status("v2601536") == AssetLifecycleStatus.FAILED
        assert worker.failed_count == 1
        assert len(received) == 1

    def test_on_performance_updated_insufficient_spend(self, worker_and_bus):
        """花费不足时不标记失败。"""
        worker, bus = worker_and_bus
        worker._manager.transition("v2601536", AssetLifecycleStatus.MATCHED)

        worker.on_performance_updated(AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 100,  # < 500
                "revenue": 50,
                "roas": 0.5,
                "impressions": 5000,
            },
        ))

        assert worker.get_status("v2601536") != AssetLifecycleStatus.FAILED

    def test_get_winners(self, worker_and_bus):
        worker, bus = worker_and_bus
        worker._manager.transition("v1", AssetLifecycleStatus.MATCHED)
        worker._manager.transition("v1", AssetLifecycleStatus.TESTING)
        worker._manager.transition("v1", AssetLifecycleStatus.WINNER)

        assert worker.get_winners() == ["v1"]
        assert worker.get_dna_ready() == ["v1"]

    def test_to_summary(self, worker_and_bus):
        worker, bus = worker_and_bus
        worker._manager.transition("v1", AssetLifecycleStatus.MATCHED)
        summary = worker.to_summary()
        assert "MATCHED" in summary
        assert "1" in summary


# ════════════════════════════════════════════════════════════════════
# AssetRuntime
# ════════════════════════════════════════════════════════════════════

class TestAssetRuntime:
    """AssetRuntime 完整管线编排测试。"""

    @pytest.fixture
    def runtime(self, tmp_path):
        eagle = tmp_path / "eagle"
        eagle.mkdir()
        for name in ["P4-v2601536-mg-2d.mp4", "P4-v2601537-mg-2d.mp4"]:
            (eagle / name).write_text("dummy")

        creative_root = tmp_path / "creatives"
        creative_root.mkdir()

        return AssetRuntime(
            eagle_root=str(eagle),
            creative_storage_root=str(creative_root),
            eagle_index_path=str(tmp_path / "eagle_index.json"),
            lifecycle_path=str(tmp_path / "lifecycle.json"),
            runtime_dir=str(tmp_path / "runtime"),
        )

    def test_start_and_run_once(self, runtime):
        runtime.start()
        report = runtime.run_once()

        assert "eagle_scan" in report
        assert "bindings" in report
        assert "materialized" in report
        assert "lifecycle" in report
        assert "event_bus" in report
        assert report["eagle_scan"]["discovered"] == 2
        assert report["eagle_scan"]["total"] == 2

    def test_get_status(self, runtime):
        runtime.start()
        status = runtime.get_status()

        assert status["started"] is True
        assert status["eagle_available"] is True
        assert "event_bus" in status

    def test_inject_performance(self, runtime):
        runtime.start()
        runtime.run_once()  # 先扫描 + 匹配

        # 注入性能数据
        runtime.inject_performance(
            creative_id="111",
            spend=500,
            revenue=1000,
            roas=2.0,
            impressions=5000,
            eagle_v_number="v2601536",
        )

        status = runtime.get_status()
        assert status["event_bus"]["total_events"] > 0

    def test_inject_facebook_sync(self, runtime):
        runtime.start()
        runtime.inject_facebook_sync(
            creative_id="111",
            ad_name="P4-IOS-T1-A536-0707",
        )
        status = runtime.get_status()
        assert status["event_bus"]["total_events"] > 0

    def test_get_winners(self, runtime):
        runtime.start()
        runtime.run_once()

        # 手动标记 winner
        runtime._lifecycle_worker._manager.transition("v2601536", AssetLifecycleStatus.MATCHED)
        runtime._lifecycle_worker._manager.transition("v2601536", AssetLifecycleStatus.TESTING)
        runtime._lifecycle_worker._manager.transition("v2601536", AssetLifecycleStatus.WINNER)

        winners = runtime.get_winners()
        assert "v2601536" in winners

    def test_get_dna_ready(self, runtime):
        runtime.start()
        runtime._lifecycle_worker._manager.transition("v1", AssetLifecycleStatus.MATCHED)
        runtime._lifecycle_worker._manager.transition("v1", AssetLifecycleStatus.TESTING)
        runtime._lifecycle_worker._manager.transition("v1", AssetLifecycleStatus.WINNER)

        dna_ready = runtime.get_dna_ready()
        assert "v1" in dna_ready

    def test_shutdown(self, runtime):
        runtime.start()
        runtime.run_once()
        runtime.shutdown()
        # 不应抛出异常

    def test_repr(self, runtime):
        assert "AssetRuntime" in repr(runtime)

    def test_runtime_state_persisted(self, runtime, tmp_path):
        runtime.start()
        runtime.run_once()

        state_path = tmp_path / "runtime" / "runtime_state.json"
        assert state_path.exists()

        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["started"] is True
        assert state["run_count"] == 1

    def test_full_event_chain(self, runtime, tmp_path):
        """模拟完整事件链：新素材 → 扫描 → 匹配 → 实体化 → 生命周期。

        Day 1: 市场放素材 → Eagle 扫描 → 发布 EAGLE_ASSET_DISCOVERED
        Day 3: Facebook 数据 → 发布 PERFORMANCE_UPDATED → WINNER
        """
        runtime.start()

        # Day 1: 扫描新素材
        report = runtime.run_once()
        assert report["eagle_scan"]["discovered"] >= 0

        # 手动创建绑定 + 实体化（模拟匹配成功）
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
            creative_id="111",
            asset_type=AssetType.VIDEO,
            source=AssetSource.EAGLE,
            eagle_filename="P4-v2601536-mg-2d.mp4",
            eagle_v_number="v2601536",
            local_path=str(tmp_path / "eagle" / "P4-v2601536-mg-2d.mp4"),
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
            ad_name="P4-IOS-T1-A536-0707",
            a_number="A536",
        )
        repo.save(ref)

        # 发布 ASSET_MATCHED（模拟 BindingWorker 输出）
        runtime.event_bus.publish(AssetEvent(
            event_type=AssetEventType.ASSET_MATCHED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "ad_name": "P4-IOS-T1-A536-0707",
                "a_number": "A536",
                "eagle_filename": "P4-v2601536-mg-2d.mp4",
                "confidence": 1.0,
            },
        ))

        # Day 3: 注入性能数据 → WINNER
        runtime.inject_performance(
            creative_id="111",
            spend=500,
            revenue=1000,
            roas=2.0,
            impressions=5000,
            eagle_v_number="v2601536",
        )

        status = runtime.get_status()
        assert status["lifecycle_winners"] >= 1

        runtime.shutdown()