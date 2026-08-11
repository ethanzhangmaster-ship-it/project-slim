"""Phase 2.2A Final: Domain Event Architecture — comprehensive validation.

Tests:
  1. Dashboard renders
  2. BaseEvent: frozen + version + to_dict
  3. Event Bus: publish/subscribe/unsubscribe/async/priority/middleware
  4. Event Bus: PublishContext, replay log
  5. Worker Observer: heartbeat, offline, counters (via Event Bus)
  6. Queue Observer: depth, oldest, wait times (read-only)
  7. Latency Observer: recording, percentiles (via Event Bus)
  8. SnapshotService: memory cache (TTL + invalidate)
  9. ObserverRegistry: declarative bootstrap
  10. Observability read-only on core
  11. Worker has NO direct monitor dependency
  12. Full integration: Event Bus → Registry → Observers → SnapshotService → Dashboard
"""

import json
import os
import sys
import time
import uuid
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.core.generation_store import GenerationStore
from market_ops.observability.observability_store import ObservabilityStore
from market_ops.observability.event_bus import (
    EventBus, PublishContext, LoggerMiddleware, MetricsMiddleware,
)
from market_ops.observability.events import (
    BaseEvent, WorkerRegistered, WorkerHeartbeat, WorkerOffline,
    TaskStarted, TaskFinished, TaskFailed,
    PipelineStarted, PipelineFinished,
)
from market_ops.observability.observers.worker_observer import WorkerObserver
from market_ops.observability.observers.queue_observer import QueueObserver
from market_ops.observability.observers.latency_observer import LatencyObserver
from market_ops.observability.observers.snapshot_observer import SnapshotObserver
from market_ops.observability.snapshot_service import SnapshotService
from market_ops.observability.registry import ObserverRegistry
from market_ops.observability.dashboard import GenerationDashboard


# ── Helpers ──

def _make_core_db() -> GenerationStore:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="core_")
    os.close(fd)
    return GenerationStore(db_path=path)


def _make_obs_db() -> ObservabilityStore:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="obs_")
    os.close(fd)
    return ObservabilityStore(db_path=path)


def _insert(core: GenerationStore, creative_id: str, prompt: str = "test prompt") -> str:
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    core.insert({
        "id": task_id, "creative_id": creative_id, "prompt": prompt,
        "priority": "normal", "format": "1080x1080",
        "dna_source": "test", "batch_id": "batch_001",
    })
    return task_id


def _complete_task(core: GenerationStore, task_id: str, generation_time: float = 3.5,
                   worker_id: str = "test_worker") -> None:
    core.claim_task(task_id, worker_id)
    core.start_processing(task_id, worker_id)
    core.update_status(task_id, "SUCCESS", generation_time=generation_time, cost=0.05)


def _cleanup(core=None, obs=None, replay_path=None):
    for obj in [core, obs]:
        if obj is not None:
            try:
                p = Path(obj._db_path)
                if p.exists():
                    p.unlink(missing_ok=True)
            except Exception:
                pass
    if replay_path:
        try:
            p = Path(replay_path)
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# 1. Dashboard
# ═══════════════════════════════════════════════════════════

def test_dashboard_renders():
    core, obs = _make_core_db(), _make_obs_db()
    dashboard = GenerationDashboard(core_db=core._db_path, obs_db=obs._db_path)
    output = dashboard.render()
    assert "LOVART PRODUCTION DASHBOARD" in output
    assert "Queue" in output
    assert "Workers" in output
    _cleanup(core, obs)
    return True


# ═══════════════════════════════════════════════════════════
# 2. BaseEvent: frozen + version
# ═══════════════════════════════════════════════════════════

def test_base_event_frozen():
    """Events should be immutable after creation."""
    evt = TaskStarted(task_id="t1", worker_id="w1", creative_id="c1")
    try:
        evt.task_id = "modified"  # type: ignore
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass  # Expected
    return True


def test_base_event_version():
    """All events should have version field."""
    evt = TaskFinished(task_id="t2", worker_id="w1", creative_id="c2", generation_time=1.0, cost=0.05)
    assert evt.version == "1.0"
    assert evt.event_type == "TaskFinished"
    return True


def test_base_event_to_dict():
    """to_dict() should serialize all BaseEvent fields."""
    evt = TaskStarted(task_id="t1", worker_id="w1", creative_id="c1")
    d = evt.to_dict()
    assert d["event_id"].startswith("evt_")
    assert d["event_type"] == "TaskStarted"
    assert d["version"] == "1.0"
    assert "timestamp" in d
    return True


# ═══════════════════════════════════════════════════════════
# 3. Event Bus: core
# ═══════════════════════════════════════════════════════════

def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []
    bus.subscribe(TaskStarted, lambda e: received.append(e.task_id))
    bus.publish(TaskStarted(task_id="task_001", worker_id="w1", creative_id="c1"))
    bus.publish(TaskStarted(task_id="task_002", worker_id="w1", creative_id="c2"))
    assert received == ["task_001", "task_002"]
    return True


def test_event_bus_subscriber_isolation():
    bus = EventBus()
    received = []

    def bad_handler(event):
        raise RuntimeError("subscriber error")

    bus.subscribe(TaskFinished, bad_handler)
    bus.subscribe(TaskFinished, lambda e: received.append(e.task_id))

    bus.publish(TaskFinished(task_id="task_ok", worker_id="w1", creative_id="c1",
                             generation_time=1.0, cost=0.05))
    assert received == ["task_ok"]
    return True


def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []
    handler = lambda e: received.append(e.task_id)
    bus.subscribe(TaskFailed, handler)
    bus.publish(TaskFailed(task_id="t1", worker_id="w1", creative_id="c1", error="e", final_status="RETRY"))
    assert received == ["t1"]
    bus.unsubscribe(TaskFailed, handler)
    bus.publish(TaskFailed(task_id="t2", worker_id="w1", creative_id="c2", error="e", final_status="RETRY"))
    assert received == ["t1"]
    return True


def test_event_bus_publish_async():
    bus = EventBus(max_workers=2)
    received = []
    bus.subscribe(TaskFinished, lambda e: received.append(e.task_id))

    bus.publish_async(TaskFinished(task_id="async_1", worker_id="w1", creative_id="c1", generation_time=1.0, cost=0.05))
    bus.publish_async(TaskFinished(task_id="async_2", worker_id="w1", creative_id="c2", generation_time=1.0, cost=0.05))
    bus.shutdown()
    assert len(received) == 2
    return True


def test_event_bus_observer_priority():
    """Higher priority observers should execute first."""
    bus = EventBus()
    order = []
    bus.subscribe(TaskStarted, lambda e: order.append("low"), priority=50)
    bus.subscribe(TaskStarted, lambda e: order.append("high"), priority=100)
    bus.subscribe(TaskStarted, lambda e: order.append("mid"), priority=75)

    bus.publish(TaskStarted(task_id="t1", worker_id="w1", creative_id="c1"))
    assert order == ["high", "mid", "low"]
    return True


def test_event_bus_middleware_with_context():
    """Middleware should receive PublishContext."""
    bus = EventBus()
    ctxs = []
    bus.use(lambda e, ctx, n: (ctxs.append(ctx), n()))

    bus.publish(TaskStarted(task_id="t1", worker_id="w1", creative_id="c1"))
    assert len(ctxs) == 1
    assert ctxs[0].trace_id.startswith("trace_")
    assert ctxs[0].span_id.startswith("span_")
    return True


def test_event_bus_middleware_chain():
    bus = EventBus()
    order = []
    bus.use(lambda e, ctx, n: (order.append("A"), n()))
    bus.use(lambda e, ctx, n: (order.append("B"), n()))
    received = []
    bus.subscribe(TaskStarted, lambda e: received.append(e.task_id))
    bus.publish(TaskStarted(task_id="t1", worker_id="w1", creative_id="c1"))
    assert order == ["A", "B"]
    assert received == ["t1"]
    return True


# ═══════════════════════════════════════════════════════════
# 4. Event Bus: PublishContext + Replay
# ═══════════════════════════════════════════════════════════

def test_publish_context():
    ctx = PublishContext.create(correlation_id="corr_123", request_id="req_456")
    assert ctx.trace_id.startswith("trace_")
    assert ctx.correlation_id == "corr_123"
    assert ctx.request_id == "req_456"
    assert ctx.span_id.startswith("span_")
    return True


def test_event_bus_replay():
    fd, replay_path = tempfile.mkstemp(suffix=".jsonl", prefix="replay_")
    os.close(fd)

    bus = EventBus(replay_log=replay_path)
    received = []
    bus.subscribe(TaskFinished, lambda e: received.append(e.task_id))

    # Publish events (will be written to replay log)
    bus.publish(TaskFinished(task_id="r1", worker_id="w1", creative_id="c1", generation_time=1.0, cost=0.05))
    bus.publish(TaskFinished(task_id="r2", worker_id="w1", creative_id="c2", generation_time=2.0, cost=0.05))

    # Create a new bus and replay
    bus2 = EventBus()
    replayed = []
    bus2.subscribe(TaskFinished, lambda e: replayed.append(e.task_id))
    count = bus2.replay(replay_path)
    assert count == 2
    assert replayed == ["r1", "r2"]

    _cleanup(replay_path=replay_path)
    return True


# ═══════════════════════════════════════════════════════════
# 5. Worker Observer
# ═══════════════════════════════════════════════════════════

def test_worker_observer_heartbeat():
    obs = _make_obs_db()
    bus = EventBus()
    observer = WorkerObserver(store=obs)
    observer._subscribe(bus)
    bus.publish(WorkerRegistered(worker_id="worker_01"))
    bus.publish(WorkerHeartbeat(worker_id="worker_01", status="RUNNING", current_task="task_001"))
    workers = observer.get_all()
    assert len(workers) == 1
    assert workers[0]["status"] == "RUNNING"
    assert workers[0]["online"] is True
    _cleanup(obs=obs)
    return True


def test_worker_observer_offline():
    obs = _make_obs_db()
    bus = EventBus()
    observer = WorkerObserver(store=obs)
    observer._subscribe(bus)
    bus.publish(WorkerRegistered(worker_id="worker_02"))

    import sqlite3
    from datetime import datetime, timezone, timedelta
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    conn = sqlite3.connect(str(obs._db_path))
    conn.execute("UPDATE worker_status SET heartbeat_at = ? WHERE worker_id = ?", (old_time, "worker_02"))
    conn.commit()
    conn.close()

    assert observer.get_all()[0]["online"] is False
    _cleanup(obs=obs)
    return True


def test_worker_observer_counters():
    obs = _make_obs_db()
    bus = EventBus()
    observer = WorkerObserver(store=obs)
    observer._subscribe(bus)
    bus.publish(WorkerRegistered(worker_id="worker_03"))
    bus.publish(TaskFinished(task_id="t1", worker_id="worker_03", creative_id="c1", generation_time=1.0, cost=0.05))
    bus.publish(TaskFinished(task_id="t2", worker_id="worker_03", creative_id="c2", generation_time=2.0, cost=0.05))
    bus.publish(TaskFailed(task_id="t3", worker_id="worker_03", creative_id="c3", error="timeout", final_status="RETRY"))
    workers = observer.get_all()
    assert workers[0]["tasks_completed"] == 2
    assert workers[0]["tasks_failed"] == 1
    _cleanup(obs=obs)
    return True


# ═══════════════════════════════════════════════════════════
# 6. Queue Observer
# ═══════════════════════════════════════════════════════════

def test_queue_observer_depth():
    core = _make_core_db()
    for i in range(5):
        _insert(core, f"c{i:03d}")
    qo = QueueObserver(store=core)
    assert qo.depth()["pending"] == 5
    _cleanup(core=core)
    return True


def test_queue_observer_oldest():
    core = _make_core_db()
    _insert(core, "c001", "prompt_a")
    time.sleep(0.1)
    _insert(core, "c002", "prompt_b")
    assert QueueObserver(store=core).oldest_pending()["creative_id"] == "c001"
    _cleanup(core=core)
    return True


# ═══════════════════════════════════════════════════════════
# 7. Latency Observer
# ═══════════════════════════════════════════════════════════

def test_latency_observer_via_bus():
    core, obs = _make_core_db(), _make_obs_db()
    bus = EventBus()
    lo = LatencyObserver(core_store=core, obs_store=obs)
    lo._subscribe(bus)
    task_id = _insert(core, "c_lat", "prompt")
    _complete_task(core, task_id, generation_time=5.2)
    bus.publish(TaskFinished(task_id=task_id, worker_id="w1", creative_id="c_lat", generation_time=5.2, cost=0.05))
    assert lo.get_stats(hours=24)["count"] == 1
    _cleanup(core, obs)
    return True


def test_latency_observer_percentiles():
    core, obs = _make_core_db(), _make_obs_db()
    lo = LatencyObserver(core_store=core, obs_store=obs)
    task_ids = []
    for i, gen_time in enumerate([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]):
        tid = _insert(core, f"c_p{i:03d}", f"prompt_{i}")
        _complete_task(core, tid, generation_time=gen_time)
        task_ids.append(tid)
    for tid in task_ids:
        lo.record_manual(tid)
    stats = lo.get_stats(hours=24)
    assert stats["count"] == 10
    assert stats["percentiles"]["p50"] > 0
    _cleanup(core, obs)
    return True


# ═══════════════════════════════════════════════════════════
# 8. SnapshotService: cache
# ═══════════════════════════════════════════════════════════

def test_snapshot_service_cache():
    core, obs = _make_core_db(), _make_obs_db()
    wo = WorkerObserver(store=obs)
    lo = LatencyObserver(core_store=core, obs_store=obs)
    qo = QueueObserver(store=core)
    svc = SnapshotService(core_store=core, obs_store=obs, worker_observer=wo, latency_observer=lo, queue_observer=qo)

    snap1 = svc.get_snapshot()
    snap2 = svc.get_snapshot()
    assert snap1 is snap2  # Same object from cache

    svc.invalidate()
    snap3 = svc.get_snapshot()
    assert snap3 is not snap1  # New object after invalidate

    _cleanup(core, obs)
    return True


def test_snapshot_service_current():
    core, obs = _make_core_db(), _make_obs_db()
    wo = WorkerObserver(store=obs)
    lo = LatencyObserver(core_store=core, obs_store=obs)
    qo = QueueObserver(store=core)
    svc = SnapshotService(core_store=core, obs_store=obs, worker_observer=wo, latency_observer=lo, queue_observer=qo)

    snap = svc.current
    assert "queue" in snap
    assert "workers" in snap
    assert "production" in snap
    _cleanup(core, obs)
    return True


# ═══════════════════════════════════════════════════════════
# 9. ObserverRegistry
# ═══════════════════════════════════════════════════════════

def test_observer_registry():
    bus = EventBus()
    registry = ObserverRegistry(bus)
    obs = _make_obs_db()

    wo = WorkerObserver(store=obs)
    registry.register(wo, priority=100)
    assert registry.count == 1

    registry.bootstrap()

    # Verify observer is wired: publish heartbeat, check it's recorded
    bus.publish(WorkerRegistered(worker_id="w_reg"))
    bus.publish(WorkerHeartbeat(worker_id="w_reg", status="RUNNING"))

    workers = wo.get_all()
    assert len(workers) == 1
    assert workers[0]["worker_id"] == "w_reg"

    _cleanup(obs=obs)
    return True


# ═══════════════════════════════════════════════════════════
# 10. Read-only
# ═══════════════════════════════════════════════════════════

def test_observability_readonly():
    core, obs = _make_core_db(), _make_obs_db()
    task_id = _insert(core, "c_ro", "readonly test")
    assert core.get(task_id)["status"] == "PENDING"
    QueueObserver(store=core).depth()
    LatencyObserver(core_store=core, obs_store=obs).record_manual(task_id)
    obs.snapshot_current_state(core.get_stats())
    assert core.get(task_id)["status"] == "PENDING"
    _cleanup(core, obs)
    return True


# ═══════════════════════════════════════════════════════════
# 11. Worker decoupling
# ═══════════════════════════════════════════════════════════

def test_worker_no_monitor_import():
    import ast
    worker_path = Path(__file__).parent.parent / "src" / "market_ops" / "core" / "lovart_worker.py"
    source = worker_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    for banned in ["worker_observer", "latency_observer", "queue_observer",
                   "worker_monitor", "latency_monitor", "queue_metrics", "registry"]:
        assert banned not in str(imports), f"Worker should not import {banned}"
    return True


# ═══════════════════════════════════════════════════════════
# 12. Full integration
# ═══════════════════════════════════════════════════════════

def test_full_integration():
    core, obs = _make_core_db(), _make_obs_db()
    bus = EventBus()

    # Wire up via Registry
    registry = ObserverRegistry(bus)
    wo = WorkerObserver(store=obs)
    lo = LatencyObserver(core_store=core, obs_store=obs)
    qo = QueueObserver(store=core)
    so = SnapshotObserver(core_store=core, obs_store=obs)
    registry.register(wo, priority=100).register(lo, priority=80).register(so, priority=50)
    registry.bootstrap()

    svc = SnapshotService(core_store=core, obs_store=obs, worker_observer=wo, latency_observer=lo, queue_observer=qo)

    # Simulate worker lifecycle
    task_ids = [_insert(core, f"c_int_{i}", f"integration {i}") for i in range(3)]
    bus.publish(WorkerRegistered(worker_id="worker_01"))
    bus.publish(WorkerHeartbeat(worker_id="worker_01", status="RUNNING", current_task=task_ids[0]))

    _complete_task(core, task_ids[0], generation_time=4.2)
    bus.publish(TaskFinished(task_id=task_ids[0], worker_id="worker_01", creative_id="c_int_0", generation_time=4.2, cost=0.05))
    bus.publish(TaskFailed(task_id=task_ids[1], worker_id="worker_01", creative_id="c_int_1", error="timeout", final_status="RETRY"))

    # Verify
    assert wo.get_all()[0]["tasks_completed"] == 1
    assert wo.get_all()[0]["tasks_failed"] == 1
    assert lo.get_stats(hours=24)["count"] == 1
    assert svc.current["workers"]["workers"][0]["worker_id"] == "worker_01"

    dashboard = GenerationDashboard(core_db=core._db_path, obs_db=obs._db_path)
    assert "worker_01" in dashboard.render()

    _cleanup(core, obs)
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("Dashboard 渲染", test_dashboard_renders),
        ("BaseEvent frozen", test_base_event_frozen),
        ("BaseEvent version", test_base_event_version),
        ("BaseEvent to_dict", test_base_event_to_dict),
        ("Event Bus 发布/订阅", test_event_bus_publish_subscribe),
        ("Event Bus 订阅者异常隔离", test_event_bus_subscriber_isolation),
        ("Event Bus 取消订阅", test_event_bus_unsubscribe),
        ("Event Bus 异步发布", test_event_bus_publish_async),
        ("Event Bus Observer 优先级", test_event_bus_observer_priority),
        ("Event Bus Middleware + Context", test_event_bus_middleware_with_context),
        ("Event Bus Middleware 链", test_event_bus_middleware_chain),
        ("PublishContext", test_publish_context),
        ("Event Bus Replay", test_event_bus_replay),
        ("Worker Observer", test_worker_observer_heartbeat),
        ("Worker Observer 离线", test_worker_observer_offline),
        ("Worker Observer 计数器", test_worker_observer_counters),
        ("Queue Observer", test_queue_observer_depth),
        ("Queue Observer 最老任务", test_queue_observer_oldest),
        ("Latency Observer", test_latency_observer_via_bus),
        ("Latency Observer 百分位", test_latency_observer_percentiles),
        ("SnapshotService Cache", test_snapshot_service_cache),
        ("SnapshotService.current", test_snapshot_service_current),
        ("ObserverRegistry", test_observer_registry),
        ("只读核心数据", test_observability_readonly),
        ("Worker 无 Monitor 依赖", test_worker_no_monitor_import),
        ("完整集成路径", test_full_integration),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  Phase 2.2A Final: Domain Event Architecture Validation")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            result = fn()
            if result:
                passed += 1
                print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    print(f"  Results: {passed}/{passed + failed} PASS")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)