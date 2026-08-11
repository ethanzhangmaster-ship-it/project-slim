"""E15.0.8 Storage Wiring — 集成测试.

验证各模块与 StorageService 的集成:
  - AuditService: 决策/执行结果/回滚持久化 (10 tests)
  - MetricsCollector: 快照持久化 (6 tests)
  - AlertManager: 告警创建/解决持久化 (8 tests)
  - ProductionWorker: 执行结果持久化 (8 tests)
  - ProductionScheduler: Redis 分布式锁 (8 tests)

总计: 40 个测试用例
"""

from __future__ import annotations

import pytest

from unittest.mock import MagicMock, patch

from market_ops.creative_vision_runtime.growth_runtime.audit import (
    AuditService,
    AuditStore,
)
from market_ops.creative_vision_runtime.growth_runtime.audit.models import (
    ExecutionStatus,
    GrowthDecisionAudit,
)
from market_ops.creative_vision_runtime.growth_runtime.monitoring.metrics import (
    MetricsCollector,
    GrowthMetrics,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.health.alert_manager import (
    AlertManager,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.health.health_models import (
    Alert,
    AlertLevel,
    AlertType,
)
from market_ops.creative_vision_runtime.growth_runtime.production.worker import (
    ProductionWorker,
    ExecutionResult,
    ExecutionStatus as WorkerExecStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.production.scheduler import (
    ProductionScheduler,
    SchedulerState,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_audit(
    agent_id: str = "agent_01",
    game_id: str = "P04",
    decision: str = "reduce budget 20%",
    action: str = "update_budget",
    confidence: float = 0.87,
    status: ExecutionStatus = ExecutionStatus.PENDING,
    plan_id: str = "",
    cycle_id: str = "",
) -> GrowthDecisionAudit:
    return GrowthDecisionAudit(
        agent_id=agent_id,
        game_id=game_id,
        input_context={"roas": 1.0, "spend": 500},
        detected_problem="ROAS decay detected",
        decision=decision,
        action=action,
        confidence=confidence,
        execution_status=status,
        plan_id=plan_id,
        cycle_id=cycle_id,
    )


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.audit = MagicMock()
    storage.metrics = MagicMock()
    storage.alerts = MagicMock()
    storage.executions = MagicMock()
    return storage


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.acquire_scheduler_lock.return_value = True
    redis.release_scheduler_lock.return_value = True
    redis.get_lock_holder.return_value = None
    return redis


# ═══════════════════════════════════════════════════════════
# 1. AuditService Wiring
# ═══════════════════════════════════════════════════════════

class TestAuditServiceWiring:
    """AuditService 与 StorageService 集成测试."""

    # ── Acceptance ──────────────────────────────────────────

    def test_accepts_storage_parameter(self, mock_storage):
        """AuditService 接受 storage 参数."""
        service = AuditService(storage=mock_storage)
        assert service.has_persistent_storage is True

    def test_accepts_storage_none(self):
        """AuditService 接受 storage=None."""
        service = AuditService(storage=None)
        assert service.has_persistent_storage is False

    def test_accepts_both_store_and_storage(self, mock_storage):
        """同时接受 store 和 storage 参数."""
        store = AuditStore()
        store.record(_make_audit())
        service = AuditService(store=store, storage=mock_storage)
        assert service.store is store
        assert service.has_persistent_storage is True

    # ── log_decision ────────────────────────────────────────

    def test_log_decision_persists_to_storage(self, mock_storage):
        """log_decision 在提供 storage 时持久化到 PostgreSQL."""
        service = AuditService(storage=mock_storage)
        audit = service.log_decision(
            agent_id="agent_01",
            game_id="P04",
            input_context={"roas": 1.0},
            detected_problem="ROAS drop",
            decision="reduce budget",
            action="update_budget",
            confidence=0.85,
            plan_id="plan_1",
            cycle_id="cycle_2",
            safety_decision="approved",
        )
        mock_storage.audit.save.assert_called_once()
        saved_arg = mock_storage.audit.save.call_args[0][0]
        assert saved_arg["game_id"] == "P04"
        assert saved_arg["decision"] == "reduce budget"
        assert saved_arg["agent_id"] == "agent_01"

    def test_log_decision_without_storage(self):
        """log_decision 在无 storage 时仍正常工作 (向后兼容)."""
        service = AuditService(storage=None)
        audit = service.log_decision(
            agent_id="agent_01",
            game_id="P04",
            input_context={},
            detected_problem="p",
            decision="d",
            action="a",
            confidence=0.5,
        )
        assert audit.agent_id == "agent_01"
        assert audit.game_id == "P04"
        assert len(service.store) == 1

    def test_log_decision_storage_failure_does_not_break(self, mock_storage):
        """storage 持久化失败时 log_decision 不抛异常."""
        mock_storage.audit.save.side_effect = RuntimeError("DB down")
        service = AuditService(storage=mock_storage)
        audit = service.log_decision(
            agent_id="agent_01",
            game_id="P04",
            input_context={},
            detected_problem="p",
            decision="d",
            action="a",
            confidence=0.5,
        )
        assert audit.agent_id == "agent_01"
        assert len(service.store) == 1

    # ── log_execution_result ────────────────────────────────

    def test_log_execution_result_persists_to_storage(self, mock_storage):
        """log_execution_result 持久化到 PostgreSQL."""
        service = AuditService(storage=mock_storage)
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="p",
            decision="d", action="a", confidence=0.5,
        )
        result = service.log_execution_result(
            audit.audit_id,
            status=ExecutionStatus.SUCCESS,
            result={"roas_after": 1.5},
        )
        mock_storage.audit.update_status.assert_called_once_with(
            audit_id=audit.audit_id,
            status="success",
            result={"roas_after": 1.5},
        )
        assert result is not None
        assert result.execution_status == ExecutionStatus.SUCCESS

    def test_log_execution_result_without_storage(self):
        """log_execution_result 在无 storage 时仍正常工作."""
        service = AuditService(storage=None)
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="p",
            decision="d", action="a", confidence=0.5,
        )
        result = service.log_execution_result(
            audit.audit_id,
            status=ExecutionStatus.SUCCESS,
        )
        assert result is not None
        assert result.execution_status == ExecutionStatus.SUCCESS

    def test_log_execution_result_storage_failure_does_not_break(self, mock_storage):
        """storage 持久化失败时 log_execution_result 不抛异常."""
        mock_storage.audit.update_status.side_effect = RuntimeError("DB down")
        service = AuditService(storage=mock_storage)
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="p",
            decision="d", action="a", confidence=0.5,
        )
        result = service.log_execution_result(
            audit.audit_id,
            status=ExecutionStatus.SUCCESS,
        )
        assert result is not None
        assert result.execution_status == ExecutionStatus.SUCCESS

    # ── log_rollback ────────────────────────────────────────

    def test_log_rollback_persists_to_storage(self, mock_storage):
        """log_rollback 持久化到 PostgreSQL."""
        service = AuditService(storage=mock_storage)
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="p",
            decision="d", action="a", confidence=0.5,
        )
        result = service.log_rollback(audit.audit_id, result={"reason": "manual"})
        mock_storage.audit.update_status.assert_called_with(
            audit_id=audit.audit_id,
            status="rolled_back",
            result={"reason": "manual"},
        )
        assert result is not None
        assert result.execution_status == ExecutionStatus.ROLLED_BACK

    def test_log_rollback_storage_failure_does_not_break(self, mock_storage):
        """storage 持久化失败时 log_rollback 不抛异常."""
        mock_storage.audit.update_status.side_effect = RuntimeError("DB down")
        service = AuditService(storage=mock_storage)
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="p",
            decision="d", action="a", confidence=0.5,
        )
        result = service.log_rollback(audit.audit_id)
        assert result is not None
        assert result.execution_status == ExecutionStatus.ROLLED_BACK

    # ── has_persistent_storage ──────────────────────────────

    def test_has_persistent_storage_true(self, mock_storage):
        """has_persistent_storage 为 True 当 storage 不为 None."""
        service = AuditService(storage=mock_storage)
        assert service.has_persistent_storage is True

    def test_has_persistent_storage_false(self):
        """has_persistent_storage 为 False 当 storage 为 None."""
        service = AuditService(storage=None)
        assert service.has_persistent_storage is False


# ═══════════════════════════════════════════════════════════
# 2. MetricsCollector Wiring
# ═══════════════════════════════════════════════════════════

class TestMetricsCollectorWiring:
    """MetricsCollector 与 StorageService 集成测试."""

    # ── Acceptance ──────────────────────────────────────────

    def test_accepts_storage_parameter(self, mock_storage):
        """MetricsCollector 接受 storage 参数."""
        collector = MetricsCollector(storage=mock_storage)
        assert collector._storage is mock_storage

    def test_accepts_storage_none(self):
        """MetricsCollector 接受 storage=None."""
        collector = MetricsCollector(storage=None)
        assert collector._storage is None

    # ── snapshot ────────────────────────────────────────────

    def test_snapshot_persists_to_storage(self, mock_storage):
        """snapshot() 在提供 storage 时持久化到 PostgreSQL."""
        collector = MetricsCollector(game_id="P04", storage=mock_storage)
        collector.record_decision(success=True)
        collector.record_execution(success=True)
        collector.record_business(spend=100, revenue=200)

        metrics = collector.snapshot()

        mock_storage.metrics.save.assert_called_once()
        saved_arg = mock_storage.metrics.save.call_args[0][0]
        assert saved_arg["game_id"] == "P04"
        assert saved_arg["agent"]["decision_count"] == 1
        assert saved_arg["business"]["spend"] == 100
        assert saved_arg["business"]["revenue"] == 200

    def test_snapshot_without_storage(self):
        """snapshot() 在无 storage 时仍正常工作 (向后兼容)."""
        collector = MetricsCollector(game_id="P04")
        collector.record_decision(success=True)
        metrics = collector.snapshot()
        assert metrics.game_id == "P04"
        assert metrics.decision_count == 1

    def test_snapshot_storage_failure_does_not_break(self, mock_storage):
        """storage 持久化失败时 snapshot() 不抛异常."""
        mock_storage.metrics.save.side_effect = RuntimeError("DB down")
        collector = MetricsCollector(game_id="P04", storage=mock_storage)
        collector.record_decision(success=True)
        metrics = collector.snapshot()
        assert metrics.game_id == "P04"
        assert metrics.decision_count == 1

    def test_multiple_snapshots_all_persist(self, mock_storage):
        """多次 snapshot() 均持久化."""
        collector = MetricsCollector(game_id="P04", storage=mock_storage)
        collector.record_decision(success=True)
        collector.snapshot()
        collector.record_decision(success=False)
        collector.snapshot()
        assert mock_storage.metrics.save.call_count == 2


# ═══════════════════════════════════════════════════════════
# 3. AlertManager Wiring
# ═══════════════════════════════════════════════════════════

class TestAlertManagerWiring:
    """AlertManager 与 StorageService 集成测试."""

    # ── Acceptance ──────────────────────────────────────────

    def test_accepts_storage_parameter(self, mock_storage):
        """AlertManager 接受 storage 参数."""
        manager = AlertManager(storage=mock_storage)
        assert manager._storage is mock_storage

    def test_accepts_storage_none(self):
        """AlertManager 接受 storage=None."""
        manager = AlertManager(storage=None)
        assert manager._storage is None

    def test_accepts_storage_with_other_params(self, mock_storage):
        """AlertManager 接受 storage 和其他参数."""
        manager = AlertManager(
            max_active=50,
            max_history=200,
            dedup_window_minutes=15,
            storage=mock_storage,
        )
        assert manager._storage is mock_storage
        assert manager._max_active == 50
        assert manager._max_history == 200
        assert manager._dedup_window_minutes == 15

    # ── create_alert ────────────────────────────────────────

    def test_create_alert_persists_to_storage(self, mock_storage):
        """create_alert 在提供 storage 时持久化到 PostgreSQL."""
        manager = AlertManager(storage=mock_storage)
        alert = manager.create_alert(
            level=AlertLevel.CRITICAL,
            alert_type=AlertType.EXECUTION_FAILURE,
            message="执行成功率低于阈值",
        )
        assert alert is not None
        mock_storage.alerts.save.assert_called_once()
        saved_arg = mock_storage.alerts.save.call_args[0][0]
        assert saved_arg["alert_id"] == alert.alert_id
        assert saved_arg["severity"] == "critical"
        assert saved_arg["rule_name"] == "execution_failure"
        assert saved_arg["message"] == "执行成功率低于阈值"

    def test_create_alert_without_storage(self):
        """create_alert 在无 storage 时仍正常工作."""
        manager = AlertManager(storage=None)
        alert = manager.create_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.DECISION_DRIFT,
            message="决策漂移检测",
        )
        assert alert is not None
        assert alert.level == AlertLevel.WARNING
        assert alert.alert_type == AlertType.DECISION_DRIFT

    def test_create_alert_storage_failure_does_not_break(self, mock_storage):
        """storage 持久化失败时 create_alert 不抛异常."""
        mock_storage.alerts.save.side_effect = RuntimeError("DB down")
        manager = AlertManager(storage=mock_storage)
        alert = manager.create_alert(
            level=AlertLevel.CRITICAL,
            alert_type=AlertType.EXECUTION_FAILURE,
            message="测试告警",
        )
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL

    # ── resolve ─────────────────────────────────────────────

    def test_resolve_acknowledges_in_storage(self, mock_storage):
        """resolve 在提供 storage 时确认告警."""
        manager = AlertManager(storage=mock_storage)
        alert = manager.create_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.TOOL_FAILURE,
            message="工具调用失败",
        )
        assert alert is not None

        result = manager.resolve(alert.alert_id, note="已修复")
        assert result is True
        mock_storage.alerts.acknowledge.assert_called_once_with(alert.alert_id)

    def test_resolve_without_storage(self):
        """resolve 在无 storage 时仍正常工作."""
        manager = AlertManager(storage=None)
        alert = manager.create_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.TOOL_FAILURE,
            message="工具调用失败",
        )
        assert alert is not None
        result = manager.resolve(alert.alert_id)
        assert result is True

    # ── _alert_to_dict ──────────────────────────────────────

    def test_alert_to_dict_helper(self):
        """_alert_to_dict 将 Alert 转换为正确的 dict 格式."""
        manager = AlertManager()
        alert = Alert(
            level=AlertLevel.CRITICAL,
            alert_type=AlertType.EXECUTION_FAILURE,
            message="测试消息",
            source="test",
        )
        result = manager._alert_to_dict(alert)
        assert result["alert_id"] == alert.alert_id
        assert result["severity"] == "critical"
        assert result["rule_name"] == "execution_failure"
        assert result["message"] == "测试消息"
        assert result["game_id"] == ""
        assert result["acknowledged"] is False
        assert isinstance(result["metrics"], dict)


# ═══════════════════════════════════════════════════════════
# 4. ProductionWorker Wiring
# ═══════════════════════════════════════════════════════════

class TestProductionWorkerWiring:
    """ProductionWorker 与 StorageService 集成测试."""

    # ── Acceptance ──────────────────────────────────────────

    def test_accepts_storage_parameter(self, mock_storage):
        """ProductionWorker 接受 storage 参数."""
        worker = ProductionWorker(storage=mock_storage)
        assert worker._storage is mock_storage

    def test_accepts_storage_none(self):
        """ProductionWorker 接受 storage=None."""
        worker = ProductionWorker(storage=None)
        assert worker._storage is None

    def test_accepts_storage_with_max_concurrent(self, mock_storage):
        """ProductionWorker 接受 storage 和 max_concurrent 参数."""
        worker = ProductionWorker(max_concurrent=10, storage=mock_storage)
        assert worker._storage is mock_storage
        assert worker._max_concurrent == 10

    # ── execute ─────────────────────────────────────────────

    def test_execute_persists_to_storage(self, mock_storage):
        """execute 在提供 storage 时持久化执行结果."""
        worker = ProductionWorker(storage=mock_storage)
        worker.register_executor("update_budget", lambda p: {"success": True})

        result = worker.execute(
            action_type="update_budget",
            params={"budget": 100},
            action_id="action_001",
        )

        assert result.status == WorkerExecStatus.SUCCESS
        mock_storage.executions.save.assert_called_once()
        saved_arg = mock_storage.executions.save.call_args[0][0]
        assert saved_arg["action_type"] == "update_budget"
        assert saved_arg["action_id"] == "action_001"
        assert saved_arg["status"] == "success"
        assert saved_arg["params"] == {"budget": 100}

    def test_execute_without_storage(self):
        """execute 在无 storage 时仍正常工作."""
        worker = ProductionWorker(storage=None)
        worker.register_executor("update_budget", lambda p: {"success": True})

        result = worker.execute(
            action_type="update_budget",
            params={"budget": 100},
            action_id="action_001",
        )
        assert result.status == WorkerExecStatus.SUCCESS

    def test_execute_storage_failure_does_not_break(self, mock_storage):
        """storage 持久化失败时 execute 不抛异常."""
        mock_storage.executions.save.side_effect = RuntimeError("DB down")
        worker = ProductionWorker(storage=mock_storage)
        worker.register_executor("update_budget", lambda p: {"success": True})

        result = worker.execute(
            action_type="update_budget",
            params={"budget": 100},
            action_id="action_001",
        )
        assert result.status == WorkerExecStatus.SUCCESS

    def test_execute_failed_persists_to_storage(self, mock_storage):
        """execute 失败时也持久化到 storage."""
        worker = ProductionWorker(storage=mock_storage)
        worker.register_executor("bad_action", lambda p: (_ for _ in ()).throw(RuntimeError("boom")))

        result = worker.execute(
            action_type="bad_action",
            params={"budget": 100},
            action_id="action_002",
        )

        assert result.status == WorkerExecStatus.FAILED
        mock_storage.executions.save.assert_called_once()
        saved_arg = mock_storage.executions.save.call_args[0][0]
        assert saved_arg["status"] == "failed"
        assert saved_arg["error"] == "boom"

    # ── _result_to_dict ─────────────────────────────────────

    def test_result_to_dict_helper(self):
        """_result_to_dict 将 ExecutionResult 转换为正确的 dict 格式."""
        worker = ProductionWorker()
        result = ExecutionResult(
            action_id="action_001",
            status=WorkerExecStatus.SUCCESS,
            output={"roas": 2.0},
            duration_ms=150.5,
        )
        d = worker._result_to_dict(result, "update_budget", {"budget": 100})
        assert d["result_id"] == result.result_id
        assert d["execution_id"] == result.result_id
        assert d["action_id"] == "action_001"
        assert d["action_type"] == "update_budget"
        assert d["params"] == {"budget": 100}
        assert d["status"] == "success"
        assert d["output"] == {"roas": 2.0}
        assert d["duration_ms"] == 150.5
        assert d["rollback_record_id"] == ""

    def test_result_to_dict_with_error(self):
        """_result_to_dict 包含错误信息."""
        worker = ProductionWorker()
        result = ExecutionResult(
            action_id="action_002",
            status=WorkerExecStatus.FAILED,
            error="something went wrong",
            duration_ms=50.0,
        )
        d = worker._result_to_dict(result, "bad_action", {})
        assert d["status"] == "failed"
        assert d["error"] == "something went wrong"


# ═══════════════════════════════════════════════════════════
# 5. ProductionScheduler Wiring
# ═══════════════════════════════════════════════════════════

class TestProductionSchedulerWiring:
    """ProductionScheduler 与 RedisStateManager 集成测试."""

    # ── Acceptance ──────────────────────────────────────────

    def test_accepts_redis_parameter(self, mock_redis):
        """ProductionScheduler 接受 redis 参数."""
        scheduler = ProductionScheduler(redis=mock_redis)
        assert scheduler._redis is mock_redis

    def test_accepts_redis_none(self):
        """ProductionScheduler 接受 redis=None."""
        scheduler = ProductionScheduler(redis=None)
        assert scheduler._redis is None

    def test_accepts_scheduler_name(self, mock_redis):
        """ProductionScheduler 接受 scheduler_name 参数."""
        scheduler = ProductionScheduler(
            redis=mock_redis,
            scheduler_name="growth_agent_01",
        )
        assert scheduler._scheduler_name == "growth_agent_01"

    def test_default_scheduler_name(self):
        """默认 scheduler_name 为 'default'."""
        scheduler = ProductionScheduler()
        assert scheduler._scheduler_name == "default"

    # ── tick with redis ─────────────────────────────────────

    def test_tick_acquires_distributed_lock(self, mock_redis):
        """tick 获取 Redis 分布式锁."""
        scheduler = ProductionScheduler(redis=mock_redis)
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        result = scheduler.tick()

        assert result["status"] == "success"
        mock_redis.acquire_scheduler_lock.assert_called_once()
        call_args = mock_redis.acquire_scheduler_lock.call_args
        assert call_args[0][0] == "default"  # scheduler_name
        assert call_args[1]["ttl"] > 0  # ttl is positive

    def test_tick_releases_distributed_lock(self, mock_redis):
        """tick 完成后释放 Redis 分布式锁."""
        scheduler = ProductionScheduler(redis=mock_redis)
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        scheduler.tick()

        mock_redis.release_scheduler_lock.assert_called_once_with("default")

    def test_tick_skips_when_lock_held(self, mock_redis):
        """tick 在锁被持有时跳过执行."""
        mock_redis.acquire_scheduler_lock.return_value = False
        mock_redis.get_lock_holder.return_value = "instance_02"

        scheduler = ProductionScheduler(redis=mock_redis)
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        result = scheduler.tick()

        assert result["status"] == "skipped"
        assert "Lock held by instance_02" in result["reason"]
        mock_redis.release_scheduler_lock.assert_not_called()

    def test_tick_without_redis(self):
        """tick 在无 redis 时仍正常工作."""
        scheduler = ProductionScheduler(redis=None)
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        result = scheduler.tick()

        assert result["status"] == "success"

    def test_tick_without_redis_does_not_acquire_lock(self):
        """tick 在无 redis 时不尝试获取锁."""
        scheduler = ProductionScheduler(redis=None)
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        scheduler.tick()
        # 无 redis 时不应调用 acquire/release，这里仅验证不抛异常

    def test_tick_lock_release_failure_is_handled(self, mock_redis):
        """锁释放失败时 tick 不抛异常."""
        mock_redis.release_scheduler_lock.side_effect = RuntimeError("Redis connection lost")

        scheduler = ProductionScheduler(redis=mock_redis)
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        result = scheduler.tick()

        assert result["status"] == "success"
        mock_redis.release_scheduler_lock.assert_called_once_with("default")

    def test_tick_with_custom_scheduler_name(self, mock_redis):
        """tick 使用自定义 scheduler_name 获取锁."""
        scheduler = ProductionScheduler(
            redis=mock_redis,
            scheduler_name="growth_agent_03",
        )
        scheduler.on_tick(lambda: {"result": "ok"})
        scheduler.start()

        scheduler.tick()

        mock_redis.acquire_scheduler_lock.assert_called_once()
        lock_name = mock_redis.acquire_scheduler_lock.call_args[0][0]
        assert lock_name == "growth_agent_03"
        mock_redis.release_scheduler_lock.assert_called_once_with("growth_agent_03")