"""V4.4.1 Production Runtime — Extended Release Gate.

Per architecture review, expanded from 50 → 100 tests:
  1-10. Original 50 tests (imported from release_gate_v44)
  11. State Manager (5)
  12. Event Bus (5)
  13. Lock Manager (5)
  14. Rate Limiter (5)
  15. Artifact Manager (5)
  16. Secret Manager (5)
  17. OnErrorPolicy / Workflow (5)
  18. Chaos Tests (10)
  19. Performance Tests (5)

Total: 100 tests. All must PASS.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.production_runtime.schemas import (
    RuntimeTask, TaskStatus, TaskPriority, WorkerType, WorkerStatus, Worker,
    ResourceType, ResourceState, HealthStatus, HealthReport, RuntimeMetrics,
    Alert, AlertLevel, Checkpoint, WorkflowNode, WorkflowDAG, RuntimeReport,
    ScheduleType, WorkflowState, OnErrorPolicy, ArtifactType, ArtifactStatus,
    SecretLevel, WorkflowStateData, RuntimeEvent, DistributedLock, Artifact, Secret,
)
from market_ops.creative_brain.production_runtime.config_manager import ConfigManager
from market_ops.creative_brain.production_runtime.logger import Logger
from market_ops.creative_brain.production_runtime.task_queue import TaskQueue
from market_ops.creative_brain.production_runtime.worker_pool import WorkerPool
from market_ops.creative_brain.production_runtime.cache_manager import CacheManager
from market_ops.creative_brain.production_runtime.dependency_graph import DependencyGraph
from market_ops.creative_brain.production_runtime.retry_manager import RetryManager
from market_ops.creative_brain.production_runtime.rollback_manager import RollbackManager
from market_ops.creative_brain.production_runtime.checkpoint_manager import CheckpointManager
from market_ops.creative_brain.production_runtime.resource_manager import ResourceManager
from market_ops.creative_brain.production_runtime.health_monitor import HealthMonitor
from market_ops.creative_brain.production_runtime.metrics_collector import MetricsCollector
from market_ops.creative_brain.production_runtime.alert_manager import AlertManager
from market_ops.creative_brain.production_runtime.service_registry import ServiceRegistry
from market_ops.creative_brain.production_runtime.plugin_manager import PluginManager
from market_ops.creative_brain.production_runtime.scheduler import Scheduler
from market_ops.creative_brain.production_runtime.workflow_engine import WorkflowEngine
from market_ops.creative_brain.production_runtime.runtime_api import RuntimeAPI
from market_ops.creative_brain.production_runtime.runtime_engine import RuntimeEngine
from market_ops.creative_brain.production_runtime.state_manager import StateManager
from market_ops.creative_brain.production_runtime.event_bus import EventBus
from market_ops.creative_brain.production_runtime.lock_manager import LockManager
from market_ops.creative_brain.production_runtime.rate_limiter import RateLimiter
from market_ops.creative_brain.production_runtime.artifact_manager import ArtifactManager
from market_ops.creative_brain.production_runtime.secret_manager import SecretManager


# ═══════════════════════════════════════════════════════════
# 1–10: Original 50 tests (imported inline)
# ═══════════════════════════════════════════════════════════

# ── 1. Runtime Engine ────────────────────────────────────

def test_runtime_engine_init():
    engine = RuntimeEngine()
    assert engine.config is not None
    assert engine.scheduler is not None
    assert engine.task_queue is not None
    assert engine.worker_pool is not None
    assert engine.cache is not None
    assert engine.resource_manager is not None
    assert engine.retry_manager is not None
    assert engine.rollback_manager is not None
    assert engine.checkpoint_manager is not None
    assert engine.state_manager is not None
    assert engine.event_bus is not None
    assert engine.lock_manager is not None
    assert engine.rate_limiter is not None
    assert engine.artifact_manager is not None
    assert engine.secret_manager is not None
    assert engine.health_monitor is not None
    assert engine.metrics is not None
    assert engine.alerts is not None
    assert engine.service_registry is not None
    assert engine.plugin_manager is not None
    assert engine.workflow_engine is not None
    return True

def test_runtime_engine_start_stop():
    engine = RuntimeEngine()
    assert not engine.is_running
    engine.start()
    assert engine.is_running
    engine.stop()
    assert not engine.is_running
    return True

def test_runtime_engine_register_executor():
    engine = RuntimeEngine()
    def dummy_executor(task):
        return True, {"result": "ok"}
    engine.register_executor("test_type", dummy_executor)
    result = engine.workflow_engine._task_executors.get("test_type")
    assert result is not None
    return True

def test_runtime_engine_register_health():
    engine = RuntimeEngine()
    engine.register_health_check("facebook_api", lambda: True)
    result = engine.health_monitor.check_service("facebook_api")
    assert result.status == HealthStatus.HEALTHY
    return True

def test_runtime_engine_get_status():
    engine = RuntimeEngine()
    engine.start()
    status = engine.get_status()
    assert "engine" in status
    assert "scheduler" in status
    assert "state" in status
    assert "event_bus" in status
    assert "locks" in status
    assert "rate_limiter" in status
    assert "artifacts" in status
    assert "secrets" in status
    engine.stop()
    return True

# ── 2. Scheduler ─────────────────────────────────────────

def test_scheduler_add_cron():
    s = Scheduler()
    executed = []
    s.add_cron("test_job", "0 8 * * *", lambda: executed.append(1), "Test job")
    job = s.get_job("test_job")
    assert job["schedule_type"] == "cron"
    return True

def test_scheduler_add_interval():
    s = Scheduler()
    s.add_interval("test_job", 3600, lambda: None, "Hourly")
    job = s.get_job("test_job")
    assert job["schedule_type"] == "interval"
    return True

def test_scheduler_add_event():
    s = Scheduler()
    s.add_event("test_job", "facebook_sync_done", lambda: None)
    job = s.get_job("test_job")
    assert job["schedule_type"] == "event"
    return True

def test_scheduler_trigger_event():
    s = Scheduler()
    triggered = []
    s.add_event("test_job", "data_ready", lambda: triggered.append("done"))
    result = s.trigger_event("data_ready")
    assert "test_job" in result
    assert triggered == ["done"]
    return True

def test_scheduler_disable_enable():
    s = Scheduler()
    s.add_cron("test_job", "0 8 * * *", lambda: None)
    assert s.get_job("test_job")["enabled"]
    s.disable_job("test_job")
    assert not s.get_job("test_job")["enabled"]
    s.enable_job("test_job")
    assert s.get_job("test_job")["enabled"]
    return True

# ── 3. Workflow ──────────────────────────────────────────

def test_workflow_register():
    engine = WorkflowEngine()
    wf = WorkflowDAG(workflow_id="test_wf", name="Test Workflow",
                     nodes=[WorkflowNode(task_name="A", task_type="type_a", dependencies=[]),
                            WorkflowNode(task_name="B", task_type="type_b", dependencies=["A"])])
    engine.register_workflow(wf)
    assert engine._registered_workflows["test_wf"] is wf
    return True

def test_workflow_build_dag():
    engine = WorkflowEngine()
    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[WorkflowNode(task_name="A", task_type="type_a", dependencies=[]),
                            WorkflowNode(task_name="B", task_type="type_b", dependencies=["A"]),
                            WorkflowNode(task_name="C", task_type="type_c", dependencies=["A"]),
                            WorkflowNode(task_name="D", task_type="type_d", dependencies=["B", "C"])])
    engine.register_workflow(wf)
    graph = engine.build_dag("test_wf")
    assert graph.get_node_count() == 4
    assert not graph.has_cycle()
    levels = graph.get_execution_levels()
    assert len(levels) >= 3
    return True

def test_workflow_execute():
    engine = WorkflowEngine()
    def exec_a(task): return True, "A done"
    def exec_b(task): return True, "B done"
    engine.register_executor("type_a", exec_a)
    engine.register_executor("type_b", exec_b)
    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[WorkflowNode(task_name="A", task_type="type_a", dependencies=[]),
                            WorkflowNode(task_name="B", task_type="type_b", dependencies=["A"])])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.completed == 2
    assert report.failed == 0
    return True

def test_workflow_execute_failure():
    engine = WorkflowEngine()
    def exec_fail(task): return False, "Failed"
    engine.register_executor("type_a", exec_fail)
    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[WorkflowNode(task_name="A", task_type="type_a", dependencies=[])])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.failed == 1
    return True

def test_workflow_list():
    engine = WorkflowEngine()
    wf = WorkflowDAG(workflow_id="wf1", name="WF1", nodes=[])
    engine.register_workflow(wf)
    workflows = engine.list_workflows()
    assert len(workflows) == 1
    return True

# ── 4. Task Queue ────────────────────────────────────────

def test_queue_enqueue_dequeue():
    q = TaskQueue()
    task = RuntimeTask(task_id="t1", name="Task 1", task_type="test")
    q.enqueue(task)
    assert q.get_queue_length() == 1
    dequeued = q.dequeue()
    assert dequeued.task_id == "t1"
    return True

def test_queue_priority_order():
    q = TaskQueue()
    t1 = RuntimeTask(task_id="t1", name="Low", priority=TaskPriority.LOW)
    t2 = RuntimeTask(task_id="t2", name="High", priority=TaskPriority.HIGH)
    q.enqueue(t1)
    q.enqueue(t2)
    result = q.dequeue()
    assert result.task_id == "t2"
    return True

def test_queue_dependency_blocking():
    q = TaskQueue()
    t1 = RuntimeTask(task_id="t1", name="A", dependencies=["t2"])
    t2 = RuntimeTask(task_id="t2", name="B")
    q.enqueue(t1)
    q.enqueue(t2)
    result = q.dequeue()
    assert result.task_id == "t2"
    return True

def test_queue_complete_unblocks():
    q = TaskQueue()
    t1 = RuntimeTask(task_id="t1", name="A", dependencies=["t2"])
    t2 = RuntimeTask(task_id="t2", name="B")
    q.enqueue(t1)
    q.enqueue(t2)
    assert q.dequeue().task_id == "t2"
    q.complete("t2")
    result = q.dequeue()
    assert result is not None
    assert result.task_id == "t1"
    return True

def test_queue_status_counts():
    q = TaskQueue()
    q.enqueue(RuntimeTask(task_id="t1", name="T1"))
    q.enqueue(RuntimeTask(task_id="t2", name="T2"))
    q.dequeue()
    q.complete("t1")
    counts = q.get_status_counts()
    assert "queued" in counts
    assert "completed" in counts
    return True

# ── 5. Worker Pool ───────────────────────────────────────

def test_worker_pool_init():
    pool = WorkerPool(cpu_workers=2, gpu_workers=1, io_workers=3)
    assert len(pool.get_all_workers()) == 6
    return True

def test_worker_assign_task():
    pool = WorkerPool(cpu_workers=1, gpu_workers=0, io_workers=0)
    task = RuntimeTask(task_id="t1", name="T1", worker_type=WorkerType.CPU)
    worker = pool.assign_task(task)
    assert worker is not None
    assert worker.status == WorkerStatus.BUSY
    return True

def test_worker_no_available():
    pool = WorkerPool(cpu_workers=1, gpu_workers=0, io_workers=0)
    pool.assign_task(RuntimeTask(task_id="t1", worker_type=WorkerType.CPU))
    result = pool.assign_task(RuntimeTask(task_id="t2", worker_type=WorkerType.CPU))
    assert result is None
    return True

def test_worker_complete_task():
    pool = WorkerPool(cpu_workers=1, gpu_workers=0, io_workers=0)
    pool.assign_task(RuntimeTask(task_id="t1", worker_type=WorkerType.CPU))
    pool.complete_task("cpu_0", success=True)
    worker = pool.get_all_workers()[0]
    assert worker.tasks_completed == 1
    assert worker.status == WorkerStatus.IDLE
    return True

def test_worker_pool_status():
    pool = WorkerPool(cpu_workers=2, gpu_workers=1, io_workers=2)
    status = pool.get_status()
    assert status["total_workers"] == 5
    return True

# ── 6. Resource Manager ──────────────────────────────────

def test_resource_allocate():
    rm = ResourceManager()
    assert rm.allocate(ResourceType.CPU, 10.0)
    state = rm.get_state(ResourceType.CPU)
    assert state.used == 10.0
    return True

def test_resource_limit():
    rm = ResourceManager(cpu_limit=0.5)
    assert rm.allocate(ResourceType.CPU, 40.0)
    assert rm.allocate(ResourceType.CPU, 15.0) is False
    return True

def test_resource_release():
    rm = ResourceManager()
    rm.allocate(ResourceType.GPU, 30.0)
    rm.release(ResourceType.GPU, 10.0)
    state = rm.get_state(ResourceType.GPU)
    assert state.used == 20.0
    return True

def test_resource_bottleneck():
    rm = ResourceManager()
    rm.set_usage(ResourceType.GPU, 90.0)
    bottleneck = rm.get_bottleneck()
    assert bottleneck == ResourceType.GPU
    return True

def test_resource_workflow_pause():
    rm = ResourceManager()
    rm.pause_workflow("wf_1")
    assert rm.is_paused("wf_1")
    rm.resume_workflow("wf_1")
    assert not rm.is_paused("wf_1")
    return True

# ── 7. Retry / Rollback ─────────────────────────────────

def test_retry_should_retry():
    rm = RetryManager(max_retries=3)
    task = RuntimeTask(task_id="t1", status=TaskStatus.FAILED, retry_count=0)
    assert rm.should_retry(task)
    return True

def test_retry_max_exceeded():
    rm = RetryManager(max_retries=3)
    task = RuntimeTask(task_id="t1", status=TaskStatus.FAILED, retry_count=3)
    assert not rm.should_retry(task)
    return True

def test_retry_exponential_backoff():
    rm = RetryManager(base_delay=1.0, backoff_multiplier=2.0)
    task = RuntimeTask(task_id="t1", retry_count=0)
    d0 = rm.get_delay(task)
    task.retry_count = 1
    d1 = rm.get_delay(task)
    task.retry_count = 2
    d2 = rm.get_delay(task)
    assert d0 == 1.0
    assert d1 == 2.0
    assert d2 == 4.0
    return True

def test_rollback_snapshot_restore():
    rbm = RollbackManager()
    state = {"version": "v25", "data": {"count": 100}}
    rbm.snapshot("wf_1", state)
    rbm.snapshot("wf_1", {"version": "v26", "data": {"count": 200}})
    restored = rbm.rollback("wf_1")
    assert restored["version"] == "v25"
    return True

def test_rollback_no_snapshot():
    rbm = RollbackManager()
    result = rbm.rollback("nonexistent")
    assert result is None
    return True

# ── 8. Health Monitor ────────────────────────────────────

def test_health_register_service():
    hm = HealthMonitor()
    hm.register_service("facebook_api", lambda: True)
    assert "facebook_api" in hm.get_services()
    return True

def test_health_check_healthy():
    hm = HealthMonitor()
    hm.register_service("api", lambda: True)
    report = hm.check_service("api")
    assert report.status == HealthStatus.HEALTHY
    return True

def test_health_check_unhealthy():
    hm = HealthMonitor(max_consecutive_failures=2)
    hm.register_service("api", lambda: False)
    hm.check_service("api")
    report = hm.check_service("api")
    assert report.status == HealthStatus.UNHEALTHY
    return True

def test_health_check_exception():
    hm = HealthMonitor()
    hm.register_service("api", lambda: 1 / 0)
    report = hm.check_service("api")
    assert report.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
    assert report.error_count > 0
    return True

def test_health_check_down():
    hm = HealthMonitor(max_consecutive_failures=2)
    hm.register_service("api", lambda: False)
    for _ in range(5):
        hm.check_service("api")
    report = hm.get_report("api")
    assert report.status == HealthStatus.DOWN
    return True

# ── 9. Metrics ───────────────────────────────────────────

def test_metrics_record_task():
    mc = MetricsCollector()
    mc.record_task_start("t1")
    mc.record_task_complete("t1", latency=0.5)
    metrics = mc.collect()
    assert metrics.avg_latency > 0.0
    return True

def test_metrics_percentile():
    mc = MetricsCollector()
    for i in range(100):
        mc.record_task_complete(f"t{i}", latency=float(i + 1) / 100.0)
    m = mc.collect()
    assert m.p95_latency > 0.0
    assert m.p99_latency >= m.p95_latency
    return True

def test_metrics_throughput():
    mc = MetricsCollector()
    for i in range(10):
        mc.record_task_complete(f"t{i}", latency=0.1)
        time.sleep(0.001)
    m = mc.collect()
    assert m.throughput > 0.0
    return True

def test_metrics_resource():
    mc = MetricsCollector()
    mc.record_resource_usage(cpu=0.5, gpu=0.3, memory=0.6, disk=0.4)
    m = mc.collect()
    assert m.cpu_usage == 0.5
    return True

def test_metrics_summary():
    mc = MetricsCollector()
    mc.record_task_start("t1")
    mc.record_task_complete("t1", latency=0.2)
    mc.record_task_fail("t2")
    summary = mc.get_summary()
    assert "tasks" in summary
    assert "performance" in summary
    return True

# ── 10. E2E ──────────────────────────────────────────────

def test_e2e_runtime_api_init():
    api = RuntimeAPI()
    assert api.config is not None
    assert api.task_queue is not None
    return True

def test_e2e_runtime_api_start_stop():
    api = RuntimeAPI()
    api.start()
    assert api.is_running()
    api.stop()
    assert not api.is_running()
    return True

def test_e2e_submit_and_get_task():
    api = RuntimeAPI()
    task_id = api.submit_task("Test Task", "test_type")
    task = api.get_task(task_id)
    assert task is not None
    assert task["name"] == "Test Task"
    return True

def test_e2e_alert_create_and_ack():
    api = RuntimeAPI()
    alert = api.alerts.warning("test_service", "Test warning")
    assert alert.level == AlertLevel.WARNING
    assert api.alerts.acknowledge(alert.alert_id)
    assert api.alerts.resolve(alert.alert_id)
    return True

def test_e2e_full_pipeline():
    engine = RuntimeEngine()
    engine.start()
    def fake_executor(task): return True, {"ok": True}
    engine.register_executor("test_type", fake_executor)
    engine.register_health_check("test_service", lambda: True)
    engine.register_service("test_service", "test", tags=["test"])
    engine.api.submit_task("E2E Task", "test_type")
    status = engine.get_status()
    assert status["engine"]["running"]
    health = engine.check_health()
    assert health["total_services"] >= 1
    engine.stop()
    return True


# ═══════════════════════════════════════════════════════════
# 11. State Manager (5 tests)
# ═══════════════════════════════════════════════════════════

def test_state_init_workflow():
    sm = StateManager()
    state = sm.init_workflow("wf_1", total_levels=3)
    assert state.state == WorkflowState.IDLE
    assert state.total_levels == 3
    return True

def test_state_transition():
    sm = StateManager()
    sm.init_workflow("wf_1")
    assert sm.transition("wf_1", WorkflowState.RUNNING)
    assert sm.get_workflow_state_value("wf_1") == WorkflowState.RUNNING
    return True

def test_state_invalid_transition():
    sm = StateManager()
    sm.init_workflow("wf_1")
    # Cannot go from IDLE directly to SUCCESS
    assert not sm.transition("wf_1", WorkflowState.SUCCESS)
    return True

def test_state_terminal():
    sm = StateManager()
    sm.init_workflow("wf_1")
    sm.transition("wf_1", WorkflowState.RUNNING)
    sm.transition("wf_1", WorkflowState.SUCCESS)
    # Cannot transition from terminal state
    assert not sm.transition("wf_1", WorkflowState.RUNNING)
    return True

def test_state_progress():
    sm = StateManager()
    sm.init_workflow("wf_1", total_levels=5)
    sm.update_progress("wf_1", current_level=2, completed_task="task_A")
    state = sm.get_workflow_state("wf_1")
    assert state.current_level == 2
    assert "task_A" in state.completed_tasks
    return True


# ═══════════════════════════════════════════════════════════
# 12. Event Bus (5 tests)
# ═══════════════════════════════════════════════════════════

def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []
    bus.subscribe("knowledge_updated", lambda e: received.append(e.payload))
    bus.publish("knowledge_updated", source="knowledge", payload={"version": "v25"})
    assert len(received) == 1
    assert received[0]["version"] == "v25"
    return True

def test_event_bus_wildcard():
    bus = EventBus()
    received = []
    bus.subscribe("*", lambda e: received.append(e.event_type))
    bus.publish("knowledge_updated", source="test")
    bus.publish("creative_uploaded", source="test")
    assert len(received) == 2
    return True

def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []
    def handler(e): received.append(1)
    bus.subscribe("test_event", handler)
    bus.publish("test_event")
    assert len(received) == 1
    bus.unsubscribe("test_event", handler)
    bus.publish("test_event")
    assert len(received) == 1  # unchanged
    return True

def test_event_bus_chain():
    bus = EventBus()
    cid = bus.publish_chain([
        ("knowledge_updated", "knowledge", {"v": 1}),
        ("validation_done", "validation", {"v": 1}),
        ("policy_applied", "policy", {"v": 1}),
    ])
    assert cid.startswith("corr_")
    history = bus.get_history()
    assert len(history) == 3
    return True

def test_event_bus_stats():
    bus = EventBus()
    bus.subscribe("knowledge_updated", lambda e: None)
    bus.publish("knowledge_updated")
    bus.publish("creative_uploaded")
    stats = bus.get_stats()
    assert stats["total_events"] == 2
    assert stats["subscriber_count"] >= 1
    return True


# ═══════════════════════════════════════════════════════════
# 13. Lock Manager (5 tests)
# ═══════════════════════════════════════════════════════════

def test_lock_acquire_release():
    lm = LockManager()
    lock = lm.acquire("knowledge_update")
    assert lock is not None
    assert lm.is_locked("knowledge_update")
    assert lm.release("knowledge_update")
    assert not lm.is_locked("knowledge_update")
    return True

def test_lock_conflict():
    lm = LockManager()
    lock = lm.acquire("knowledge_update")
    assert lock is not None
    # Second acquire should fail
    lock2 = lm.acquire("knowledge_update")
    assert lock2 is None
    return True

def test_lock_ttl_expiry():
    lm = LockManager()
    lock = lm.acquire("knowledge_update", ttl=0.01)
    assert lock is not None
    time.sleep(0.02)
    # After TTL, should be expired
    assert not lm.is_locked("knowledge_update")
    # New acquire should succeed
    lock2 = lm.acquire("knowledge_update")
    assert lock2 is not None
    return True

def test_lock_extend():
    lm = LockManager()
    lm.acquire("knowledge_update", ttl=5.0)
    assert lm.extend("knowledge_update", 30.0)
    lock = lm.get_lock("knowledge_update")
    assert lock is not None
    return True

def test_lock_force_release():
    lm = LockManager()
    lm.acquire("knowledge_update")
    assert lm.force_release("knowledge_update")
    assert not lm.is_locked("knowledge_update")
    return True


# ═══════════════════════════════════════════════════════════
# 14. Rate Limiter (5 tests)
# ═══════════════════════════════════════════════════════════

def test_rate_limiter_allow():
    rl = RateLimiter()
    rl.set_limit("facebook_api", max_requests=100, window_seconds=60)
    assert rl.allow("facebook_api")
    return True

def test_rate_limiter_exhaust():
    rl = RateLimiter()
    rl.set_limit("facebook_api", max_requests=3, window_seconds=60)
    assert rl.allow("facebook_api")
    assert rl.allow("facebook_api")
    assert rl.allow("facebook_api")
    assert not rl.allow("facebook_api")  # Exhausted
    return True

def test_rate_limiter_no_limit():
    rl = RateLimiter()
    # No limit set, always allowed
    for _ in range(1000):
        assert rl.allow("unlimited_service")
    return True

def test_rate_limiter_remaining():
    rl = RateLimiter()
    rl.set_limit("facebook_api", max_requests=100, window_seconds=60)
    rl.allow("facebook_api")
    rl.allow("facebook_api")
    remaining = rl.get_remaining("facebook_api")
    assert remaining <= 98  # Allow for token refill
    return True

def test_rate_limiter_stats():
    rl = RateLimiter()
    rl.set_limit("facebook_api", max_requests=10, window_seconds=60)
    for _ in range(5):
        rl.allow("facebook_api")
    for _ in range(3):
        rl.allow("facebook_api")  # Will reject some
    stats = rl.get_summary()
    assert stats["services"] == 1
    return True


# ═══════════════════════════════════════════════════════════
# 15. Artifact Manager (5 tests)
# ═══════════════════════════════════════════════════════════

def test_artifact_register():
    am = ArtifactManager()
    artifact = am.register("creative_001", ArtifactType.CREATIVE_VIDEO,
                           storage_path="/assets/videos/001.mp4",
                           size_bytes=1048576, tags=["facebook", "winner"])
    assert artifact.artifact_id is not None
    assert artifact.status == ArtifactStatus.ACTIVE
    return True

def test_artifact_find_by_type():
    am = ArtifactManager()
    am.register("creative_001", ArtifactType.CREATIVE_VIDEO)
    am.register("prompt_001", ArtifactType.PROMPT)
    videos = am.find_by_type(ArtifactType.CREATIVE_VIDEO)
    assert len(videos) == 1
    return True

def test_artifact_find_by_tag():
    am = ArtifactManager()
    am.register("creative_001", ArtifactType.CREATIVE_VIDEO, tags=["facebook", "winner"])
    am.register("creative_002", ArtifactType.CREATIVE_VIDEO, tags=["google", "loser"])
    winners = am.find_by_tag("winner")
    assert len(winners) == 1
    assert winners[0].name == "creative_001"
    return True

def test_artifact_versioning():
    am = ArtifactManager()
    am.register("creative_001", ArtifactType.CREATIVE_VIDEO, version="1.0.0")
    am.register("creative_001", ArtifactType.CREATIVE_VIDEO, version="1.1.0")
    latest = am.get_latest("creative_001")
    assert latest.version == "1.1.0"
    v1 = am.get_version("creative_001", "1.0.0")
    assert v1 is not None
    return True

def test_artifact_lifecycle():
    am = ArtifactManager()
    artifact = am.register("creative_001", ArtifactType.CREATIVE_VIDEO)
    assert am.archive(artifact.artifact_id)
    assert am.get(artifact.artifact_id).status == ArtifactStatus.ARCHIVED
    assert am.delete(artifact.artifact_id)
    assert am.get(artifact.artifact_id).status == ArtifactStatus.DELETED
    return True


# ═══════════════════════════════════════════════════════════
# 16. Secret Manager (5 tests)
# ═══════════════════════════════════════════════════════════

def test_secret_store_get():
    sm = SecretManager()
    sm.store("FB_ACCESS_TOKEN", "fb_token_abc123", level=SecretLevel.HIGH)
    value = sm.get("FB_ACCESS_TOKEN")
    assert value == "fb_token_abc123"
    return True

def test_secret_metadata_no_leak():
    sm = SecretManager()
    sm.store("FB_ACCESS_TOKEN", "fb_token_abc123")
    meta = sm.get_metadata("FB_ACCESS_TOKEN")
    # Value hash should be set, but raw value should NOT be in metadata
    assert meta.value_hash != ""
    assert meta.to_dict()["key"] == "FB_ACCESS_TOKEN"
    # Raw value is never exposed in to_dict()
    assert "value" not in meta.to_dict()
    return True

def test_secret_rotate():
    sm = SecretManager()
    sm.store("FB_ACCESS_TOKEN", "old_token")
    sm.rotate("FB_ACCESS_TOKEN", "new_token")
    assert sm.get("FB_ACCESS_TOKEN") == "new_token"
    return True

def test_secret_delete():
    sm = SecretManager()
    sm.store("FB_ACCESS_TOKEN", "fb_token")
    assert sm.delete("FB_ACCESS_TOKEN")
    assert sm.get("FB_ACCESS_TOKEN") is None
    return True

def test_secret_list_keys():
    sm = SecretManager()
    sm.store("FB_ACCESS_TOKEN", "t1")
    sm.store("OPENAI_API_KEY", "t2")
    sm.store("GEMINI_KEY", "t3")
    keys = sm.list_keys()
    assert len(keys) == 3
    assert "FB_ACCESS_TOKEN" in keys
    return True


# ═══════════════════════════════════════════════════════════
# 17. OnErrorPolicy / Workflow (5 tests)
# ═══════════════════════════════════════════════════════════

def test_on_error_skip_continue():
    """Validation fails → skip → continue to Generation."""
    engine = WorkflowEngine()
    def exec_pass(task): return True, "ok"
    def exec_fail(task): return False, "validation_failed"
    engine.register_executor("knowledge", exec_pass)
    engine.register_executor("validation", exec_fail)
    engine.register_executor("generation", exec_pass)

    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[
                         WorkflowNode(task_name="knowledge", task_type="knowledge", dependencies=[]),
                         WorkflowNode(task_name="validation", task_type="validation",
                                      dependencies=["knowledge"],
                                      on_error=OnErrorPolicy.SKIP_CONTINUE),
                         WorkflowNode(task_name="generation", task_type="generation",
                                      dependencies=["knowledge"]),
                     ])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    # knowledge and generation should complete, validation skipped
    assert report.completed >= 2
    assert report.skipped >= 1
    return True

def test_on_error_retry_then_skip():
    engine = WorkflowEngine()
    def exec_pass(task): return True, "ok"
    def exec_fail(task): return False, "failed"
    engine.register_executor("knowledge", exec_pass)
    engine.register_executor("validation", exec_fail)
    engine.register_executor("generation", exec_pass)

    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[
                         WorkflowNode(task_name="knowledge", task_type="knowledge", dependencies=[]),
                         WorkflowNode(task_name="validation", task_type="validation",
                                      dependencies=["knowledge"],
                                      on_error=OnErrorPolicy.RETRY_THEN_SKIP,
                                      max_retries=1),
                         WorkflowNode(task_name="generation", task_type="generation",
                                      dependencies=["knowledge"]),
                     ])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.completed >= 2
    assert report.skipped >= 1
    return True

def test_on_error_fail_workflow_default():
    """Default behavior: fail_workflow should raise."""
    engine = WorkflowEngine()
    def exec_fail(task): return False, "failed"
    engine.register_executor("critical_task", exec_fail)

    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[WorkflowNode(task_name="critical_task", task_type="critical_task",
                                         dependencies=[])])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.failed >= 1
    return True

def test_on_error_retry_then_fail():
    engine = WorkflowEngine()
    def exec_fail(task): return False, "failed"
    engine.register_executor("critical_task", exec_fail)

    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[WorkflowNode(task_name="critical_task", task_type="critical_task",
                                         dependencies=[],
                                         on_error=OnErrorPolicy.RETRY_THEN_FAIL,
                                         max_retries=1)])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.failed >= 1
    return True

def test_on_error_mixed_policies():
    engine = WorkflowEngine()
    def exec_pass(task): return True, "ok"
    def exec_fail(task): return False, "failed"
    engine.register_executor("A", exec_pass)
    engine.register_executor("B", exec_fail)
    engine.register_executor("C", exec_pass)
    engine.register_executor("D", exec_fail)

    wf = WorkflowDAG(workflow_id="test_wf", name="Test",
                     nodes=[
                         WorkflowNode(task_name="A", task_type="A", dependencies=[]),
                         WorkflowNode(task_name="B", task_type="B", dependencies=["A"],
                                      on_error=OnErrorPolicy.SKIP_CONTINUE),
                         WorkflowNode(task_name="C", task_type="C", dependencies=["A"]),
                         WorkflowNode(task_name="D", task_type="D", dependencies=["B", "C"],
                                      on_error=OnErrorPolicy.SKIP_CONTINUE),
                     ])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    # A and C complete, B and D skip
    assert report.completed >= 2
    assert report.skipped >= 2
    return True


# ═══════════════════════════════════════════════════════════
# 18. Chaos Tests (10 tests)
# ═══════════════════════════════════════════════════════════

def test_chaos_gpu_down():
    """GPU goes down → workflow should handle gracefully."""
    engine = WorkflowEngine()
    def exec_gpu(task): return False, "GPU unavailable"
    def exec_cpu(task): return True, "CPU ok"
    engine.register_executor("gpu_task", exec_gpu)
    engine.register_executor("cpu_task", exec_cpu)

    wf = WorkflowDAG(workflow_id="test_wf", name="GPU Down",
                     nodes=[
                         WorkflowNode(task_name="cpu_task", task_type="cpu_task", dependencies=[]),
                         WorkflowNode(task_name="gpu_task", task_type="gpu_task",
                                      dependencies=["cpu_task"],
                                      on_error=OnErrorPolicy.SKIP_CONTINUE),
                     ])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.completed >= 1
    assert report.skipped >= 1
    return True

def test_chaos_api_500_retry():
    """Facebook API 500 → retry → eventually succeed."""
    engine = WorkflowEngine()
    call_count = [0]
    def flaky_api(task):
        call_count[0] += 1
        if call_count[0] < 3:
            return False, "500 Internal Server Error"
        return True, "OK"
    engine.register_executor("api_call", flaky_api)

    wf = WorkflowDAG(workflow_id="test_wf", name="API 500",
                     nodes=[WorkflowNode(task_name="api_call", task_type="api_call",
                                         dependencies=[], max_retries=3)])
    engine.register_workflow(wf)
    report = engine.execute("test_wf")
    assert report.completed >= 1
    assert report.retries >= 2
    return True

def test_chaos_embedding_partial_update():
    """Embedding update halfway → checkpoint → recover."""
    cpm = CheckpointManager()
    cpm.save("embedding_update", tasks=[
        RuntimeTask(task_id="e1", name="chunk_1", task_type="embed"),
        RuntimeTask(task_id="e2", name="chunk_2", task_type="embed"),
    ], task_states={"completed_chunks": 1, "total_chunks": 2})
    loaded = cpm.load("embedding_update")
    assert loaded is not None
    assert loaded.task_states["completed_chunks"] == 1
    return True

def test_chaos_rollback_on_failure():
    """Knowledge update fails → auto rollback to previous version."""
    rbm = RollbackManager()
    rbm.snapshot("knowledge", {"version": "v24", "graph_nodes": 500})
    rbm.snapshot("knowledge", {"version": "v25", "graph_nodes": 520})
    restored = rbm.rollback("knowledge")
    assert restored["version"] == "v24"
    assert restored["graph_nodes"] == 500
    return True

def test_chaos_concurrent_lock_conflict():
    """Two workers try to update Retriever → lock prevents conflict."""
    lm = LockManager()
    lock1 = lm.acquire("retriever_update")
    assert lock1 is not None
    lock2 = lm.acquire("retriever_update")
    assert lock2 is None  # Blocked by lock1
    lm.release("retriever_update")
    lock3 = lm.acquire("retriever_update")
    assert lock3 is not None  # Now available
    return True

def test_chaos_rate_limiter_saves_api():
    """Rate limiter prevents API abuse."""
    rl = RateLimiter()
    rl.set_limit("facebook_api", max_requests=5, window_seconds=60)
    allowed = sum(1 for _ in range(20) if rl.allow("facebook_api"))
    assert allowed == 5  # Only 5 allowed, 15 rejected
    return True

def test_chaos_health_monitor_degradation():
    """Service degrades over time → health monitor detects it."""
    hm = HealthMonitor(max_consecutive_failures=2)
    failures = [0]
    def degrading_service():
        failures[0] += 1
        return failures[0] <= 2  # OK for first 2, then fail
    hm.register_service("degrading_svc", degrading_service)
    # First check: OK
    r1 = hm.check_service("degrading_svc")
    assert r1.status == HealthStatus.HEALTHY
    # More checks: should degrade
    for _ in range(3):
        hm.check_service("degrading_svc")
    r = hm.get_report("degrading_svc")
    assert r.status != HealthStatus.HEALTHY
    return True

def test_chaos_event_bus_isolation():
    """One subscriber crashes → others still get events."""
    bus = EventBus()
    good = []
    def crashing_handler(e):
        raise RuntimeError("Crash!")
    def good_handler(e):
        good.append(e.event_type)
    bus.subscribe("test", crashing_handler)
    bus.subscribe("test", good_handler)
    bus.publish("test")
    assert len(good) == 1  # Good handler still received
    return True

def test_chaos_cache_eviction():
    """Cache full → LRU eviction works."""
    cm = CacheManager(max_size=5)
    for i in range(10):
        cm.set(f"key_{i}", f"value_{i}")
    # Should only have 5 items (max_size)
    stats = cm.get_stats()
    assert stats["size"] <= 5
    return True

def test_chaos_dependency_cycle():
    """Cycle detection prevents deadlock."""
    dg = DependencyGraph()
    dg.add_node("A", ["C"])
    dg.add_node("B", ["A"])
    dg.add_node("C", ["B"])
    assert dg.has_cycle()  # A → C → B → A
    return True


# ═══════════════════════════════════════════════════════════
# 19. Performance Tests (5 tests)
# ═══════════════════════════════════════════════════════════

def test_perf_task_queue_large_scale():
    """10000 tasks → queue handles them efficiently."""
    q = TaskQueue()
    start = time.time()
    for i in range(10000):
        q.enqueue(RuntimeTask(task_id=f"t{i}", name=f"Task {i}",
                              priority=TaskPriority.NORMAL))
    enqueue_time = time.time() - start
    # 10000 enqueues should complete quickly
    assert enqueue_time < 5.0
    return True

def test_perf_scheduler_tick():
    """Multiple jobs → tick executes efficiently."""
    s = Scheduler()
    for i in range(100):
        s.add_interval(f"job_{i}", 3600, lambda: None)
    start = time.time()
    executed = s.tick()
    tick_time = time.time() - start
    assert tick_time < 1.0
    return True

def test_perf_cache_lookup():
    """Cache lookups should be fast."""
    cm = CacheManager(max_size=10000)
    for i in range(1000):
        cm.set(f"key_{i}", f"value_{i}")
    start = time.time()
    for i in range(1000):
        cm.get(f"key_{i}")
    lookup_time = time.time() - start
    assert lookup_time < 0.5
    return True

def test_perf_dependency_graph_large():
    """Large DAG → topological sort is efficient."""
    dg = DependencyGraph()
    for i in range(100):
        deps = [f"node_{i-1}"] if i > 0 else []
        dg.add_node(f"node_{i}", deps)
    start = time.time()
    levels = dg.get_execution_levels()
    sort_time = time.time() - start
    assert sort_time < 1.0
    assert len(levels) == 100  # Sequential chain → 100 levels
    return True

def test_perf_artifact_bulk_register():
    """1000 artifacts → register efficiently."""
    am = ArtifactManager()
    start = time.time()
    for i in range(1000):
        am.register(f"asset_{i}", ArtifactType.GENERATED_ASSET,
                    tags=[f"tag_{i % 10}"])
    register_time = time.time() - start
    assert register_time < 3.0
    stats = am.get_stats()
    assert stats["total_artifacts"] == 1000
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Runtime Engine (5)
        ("Runtime: Init", test_runtime_engine_init),
        ("Runtime: Start/Stop", test_runtime_engine_start_stop),
        ("Runtime: Register Executor", test_runtime_engine_register_executor),
        ("Runtime: Register Health", test_runtime_engine_register_health),
        ("Runtime: Get Status", test_runtime_engine_get_status),
        # 2. Scheduler (5)
        ("Scheduler: Cron", test_scheduler_add_cron),
        ("Scheduler: Interval", test_scheduler_add_interval),
        ("Scheduler: Event", test_scheduler_add_event),
        ("Scheduler: Trigger", test_scheduler_trigger_event),
        ("Scheduler: Disable/Enable", test_scheduler_disable_enable),
        # 3. Workflow (5)
        ("Workflow: Register", test_workflow_register),
        ("Workflow: Build DAG", test_workflow_build_dag),
        ("Workflow: Execute", test_workflow_execute),
        ("Workflow: Failure", test_workflow_execute_failure),
        ("Workflow: List", test_workflow_list),
        # 4. Task Queue (5)
        ("Queue: Enqueue/Dequeue", test_queue_enqueue_dequeue),
        ("Queue: Priority", test_queue_priority_order),
        ("Queue: Dependency", test_queue_dependency_blocking),
        ("Queue: Complete Unblocks", test_queue_complete_unblocks),
        ("Queue: Status Counts", test_queue_status_counts),
        # 5. Worker Pool (5)
        ("Worker: Init", test_worker_pool_init),
        ("Worker: Assign", test_worker_assign_task),
        ("Worker: No Available", test_worker_no_available),
        ("Worker: Complete", test_worker_complete_task),
        ("Worker: Status", test_worker_pool_status),
        # 6. Resource Manager (5)
        ("Resource: Allocate", test_resource_allocate),
        ("Resource: Limit", test_resource_limit),
        ("Resource: Release", test_resource_release),
        ("Resource: Bottleneck", test_resource_bottleneck),
        ("Resource: Pause", test_resource_workflow_pause),
        # 7. Retry / Rollback (5)
        ("Retry: Should Retry", test_retry_should_retry),
        ("Retry: Max Exceeded", test_retry_max_exceeded),
        ("Retry: Backoff", test_retry_exponential_backoff),
        ("Rollback: Snapshot", test_rollback_snapshot_restore),
        ("Rollback: No Snapshot", test_rollback_no_snapshot),
        # 8. Health Monitor (5)
        ("Health: Register", test_health_register_service),
        ("Health: Healthy", test_health_check_healthy),
        ("Health: Unhealthy", test_health_check_unhealthy),
        ("Health: Exception", test_health_check_exception),
        ("Health: Down", test_health_check_down),
        # 9. Metrics (5)
        ("Metrics: Record", test_metrics_record_task),
        ("Metrics: Percentile", test_metrics_percentile),
        ("Metrics: Throughput", test_metrics_throughput),
        ("Metrics: Resource", test_metrics_resource),
        ("Metrics: Summary", test_metrics_summary),
        # 10. E2E (5)
        ("E2E: API Init", test_e2e_runtime_api_init),
        ("E2E: API Start/Stop", test_e2e_runtime_api_start_stop),
        ("E2E: Submit+Get", test_e2e_submit_and_get_task),
        ("E2E: Alert", test_e2e_alert_create_and_ack),
        ("E2E: Full Pipeline", test_e2e_full_pipeline),
        # 11. State Manager (5)
        ("State: Init", test_state_init_workflow),
        ("State: Transition", test_state_transition),
        ("State: Invalid", test_state_invalid_transition),
        ("State: Terminal", test_state_terminal),
        ("State: Progress", test_state_progress),
        # 12. Event Bus (5)
        ("EventBus: Pub/Sub", test_event_bus_publish_subscribe),
        ("EventBus: Wildcard", test_event_bus_wildcard),
        ("EventBus: Unsubscribe", test_event_bus_unsubscribe),
        ("EventBus: Chain", test_event_bus_chain),
        ("EventBus: Stats", test_event_bus_stats),
        # 13. Lock Manager (5)
        ("Lock: Acquire/Release", test_lock_acquire_release),
        ("Lock: Conflict", test_lock_conflict),
        ("Lock: TTL Expiry", test_lock_ttl_expiry),
        ("Lock: Extend", test_lock_extend),
        ("Lock: Force Release", test_lock_force_release),
        # 14. Rate Limiter (5)
        ("RateLimit: Allow", test_rate_limiter_allow),
        ("RateLimit: Exhaust", test_rate_limiter_exhaust),
        ("RateLimit: No Limit", test_rate_limiter_no_limit),
        ("RateLimit: Remaining", test_rate_limiter_remaining),
        ("RateLimit: Stats", test_rate_limiter_stats),
        # 15. Artifact Manager (5)
        ("Artifact: Register", test_artifact_register),
        ("Artifact: FindByType", test_artifact_find_by_type),
        ("Artifact: FindByTag", test_artifact_find_by_tag),
        ("Artifact: Versioning", test_artifact_versioning),
        ("Artifact: Lifecycle", test_artifact_lifecycle),
        # 16. Secret Manager (5)
        ("Secret: Store/Get", test_secret_store_get),
        ("Secret: Metadata No Leak", test_secret_metadata_no_leak),
        ("Secret: Rotate", test_secret_rotate),
        ("Secret: Delete", test_secret_delete),
        ("Secret: List Keys", test_secret_list_keys),
        # 17. OnErrorPolicy (5)
        ("OnError: Skip Continue", test_on_error_skip_continue),
        ("OnError: Retry Then Skip", test_on_error_retry_then_skip),
        ("OnError: Fail Workflow", test_on_error_fail_workflow_default),
        ("OnError: Retry Then Fail", test_on_error_retry_then_fail),
        ("OnError: Mixed Policies", test_on_error_mixed_policies),
        # 18. Chaos Tests (10)
        ("Chaos: GPU Down", test_chaos_gpu_down),
        ("Chaos: API 500 Retry", test_chaos_api_500_retry),
        ("Chaos: Embedding Partial", test_chaos_embedding_partial_update),
        ("Chaos: Rollback", test_chaos_rollback_on_failure),
        ("Chaos: Lock Conflict", test_chaos_concurrent_lock_conflict),
        ("Chaos: Rate Limiter", test_chaos_rate_limiter_saves_api),
        ("Chaos: Health Degradation", test_chaos_health_monitor_degradation),
        ("Chaos: Event Isolation", test_chaos_event_bus_isolation),
        ("Chaos: Cache Eviction", test_chaos_cache_eviction),
        ("Chaos: Cycle Detection", test_chaos_dependency_cycle),
        # 19. Performance Tests (5)
        ("Perf: Queue 10000", test_perf_task_queue_large_scale),
        ("Perf: Scheduler Tick", test_perf_scheduler_tick),
        ("Perf: Cache Lookup", test_perf_cache_lookup),
        ("Perf: DAG Large", test_perf_dependency_graph_large),
        ("Perf: Artifact Bulk", test_perf_artifact_bulk_register),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.4.1 Production Runtime — Extended Release Gate")
    print("  Architecture Review: 50 → 100 tests")
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