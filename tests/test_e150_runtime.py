"""E15.0.4 Production Runtime — 测试套件.

覆盖:
  - ProductionScheduler: 创建/生命周期/tick/should_tick/统计/重置/错误处理/SchedulerState
  - ProductionWorker: 创建/注册注销/执行/批量执行/结果查询/统计/重置/状态转换/WorkerState
  - ExecutionResult: 创建/to_dict/ExecutionStatus
  - HealthChecker: 注册注销/单组件检查/全量检查/Agent/Connector/DB/API检查/报告/摘要/重置
  - HealthStatus / ComponentHealth / HealthReport
  - 边界情况: 空调度器/Worker满容/未注册检查/健康检查失败
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.production.scheduler import (
    ProductionScheduler,
    SchedulerState,
)
from market_ops.creative_vision_runtime.growth_runtime.production.worker import (
    ProductionWorker,
    WorkerState,
    ExecutionResult,
    ExecutionStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.production.health_check import (
    HealthChecker,
    HealthStatus,
    ComponentHealth,
    HealthReport,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_success_handler(result=None):
    """创建返回成功结果的 handler."""
    return lambda: result or {"ok": True, "data": "processed"}


def _make_failing_handler(error_msg="fail"):
    """创建总是抛异常的 handler."""
    def _raise():
        raise RuntimeError(error_msg)
    return _raise


def _make_flaky_handler(fail_times=2, result=None):
    """创建前 N 次失败、之后成功的 handler."""
    counter = {"count": 0}

    def _flaky():
        counter["count"] += 1
        if counter["count"] <= fail_times:
            raise RuntimeError(f"attempt {counter['count']} failed")
        return result or {"ok": True, "recovered": True}
    return _flaky


def _make_executor(output=None):
    """创建返回指定输出的 executor."""
    return lambda params: output or {"result": "done"}


def _make_failing_executor(error_msg="executor error"):
    """创建总是抛异常的 executor."""
    def _raise(params):
        raise RuntimeError(error_msg)
    return _raise


def _make_healthy_check(component="test"):
    """创建返回健康的检查函数."""
    def _check():
        return ComponentHealth(
            component=component,
            status=HealthStatus.HEALTHY,
            message=f"{component} is healthy",
        )
    return _check


def _make_unhealthy_check(component="test"):
    """创建返回不健康的检查函数."""
    def _check():
        return ComponentHealth(
            component=component,
            status=HealthStatus.UNHEALTHY,
            message=f"{component} is down",
        )
    return _check


def _make_failing_check(error_msg="check failed"):
    """创建抛出异常的检查函数."""
    def _check():
        raise RuntimeError(error_msg)
    return _check


# ═══════════════════════════════════════════════════════════════
# SchedulerState enum
# ═══════════════════════════════════════════════════════════════


class TestSchedulerStateEnum:
    """SchedulerState 枚举测试."""

    def test_states_exist(self):
        assert SchedulerState.IDLE == "idle"
        assert SchedulerState.RUNNING == "running"
        assert SchedulerState.PAUSED == "paused"
        assert SchedulerState.STOPPED == "stopped"
        assert SchedulerState.ERROR == "error"

    def test_is_string_enum(self):
        assert isinstance(SchedulerState.IDLE, str)
        assert SchedulerState.IDLE.value == "idle"


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — Creation
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerCreation:
    """ProductionScheduler 创建测试."""

    def test_create_with_defaults(self):
        s = ProductionScheduler()
        assert s.state == SchedulerState.IDLE
        assert s.tick_count == 0
        assert s.is_running is False

    def test_create_with_custom_interval(self):
        s = ProductionScheduler(interval_minutes=30)
        assert s.state == SchedulerState.IDLE

    def test_create_with_custom_retries(self):
        s = ProductionScheduler(max_retries=5, retry_delay_seconds=10)
        assert s.state == SchedulerState.IDLE

    def test_is_running_false_when_idle(self):
        s = ProductionScheduler()
        assert s.is_running is False

    def test_is_running_false_when_paused(self):
        s = ProductionScheduler()
        s.start()
        s.pause()
        assert s.is_running is False

    def test_is_running_false_when_stopped(self):
        s = ProductionScheduler()
        s.start()
        s.stop()
        assert s.is_running is False


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — Lifecycle
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerLifecycle:
    """ProductionScheduler 生命周期测试."""

    def test_start_sets_running(self):
        s = ProductionScheduler()
        s.start()
        assert s.state == SchedulerState.RUNNING
        assert s.is_running is True

    def test_pause_from_running(self):
        s = ProductionScheduler()
        s.start()
        s.pause()
        assert s.state == SchedulerState.PAUSED

    def test_pause_from_idle_does_nothing(self):
        s = ProductionScheduler()
        s.pause()
        assert s.state == SchedulerState.IDLE

    def test_pause_from_stopped_does_nothing(self):
        s = ProductionScheduler()
        s.start()
        s.stop()
        s.pause()
        assert s.state == SchedulerState.STOPPED

    def test_resume_from_paused(self):
        s = ProductionScheduler()
        s.start()
        s.pause()
        s.resume()
        assert s.state == SchedulerState.RUNNING

    def test_resume_from_idle_does_nothing(self):
        s = ProductionScheduler()
        s.resume()
        assert s.state == SchedulerState.IDLE

    def test_resume_from_running_does_nothing(self):
        s = ProductionScheduler()
        s.start()
        s.resume()
        assert s.state == SchedulerState.RUNNING

    def test_stop_from_running(self):
        s = ProductionScheduler()
        s.start()
        s.stop()
        assert s.state == SchedulerState.STOPPED

    def test_stop_from_idle(self):
        s = ProductionScheduler()
        s.stop()
        assert s.state == SchedulerState.STOPPED

    def test_stop_from_paused(self):
        s = ProductionScheduler()
        s.start()
        s.pause()
        s.stop()
        assert s.state == SchedulerState.STOPPED


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — Tick
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerTick:
    """ProductionScheduler tick 测试."""

    def test_tick_when_not_running(self):
        s = ProductionScheduler()
        result = s.tick()
        assert result["status"] == "skipped"
        assert "idle" in result["reason"]

    def test_tick_when_paused(self):
        s = ProductionScheduler()
        s.start()
        s.pause()
        result = s.tick()
        assert result["status"] == "skipped"
        assert "paused" in result["reason"]

    def test_tick_without_handler(self):
        s = ProductionScheduler()
        s.start()
        result = s.tick()
        assert result["status"] == "skipped"
        assert "No tick handler" in result["reason"]

    def test_tick_with_handler_success(self):
        s = ProductionScheduler()
        s.on_tick(_make_success_handler({"ok": True}))
        s.start()
        result = s.tick()
        assert result["status"] == "success"
        assert result["attempt"] == 1
        assert result["result"] == {"ok": True}
        assert result["tick"] == 1

    def test_tick_increments_tick_count(self):
        s = ProductionScheduler()
        s.on_tick(_make_success_handler())
        s.start()
        s.tick()
        assert s.tick_count == 1
        s.tick()
        assert s.tick_count == 2

    def test_tick_with_handler_error_and_retry(self):
        s = ProductionScheduler(max_retries=3, retry_delay_seconds=0)
        s.on_tick(_make_failing_handler("always fail"))
        s.start()
        result = s.tick()
        assert result["status"] == "error"
        assert result["attempts"] == 3
        assert "always fail" in str(result["error"])

    def test_tick_error_transitions_to_error_state(self):
        s = ProductionScheduler(max_retries=2, retry_delay_seconds=0)
        s.on_tick(_make_failing_handler())
        s.start()
        s.tick()
        assert s.state == SchedulerState.ERROR

    def test_tick_with_flaky_handler_recovers(self):
        s = ProductionScheduler(max_retries=3, retry_delay_seconds=0)
        s.on_tick(_make_flaky_handler(fail_times=1, result={"recovered": True}))
        s.start()
        result = s.tick()
        assert result["status"] == "success"
        assert result["attempt"] == 2
        assert result["result"] == {"recovered": True}

    def test_tick_error_callback_called(self):
        errors = []

        def error_handler(e):
            errors.append(str(e))

        s = ProductionScheduler(max_retries=2, retry_delay_seconds=0)
        s.on_tick(_make_failing_handler("callback test"))
        s.on_error(error_handler)
        s.start()
        s.tick()
        assert len(errors) == 2
        assert "callback test" in errors[0]

    def test_on_tick_registration(self):
        s = ProductionScheduler()
        handler = _make_success_handler()
        s.on_tick(handler)
        s.start()
        result = s.tick()
        assert result["status"] == "success"

    def test_on_error_registration(self):
        s = ProductionScheduler(max_retries=1, retry_delay_seconds=0)
        s.on_tick(_make_failing_handler())
        called = []

        def on_err(e):
            called.append(e)
        s.on_error(on_err)
        s.start()
        s.tick()
        assert len(called) == 1


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — should_tick
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerShouldTick:
    """ProductionScheduler should_tick 测试."""

    def test_should_tick_when_idle(self):
        s = ProductionScheduler()
        assert s.should_tick() is False

    def test_should_tick_when_paused(self):
        s = ProductionScheduler()
        s.start()
        s.pause()
        assert s.should_tick() is False

    def test_should_tick_when_stopped(self):
        s = ProductionScheduler()
        s.start()
        s.stop()
        assert s.should_tick() is False

    def test_should_tick_when_running_no_last_tick(self):
        s = ProductionScheduler()
        s.start()
        assert s.should_tick() is True

    def test_should_tick_when_running_past_interval(self):
        s = ProductionScheduler(interval_minutes=0)
        s.on_tick(_make_success_handler())
        s.start()
        s.tick()
        assert s.should_tick() is True


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — Statistics
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerStatistics:
    """ProductionScheduler 统计测试."""

    def test_get_stats_idle(self):
        s = ProductionScheduler()
        stats = s.get_stats()
        assert stats["state"] == "idle"
        assert stats["tick_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["interval_minutes"] == 60

    def test_get_stats_after_success(self):
        s = ProductionScheduler()
        s.on_tick(_make_success_handler())
        s.start()
        s.tick()
        stats = s.get_stats()
        assert stats["state"] == "running"
        assert stats["tick_count"] == 1
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 1.0

    def test_get_stats_after_failure(self):
        s = ProductionScheduler(max_retries=1, retry_delay_seconds=0)
        s.on_tick(_make_failing_handler())
        s.start()
        s.tick()
        stats = s.get_stats()
        assert stats["state"] == "error"
        assert stats["tick_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 0.0

    def test_get_stats_mixed(self):
        s = ProductionScheduler(max_retries=1, retry_delay_seconds=0)
        s.start()
        s.on_tick(_make_success_handler())
        s.tick()
        s.on_tick(_make_failing_handler())
        s.start()
        s.tick()
        stats = s.get_stats()
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 0.5

    def test_get_uptime_seconds_no_start(self):
        s = ProductionScheduler()
        assert s.get_uptime_seconds() == 0.0

    def test_get_uptime_seconds_after_start(self):
        s = ProductionScheduler()
        s.start()
        uptime = s.get_uptime_seconds()
        assert uptime >= 0.0

    def test_success_rate_no_data(self):
        s = ProductionScheduler()
        assert s.success_rate == 1.0

    def test_success_rate_with_data(self):
        s = ProductionScheduler(max_retries=1, retry_delay_seconds=0)
        s.on_tick(_make_success_handler())
        s.start()
        s.tick()
        s.on_tick(_make_failing_handler())
        s.start()
        s.tick()
        assert s.success_rate == 0.5


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — Reset
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerReset:
    """ProductionScheduler reset 测试."""

    def test_reset_clears_state(self):
        s = ProductionScheduler()
        s.on_tick(_make_success_handler())
        s.start()
        s.tick()
        s.reset()
        assert s.state == SchedulerState.IDLE
        assert s.tick_count == 0
        assert s.success_rate == 1.0

    def test_reset_clears_stats(self):
        s = ProductionScheduler(max_retries=1, retry_delay_seconds=0)
        s.on_tick(_make_failing_handler())
        s.start()
        s.tick()
        s.reset()
        stats = s.get_stats()
        assert stats["tick_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 1.0

    def test_reset_clears_uptime(self):
        s = ProductionScheduler()
        s.start()
        s.reset()
        assert s.get_uptime_seconds() == 0.0


# ═══════════════════════════════════════════════════════════════
# ProductionScheduler — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestProductionSchedulerEdgeCases:
    """ProductionScheduler 边界情况测试."""

    def test_empty_scheduler_tick(self):
        s = ProductionScheduler()
        s.start()
        result = s.tick()
        assert result["status"] == "skipped"

    def test_empty_scheduler_stats(self):
        s = ProductionScheduler()
        stats = s.get_stats()
        assert stats["state"] == "idle"
        assert stats["tick_count"] == 0

    def test_empty_scheduler_should_tick(self):
        s = ProductionScheduler()
        assert s.should_tick() is False

    def test_tick_count_after_multiple_cycles(self):
        s = ProductionScheduler()
        s.on_tick(_make_success_handler())
        s.start()
        for _ in range(10):
            s.tick()
        assert s.tick_count == 10

    def test_state_after_stop_no_more_ticks(self):
        s = ProductionScheduler()
        s.on_tick(_make_success_handler())
        s.start()
        s.stop()
        result = s.tick()
        assert result["status"] == "skipped"
        assert "stopped" in result["reason"]


# ═══════════════════════════════════════════════════════════════
# WorkerState enum
# ═══════════════════════════════════════════════════════════════


class TestWorkerStateEnum:
    """WorkerState 枚举测试."""

    def test_states_exist(self):
        assert WorkerState.IDLE == "idle"
        assert WorkerState.BUSY == "busy"
        assert WorkerState.ERROR == "error"

    def test_is_string_enum(self):
        assert isinstance(WorkerState.IDLE, str)
        assert WorkerState.IDLE.value == "idle"


# ═══════════════════════════════════════════════════════════════
# ExecutionStatus enum
# ═══════════════════════════════════════════════════════════════


class TestExecutionStatusEnum:
    """ExecutionStatus 枚举测试."""

    def test_statuses_exist(self):
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.SUCCESS == "success"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.ROLLED_BACK == "rolled_back"

    def test_is_string_enum(self):
        assert isinstance(ExecutionStatus.PENDING, str)


# ═══════════════════════════════════════════════════════════════
# ExecutionResult
# ═══════════════════════════════════════════════════════════════


class TestExecutionResult:
    """ExecutionResult 测试."""

    def test_create_with_defaults(self):
        r = ExecutionResult()
        assert r.action_id == ""
        assert r.status == ExecutionStatus.PENDING
        assert r.output == {}
        assert r.error == ""
        assert r.duration_ms == 0.0
        assert r.rollback_record_id == ""
        assert r.result_id != ""

    def test_create_with_params(self):
        r = ExecutionResult(
            action_id="act_001",
            status=ExecutionStatus.SUCCESS,
            output={"ok": True},
            duration_ms=150.0,
        )
        assert r.action_id == "act_001"
        assert r.status == ExecutionStatus.SUCCESS
        assert r.output == {"ok": True}
        assert r.duration_ms == 150.0

    def test_to_dict(self):
        r = ExecutionResult(
            action_id="act_001",
            status=ExecutionStatus.SUCCESS,
            output={"key": "value"},
            error="",
            duration_ms=100.0,
        )
        d = r.to_dict()
        assert d["action_id"] == "act_001"
        assert d["status"] == "success"
        assert d["output"] == {"key": "value"}
        assert d["duration_ms"] == 100.0
        assert "result_id" in d
        assert "timestamp" in d

    def test_to_dict_includes_all_fields(self):
        r = ExecutionResult()
        d = r.to_dict()
        expected_keys = {"result_id", "action_id", "status", "output", "error",
                         "duration_ms", "rollback_record_id", "timestamp"}
        assert set(d.keys()) == expected_keys


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Creation
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerCreation:
    """ProductionWorker 创建测试."""

    def test_create_with_defaults(self):
        w = ProductionWorker()
        assert w.state == WorkerState.IDLE
        assert w.is_idle is True
        assert w.is_available is True

    def test_create_with_custom_capacity(self):
        w = ProductionWorker(max_concurrent=10)
        assert w.state == WorkerState.IDLE
        assert w.is_available is True

    def test_create_with_min_capacity(self):
        w = ProductionWorker(max_concurrent=1)
        assert w.is_available is True


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Registration
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerRegistration:
    """ProductionWorker 注册/注销测试."""

    def test_register_executor(self):
        w = ProductionWorker()
        w.register_executor("update_budget", _make_executor())
        assert "update_budget" in w.registered_actions

    def test_register_multiple_executors(self):
        w = ProductionWorker()
        w.register_executor("update_budget", _make_executor())
        w.register_executor("adjust_bid", _make_executor())
        assert len(w.registered_actions) == 2
        assert "update_budget" in w.registered_actions
        assert "adjust_bid" in w.registered_actions

    def test_unregister_executor_success(self):
        w = ProductionWorker()
        w.register_executor("update_budget", _make_executor())
        result = w.unregister_executor("update_budget")
        assert result is True
        assert "update_budget" not in w.registered_actions

    def test_unregister_executor_not_found(self):
        w = ProductionWorker()
        result = w.unregister_executor("nonexistent")
        assert result is False

    def test_registered_actions_empty(self):
        w = ProductionWorker()
        assert w.registered_actions == []

    def test_unregister_does_not_affect_others(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.register_executor("b", _make_executor())
        w.unregister_executor("a")
        assert w.registered_actions == ["b"]


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Execute
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerExecute:
    """ProductionWorker execute 测试."""

    def test_execute_success(self):
        w = ProductionWorker()
        w.register_executor("update_budget", _make_executor({"budget": 100}))
        result = w.execute("update_budget", {"campaign_id": "c1"}, action_id="act_001")
        assert result.status == ExecutionStatus.SUCCESS
        assert result.action_id == "act_001"
        assert result.output == {"budget": 100}
        assert result.duration_ms >= 0

    def test_execute_failure(self):
        w = ProductionWorker()
        w.register_executor("update_budget", _make_failing_executor("boom"))
        result = w.execute("update_budget", {}, action_id="act_002")
        assert result.status == ExecutionStatus.FAILED
        assert result.error == "boom"
        assert result.action_id == "act_002"

    def test_execute_unregistered_action(self):
        w = ProductionWorker()
        result = w.execute("unknown_action", {}, action_id="act_003")
        assert result.status == ExecutionStatus.FAILED
        assert "No executor registered" in result.error

    def test_execute_at_capacity(self):
        w = ProductionWorker(max_concurrent=1)
        w.register_executor("task", _make_executor())
        # Fill capacity
        w._active_count = 1
        result = w.execute("task", {}, action_id="act_004")
        assert result.status == ExecutionStatus.FAILED
        assert "max capacity" in result.error

    def test_execute_sets_state_to_busy(self):
        w = ProductionWorker()
        w.register_executor("task", _make_executor())
        w.execute("task")
        assert w.state == WorkerState.IDLE  # Returns to IDLE after execution

    def test_execute_increments_counters(self):
        w = ProductionWorker()
        w.register_executor("task", _make_executor())
        w.execute("task")
        stats = w.get_stats()
        assert stats["total_executed"] == 1
        assert stats["total_success"] == 1
        assert stats["total_failed"] == 0

    def test_execute_failure_increments_failed_counter(self):
        w = ProductionWorker()
        w.register_executor("task", _make_failing_executor())
        w.execute("task")
        stats = w.get_stats()
        assert stats["total_executed"] == 1
        assert stats["total_failed"] == 1

    def test_execute_with_non_dict_output(self):
        w = ProductionWorker()
        w.register_executor("task", lambda params: 42)
        result = w.execute("task")
        assert result.status == ExecutionStatus.SUCCESS
        assert result.output == {"result": 42}

    def test_execute_with_empty_params(self):
        w = ProductionWorker()
        w.register_executor("task", _make_executor({"got": "none"}))
        result = w.execute("task")
        assert result.status == ExecutionStatus.SUCCESS
        assert result.output == {"got": "none"}


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Execute Batch
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerExecuteBatch:
    """ProductionWorker execute_batch 测试."""

    def test_execute_batch_all_success(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor({"a": 1}))
        w.register_executor("b", _make_executor({"b": 2}))
        actions = [
            {"action_type": "a", "params": {}, "action_id": "id1"},
            {"action_type": "b", "params": {}, "action_id": "id2"},
        ]
        results = w.execute_batch(actions)
        assert len(results) == 2
        assert all(r.status == ExecutionStatus.SUCCESS for r in results)

    def test_execute_batch_mixed(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        actions = [
            {"action_type": "a", "params": {}, "action_id": "id1"},
            {"action_type": "unknown", "params": {}, "action_id": "id2"},
        ]
        results = w.execute_batch(actions)
        assert results[0].status == ExecutionStatus.SUCCESS
        assert results[1].status == ExecutionStatus.FAILED

    def test_execute_batch_empty(self):
        w = ProductionWorker()
        results = w.execute_batch([])
        assert results == []

    def test_execute_batch_preserves_order(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor({"idx": 1}))
        w.register_executor("b", _make_executor({"idx": 2}))
        actions = [
            {"action_type": "a", "params": {}, "action_id": "id1"},
            {"action_type": "b", "params": {}, "action_id": "id2"},
            {"action_type": "a", "params": {}, "action_id": "id3"},
        ]
        results = w.execute_batch(actions)
        assert len(results) == 3
        assert all(r.status == ExecutionStatus.SUCCESS for r in results)
        assert results[0].action_id == "id1"
        assert results[1].action_id == "id2"
        assert results[2].action_id == "id3"


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Results
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerResults:
    """ProductionWorker 结果查询测试."""

    def test_get_results_empty(self):
        w = ProductionWorker()
        assert w.get_results() == []

    def test_get_results(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a", {}, action_id="id1")
        results = w.get_results()
        assert len(results) == 1
        assert results[0].action_id == "id1"

    def test_get_results_with_limit(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        for i in range(10):
            w.execute("a", {}, action_id=f"id{i}")
        results = w.get_results(limit=3)
        assert len(results) == 3

    def test_get_failed_empty(self):
        w = ProductionWorker()
        assert w.get_failed() == []

    def test_get_failed(self):
        w = ProductionWorker()
        w.register_executor("a", _make_failing_executor("err"))
        w.execute("a", {}, action_id="failed_1")
        w.register_executor("b", _make_executor())
        w.execute("b", {}, action_id="ok_1")
        failed = w.get_failed()
        assert len(failed) == 1
        assert failed[0].action_id == "failed_1"

    def test_get_by_action_found(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a", {}, action_id="target")
        r = w.get_by_action("target")
        assert r is not None
        assert r.action_id == "target"

    def test_get_by_action_not_found(self):
        w = ProductionWorker()
        assert w.get_by_action("nonexistent") is None

    def test_get_by_action_returns_latest(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor({"v": 1}))
        w.execute("a", {}, action_id="dup")
        w.register_executor("a", _make_executor({"v": 2}))
        w.execute("a", {}, action_id="dup")
        r = w.get_by_action("dup")
        assert r.output == {"v": 2}


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Statistics
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerStatistics:
    """ProductionWorker 统计测试."""

    def test_get_stats_idle(self):
        w = ProductionWorker()
        stats = w.get_stats()
        assert stats["state"] == "idle"
        assert stats["total_executed"] == 0
        assert stats["total_success"] == 0
        assert stats["total_failed"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["max_concurrent"] == 5

    def test_get_stats_after_execution(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a")
        stats = w.get_stats()
        assert stats["total_executed"] == 1
        assert stats["total_success"] == 1

    def test_success_rate_no_data(self):
        w = ProductionWorker()
        assert w.success_rate == 1.0

    def test_success_rate_mixed(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a")
        w.register_executor("b", _make_failing_executor())
        w.execute("b")
        assert w.success_rate == 0.5

    def test_success_rate_all_failed(self):
        w = ProductionWorker()
        w.register_executor("a", _make_failing_executor())
        w.execute("a")
        assert w.success_rate == 0.0


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Reset
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerReset:
    """ProductionWorker reset 测试."""

    def test_reset_clears_state(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a")
        w.reset()
        assert w.state == WorkerState.IDLE
        assert w.is_idle is True

    def test_reset_clears_counters(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a")
        w.register_executor("b", _make_failing_executor())
        w.execute("b")
        w.reset()
        stats = w.get_stats()
        assert stats["total_executed"] == 0
        assert stats["total_success"] == 0
        assert stats["total_failed"] == 0

    def test_reset_clears_results(self):
        w = ProductionWorker()
        w.register_executor("a", _make_executor())
        w.execute("a")
        w.reset()
        assert w.get_results() == []


# ═══════════════════════════════════════════════════════════════
# ProductionWorker — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestProductionWorkerEdgeCases:
    """ProductionWorker 边界情况测试."""

    def test_worker_at_max_capacity(self):
        w = ProductionWorker(max_concurrent=1)
        w.register_executor("task", _make_executor())
        w._active_count = 1
        result = w.execute("task")
        assert result.status == ExecutionStatus.FAILED
        assert "max capacity" in result.error

    def test_empty_worker_stats(self):
        w = ProductionWorker()
        stats = w.get_stats()
        assert stats["total_executed"] == 0
        assert stats["registered_actions"] == []

    def test_empty_worker_results(self):
        w = ProductionWorker()
        assert w.get_results() == []
        assert w.get_failed() == []
        assert w.get_by_action("any") is None

    def test_unregistered_executor_error_message(self):
        w = ProductionWorker()
        result = w.execute("nonexistent_action")
        assert "No executor registered" in result.error
        assert "nonexistent_action" in result.error


# ═══════════════════════════════════════════════════════════════
# HealthStatus enum
# ═══════════════════════════════════════════════════════════════


class TestHealthStatusEnum:
    """HealthStatus 枚举测试."""

    def test_statuses_exist(self):
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNKNOWN == "unknown"

    def test_is_string_enum(self):
        assert isinstance(HealthStatus.HEALTHY, str)


# ═══════════════════════════════════════════════════════════════
# ComponentHealth
# ═══════════════════════════════════════════════════════════════


class TestComponentHealth:
    """ComponentHealth 测试."""

    def test_create_defaults(self):
        c = ComponentHealth()
        assert c.component == ""
        assert c.status == HealthStatus.UNKNOWN
        assert c.message == ""
        assert c.latency_ms == 0.0
        assert c.last_checked == ""
        assert c.metadata == {}

    def test_create_with_params(self):
        c = ComponentHealth(
            component="agent",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=5.0,
            last_checked="2026-01-01T00:00:00+00:00",
            metadata={"version": "1.0"},
        )
        assert c.component == "agent"
        assert c.status == HealthStatus.HEALTHY
        assert c.message == "OK"
        assert c.latency_ms == 5.0
        assert c.metadata == {"version": "1.0"}

    def test_to_dict(self):
        c = ComponentHealth(
            component="agent",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=10.0,
        )
        d = c.to_dict()
        assert d["component"] == "agent"
        assert d["status"] == "healthy"
        assert d["message"] == "OK"
        assert d["latency_ms"] == 10.0
        assert "last_checked" in d
        assert "metadata" in d


# ═══════════════════════════════════════════════════════════════
# HealthReport
# ═══════════════════════════════════════════════════════════════


class TestHealthReport:
    """HealthReport 测试."""

    def test_create_defaults(self):
        r = HealthReport()
        assert r.overall == HealthStatus.UNKNOWN
        assert r.components == []
        assert r.uptime_seconds == 0.0

    def test_is_healthy(self):
        r = HealthReport(overall=HealthStatus.HEALTHY)
        assert r.is_healthy is True

    def test_is_healthy_false(self):
        r = HealthReport(overall=HealthStatus.UNHEALTHY)
        assert r.is_healthy is False

    def test_unhealthy_components(self):
        c1 = ComponentHealth(component="a", status=HealthStatus.HEALTHY)
        c2 = ComponentHealth(component="b", status=HealthStatus.UNHEALTHY)
        c3 = ComponentHealth(component="c", status=HealthStatus.UNHEALTHY)
        r = HealthReport(components=[c1, c2, c3])
        unhealthy = r.unhealthy_components
        assert len(unhealthy) == 2
        assert {c.component for c in unhealthy} == {"b", "c"}

    def test_unhealthy_components_empty(self):
        r = HealthReport(components=[
            ComponentHealth(component="a", status=HealthStatus.HEALTHY),
        ])
        assert r.unhealthy_components == []

    def test_to_dict(self):
        c = ComponentHealth(component="agent", status=HealthStatus.HEALTHY)
        r = HealthReport(
            overall=HealthStatus.HEALTHY,
            components=[c],
            uptime_seconds=3600,
        )
        d = r.to_dict()
        assert d["overall"] == "healthy"
        assert d["is_healthy"] is True
        assert d["uptime_seconds"] == 3600
        assert len(d["components"]) == 1
        assert d["unhealthy_count"] == 0


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Creation & Registration
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerCreation:
    """HealthChecker 创建与注册测试."""

    def test_create(self):
        h = HealthChecker()
        assert h.registered_components == []

    def test_register(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        assert "agent" in h.registered_components

    def test_register_multiple(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", _make_healthy_check("db"))
        h.register("api", _make_healthy_check("api"))
        assert len(h.registered_components) == 3

    def test_unregister_success(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        result = h.unregister("agent")
        assert result is True
        assert "agent" not in h.registered_components

    def test_unregister_not_found(self):
        h = HealthChecker()
        result = h.unregister("nonexistent")
        assert result is False

    def test_registered_components_empty(self):
        h = HealthChecker()
        assert h.registered_components == []


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Check Single Component
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerCheck:
    """HealthChecker 单组件检查测试."""

    def test_check_healthy(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        result = h.check("agent")
        assert result.component == "agent"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms >= 0

    def test_check_unhealthy(self):
        h = HealthChecker()
        h.register("db", _make_unhealthy_check("db"))
        result = h.check("db")
        assert result.status == HealthStatus.UNHEALTHY

    def test_check_unregistered(self):
        h = HealthChecker()
        result = h.check("unknown")
        assert result.status == HealthStatus.UNKNOWN
        assert "No check registered" in result.message

    def test_check_exception_in_handler(self):
        h = HealthChecker()
        h.register("bad", _make_failing_check("handler error"))
        result = h.check("bad")
        assert result.status == HealthStatus.UNHEALTHY
        assert "Check failed" in result.message
        assert "handler error" in result.message


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Check All
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerCheckAll:
    """HealthChecker check_all 测试."""

    def test_check_all_all_healthy(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", _make_healthy_check("db"))
        report = h.check_all()
        assert report.overall == HealthStatus.HEALTHY
        assert report.is_healthy is True
        assert len(report.components) == 2

    def test_check_all_some_unhealthy(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", _make_unhealthy_check("db"))
        report = h.check_all()
        assert report.overall == HealthStatus.UNHEALTHY
        assert len(report.unhealthy_components) == 1

    def test_check_all_some_degraded(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", lambda: ComponentHealth(
            component="db", status=HealthStatus.DEGRADED, message="slow",
        ))
        report = h.check_all()
        assert report.overall == HealthStatus.DEGRADED

    def test_check_all_empty(self):
        h = HealthChecker()
        report = h.check_all()
        assert report.overall == HealthStatus.UNKNOWN
        assert report.components == []

    def test_check_all_mixed_degraded_and_unhealthy(self):
        h = HealthChecker()
        h.register("a", _make_healthy_check("a"))
        h.register("b", lambda: ComponentHealth(
            component="b", status=HealthStatus.DEGRADED,
        ))
        h.register("c", _make_unhealthy_check("c"))
        report = h.check_all()
        assert report.overall == HealthStatus.UNHEALTHY


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Built-in Checks
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerBuiltinChecks:
    """HealthChecker 内置检查方法测试."""

    def test_check_agent_healthy(self):
        h = HealthChecker()
        result = h.check_agent(is_running=True, error_count=0)
        assert result.component == "agent"
        assert result.status == HealthStatus.HEALTHY
        assert "running normally" in result.message

    def test_check_agent_degraded(self):
        h = HealthChecker()
        result = h.check_agent(is_running=True, error_count=10)
        assert result.status == HealthStatus.DEGRADED
        assert "10 errors" in result.message

    def test_check_agent_unhealthy(self):
        h = HealthChecker()
        result = h.check_agent(is_running=False)
        assert result.status == HealthStatus.UNHEALTHY
        assert "not running" in result.message

    def test_check_agent_boundary_error_count(self):
        h = HealthChecker()
        result = h.check_agent(is_running=True, error_count=5)
        assert result.status == HealthStatus.HEALTHY

    def test_check_agent_just_above_boundary(self):
        h = HealthChecker()
        result = h.check_agent(is_running=True, error_count=6)
        assert result.status == HealthStatus.DEGRADED

    def test_check_connector_connected(self):
        h = HealthChecker()
        result = h.check_connector("meta", is_connected=True, last_sync="2026-01-01")
        assert result.component == "meta_connector"
        assert result.status == HealthStatus.HEALTHY
        assert result.metadata["last_sync"] == "2026-01-01"

    def test_check_connector_disconnected(self):
        h = HealthChecker()
        result = h.check_connector("adjust", is_connected=False, error="timeout")
        assert result.status == HealthStatus.UNHEALTHY
        assert "disconnected" in result.message
        assert result.metadata["error"] == "timeout"

    def test_check_database_healthy(self):
        h = HealthChecker()
        result = h.check_database(is_connected=True, latency_ms=50.0)
        assert result.component == "database"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 50.0

    def test_check_database_degraded_high_latency(self):
        h = HealthChecker()
        result = h.check_database(is_connected=True, latency_ms=1500.0)
        assert result.status == HealthStatus.DEGRADED
        assert "latency" in result.message.lower()

    def test_check_database_unhealthy(self):
        h = HealthChecker()
        result = h.check_database(is_connected=False)
        assert result.status == HealthStatus.UNHEALTHY
        assert "connection failed" in result.message.lower()

    def test_check_database_boundary_latency(self):
        h = HealthChecker()
        result = h.check_database(is_connected=True, latency_ms=1000.0)
        assert result.status == HealthStatus.HEALTHY

    def test_check_database_just_above_latency_boundary(self):
        h = HealthChecker()
        result = h.check_database(is_connected=True, latency_ms=1001.0)
        assert result.status == HealthStatus.DEGRADED

    def test_check_api_available(self):
        h = HealthChecker()
        result = h.check_api("growth", is_available=True, status_code=200)
        assert result.component == "growth_api"
        assert result.status == HealthStatus.HEALTHY

    def test_check_api_degraded_500(self):
        h = HealthChecker()
        result = h.check_api("growth", is_available=True, status_code=500)
        assert result.status == HealthStatus.DEGRADED
        assert "500" in result.message

    def test_check_api_degraded_503(self):
        h = HealthChecker()
        result = h.check_api("growth", is_available=True, status_code=503)
        assert result.status == HealthStatus.DEGRADED

    def test_check_api_unavailable(self):
        h = HealthChecker()
        result = h.check_api("growth", is_available=False)
        assert result.status == HealthStatus.UNHEALTHY
        assert "unavailable" in result.message.lower()

    def test_check_api_edge_499(self):
        h = HealthChecker()
        result = h.check_api("growth", is_available=True, status_code=499)
        assert result.status == HealthStatus.HEALTHY


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Report & Summary
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerReport:
    """HealthChecker 报告与摘要测试."""

    def test_get_last_report_none(self):
        h = HealthChecker()
        assert h.get_last_report() is None

    def test_get_last_report_after_check_all(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.check_all()
        report = h.get_last_report()
        assert report is not None
        assert report.overall == HealthStatus.HEALTHY

    def test_get_summary_no_report(self):
        h = HealthChecker()
        summary = h.get_summary()
        assert summary["status"] == "no_report"

    def test_get_summary_healthy(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", _make_healthy_check("db"))
        h.check_all()
        summary = h.get_summary()
        assert summary["overall"] == "healthy"
        assert summary["is_healthy"] is True
        assert "components" in summary
        assert summary["unhealthy"] == []

    def test_get_summary_with_unhealthy(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", _make_unhealthy_check("db"))
        h.check_all()
        summary = h.get_summary()
        assert summary["overall"] == "unhealthy"
        assert summary["unhealthy"] == ["db"]

    def test_get_summary_components_dict(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.register("db", _make_unhealthy_check("db"))
        h.check_all()
        summary = h.get_summary()
        assert summary["components"]["agent"] == "healthy"
        assert summary["components"]["db"] == "unhealthy"


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Reset
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerReset:
    """HealthChecker reset 测试."""

    def test_reset_clears_report(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.check_all()
        assert h.get_last_report() is not None
        h.reset()
        assert h.get_last_report() is None

    def test_reset_does_not_clear_registrations(self):
        h = HealthChecker()
        h.register("agent", _make_healthy_check("agent"))
        h.reset()
        assert "agent" in h.registered_components


# ═══════════════════════════════════════════════════════════════
# HealthChecker — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestHealthCheckerEdgeCases:
    """HealthChecker 边界情况测试."""

    def test_check_unregistered_component(self):
        h = HealthChecker()
        result = h.check("nonexistent")
        assert result.status == HealthStatus.UNKNOWN
        assert result.component == "nonexistent"

    def test_check_all_empty_registry(self):
        h = HealthChecker()
        report = h.check_all()
        assert report.overall == HealthStatus.UNKNOWN
        assert report.components == []

    def test_check_exception_produces_unhealthy(self):
        h = HealthChecker()
        h.register("bad", _make_failing_check("crash"))
        result = h.check("bad")
        assert result.status == HealthStatus.UNHEALTHY
        assert "crash" in result.message

    def test_check_all_with_exception_in_handler(self):
        h = HealthChecker()
        h.register("a", _make_healthy_check("a"))
        h.register("b", _make_failing_check("b crash"))
        report = h.check_all()
        assert report.overall == HealthStatus.UNHEALTHY
        assert len(report.unhealthy_components) == 1
        assert report.unhealthy_components[0].component == "b"

    def test_multiple_unhealthy_components(self):
        h = HealthChecker()
        h.register("a", _make_unhealthy_check("a"))
        h.register("b", _make_unhealthy_check("b"))
        h.register("c", _make_healthy_check("c"))
        report = h.check_all()
        assert report.overall == HealthStatus.UNHEALTHY
        assert len(report.unhealthy_components) == 2