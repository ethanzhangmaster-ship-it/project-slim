"""E13.7.4.3 Agent Health Monitor — 测试套件.

覆盖:
  - Health Models (HealthStatus, HealthSnapshot, HealthRule, Alert, SafeModePolicy)
  - Health Metrics (RuntimeMetricsCollector, DecisionMetricsCollector, ExecutionMetricsCollector, ToolMetricsCollector, MetricsCollector)
  - Health Rules (执行失败, 工具失败, 决策漂移, 循环超时, 连续错误, API 超时, 限流, 心跳丢失, 低置信度比例)
  - Health Monitor (健康检查, 状态切换, 安全模式, 告警触发, 状态变更回调)
  - Alert Manager (创建/发送/解决告警, 去重, 统计)
  - Health Policy (Safe Mode 行为约束, 各状态允许/禁止动作)
  - Integration (Runtime 集成: 指标采集 → 健康检查 → 安全模式)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.health import (
    # Enums
    HealthStatus,
    HealthMetricCategory,
    AlertLevel,
    AlertType,
    # Models
    MetricDefinition,
    RuntimeHealth,
    DecisionHealth,
    ExecutionHealth,
    ToolHealth,
    HealthSnapshot,
    HealthRule,
    HealthRuleResult,
    HealthEvaluation,
    Alert,
    SafeModePolicy,
    # Helpers
    HEALTH_STATUS_SEVERITY,
    most_severe_status,
    # Metrics
    RuntimeMetricsCollector,
    DecisionMetricsCollector,
    ExecutionMetricsCollector,
    ToolMetricsCollector,
    MetricsCollector,
    # Rules
    build_default_health_rules,
    # Monitor
    HealthMonitor,
    create_health_monitor,
    # Alert
    AlertManager,
    create_alert_manager,
    # Policy
    HealthPolicy,
    DEFAULT_SAFE_MODE_POLICY,
    create_health_policy,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_healthy_snapshot() -> HealthSnapshot:
    """创建健康快照."""
    return HealthSnapshot(
        runtime=RuntimeHealth(
            cycle_count=10,
            cycle_duration_avg=5.0,
            last_heartbeat="2026-01-01T00:00:00+00:00",
            failed_cycles=0,
            uptime_seconds=3600,
        ),
        decision=DecisionHealth(
            decision_count=20,
            average_confidence=0.85,
            low_confidence_rate=0.1,
            decision_latency_avg=50.0,
        ),
        execution=ExecutionHealth(
            execution_success_rate=0.95,
            rollback_rate=0.0,
            failure_rate=0.05,
            total_executions=100,
            consecutive_errors=0,
        ),
        tool=ToolHealth(
            api_success_rate=0.98,
            timeout_count=0,
            rate_limit_count=0,
            total_api_calls=50,
            avg_latency_ms=200.0,
        ),
    )


def make_snapshot_with_failures(
    failure_rate: float = 0.5,
    consecutive_errors: int = 0,
    api_success_rate: float = 1.0,
    timeout_count: int = 0,
    confidence: float = 0.85,
    low_confidence_rate: float = 0.1,
    rate_limit_count: int = 0,
) -> HealthSnapshot:
    """创建指定参数的快照."""
    return HealthSnapshot(
        runtime=RuntimeHealth(cycle_count=10, cycle_duration_avg=5.0),
        decision=DecisionHealth(
            decision_count=20,
            average_confidence=confidence,
            low_confidence_rate=low_confidence_rate,
        ),
        execution=ExecutionHealth(
            execution_success_rate=1.0 - failure_rate,
            failure_rate=failure_rate,
            total_executions=100,
            consecutive_errors=consecutive_errors,
        ),
        tool=ToolHealth(
            api_success_rate=api_success_rate,
            timeout_count=timeout_count,
            rate_limit_count=rate_limit_count,
            total_api_calls=50,
        ),
    )


# ═══════════════════════════════════════════════════════════════
# Test Health Models
# ═══════════════════════════════════════════════════════════════


class TestHealthStatus:
    """测试 HealthStatus 枚举."""

    def test_all_status_values(self):
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.WARNING == "warning"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.SAFE_MODE == "safe_mode"
        assert HealthStatus.FAILED == "failed"

    def test_severity_ordering(self):
        assert HEALTH_STATUS_SEVERITY[HealthStatus.HEALTHY] == 0
        assert HEALTH_STATUS_SEVERITY[HealthStatus.WARNING] == 1
        assert HEALTH_STATUS_SEVERITY[HealthStatus.DEGRADED] == 2
        assert HEALTH_STATUS_SEVERITY[HealthStatus.SAFE_MODE] == 3
        assert HEALTH_STATUS_SEVERITY[HealthStatus.FAILED] == 4

    def test_most_severe_status(self):
        assert most_severe_status([]) == HealthStatus.HEALTHY
        assert most_severe_status([HealthStatus.HEALTHY]) == HealthStatus.HEALTHY
        assert most_severe_status([HealthStatus.HEALTHY, HealthStatus.WARNING]) == HealthStatus.WARNING
        assert most_severe_status([HealthStatus.WARNING, HealthStatus.SAFE_MODE]) == HealthStatus.SAFE_MODE
        assert most_severe_status([HealthStatus.HEALTHY, HealthStatus.FAILED]) == HealthStatus.FAILED


class TestHealthMetricCategory:
    """测试 HealthMetricCategory 枚举."""

    def test_categories(self):
        assert HealthMetricCategory.RUNTIME == "runtime"
        assert HealthMetricCategory.DECISION == "decision"
        assert HealthMetricCategory.EXECUTION == "execution"
        assert HealthMetricCategory.TOOL == "tool"
        assert HealthMetricCategory.MEMORY == "memory"


class TestAlertEnums:
    """测试告警枚举."""

    def test_alert_levels(self):
        assert AlertLevel.INFO == "info"
        assert AlertLevel.WARNING == "warning"
        assert AlertLevel.CRITICAL == "critical"

    def test_alert_types(self):
        assert AlertType.EXECUTION_FAILURE == "execution_failure"
        assert AlertType.TOOL_FAILURE == "tool_failure"
        assert AlertType.DECISION_DRIFT == "decision_drift"
        assert AlertType.API_TIMEOUT == "api_timeout"
        assert AlertType.RATE_LIMIT == "rate_limit"
        assert AlertType.SAFE_MODE_ACTIVATED == "safe_mode_activated"


class TestHealthSnapshot:
    """测试 HealthSnapshot."""

    def test_default_snapshot(self):
        s = HealthSnapshot()
        assert s.status == HealthStatus.HEALTHY
        assert s.runtime.cycle_count == 0

    def test_snapshot_to_dict(self):
        s = make_healthy_snapshot()
        d = s.to_dict()
        assert d["status"] == "healthy"
        assert "runtime" in d
        assert "execution" in d

    def test_runtime_health_to_dict(self):
        r = RuntimeHealth(cycle_count=5, cycle_duration_avg=3.0)
        d = r.to_dict()
        assert d["cycle_count"] == 5
        assert d["cycle_duration_avg"] == 3.0

    def test_decision_health_to_dict(self):
        d = DecisionHealth(decision_count=10, average_confidence=0.8)
        dd = d.to_dict()
        assert dd["decision_count"] == 10

    def test_execution_health_to_dict(self):
        e = ExecutionHealth(execution_success_rate=0.95)
        d = e.to_dict()
        assert d["execution_success_rate"] == 0.95

    def test_tool_health_to_dict(self):
        t = ToolHealth(api_success_rate=0.98)
        d = t.to_dict()
        assert d["api_success_rate"] == 0.98


class TestHealthRule:
    """测试 HealthRule 基类."""

    def test_rule_triggered(self):
        rule = HealthRule(
            name="test_rule",
            condition=lambda s: s.execution.failure_rate > 0.3,
            reason_template="failure rate too high",
            target_status=HealthStatus.SAFE_MODE,
        )
        snapshot = make_snapshot_with_failures(failure_rate=0.5)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.SAFE_MODE

    def test_rule_not_triggered(self):
        rule = HealthRule(
            name="test_rule",
            condition=lambda s: s.execution.failure_rate > 0.3,
            target_status=HealthStatus.SAFE_MODE,
        )
        snapshot = make_snapshot_with_failures(failure_rate=0.1)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_rule_disabled(self):
        rule = HealthRule(
            name="test_rule",
            enabled=False,
            condition=lambda s: True,
            target_status=HealthStatus.SAFE_MODE,
        )
        result = rule.evaluate(make_healthy_snapshot())
        assert not result.triggered

    def test_rule_condition_error(self):
        rule = HealthRule(
            name="test_rule",
            condition=lambda s: 1 / 0,
            target_status=HealthStatus.SAFE_MODE,
        )
        result = rule.evaluate(make_healthy_snapshot())
        assert not result.triggered


class TestAlert:
    """测试 Alert 模型."""

    def test_alert_creation(self):
        alert = Alert(
            level=AlertLevel.CRITICAL,
            alert_type=AlertType.EXECUTION_FAILURE,
            message="test alert",
        )
        assert alert.level == AlertLevel.CRITICAL
        assert not alert.is_resolved
        assert alert.resolved_at == ""

    def test_alert_resolve(self):
        alert = Alert(message="test")
        alert.resolve("fixed")
        assert alert.is_resolved
        assert alert.resolution_note == "fixed"

    def test_alert_to_dict(self):
        alert = Alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.TOOL_FAILURE,
            message="test",
        )
        d = alert.to_dict()
        assert d["level"] == "warning"
        assert d["alert_type"] == "tool_failure"


class TestSafeModePolicy:
    """测试 SafeModePolicy."""

    def test_default_policy(self):
        policy = DEFAULT_SAFE_MODE_POLICY
        assert "analyze" in policy.allowed_actions
        assert "create_campaign" in policy.blocked_actions
        assert policy.require_manual_approval

    def test_is_action_allowed(self):
        policy = SafeModePolicy()
        assert policy.is_action_allowed("analyze")
        assert not policy.is_action_allowed("create_campaign")

    def test_is_action_blocked(self):
        policy = SafeModePolicy()
        assert policy.is_action_blocked("create_campaign")
        assert not policy.is_action_blocked("analyze")


# ═══════════════════════════════════════════════════════════════
# Test Health Metrics Collectors
# ═══════════════════════════════════════════════════════════════


class TestRuntimeMetricsCollector:
    """测试 RuntimeMetricsCollector."""

    def test_initial_state(self):
        c = RuntimeMetricsCollector()
        health = c.collect()
        assert health.cycle_count == 0
        assert health.cycle_duration_avg == 0.0

    def test_record_cycle(self):
        c = RuntimeMetricsCollector()
        c.record_cycle_start()
        c.record_cycle_complete(5.0)
        c.record_cycle_complete(10.0)
        health = c.collect()
        assert health.cycle_count == 2
        assert health.cycle_duration_avg == 7.5

    def test_record_failed_cycle(self):
        c = RuntimeMetricsCollector()
        c.record_cycle_failed()
        c.record_cycle_failed()
        health = c.collect()
        assert health.failed_cycles == 2

    def test_heartbeat(self):
        c = RuntimeMetricsCollector()
        c.record_cycle_complete(5.0)
        health = c.collect()
        assert health.last_heartbeat != ""

    def test_reset(self):
        c = RuntimeMetricsCollector()
        c.record_cycle_complete(5.0)
        c.reset()
        health = c.collect()
        assert health.cycle_count == 0


class TestDecisionMetricsCollector:
    """测试 DecisionMetricsCollector."""

    def test_initial_state(self):
        c = DecisionMetricsCollector()
        health = c.collect()
        assert health.decision_count == 0
        assert health.average_confidence == 0.0

    def test_record_decisions(self):
        c = DecisionMetricsCollector()
        c.record_decision(0.9, 100)
        c.record_decision(0.7, 200)
        health = c.collect()
        assert health.decision_count == 2
        assert health.average_confidence == 0.8
        assert health.decision_latency_avg == 150.0

    def test_low_confidence_rate(self):
        c = DecisionMetricsCollector(low_confidence_threshold=0.7)
        c.record_decision(0.6)  # low
        c.record_decision(0.9)  # high
        c.record_decision(0.5)  # low
        health = c.collect()
        assert health.low_confidence_rate == 2 / 3


class TestExecutionMetricsCollector:
    """测试 ExecutionMetricsCollector."""

    def test_initial_state(self):
        c = ExecutionMetricsCollector()
        health = c.collect()
        assert health.execution_success_rate == 1.0  # 无执行时默认健康

    def test_record_success_failure(self):
        c = ExecutionMetricsCollector()
        c.record_success()
        c.record_success()
        c.record_failure()
        health = c.collect()
        assert health.execution_success_rate == 2 / 3
        assert health.failure_rate == 1 / 3
        assert health.total_executions == 3

    def test_consecutive_errors(self):
        c = ExecutionMetricsCollector()
        c.record_failure()
        c.record_failure()
        c.record_failure()
        health = c.collect()
        assert health.consecutive_errors == 3
        c.record_success()
        health = c.collect()
        assert health.consecutive_errors == 0

    def test_rollback(self):
        c = ExecutionMetricsCollector()
        c.record_rollback()
        health = c.collect()
        # rollback 单独记录不计入 total_executions，所以 rollback_rate = 1/1 = 1.0
        assert health.rollback_rate == 1.0


class TestToolMetricsCollector:
    """测试 ToolMetricsCollector."""

    def test_initial_state(self):
        c = ToolMetricsCollector()
        health = c.collect()
        assert health.api_success_rate == 1.0

    def test_record_api_calls(self):
        c = ToolMetricsCollector()
        c.record_api_call(True, 100)
        c.record_api_call(False, 200)
        c.record_api_call(True, 300)
        health = c.collect()
        assert health.api_success_rate == 2 / 3
        assert health.total_api_calls == 3
        assert health.avg_latency_ms == 200.0

    def test_record_timeout(self):
        c = ToolMetricsCollector()
        c.record_timeout()
        c.record_timeout()
        health = c.collect()
        assert health.timeout_count == 2

    def test_record_rate_limit(self):
        c = ToolMetricsCollector()
        c.record_rate_limit()
        c.record_rate_limit()
        c.record_rate_limit()
        health = c.collect()
        assert health.rate_limit_count == 3


class TestMetricsCollector:
    """测试 MetricsCollector 聚合器."""

    def test_collect_all(self):
        c = MetricsCollector()
        c.runtime.record_cycle_complete(5.0)
        c.decision.record_decision(0.8)
        c.execution.record_success()
        c.tool.record_api_call(True, 100)

        snapshot = c.collect_all()
        assert snapshot.runtime.cycle_count == 1
        assert snapshot.decision.decision_count == 1
        assert snapshot.execution.total_executions == 1
        assert snapshot.tool.total_api_calls == 1

    def test_reset_all(self):
        c = MetricsCollector()
        c.execution.record_success()
        c.reset_all()
        snapshot = c.collect_all()
        assert snapshot.execution.total_executions == 0


# ═══════════════════════════════════════════════════════════════
# Test Health Rules
# ═══════════════════════════════════════════════════════════════


class TestExecutionFailureRule:
    """测试执行失败率规则."""

    def test_normal_execution_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "execution_failure"][0]
        snapshot = make_snapshot_with_failures(failure_rate=0.1)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_high_failure_rate_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "execution_failure"][0]
        snapshot = make_snapshot_with_failures(failure_rate=0.5)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.SAFE_MODE

    def test_insufficient_sample_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "execution_failure"][0]
        snapshot = HealthSnapshot(
            execution=ExecutionHealth(
                failure_rate=0.5,
                total_executions=5,  # < 10 min_sample
            ),
        )
        result = rule.evaluate(snapshot)
        assert not result.triggered


class TestConsecutiveErrorRule:
    """测试连续错误规则."""

    def test_no_errors_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "consecutive_errors"][0]
        snapshot = make_snapshot_with_failures(consecutive_errors=0)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_many_errors_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "consecutive_errors"][0]
        snapshot = make_snapshot_with_failures(consecutive_errors=6)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.SAFE_MODE


class TestToolFailureRule:
    """测试工具失败规则."""

    def test_healthy_tool_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "tool_failure"][0]
        snapshot = make_snapshot_with_failures(api_success_rate=0.95)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_tool_failure_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "tool_failure"][0]
        snapshot = make_snapshot_with_failures(
            api_success_rate=0.3,
        )
        snapshot.tool.total_api_calls = 50
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.DEGRADED


class TestDecisionDriftRule:
    """测试决策漂移规则."""

    def test_high_confidence_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "decision_drift"][0]
        snapshot = make_snapshot_with_failures(confidence=0.85)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_low_confidence_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "decision_drift"][0]
        snapshot = make_snapshot_with_failures(confidence=0.4)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.WARNING


class TestAPITimeoutRule:
    """测试 API 超时规则."""

    def test_no_timeout_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "api_timeout"][0]
        snapshot = make_snapshot_with_failures(timeout_count=0)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_many_timeouts_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "api_timeout"][0]
        snapshot = make_snapshot_with_failures(timeout_count=15)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.DEGRADED


class TestRateLimitRule:
    """测试限流规则."""

    def test_no_rate_limit_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "rate_limit"][0]
        snapshot = make_snapshot_with_failures(rate_limit_count=0)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_many_rate_limits_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "rate_limit"][0]
        snapshot = make_snapshot_with_failures(rate_limit_count=10)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.WARNING


class TestCycleTimeoutRule:
    """测试循环超时规则."""

    def test_fast_cycle_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "cycle_timeout"][0]
        snapshot = make_healthy_snapshot()
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_slow_cycle_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "cycle_timeout"][0]
        snapshot = HealthSnapshot(
            runtime=RuntimeHealth(cycle_count=10, cycle_duration_avg=400.0),
        )
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.WARNING


class TestLowConfidenceRateRule:
    """测试低置信度比例规则."""

    def test_low_rate_not_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "low_confidence_rate"][0]
        snapshot = make_snapshot_with_failures(low_confidence_rate=0.2)
        result = rule.evaluate(snapshot)
        assert not result.triggered

    def test_high_low_confidence_rate_triggered(self):
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "low_confidence_rate"][0]
        snapshot = make_snapshot_with_failures(low_confidence_rate=0.6)
        result = rule.evaluate(snapshot)
        assert result.triggered
        assert result.status == HealthStatus.DEGRADED


class TestBuildDefaultHealthRules:
    """测试默认规则集构建."""

    def test_all_rules_created(self):
        rules = build_default_health_rules()
        assert len(rules) == 9

    def test_rules_sorted_by_priority(self):
        rules = build_default_health_rules()
        for i in range(len(rules) - 1):
            assert rules[i].priority <= rules[i + 1].priority


# ═══════════════════════════════════════════════════════════════
# Test Health Monitor
# ═══════════════════════════════════════════════════════════════


class TestHealthMonitor:
    """测试 HealthMonitor 核心."""

    def test_create_monitor(self):
        monitor = create_health_monitor()
        assert monitor.status == HealthStatus.HEALTHY
        assert len(monitor.rules) == 9

    def test_healthy_check(self):
        """正常指标 → HEALTHY."""
        monitor = create_health_monitor()
        monitor.collector.runtime.record_cycle_complete(5.0)
        monitor.collector.decision.record_decision(0.85)
        for _ in range(10):
            monitor.collector.execution.record_success()
        for _ in range(10):
            monitor.collector.tool.record_api_call(True, 100)

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.HEALTHY

    def test_execution_failure_safe_mode(self):
        """执行失败率 > 50% → SAFE_MODE."""
        monitor = create_health_monitor()
        for _ in range(50):
            monitor.collector.execution.record_failure()
        for _ in range(50):
            monitor.collector.execution.record_success()

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.SAFE_MODE
        assert evaluation.requires_safe_mode

    def test_consecutive_errors_safe_mode(self):
        """连续错误 > 5 → SAFE_MODE."""
        monitor = create_health_monitor()
        for _ in range(6):
            monitor.collector.execution.record_failure()

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.SAFE_MODE

    def test_api_timeout_degraded(self):
        """API 超时 → DEGRADED."""
        monitor = create_health_monitor()
        for _ in range(15):
            monitor.collector.tool.record_timeout()

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.DEGRADED

    def test_decision_drift_warning(self):
        """决策置信度下降 → WARNING (avg=0.475, 仅触发决策漂移, 低置信度比例不触发)."""
        monitor = create_health_monitor()
        # 5 个高置信度 (≥0.7), 5 个低置信度 (0.1)
        # avg = (5*0.85 + 5*0.10) / 10 = 0.475 < 0.5 → 触发 decision_drift
        # low_confidence_rate = 5/10 = 0.5, 不 > 0.5 → 不触发 low_confidence_rate
        for _ in range(5):
            monitor.collector.decision.record_decision(0.85)
        for _ in range(5):
            monitor.collector.decision.record_decision(0.10)

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.WARNING
        assert "decision_drift" in evaluation.snapshot.triggered_rules

    def test_low_confidence_rate_degraded(self):
        """低置信度比例过高 → DEGRADED."""
        monitor = create_health_monitor()
        for _ in range(6):
            monitor.collector.decision.record_decision(0.3)  # low
        for _ in range(4):
            monitor.collector.decision.record_decision(0.9)  # high

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.DEGRADED

    def test_status_transition(self):
        """状态变更检测."""
        monitor = create_health_monitor()
        # 正常
        for _ in range(10):
            monitor.collector.execution.record_success()
        e1 = monitor.check()
        assert e1.status == HealthStatus.HEALTHY
        assert not e1.status_changed  # 从初始 HEALTHY → HEALTHY

        # 异常
        for _ in range(6):
            monitor.collector.execution.record_failure()
        e2 = monitor.check()
        assert e2.status == HealthStatus.SAFE_MODE
        assert e2.status_changed

    def test_status_changed_callback(self):
        """状态变更回调."""
        changes = []
        monitor = create_health_monitor()
        monitor.on_status_changed(lambda old, new, ev: changes.append((old, new)))

        for _ in range(6):
            monitor.collector.execution.record_failure()
        monitor.check()

        assert len(changes) == 1
        assert changes[0][0] == HealthStatus.HEALTHY
        assert changes[0][1] == HealthStatus.SAFE_MODE

    def test_is_safe_mode(self):
        monitor = create_health_monitor()
        monitor._current_status = HealthStatus.SAFE_MODE
        assert monitor.is_safe_mode
        assert not monitor.is_healthy

    def test_is_degraded(self):
        monitor = create_health_monitor()
        monitor._current_status = HealthStatus.DEGRADED
        assert monitor.is_degraded

    def test_safe_mode_action_check(self):
        """安全模式下动作检查."""
        monitor = create_health_monitor()
        monitor._current_status = HealthStatus.SAFE_MODE
        assert monitor.is_action_allowed_in_safe_mode("analyze")
        assert not monitor.is_action_allowed_in_safe_mode("create_campaign")
        assert monitor.is_action_blocked_in_safe_mode("create_campaign")
        assert not monitor.is_action_blocked_in_safe_mode("analyze")

    def test_normal_mode_all_actions_allowed(self):
        """正常模式下所有动作允许."""
        monitor = create_health_monitor()
        assert monitor.is_action_allowed_in_safe_mode("create_campaign")
        assert not monitor.is_action_blocked_in_safe_mode("create_campaign")

    def test_add_remove_rule(self):
        monitor = create_health_monitor()
        initial = len(monitor.rules)
        rule = HealthRule(name="test", condition=lambda s: False)
        monitor.add_rule(rule)
        assert len(monitor.rules) == initial + 1
        assert monitor.remove_rule(rule.rule_id)
        assert len(monitor.rules) == initial

    def test_enable_disable_rule(self):
        monitor = create_health_monitor()
        first_rule = monitor.rules[0]
        assert monitor.disable_rule(first_rule.rule_id)
        assert not first_rule.enabled
        assert monitor.enable_rule(first_rule.rule_id)
        assert first_rule.enabled

    def test_get_history(self):
        monitor = create_health_monitor()
        for _ in range(5):
            monitor.collector.execution.record_success()
            monitor.check()
        assert len(monitor.get_history()) == 5
        assert len(monitor.get_history(3)) == 3

    def test_get_latest(self):
        monitor = create_health_monitor()
        monitor.collector.execution.record_success()
        monitor.check()
        latest = monitor.get_latest()
        assert latest is not None
        assert latest.status == HealthStatus.HEALTHY

    def test_get_status_timeline(self):
        monitor = create_health_monitor()
        monitor.collector.execution.record_success()
        monitor.check()
        for _ in range(6):
            monitor.collector.execution.record_failure()
        monitor.check()
        timeline = monitor.get_status_timeline()
        assert len(timeline) >= 1

    def test_get_summary(self):
        monitor = create_health_monitor()
        summary = monitor.get_summary()
        assert "current_status" in summary
        assert "rules_count" in summary
        assert summary["rules_count"] == 9

    def test_reset(self):
        monitor = create_health_monitor()
        monitor.collector.execution.record_success()
        monitor.check()
        monitor.reset()
        assert monitor.status == HealthStatus.HEALTHY
        assert len(monitor.history) == 0

    def test_rate_limit_warning(self):
        """限流频繁 → WARNING."""
        monitor = create_health_monitor()
        for _ in range(10):
            monitor.collector.tool.record_rate_limit()

        # 添加足够的决策和执行数据
        for _ in range(10):
            monitor.collector.decision.record_decision(0.85)
        for _ in range(10):
            monitor.collector.execution.record_success()

        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.WARNING
        assert "rate_limit" in evaluation.snapshot.triggered_rules


# ═══════════════════════════════════════════════════════════════
# Test Alert Manager
# ═══════════════════════════════════════════════════════════════


class TestAlertManager:
    """测试 AlertManager."""

    def test_create_alert(self):
        manager = create_alert_manager()
        alert = manager.create_alert(
            level=AlertLevel.CRITICAL,
            alert_type=AlertType.EXECUTION_FAILURE,
            message="test alert",
        )
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL
        assert not alert.is_resolved

    def test_alert_dedup(self):
        """同类型告警去重."""
        manager = create_alert_manager()
        a1 = manager.create_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.TOOL_FAILURE,
            message="alert 1",
        )
        a2 = manager.create_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.TOOL_FAILURE,
            message="alert 2",
        )
        assert a1 is not None
        assert a2 is None  # 去重过滤

    def test_create_from_evaluation(self):
        manager = create_alert_manager()
        monitor = create_health_monitor()
        for _ in range(6):
            monitor.collector.execution.record_failure()
        evaluation = monitor.check()

        alert = manager.create_from_evaluation(evaluation)
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL

    def test_create_from_evaluation_no_alert(self):
        manager = create_alert_manager()
        monitor = create_health_monitor()
        for _ in range(10):
            monitor.collector.execution.record_success()
        evaluation = monitor.check()

        alert = manager.create_from_evaluation(evaluation)
        assert alert is None

    def test_resolve_alert(self):
        manager = create_alert_manager()
        alert = manager.create_alert(
            level=AlertLevel.WARNING,
            alert_type=AlertType.TOOL_FAILURE,
            message="test",
        )
        assert alert is not None
        assert manager.resolve(alert.alert_id, "fixed")
        assert not manager.unresolved_count

    def test_resolve_all(self):
        manager = create_alert_manager()
        for t in [AlertType.TOOL_FAILURE, AlertType.API_TIMEOUT, AlertType.RATE_LIMIT]:
            manager.create_alert(level=AlertLevel.WARNING, alert_type=t, message="test")
        assert manager.resolve_all() == 3

    def test_resolve_by_type(self):
        manager = create_alert_manager()
        manager.create_alert(level=AlertLevel.WARNING, alert_type=AlertType.TOOL_FAILURE, message="test")
        manager.create_alert(level=AlertLevel.WARNING, alert_type=AlertType.API_TIMEOUT, message="test")
        assert manager.resolve_by_type(AlertType.TOOL_FAILURE) == 1

    def test_get_active(self):
        manager = create_alert_manager()
        manager.create_alert(level=AlertLevel.WARNING, alert_type=AlertType.TOOL_FAILURE, message="test")
        active = manager.get_active()
        assert len(active) == 1

    def test_get_by_type(self):
        manager = create_alert_manager()
        manager.create_alert(level=AlertLevel.WARNING, alert_type=AlertType.TOOL_FAILURE, message="test")
        alerts = manager.get_by_type(AlertType.TOOL_FAILURE)
        assert len(alerts) == 1

    def test_get_critical(self):
        manager = create_alert_manager()
        manager.create_alert(level=AlertLevel.CRITICAL, alert_type=AlertType.EXECUTION_FAILURE, message="test")
        manager.create_alert(level=AlertLevel.WARNING, alert_type=AlertType.TOOL_FAILURE, message="test")
        critical = manager.get_critical()
        assert len(critical) == 1

    def test_get_stats(self):
        manager = create_alert_manager()
        manager.create_alert(level=AlertLevel.CRITICAL, alert_type=AlertType.EXECUTION_FAILURE, message="test")
        stats = manager.get_stats()
        assert stats["active_count"] == 1
        assert stats["unresolved_count"] == 1

    def test_resolve_non_existent(self):
        manager = create_alert_manager()
        assert not manager.resolve("non_existent_id")

    def test_get_history(self):
        manager = create_alert_manager()
        for i in range(3):
            alert = manager.create_alert(
                level=AlertLevel.WARNING,
                alert_type=AlertType.TOOL_FAILURE,
                message=f"test {i}",
            )
            manager.resolve(alert.alert_id)
        history = manager.get_history()
        assert len(history) == 3

    def test_reset(self):
        manager = create_alert_manager()
        manager.create_alert(level=AlertLevel.WARNING, alert_type=AlertType.TOOL_FAILURE, message="test")
        manager.reset()
        assert manager.active_count == 0
        assert manager.unresolved_count == 0


# ═══════════════════════════════════════════════════════════════
# Test Health Policy
# ═══════════════════════════════════════════════════════════════


class TestHealthPolicy:
    """测试 HealthPolicy."""

    def test_default_policy(self):
        policy = create_health_policy()
        assert not policy.auto_recovery_enabled

    def test_get_allowed_actions_healthy(self):
        policy = create_health_policy()
        actions = policy.get_allowed_actions(HealthStatus.HEALTHY)
        assert "create_campaign" in actions
        assert "analyze" in actions

    def test_get_allowed_actions_safe_mode(self):
        policy = create_health_policy()
        actions = policy.get_allowed_actions(HealthStatus.SAFE_MODE)
        assert "analyze" in actions
        assert "create_campaign" not in actions

    def test_get_allowed_actions_failed(self):
        policy = create_health_policy()
        actions = policy.get_allowed_actions(HealthStatus.FAILED)
        assert actions == []

    def test_get_blocked_actions_healthy(self):
        policy = create_health_policy()
        blocked = policy.get_blocked_actions(HealthStatus.HEALTHY)
        assert blocked == []

    def test_get_blocked_actions_safe_mode(self):
        policy = create_health_policy()
        blocked = policy.get_blocked_actions(HealthStatus.SAFE_MODE)
        assert "create_campaign" in blocked
        assert "analyze" not in blocked

    def test_is_action_allowed(self):
        policy = create_health_policy()
        assert policy.is_action_allowed(HealthStatus.HEALTHY, "create_campaign")
        assert not policy.is_action_allowed(HealthStatus.SAFE_MODE, "create_campaign")
        assert policy.is_action_allowed(HealthStatus.SAFE_MODE, "analyze")

    def test_can_auto_recover_disabled(self):
        policy = create_health_policy()
        assert not policy.can_auto_recover(HealthStatus.DEGRADED, 3, False)

    def test_can_auto_recover(self):
        policy = HealthPolicy(auto_recovery_enabled=True)
        assert policy.can_auto_recover(HealthStatus.DEGRADED, 3, False)
        assert not policy.can_auto_recover(HealthStatus.DEGRADED, 2, False)
        assert not policy.can_auto_recover(HealthStatus.DEGRADED, 3, True)

    def test_to_dict(self):
        policy = create_health_policy()
        d = policy.to_dict()
        assert "safe_mode_policy" in d
        assert "auto_recovery_enabled" in d


# ═══════════════════════════════════════════════════════════════
# Test Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """测试 Runtime 集成: 指标采集 → 健康检查 → 安全模式."""

    def test_full_healthy_cycle(self):
        """完整健康循环: 指标采集 → 检查 → 正常."""
        monitor = create_health_monitor()
        alert_manager = create_alert_manager()

        # 模拟正常 Agent 运行
        for _ in range(10):
            monitor.collector.runtime.record_cycle_complete(5.0)
            monitor.collector.decision.record_decision(0.85)
            monitor.collector.execution.record_success()
            monitor.collector.tool.record_api_call(True, 100)

        eval_result = monitor.check()
        assert eval_result.status == HealthStatus.HEALTHY
        assert not eval_result.requires_safe_mode
        assert not eval_result.requires_alert

    def test_full_degraded_cycle(self):
        """完整降级循环: 工具异常 → DEGRADED → 告警."""
        monitor = create_health_monitor()
        alert_manager = create_alert_manager()

        # 模拟运行 + 工具异常
        for _ in range(10):
            monitor.collector.runtime.record_cycle_complete(5.0)
            monitor.collector.decision.record_decision(0.85)
            monitor.collector.execution.record_success()

        for _ in range(15):
            monitor.collector.tool.record_timeout()

        eval_result = monitor.check()
        assert eval_result.status == HealthStatus.DEGRADED
        assert eval_result.requires_alert

        alert = alert_manager.create_from_evaluation(eval_result)
        assert alert is not None
        assert alert.level == AlertLevel.WARNING

    def test_full_safe_mode_cycle(self):
        """完整安全模式循环: 连续错误 → SAFE_MODE → 限制动作."""
        monitor = create_health_monitor()
        policy = create_health_policy()

        # 模拟运行 + 连续错误
        for _ in range(10):
            monitor.collector.runtime.record_cycle_complete(5.0)

        for _ in range(6):
            monitor.collector.execution.record_failure()

        eval_result = monitor.check()
        assert eval_result.status == HealthStatus.SAFE_MODE
        assert eval_result.requires_safe_mode

        # 验证安全模式行为限制
        assert not policy.is_action_allowed(HealthStatus.SAFE_MODE, "create_campaign")
        assert not policy.is_action_allowed(HealthStatus.SAFE_MODE, "update_budget")
        assert policy.is_action_allowed(HealthStatus.SAFE_MODE, "analyze")
        assert policy.is_action_allowed(HealthStatus.SAFE_MODE, "generate_report")

    def test_status_transition_healthy_to_safe_mode(self):
        """状态切换: HEALTHY → SAFE_MODE."""
        monitor = create_health_monitor()

        # 初始健康
        for _ in range(10):
            monitor.collector.execution.record_success()
        e1 = monitor.check()
        assert e1.status == HealthStatus.HEALTHY

        # 连续错误
        for _ in range(6):
            monitor.collector.execution.record_failure()
        e2 = monitor.check()
        assert e2.status == HealthStatus.SAFE_MODE
        assert e2.previous_status == HealthStatus.HEALTHY
        assert e2.status_changed

    def test_alert_manager_integration(self):
        """告警管理器集成: 健康检查 → 创建告警 → 解决."""
        monitor = create_health_monitor()
        alert_manager = create_alert_manager()

        for _ in range(6):
            monitor.collector.execution.record_failure()
        eval_result = monitor.check()

        alert = alert_manager.create_from_evaluation(eval_result)
        assert alert is not None
        assert alert_manager.unresolved_count == 1

        # 恢复后解决告警
        assert alert_manager.resolve_all("recovered")
        assert alert_manager.unresolved_count == 0

    def test_metrics_collector_full_pipeline(self):
        """指标采集器完整 Pipeline."""
        collector = MetricsCollector()

        # Runtime
        collector.runtime.record_cycle_start()
        collector.runtime.record_cycle_complete(5.0)

        # Decision
        collector.decision.record_decision(0.85, 50)
        collector.decision.record_decision(0.45, 100)

        # Execution
        collector.execution.record_success()
        collector.execution.record_success()
        collector.execution.record_failure()

        # Tool
        collector.tool.record_api_call(True, 100)
        collector.tool.record_api_call(True, 200)
        collector.tool.record_api_call(False, 300)

        snapshot = collector.collect_all()
        assert snapshot.runtime.cycle_count == 1
        assert snapshot.decision.decision_count == 2
        assert snapshot.execution.total_executions == 3
        assert snapshot.execution.execution_success_rate == 2 / 3
        assert snapshot.tool.total_api_calls == 3
        assert snapshot.tool.api_success_rate == 2 / 3


# ═══════════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """测试边界情况."""

    def test_empty_monitor_healthy(self):
        """空监控器 (无指标) → HEALTHY."""
        monitor = create_health_monitor()
        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.HEALTHY

    def test_extreme_failure_rate(self):
        """100% 失败率 → SAFE_MODE."""
        monitor = create_health_monitor()
        for _ in range(100):
            monitor.collector.execution.record_failure()
        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.SAFE_MODE

    def test_zero_confidence(self):
        """置信度为 0 触发决策漂移 + 低置信度比例 → DEGRADED."""
        monitor = create_health_monitor()
        for _ in range(10):
            monitor.collector.decision.record_decision(0.0)
        evaluation = monitor.check()
        assert evaluation.status == HealthStatus.DEGRADED

    def test_manager_alert_overflow(self):
        """告警容量管理."""
        manager = AlertManager(max_active=3)
        for t in [AlertType.TOOL_FAILURE, AlertType.API_TIMEOUT, AlertType.RATE_LIMIT, AlertType.EXECUTION_FAILURE]:
            manager.create_alert(level=AlertLevel.WARNING, alert_type=t, message="test")
        assert manager.active_count == 3  # 第4个挤掉第1个

    def test_monitor_status_change_callback_multiple(self):
        """多次状态变更."""
        changes = []
        monitor = create_health_monitor()
        monitor.on_status_changed(lambda old, new, ev: changes.append((old, new)))

        # 正常 → SAFE_MODE
        for _ in range(6):
            monitor.collector.execution.record_failure()
        monitor.check()
        assert len(changes) == 1
        assert changes[0][1] == HealthStatus.SAFE_MODE

    def test_heartbeat_rule(self):
        """心跳丢失规则."""
        rules = build_default_health_rules()
        rule = [r for r in rules if r.name == "heartbeat_lost"][0]
        # 没有心跳数据 → 不触发
        snapshot = HealthSnapshot(runtime=RuntimeHealth())
        result = rule.evaluate(snapshot)
        assert not result.triggered