"""E15.0.11 Alerts 测试 — 告警引擎测试.

测试覆盖:
  - AlertRule 创建与评估
  - AlertSeverity / AlertState 枚举
  - AlertEngine 规则触发/恢复
  - 派生指标 (rate) 支持
  - 告警通知回调
  - 告警确认/手动恢复
  - 预设规则集
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.observability.alerts import (
    Alert,
    AlertEngine,
    AlertRule,
    AlertSeverity,
    AlertState,
    default_alert_rules,
)
from market_ops.creative_vision_runtime.growth_runtime.observability.metrics import (
    MetricsCollector,
)


class TestAlertSeverity:
    def test_values(self):
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.INFO.value == "info"


class TestAlertState:
    def test_values(self):
        assert AlertState.PENDING.value == "pending"
        assert AlertState.ACTIVE.value == "active"
        assert AlertState.RESOLVED.value == "resolved"


class TestAlertRule:
    """AlertRule 单元测试."""

    def test_create_rule(self):
        rule = AlertRule(
            name="high_failure_rate",
            metric="execution_failed_rate",
            threshold=0.1,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        )
        assert rule.name == "high_failure_rate"
        assert rule.metric == "execution_failed_rate"
        assert rule.threshold == 0.1
        assert rule.operator == ">"
        assert rule.severity == AlertSeverity.CRITICAL

    def test_default_values(self):
        rule = AlertRule(name="test", metric="test_metric")
        assert rule.threshold == 0.0
        assert rule.operator == ">"
        assert rule.severity == AlertSeverity.WARNING
        assert rule.labels is None

    def test_evaluate_greater_than(self):
        rule = AlertRule(name="test", metric="m", threshold=0.1, operator=">")
        assert rule.evaluate(0.2) is True
        assert rule.evaluate(0.1) is False  # strict >
        assert rule.evaluate(0.05) is False

    def test_evaluate_less_than(self):
        rule = AlertRule(name="test", metric="m", threshold=0.1, operator="<")
        assert rule.evaluate(0.05) is True
        assert rule.evaluate(0.1) is False
        assert rule.evaluate(0.2) is False

    def test_evaluate_greater_equal(self):
        rule = AlertRule(name="test", metric="m", threshold=0.1, operator=">=")
        assert rule.evaluate(0.2) is True
        assert rule.evaluate(0.1) is True

    def test_evaluate_less_equal(self):
        rule = AlertRule(name="test", metric="m", threshold=0.1, operator="<=")
        assert rule.evaluate(0.05) is True
        assert rule.evaluate(0.1) is True

    def test_evaluate_equal(self):
        rule = AlertRule(name="test", metric="m", threshold=0.1, operator="==")
        assert rule.evaluate(0.1) is True
        assert rule.evaluate(0.2) is False

    def test_invalid_operator(self):
        with pytest.raises(ValueError, match="Invalid operator"):
            AlertRule(name="test", metric="m", operator="!=")

    def test_to_dict(self):
        rule = AlertRule(
            name="test",
            metric="m",
            threshold=0.5,
            severity=AlertSeverity.CRITICAL,
        )
        d = rule.to_dict()
        assert d["name"] == "test"
        assert d["metric"] == "m"
        assert d["threshold"] == 0.5
        assert d["severity"] == "critical"


class TestAlert:
    """Alert 单元测试."""

    def test_create_alert(self):
        rule = AlertRule(name="test", metric="m")
        alert = Alert(rule=rule, value=0.5)
        assert alert.rule is rule
        assert alert.value == 0.5
        assert alert.state == AlertState.PENDING
        assert alert.alert_id != ""

    def test_is_active(self):
        alert = Alert(rule=AlertRule(name="test", metric="m"))
        assert alert.is_active is True
        alert.state = AlertState.ACTIVE
        assert alert.is_active is True
        alert.resolve()
        assert alert.is_active is False

    def test_resolve(self):
        alert = Alert(rule=AlertRule(name="test", metric="m"))
        alert.resolve()
        assert alert.state == AlertState.RESOLVED
        assert alert.resolved_at != ""

    def test_to_dict(self):
        rule = AlertRule(name="test", metric="m")
        alert = Alert(rule=rule, value=0.5, state=AlertState.ACTIVE)
        d = alert.to_dict()
        assert d["rule"]["name"] == "test"
        assert d["value"] == 0.5
        assert d["state"] == "active"


class TestAlertEngine:
    """AlertEngine 单元测试."""

    def setup_method(self):
        self.collector = MetricsCollector()
        self.engine = AlertEngine(collector=self.collector)

    # ── Rule Management ──────────────────────────────────────

    def test_add_rule(self):
        self.engine.add_rule(AlertRule(name="test", metric="m"))
        assert len(self.engine.get_rules()) == 1

    def test_remove_rule(self):
        self.engine.add_rule(AlertRule(name="test", metric="m"))
        assert self.engine.remove_rule("test") is True
        assert self.engine.remove_rule("nonexistent") is False

    def test_get_rules(self):
        self.engine.add_rule(AlertRule(name="r1", metric="m1"))
        self.engine.add_rule(AlertRule(name="r2", metric="m2"))
        assert len(self.engine.get_rules()) == 2

    # ── Trigger Alert ────────────────────────────────────────

    def test_trigger_on_threshold(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )
        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)

        new = self.engine.check()
        assert len(new) == 1
        assert new[0].rule.name == "high_failure"

    def test_no_trigger_below_threshold(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )
        self.collector.increment("execution_failed", 5)
        self.collector.increment("execution_total", 100)

        new = self.engine.check()
        assert len(new) == 0

    def test_no_duplicate_trigger(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )
        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)

        self.engine.check()
        new = self.engine.check()
        assert len(new) == 0  # 不重复触发

    def test_alert_resolves_when_below_threshold(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )

        # 触发
        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)
        self.engine.check()
        assert len(self.engine.get_active_alerts()) == 1

        # 恢复：需要重置 collector 再设置低于阈值的值
        self.collector.reset()
        self.collector.increment("execution_failed", 5)
        self.collector.increment("execution_total", 100)
        self.engine.check()
        assert len(self.engine.get_active_alerts()) == 0

    def test_counter_metric(self):
        self.engine.add_rule(
            AlertRule(name="too_many", metric="execution_total", threshold=100, operator=">")
        )
        self.collector.increment("execution_total", 150)
        new = self.engine.check()
        assert len(new) == 1

    def test_gauge_metric(self):
        self.engine.add_rule(
            AlertRule(name="queue_full", metric="pending_approval_count", threshold=50, operator=">")
        )
        self.collector.set_gauge("pending_approval_count", 100)
        new = self.engine.check()
        assert len(new) == 1

    def test_equal_operator(self):
        self.engine.add_rule(
            AlertRule(name="zero_activity", metric="execution_total", threshold=0, operator="==")
        )
        # collector 初始值为 0
        new = self.engine.check()
        assert len(new) == 1
        assert new[0].rule.name == "zero_activity"

    # ── Notifier ─────────────────────────────────────────────

    def test_notifier_called(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )
        notified: list[Alert] = []
        self.engine.register_notifier(notified.append)

        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)
        self.engine.check()
        assert len(notified) == 1

    def test_notifier_exception_does_not_break_check(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )

        def bad_notifier(a):
            raise RuntimeError("oops")

        self.engine.register_notifier(bad_notifier)
        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)
        new = self.engine.check()
        assert len(new) == 1

    # ── Query ────────────────────────────────────────────────

    def test_get_active_alerts(self):
        self.engine.add_rule(
            AlertRule(name="high_failure", metric="execution_failed_rate", threshold=0.1, operator=">")
        )
        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)
        self.engine.check()
        assert len(self.engine.get_active_alerts()) == 1

    def test_get_alerts_by_severity(self):
        self.engine.add_rule(
            AlertRule(name="critical_rule", metric="m1", threshold=0.1, severity=AlertSeverity.CRITICAL)
        )
        self.engine.add_rule(
            AlertRule(name="warning_rule", metric="m2", threshold=0.1, severity=AlertSeverity.WARNING)
        )
        self.collector.increment("m1", 1)
        self.collector.increment("m2", 1)
        self.engine.check()

        critical = self.engine.get_alerts_by_severity(AlertSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].rule.name == "critical_rule"

    def test_get_alert_history(self):
        self.engine.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">")
        )
        self.collector.increment("m1", 1)
        self.engine.check()

        # 恢复
        self.collector.reset()
        self.collector.increment("m1", 0)
        self.engine.check()

        history = self.engine.get_alert_history()
        assert len(history) == 1

    # ── Acknowledge / Resolve ────────────────────────────────

    def test_acknowledge(self):
        self.engine.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">")
        )
        self.collector.increment("m1", 1)
        new = self.engine.check()
        alert_id = new[0].alert_id

        # 默认状态是 ACTIVE（因为 check 直接触发）
        # 如果改为 PENDING → 验证 acknowledge
        new[0].state = AlertState.PENDING
        assert self.engine.acknowledge(alert_id) is True
        assert new[0].state == AlertState.ACTIVE

    def test_acknowledge_nonexistent(self):
        assert self.engine.acknowledge("nonexistent") is False

    def test_manual_resolve(self):
        self.engine.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">")
        )
        self.collector.increment("m1", 1)
        new = self.engine.check()
        alert_id = new[0].alert_id

        assert self.engine.resolve(alert_id) is True
        assert len(self.engine.get_active_alerts()) == 0

    def test_manual_resolve_nonexistent(self):
        assert self.engine.resolve("nonexistent") is False

    # ── Stats ────────────────────────────────────────────────

    def test_stats(self):
        self.engine.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">")
        )
        self.collector.increment("m1", 1)
        self.engine.check()

        stats = self.engine.stats()
        assert stats["total_rules"] == 1
        assert stats["total_alerts"] == 1
        assert stats["active_alerts"] == 1

    def test_stats_initial(self):
        stats = self.engine.stats()
        assert stats["total_rules"] == 0
        assert stats["total_alerts"] == 0
        assert stats["active_alerts"] == 0

    # ── Clear ────────────────────────────────────────────────

    def test_clear(self):
        self.engine.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">")
        )
        self.collector.increment("m1", 1)
        self.engine.check()
        self.engine.clear()
        assert self.engine.stats()["total_alerts"] == 0

    # ── check_metric ─────────────────────────────────────────

    def test_check_metric_only(self):
        self.engine.add_rule(AlertRule(name="r1", metric="m1", threshold=0, operator=">"))
        self.engine.add_rule(AlertRule(name="r2", metric="m2", threshold=0, operator=">"))
        self.collector.increment("m1", 1)
        self.collector.increment("m2", 1)

        new = self.engine.check_metric("m1")
        assert len(new) == 1
        assert new[0].rule.name == "r1"

    # ── Default Rules ────────────────────────────────────────

    def test_default_alert_rules(self):
        rules = default_alert_rules()
        assert len(rules) == 6
        names = {r.name for r in rules}
        assert "Execution Failure Spike" in names
        assert "Approval Queue Overflow" in names
        assert "Adapter Error Rate" in names
        assert "High Execution Latency" in names
        assert "Zero Execution Activity" in names
        assert "High Rollback Rate" in names

    def test_default_rules_in_engine(self):
        engine = AlertEngine(collector=self.collector, rules=default_alert_rules())
        assert len(engine.get_rules()) == 6

    # ── Rate Derivation ──────────────────────────────────────

    def test_rate_derivation(self):
        """验证 _rate 后缀自动派生指标."""
        self.engine.add_rule(
            AlertRule(name="test", metric="execution_failed_rate", threshold=0.1, operator=">")
        )
        self.collector.increment("execution_failed", 15)
        self.collector.increment("execution_total", 100)
        new = self.engine.check()
        assert len(new) == 1

    def test_rate_derivation_zero_total(self):
        """当 total 为 0 时，rate 应为 0."""
        self.engine.add_rule(
            AlertRule(name="test", metric="execution_failed_rate", threshold=0.0, operator="==")
        )
        # 不增加任何 counter
        new = self.engine.check()
        assert len(new) == 1
        assert new[0].value == 0.0

    def test_rate_derivation_with_labels(self):
        self.engine.add_rule(
            AlertRule(
                name="adapter_error",
                metric="adapter_error_rate",
                threshold=0.05,
                operator=">",
                labels={"adapter": "meta"},
            )
        )
        self.collector.increment("adapter_error", 10, labels={"adapter": "meta"})
        self.collector.increment("adapter_total", 100, labels={"adapter": "meta"})
        new = self.engine.check()
        assert len(new) == 1

    def test_alert_check_count_increment(self):
        self.engine.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">")
        )
        self.collector.increment("m1", 1)
        new = self.engine.check()
        assert new[0].check_count == 1
        self.engine.check()
        assert new[0].check_count == 2