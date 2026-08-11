"""E15.0.5 Growth Monitoring — 测试套件.

覆盖:
  - GrowthMetrics: 创建, 属性计算, to_dict
  - MetricsCollector: 记录, 快照, 查询, 重置
  - Alert: 创建, to_dict, acknowledged
  - AlertSeverity: 枚举值
  - AlertRule: 创建, evaluate, 冷却
  - AlertManager: 规则管理, 告警评估, 查询, 确认, 统计
  - Built-in Rules: roas_drop, connector_failure, execution_anomaly, budget_anomaly
  - 边界情况: 空采集器, 无历史指标, 空管理器, 禁用规则, 冷却防重触发
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.monitoring import (
    GrowthMetrics,
    MetricsCollector,
    Alert,
    AlertRule,
    AlertSeverity,
    AlertManager,
)
from market_ops.creative_vision_runtime.growth_runtime.monitoring.alerts import (
    roas_drop_rule,
    connector_failure_rule,
    execution_anomaly_rule,
    budget_anomaly_rule,
    create_default_alert_rules,
)


# ═══════════════════════════════════════════════════════════════
# GrowthMetrics
# ═══════════════════════════════════════════════════════════════

class TestGrowthMetricsCreation:
    """GrowthMetrics 创建测试."""

    def test_creation_defaults(self):
        m = GrowthMetrics()
        assert m.game_id == ""
        assert m.decision_count == 0
        assert m.success_rate == 0.0
        assert m.failure_rate == 0.0
        assert m.action_success == 0
        assert m.action_failed == 0
        assert m.rollback_count == 0
        assert m.approval_waiting == 0
        assert m.spend == 0.0
        assert m.revenue == 0.0
        assert m.roas == 0.0
        assert m.ltv == 0.0
        assert m.installs == 0
        assert m.purchases == 0
        assert m.impressions == 0
        assert m.clicks == 0

    def test_creation_with_values(self):
        m = GrowthMetrics(
            game_id="game_001",
            decision_count=10,
            success_rate=0.8,
            failure_rate=0.2,
            action_success=5,
            action_failed=2,
            rollback_count=1,
            approval_waiting=3,
            spend=100.0,
            revenue=200.0,
            roas=2.0,
            ltv=50.0,
            installs=100,
            purchases=20,
            impressions=1000,
            clicks=50,
        )
        assert m.game_id == "game_001"
        assert m.decision_count == 10
        assert m.success_rate == 0.8
        assert m.failure_rate == 0.2
        assert m.action_success == 5
        assert m.action_failed == 2
        assert m.rollback_count == 1
        assert m.approval_waiting == 3
        assert m.spend == 100.0
        assert m.revenue == 200.0
        assert m.roas == 2.0
        assert m.ltv == 50.0
        assert m.installs == 100
        assert m.purchases == 20
        assert m.impressions == 1000
        assert m.clicks == 50

    def test_timestamp_is_set(self):
        m = GrowthMetrics()
        assert m.timestamp is not None
        assert len(m.timestamp) > 0


class TestGrowthMetricsProperties:
    """GrowthMetrics 计算属性测试."""

    def test_action_total_with_both(self):
        m = GrowthMetrics(action_success=5, action_failed=3)
        assert m.action_total == 8

    def test_action_total_zero(self):
        m = GrowthMetrics(action_success=0, action_failed=0)
        assert m.action_total == 0

    def test_action_total_only_success(self):
        m = GrowthMetrics(action_success=4, action_failed=0)
        assert m.action_total == 4

    def test_action_total_only_failed(self):
        m = GrowthMetrics(action_success=0, action_failed=5)
        assert m.action_total == 5

    def test_action_success_rate_normal(self):
        m = GrowthMetrics(action_success=7, action_failed=3)
        assert m.action_success_rate == 0.7

    def test_action_success_rate_all_success(self):
        m = GrowthMetrics(action_success=5, action_failed=0)
        assert m.action_success_rate == 1.0

    def test_action_success_rate_all_failed(self):
        m = GrowthMetrics(action_success=0, action_failed=5)
        assert m.action_success_rate == 0.0

    def test_action_success_rate_zero_total(self):
        m = GrowthMetrics(action_success=0, action_failed=0)
        assert m.action_success_rate == 1.0

    def test_ctr_normal(self):
        m = GrowthMetrics(impressions=1000, clicks=50)
        assert m.ctr == 0.05

    def test_ctr_zero_impressions(self):
        m = GrowthMetrics(impressions=0, clicks=50)
        assert m.ctr == 0.0

    def test_ctr_zero_clicks(self):
        m = GrowthMetrics(impressions=100, clicks=0)
        assert m.ctr == 0.0

    def test_cpa_normal(self):
        m = GrowthMetrics(spend=100.0, action_success=5, action_failed=5)
        assert m.cpa == 10.0

    def test_cpa_zero_actions(self):
        m = GrowthMetrics(spend=100.0, action_success=0, action_failed=0)
        assert m.cpa == 0.0


class TestGrowthMetricsToDict:
    """GrowthMetrics to_dict 测试."""

    def test_to_dict_structure(self):
        m = GrowthMetrics(
            game_id="g1",
            decision_count=5,
            action_success=3,
            action_failed=1,
            spend=50.0,
            revenue=100.0,
            installs=10,
        )
        d = m.to_dict()
        assert "timestamp" in d
        assert d["game_id"] == "g1"
        assert "agent" in d
        assert "execution" in d
        assert "business" in d

    def test_to_dict_agent_section(self):
        m = GrowthMetrics(decision_count=5, success_rate=0.8, failure_rate=0.2)
        d = m.to_dict()
        agent = d["agent"]
        assert agent["decision_count"] == 5
        assert agent["success_rate"] == 0.8
        assert agent["failure_rate"] == 0.2

    def test_to_dict_execution_section(self):
        m = GrowthMetrics(
            action_success=3,
            action_failed=2,
            rollback_count=1,
            approval_waiting=4,
        )
        d = m.to_dict()
        exe = d["execution"]
        assert exe["action_success"] == 3
        assert exe["action_failed"] == 2
        assert exe["action_total"] == 5
        assert exe["action_success_rate"] == 0.6
        assert exe["rollback_count"] == 1
        assert exe["approval_waiting"] == 4

    def test_to_dict_business_section(self):
        m = GrowthMetrics(
            spend=100.0,
            revenue=300.0,
            roas=3.0,
            ltv=60.0,
            installs=200,
            purchases=50,
            impressions=5000,
            clicks=200,
        )
        d = m.to_dict()
        biz = d["business"]
        assert biz["spend"] == 100.0
        assert biz["revenue"] == 300.0
        assert biz["roas"] == 3.0
        assert biz["ltv"] == 60.0
        assert biz["installs"] == 200
        assert biz["purchases"] == 50
        assert biz["impressions"] == 5000
        assert biz["clicks"] == 200
        assert biz["ctr"] == 0.04
        assert "cpa" in biz


# ═══════════════════════════════════════════════════════════════
# MetricsCollector
# ═══════════════════════════════════════════════════════════════

class TestMetricsCollectorInit:
    """MetricsCollector 初始化测试."""

    def test_init_default(self):
        c = MetricsCollector()
        snap = c.snapshot()
        assert snap.decision_count == 0
        assert snap.action_success == 0
        assert snap.spend == 0.0

    def test_init_with_game_id(self):
        c = MetricsCollector(game_id="game_abc")
        snap = c.snapshot()
        assert snap.game_id == "game_abc"


class TestMetricsCollectorRecordDecision:
    """MetricsCollector record_decision 测试."""

    def test_record_success(self):
        c = MetricsCollector()
        c.record_decision(success=True)
        c.record_decision(success=True)
        snap = c.snapshot()
        assert snap.decision_count == 2
        assert snap.success_rate == 1.0
        assert snap.failure_rate == 0.0

    def test_record_failure(self):
        c = MetricsCollector()
        c.record_decision(success=False)
        c.record_decision(success=False)
        snap = c.snapshot()
        assert snap.decision_count == 2
        assert snap.success_rate == 0.0
        assert snap.failure_rate == 1.0

    def test_record_mixed(self):
        c = MetricsCollector()
        c.record_decision(success=True)
        c.record_decision(success=True)
        c.record_decision(success=False)
        snap = c.snapshot()
        assert snap.decision_count == 3
        assert snap.success_rate == pytest.approx(2 / 3)
        assert snap.failure_rate == pytest.approx(1 / 3)


class TestMetricsCollectorRecordExecution:
    """MetricsCollector record_execution 测试."""

    def test_record_success(self):
        c = MetricsCollector()
        c.record_execution(success=True)
        c.record_execution(success=True)
        snap = c.snapshot()
        assert snap.action_success == 2
        assert snap.action_failed == 0

    def test_record_failure(self):
        c = MetricsCollector()
        c.record_execution(success=False)
        snap = c.snapshot()
        assert snap.action_success == 0
        assert snap.action_failed == 1

    def test_record_with_rollback(self):
        c = MetricsCollector()
        c.record_execution(success=False, rollback=True)
        snap = c.snapshot()
        assert snap.rollback_count == 1
        assert snap.action_failed == 1

    def test_record_approval_waiting(self):
        c = MetricsCollector()
        c.record_execution(success=True, approval_waiting=True)
        c.record_execution(success=True, approval_waiting=True)
        snap = c.snapshot()
        assert snap.approval_waiting == 2

    def test_record_mixed_execution(self):
        c = MetricsCollector()
        c.record_execution(success=True)
        c.record_execution(success=False, rollback=True)
        c.record_execution(success=True, approval_waiting=True)
        snap = c.snapshot()
        assert snap.action_success == 2
        assert snap.action_failed == 1
        assert snap.rollback_count == 1
        assert snap.approval_waiting == 1


class TestMetricsCollectorRecordBusiness:
    """MetricsCollector record_business 测试."""

    def test_record_basic(self):
        c = MetricsCollector()
        c.record_business(spend=100.0, revenue=200.0, installs=10)
        snap = c.snapshot()
        assert snap.spend == 100.0
        assert snap.revenue == 200.0
        assert snap.installs == 10

    def test_record_cumulative(self):
        c = MetricsCollector()
        c.record_business(spend=50.0, revenue=100.0, installs=5)
        c.record_business(spend=30.0, revenue=60.0, installs=3)
        snap = c.snapshot()
        assert snap.spend == 80.0
        assert snap.revenue == 160.0
        assert snap.installs == 8

    def test_record_ltv_keeps_max(self):
        c = MetricsCollector()
        c.record_business(ltv=10.0)
        c.record_business(ltv=25.0)
        c.record_business(ltv=15.0)
        snap = c.snapshot()
        assert snap.ltv == 25.0

    def test_record_all_fields(self):
        c = MetricsCollector()
        c.record_business(
            spend=100.0,
            revenue=300.0,
            ltv=50.0,
            installs=100,
            purchases=20,
            impressions=1000,
            clicks=50,
        )
        snap = c.snapshot()
        assert snap.spend == 100.0
        assert snap.revenue == 300.0
        assert snap.ltv == 50.0
        assert snap.installs == 100
        assert snap.purchases == 20
        assert snap.impressions == 1000
        assert snap.clicks == 50


class TestMetricsCollectorSnapshot:
    """MetricsCollector snapshot 测试."""

    def test_snapshot_returns_growth_metrics(self):
        c = MetricsCollector()
        snap = c.snapshot()
        assert isinstance(snap, GrowthMetrics)

    def test_snapshot_roas_calculation(self):
        c = MetricsCollector()
        c.record_business(spend=100.0, revenue=250.0)
        snap = c.snapshot()
        assert snap.roas == 2.5

    def test_snapshot_roas_zero_spend(self):
        c = MetricsCollector()
        c.record_business(spend=0.0, revenue=100.0)
        snap = c.snapshot()
        assert snap.roas == 0.0

    def test_snapshot_appends_to_list(self):
        c = MetricsCollector()
        c.snapshot()
        c.snapshot()
        assert len(c.get_snapshots()) == 2


class TestMetricsCollectorQuery:
    """MetricsCollector 查询测试."""

    def test_get_snapshots(self):
        c = MetricsCollector()
        c.snapshot()
        c.snapshot()
        snaps = c.get_snapshots()
        assert len(snaps) == 2

    def test_get_snapshots_limit(self):
        c = MetricsCollector()
        for _ in range(10):
            c.snapshot()
        snaps = c.get_snapshots(limit=3)
        assert len(snaps) == 3

    def test_get_latest(self):
        c = MetricsCollector()
        c.record_business(spend=10.0)
        c.snapshot()
        c.record_business(spend=20.0)
        c.snapshot()
        latest = c.get_latest()
        assert latest is not None
        assert latest.spend == 30.0

    def test_get_latest_empty(self):
        c = MetricsCollector()
        assert c.get_latest() is None

    def test_get_roas_trend(self):
        c = MetricsCollector()
        c.record_business(spend=100.0, revenue=200.0)
        c.snapshot()
        c.record_business(spend=100.0, revenue=300.0)
        c.snapshot()
        trend = c.get_roas_trend()
        assert len(trend) == 2
        assert trend[0] == 2.0
        assert trend[1] == pytest.approx(2.5)

    def test_get_roas_trend_empty(self):
        c = MetricsCollector()
        trend = c.get_roas_trend()
        assert trend == []

    def test_get_roas_trend_with_limit(self):
        c = MetricsCollector()
        for i in range(5):
            c.record_business(spend=100.0, revenue=100.0 * (i + 1))
            c.snapshot()
        trend = c.get_roas_trend(n=3)
        assert len(trend) == 3


class TestMetricsCollectorReset:
    """MetricsCollector reset 测试."""

    def test_reset_clears_counters(self):
        c = MetricsCollector()
        c.record_decision(success=True)
        c.record_execution(success=True)
        c.record_business(spend=100.0, revenue=200.0)
        c.snapshot()
        c.reset()
        # After reset, new snapshot should be all zeros
        snap = c.snapshot()
        assert snap.decision_count == 0
        assert snap.action_success == 0
        assert snap.spend == 0.0
        assert snap.revenue == 0.0

    def test_reset_clears_snapshots(self):
        c = MetricsCollector()
        c.snapshot()
        c.snapshot()
        c.reset()
        assert c.get_snapshots() == []


class TestMetricsCollectorCumulative:
    """MetricsCollector 累积指标测试."""

    def test_multiple_snapshots_independent(self):
        c = MetricsCollector()
        c.record_decision(success=True)
        snap1 = c.snapshot()
        c.record_decision(success=False)
        snap2 = c.snapshot()
        assert snap1.decision_count == 1
        assert snap2.decision_count == 2

    def test_cumulative_across_snapshots(self):
        c = MetricsCollector()
        c.record_decision(success=True)
        c.snapshot()
        c.record_decision(success=True)
        c.record_decision(success=False)
        c.snapshot()
        latest = c.get_latest()
        assert latest.decision_count == 3
        assert latest.success_rate == pytest.approx(2 / 3)
        assert latest.failure_rate == pytest.approx(1 / 3)


class TestMetricsCollectorEdgeCases:
    """MetricsCollector 边界情况测试."""

    def test_empty_collector_snapshot(self):
        c = MetricsCollector()
        snap = c.snapshot()
        assert snap.decision_count == 0
        assert snap.success_rate == 0.0
        assert snap.roas == 0.0

    def test_empty_collector_latest_none(self):
        c = MetricsCollector()
        assert c.get_latest() is None

    def test_no_previous_metrics(self):
        c = MetricsCollector()
        # No snapshots taken yet
        assert c.get_latest() is None
        assert c.get_roas_trend() == []


# ═══════════════════════════════════════════════════════════════
# Alert
# ═══════════════════════════════════════════════════════════════

class TestAlert:
    """Alert 测试."""

    def test_creation_defaults(self):
        a = Alert()
        assert a.alert_id.startswith("alert_")
        assert a.severity == AlertSeverity.INFO
        assert a.rule_name == ""
        assert a.message == ""
        assert a.game_id == ""
        assert a.metrics == {}
        assert a.acknowledged is False

    def test_creation_with_values(self):
        a = Alert(
            severity=AlertSeverity.CRITICAL,
            rule_name="test_rule",
            message="Something went wrong",
            game_id="game_001",
            metrics={"key": "value"},
            acknowledged=True,
        )
        assert a.severity == AlertSeverity.CRITICAL
        assert a.rule_name == "test_rule"
        assert a.message == "Something went wrong"
        assert a.game_id == "game_001"
        assert a.metrics == {"key": "value"}
        assert a.acknowledged is True

    def test_to_dict(self):
        a = Alert(
            severity=AlertSeverity.WARNING,
            rule_name="r1",
            message="test msg",
            game_id="g1",
        )
        d = a.to_dict()
        assert d["alert_id"] == a.alert_id
        assert d["severity"] == "warning"
        assert d["rule_name"] == "r1"
        assert d["message"] == "test msg"
        assert d["game_id"] == "g1"
        assert "metrics" in d
        assert "timestamp" in d
        assert d["acknowledged"] is False

    def test_acknowledged_flag(self):
        a = Alert(acknowledged=False)
        assert a.acknowledged is False
        a.acknowledged = True
        assert a.acknowledged is True


# ═══════════════════════════════════════════════════════════════
# AlertSeverity
# ═══════════════════════════════════════════════════════════════

class TestAlertSeverity:
    """AlertSeverity 枚举测试."""

    def test_enum_values(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.FATAL.value == "fatal"

    def test_enum_members(self):
        members = set(AlertSeverity)
        assert AlertSeverity.INFO in members
        assert AlertSeverity.WARNING in members
        assert AlertSeverity.CRITICAL in members
        assert AlertSeverity.FATAL in members
        assert len(members) == 4

    def test_enum_is_string(self):
        assert isinstance(AlertSeverity.INFO.value, str)
        assert isinstance(AlertSeverity.CRITICAL.value, str)


# ═══════════════════════════════════════════════════════════════
# AlertRule
# ═══════════════════════════════════════════════════════════════

class TestAlertRule:
    """AlertRule 测试."""

    def test_creation_defaults(self):
        r = AlertRule()
        assert r.name == ""
        assert r.description == ""
        assert r.severity == AlertSeverity.WARNING
        assert r.condition is None
        assert r.message_fn is None
        assert r.enabled is True
        assert r.cooldown_minutes == 60

    def test_creation_with_values(self):
        def cond(m, p):
            return True

        def msg(m):
            return "test"

        r = AlertRule(
            name="my_rule",
            description="A test rule",
            severity=AlertSeverity.CRITICAL,
            condition=cond,
            message_fn=msg,
            enabled=False,
            cooldown_minutes=30,
        )
        assert r.name == "my_rule"
        assert r.description == "A test rule"
        assert r.severity == AlertSeverity.CRITICAL
        assert r.condition is cond
        assert r.message_fn is msg
        assert r.enabled is False
        assert r.cooldown_minutes == 30

    def test_evaluate_triggered(self):
        def cond(m, p):
            return True

        def msg(m):
            return "Alert triggered"

        r = AlertRule(
            name="always_fire",
            severity=AlertSeverity.CRITICAL,
            condition=cond,
            message_fn=msg,
        )
        m = GrowthMetrics(game_id="g1")
        alert = r.evaluate(m)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.rule_name == "always_fire"
        assert alert.message == "Alert triggered"
        assert alert.game_id == "g1"

    def test_evaluate_not_triggered(self):
        def cond(m, p):
            return False

        r = AlertRule(
            name="never_fire",
            condition=cond,
            message_fn=lambda m: "nope",
        )
        m = GrowthMetrics()
        alert = r.evaluate(m)
        assert alert is None

    def test_evaluate_disabled(self):
        def cond(m, p):
            return True

        r = AlertRule(
            name="disabled_rule",
            condition=cond,
            message_fn=lambda m: "should not fire",
            enabled=False,
        )
        m = GrowthMetrics()
        alert = r.evaluate(m)
        assert alert is None

    def test_evaluate_no_condition(self):
        r = AlertRule(
            name="no_condition",
            message_fn=lambda m: "no cond",
        )
        m = GrowthMetrics()
        alert = r.evaluate(m)
        assert alert is None

    def test_evaluate_with_previous(self):
        def cond(m, p):
            return p is not None and m.roas < p.roas

        def msg(m):
            return f"ROAS: {m.roas}"

        r = AlertRule(
            name="compare_rule",
            condition=cond,
            message_fn=msg,
        )
        prev = GrowthMetrics(roas=3.0)
        curr = GrowthMetrics(roas=1.0)
        alert = r.evaluate(curr, prev)
        assert alert is not None
        assert alert.message == "ROAS: 1.0"

    def test_evaluate_condition_exception(self):
        def cond(m, p):
            raise RuntimeError("boom")

        r = AlertRule(
            name="error_rule",
            condition=cond,
            message_fn=lambda m: "msg",
        )
        m = GrowthMetrics()
        alert = r.evaluate(m)
        assert alert is None  # exception silently caught

    def test_evaluate_no_message_fn_uses_description(self):
        def cond(m, p):
            return True

        r = AlertRule(
            name="no_msg_fn",
            description="Default description",
            condition=cond,
        )
        m = GrowthMetrics()
        alert = r.evaluate(m)
        assert alert is not None
        assert alert.message == "Default description"


# ═══════════════════════════════════════════════════════════════
# AlertManager
# ═══════════════════════════════════════════════════════════════

class TestAlertManagerRules:
    """AlertManager 规则管理测试."""

    def test_add_rule(self):
        m = AlertManager()
        r = AlertRule(name="r1")
        m.add_rule(r)
        assert len(m.rules) == 1

    def test_add_multiple_rules(self):
        m = AlertManager()
        m.add_rule(AlertRule(name="r1"))
        m.add_rule(AlertRule(name="r2"))
        m.add_rule(AlertRule(name="r3"))
        assert len(m.rules) == 3

    def test_remove_rule(self):
        m = AlertManager()
        m.add_rule(AlertRule(name="r1"))
        m.add_rule(AlertRule(name="r2"))
        assert m.remove_rule("r1") is True
        assert len(m.rules) == 1
        assert m.rules[0].name == "r2"

    def test_remove_rule_not_found(self):
        m = AlertManager()
        m.add_rule(AlertRule(name="r1"))
        assert m.remove_rule("nonexistent") is False
        assert len(m.rules) == 1

    def test_enable_rule(self):
        m = AlertManager()
        r = AlertRule(name="r1", enabled=False)
        m.add_rule(r)
        assert m.enable_rule("r1") is True
        assert r.enabled is True

    def test_enable_rule_not_found(self):
        m = AlertManager()
        assert m.enable_rule("nonexistent") is False

    def test_disable_rule(self):
        m = AlertManager()
        r = AlertRule(name="r1", enabled=True)
        m.add_rule(r)
        assert m.disable_rule("r1") is True
        assert r.enabled is False

    def test_disable_rule_not_found(self):
        m = AlertManager()
        assert m.disable_rule("nonexistent") is False

    def test_rules_property_returns_copy(self):
        m = AlertManager()
        m.add_rule(AlertRule(name="r1"))
        rules = m.rules
        rules.append(AlertRule(name="r2"))
        assert len(m.rules) == 1  # original unaffected


class TestAlertManagerEvaluate:
    """AlertManager evaluate 测试."""

    def test_evaluate_triggers_alert(self):
        def cond(m, p):
            return True

        def msg(m):
            return "triggered"

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=cond, message_fn=msg))
        curr = GrowthMetrics()
        alerts = m.evaluate(curr)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "r1"

    def test_evaluate_no_trigger(self):
        def cond(m, p):
            return False

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=cond, message_fn=lambda m: "x"))
        curr = GrowthMetrics()
        alerts = m.evaluate(curr)
        assert len(alerts) == 0

    def test_evaluate_with_previous(self):
        def cond(m, p):
            return p is not None

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=cond, message_fn=lambda m: "x"))
        curr = GrowthMetrics()
        prev = GrowthMetrics()
        alerts = m.evaluate(curr, prev)
        assert len(alerts) == 1

    def test_evaluate_no_previous(self):
        def cond(m, p):
            return p is None

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=cond, message_fn=lambda m: "x"))
        curr = GrowthMetrics()
        alerts = m.evaluate(curr)
        assert len(alerts) == 1

    def test_evaluate_multiple_rules(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "1"))
        m.add_rule(AlertRule(name="r2", condition=always, message_fn=lambda m: "2"))
        curr = GrowthMetrics()
        alerts = m.evaluate(curr)
        assert len(alerts) == 2

    def test_evaluate_skips_disabled(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "1", enabled=False))
        m.add_rule(AlertRule(name="r2", condition=always, message_fn=lambda m: "2"))
        curr = GrowthMetrics()
        alerts = m.evaluate(curr)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "r2"


class TestAlertManagerCallback:
    """AlertManager on_alert 回调测试."""

    def test_on_alert_callback_called(self):
        def always(m, p):
            return True

        received = []

        def handler(alert):
            received.append(alert)

        m = AlertManager()
        m.on_alert(handler)
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        curr = GrowthMetrics()
        m.evaluate(curr)
        assert len(received) == 1
        assert received[0].rule_name == "r1"

    def test_on_alert_callback_not_called_without_trigger(self):
        def never(m, p):
            return False

        received = []

        def handler(alert):
            received.append(alert)

        m = AlertManager()
        m.on_alert(handler)
        m.add_rule(AlertRule(name="r1", condition=never, message_fn=lambda m: "x"))
        curr = GrowthMetrics()
        m.evaluate(curr)
        assert len(received) == 0

    def test_on_alert_callback_exception_silent(self):
        def always(m, p):
            return True

        def handler(alert):
            raise RuntimeError("callback error")

        m = AlertManager()
        m.on_alert(handler)
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        curr = GrowthMetrics()
        # Should not raise
        alerts = m.evaluate(curr)
        assert len(alerts) == 1


class TestAlertManagerQuery:
    """AlertManager 查询测试."""

    def test_get_alerts_all(self):
        m = AlertManager()
        m.add_rule(AlertRule(
            name="r1",
            condition=lambda m, p: True,
            message_fn=lambda m: "x",
            cooldown_minutes=0,
        ))
        m.evaluate(GrowthMetrics())
        m.evaluate(GrowthMetrics())
        assert len(m.get_alerts()) == 2

    def test_get_alerts_by_severity(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(
            name="r1",
            severity=AlertSeverity.WARNING,
            condition=always,
            message_fn=lambda m: "x",
        ))
        m.add_rule(AlertRule(
            name="r2",
            severity=AlertSeverity.CRITICAL,
            condition=always,
            message_fn=lambda m: "x",
        ))
        m.evaluate(GrowthMetrics())
        warnings = m.get_alerts(severity=AlertSeverity.WARNING)
        criticals = m.get_alerts(severity=AlertSeverity.CRITICAL)
        assert len(warnings) == 1
        assert len(criticals) == 1

    def test_get_alerts_by_acknowledged(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x", cooldown_minutes=0))
        m.evaluate(GrowthMetrics())
        m.evaluate(GrowthMetrics())
        # Acknowledge first
        m.acknowledge(m.get_alerts()[0].alert_id)
        unack = m.get_alerts(acknowledged=False)
        ack = m.get_alerts(acknowledged=True)
        assert len(unack) == 1
        assert len(ack) == 1

    def test_get_recent(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x", cooldown_minutes=0))
        for _ in range(5):
            m.evaluate(GrowthMetrics())
        recent = m.get_recent(n=3)
        assert len(recent) == 3

    def test_get_recent_default(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        m.evaluate(GrowthMetrics())
        recent = m.get_recent()
        assert len(recent) == 1

    def test_get_unacknowledged(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x", cooldown_minutes=0))
        m.evaluate(GrowthMetrics())
        m.evaluate(GrowthMetrics())
        # Acknowledge first
        m.acknowledge(m.get_alerts()[0].alert_id)
        unack = m.get_unacknowledged()
        assert len(unack) == 1


class TestAlertManagerAcknowledge:
    """AlertManager acknowledge 测试."""

    def test_acknowledge_by_id(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        m.evaluate(GrowthMetrics())
        alert_id = m.get_alerts()[0].alert_id
        assert m.acknowledge(alert_id) is True
        assert m.get_alerts()[0].acknowledged is True

    def test_acknowledge_not_found(self):
        m = AlertManager()
        assert m.acknowledge("nonexistent_id") is False

    def test_acknowledge_all(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x", cooldown_minutes=0))
        m.evaluate(GrowthMetrics())
        m.evaluate(GrowthMetrics())
        count = m.acknowledge_all()
        assert count == 2
        assert m.get_unacknowledged() == []

    def test_acknowledge_all_on_empty(self):
        m = AlertManager()
        count = m.acknowledge_all()
        assert count == 0

    def test_acknowledge_all_partial(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x", cooldown_minutes=0))
        m.evaluate(GrowthMetrics())
        m.evaluate(GrowthMetrics())
        # Acknowledge first already
        m.acknowledge(m.get_alerts()[0].alert_id)
        count = m.acknowledge_all()
        assert count == 1


class TestAlertManagerSummary:
    """AlertManager get_summary 测试."""

    def test_get_summary_empty(self):
        m = AlertManager()
        s = m.get_summary()
        assert s["total_alerts"] == 0
        assert s["unacknowledged"] == 0
        assert s["rules_count"] == 0
        assert s["enabled_rules"] == 0

    def test_get_summary_with_alerts(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(
            name="r1",
            severity=AlertSeverity.CRITICAL,
            condition=always,
            message_fn=lambda m: "x",
        ))
        m.add_rule(AlertRule(
            name="r2",
            severity=AlertSeverity.WARNING,
            condition=always,
            message_fn=lambda m: "x",
        ))
        m.add_rule(AlertRule(name="r3", enabled=False, condition=always, message_fn=lambda m: "x"))
        m.evaluate(GrowthMetrics())
        s = m.get_summary()
        assert s["total_alerts"] == 2
        assert s["unacknowledged"] == 2
        assert s["rules_count"] == 3
        assert s["enabled_rules"] == 2
        assert s["by_severity"]["critical"] == 1
        assert s["by_severity"]["warning"] == 1
        assert s["by_severity"]["info"] == 0
        assert s["by_severity"]["fatal"] == 0


class TestAlertManagerReset:
    """AlertManager reset 测试."""

    def test_reset_clears_alerts(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        m.evaluate(GrowthMetrics())
        m.reset()
        assert len(m.get_alerts()) == 0

    def test_reset_clears_cooldown(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        m.evaluate(GrowthMetrics())
        m.reset()
        # After reset, cooldown is cleared so alert should fire again
        alerts = m.evaluate(GrowthMetrics())
        assert len(alerts) == 1

    def test_reset_does_not_clear_rules(self):
        m = AlertManager()
        m.add_rule(AlertRule(name="r1"))
        m.reset()
        assert len(m.rules) == 1


class TestAlertManagerEdgeCases:
    """AlertManager 边界情况测试."""

    def test_empty_manager_evaluate(self):
        m = AlertManager()
        alerts = m.evaluate(GrowthMetrics())
        assert alerts == []

    def test_empty_manager_get_alerts(self):
        m = AlertManager()
        assert m.get_alerts() == []

    def test_empty_manager_get_unacknowledged(self):
        m = AlertManager()
        assert m.get_unacknowledged() == []

    def test_disabled_rules_not_evaluated(self):
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(name="r1", condition=always, message_fn=lambda m: "x"))
        m.disable_rule("r1")
        alerts = m.evaluate(GrowthMetrics())
        assert alerts == []

    def test_cooldown_prevents_re_trigger(self):
        """冷却时间内不应重复触发同一规则."""
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(
            name="r1",
            condition=always,
            message_fn=lambda m: "x",
            cooldown_minutes=60,  # 1 hour cooldown
        ))
        # First evaluation triggers
        alerts1 = m.evaluate(GrowthMetrics())
        assert len(alerts1) == 1
        # Second evaluation should be suppressed by cooldown
        alerts2 = m.evaluate(GrowthMetrics())
        assert len(alerts2) == 0

    def test_no_cooldown_on_different_rules(self):
        """不同规则不受各自的冷却时间影响."""
        def always(m, p):
            return True

        m = AlertManager()
        m.add_rule(AlertRule(
            name="r1",
            condition=always,
            message_fn=lambda m: "x",
            cooldown_minutes=60,
        ))
        m.add_rule(AlertRule(
            name="r2",
            condition=always,
            message_fn=lambda m: "y",
            cooldown_minutes=60,
        ))
        m.evaluate(GrowthMetrics())
        # After first evaluation, r1 on cooldown but r2 also triggered
        # Second evaluation: both should be on cooldown
        alerts = m.evaluate(GrowthMetrics())
        assert len(alerts) == 0  # both on cooldown


# ═══════════════════════════════════════════════════════════════
# Built-in Alert Rules
# ═══════════════════════════════════════════════════════════════

class TestRoasDropRule:
    """ROAS 下降规则测试."""

    def test_triggers_when_roas_drops_below_threshold(self):
        rule = roas_drop_rule(threshold=-0.30)
        prev = GrowthMetrics(roas=10.0)
        curr = GrowthMetrics(roas=6.0)  # -40%
        alert = rule.evaluate(curr, prev)
        assert alert is not None
        assert alert.rule_name == "roas_drop_30"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_triggers_at_exact_threshold(self):
        rule = roas_drop_rule(threshold=-0.30)
        prev = GrowthMetrics(roas=10.0)
        curr = GrowthMetrics(roas=7.0)  # exactly -30%
        alert = rule.evaluate(curr, prev)
        assert alert is not None

    def test_no_trigger_when_roas_stable(self):
        rule = roas_drop_rule(threshold=-0.30)
        prev = GrowthMetrics(roas=10.0)
        curr = GrowthMetrics(roas=9.0)  # -10%
        alert = rule.evaluate(curr, prev)
        assert alert is None

    def test_no_trigger_when_roas_increases(self):
        rule = roas_drop_rule(threshold=-0.30)
        prev = GrowthMetrics(roas=5.0)
        curr = GrowthMetrics(roas=10.0)
        alert = rule.evaluate(curr, prev)
        assert alert is None

    def test_no_trigger_without_previous(self):
        rule = roas_drop_rule()
        curr = GrowthMetrics(roas=1.0)
        alert = rule.evaluate(curr, None)
        assert alert is None

    def test_no_trigger_when_previous_roas_zero(self):
        rule = roas_drop_rule()
        prev = GrowthMetrics(roas=0.0)
        curr = GrowthMetrics(roas=1.0)
        alert = rule.evaluate(curr, prev)
        assert alert is None


class TestConnectorFailureRule:
    """Connector 失败规则测试."""

    def test_triggers_when_all_failed(self):
        rule = connector_failure_rule()
        curr = GrowthMetrics(action_success=0, action_failed=3)
        alert = rule.evaluate(curr)
        assert alert is not None
        assert alert.rule_name == "connector_failure"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_no_trigger_with_successes(self):
        rule = connector_failure_rule()
        curr = GrowthMetrics(action_success=1, action_failed=3)
        alert = rule.evaluate(curr)
        assert alert is None

    def test_no_trigger_with_no_actions(self):
        rule = connector_failure_rule()
        curr = GrowthMetrics(action_success=0, action_failed=0)
        alert = rule.evaluate(curr)
        assert alert is None


class TestExecutionAnomalyRule:
    """执行异常规则测试."""

    def test_triggers_with_enough_failures(self):
        rule = execution_anomaly_rule(max_failures=3)
        curr = GrowthMetrics(action_failed=5)
        alert = rule.evaluate(curr)
        assert alert is not None
        assert alert.rule_name == "execution_anomaly"
        assert alert.severity == AlertSeverity.WARNING

    def test_triggers_at_threshold(self):
        rule = execution_anomaly_rule(max_failures=3)
        curr = GrowthMetrics(action_failed=3)
        alert = rule.evaluate(curr)
        assert alert is not None

    def test_no_trigger_below_threshold(self):
        rule = execution_anomaly_rule(max_failures=3)
        curr = GrowthMetrics(action_failed=2)
        alert = rule.evaluate(curr)
        assert alert is None

    def test_default_threshold(self):
        rule = execution_anomaly_rule()
        curr = GrowthMetrics(action_failed=3)
        alert = rule.evaluate(curr)
        assert alert is not None

    def test_custom_threshold(self):
        rule = execution_anomaly_rule(max_failures=10)
        curr = GrowthMetrics(action_failed=5)
        alert = rule.evaluate(curr)
        assert alert is None


class TestBudgetAnomalyRule:
    """预算异常规则测试."""

    def test_triggers_on_large_spend_change(self):
        rule = budget_anomaly_rule(max_spend_change_pct=0.50)
        prev = GrowthMetrics(spend=100.0)
        curr = GrowthMetrics(spend=200.0)  # +100%
        alert = rule.evaluate(curr, prev)
        assert alert is not None
        assert alert.rule_name == "budget_anomaly"
        assert alert.severity == AlertSeverity.WARNING

    def test_no_trigger_on_small_change(self):
        rule = budget_anomaly_rule(max_spend_change_pct=0.50)
        prev = GrowthMetrics(spend=100.0)
        curr = GrowthMetrics(spend=120.0)  # +20%
        alert = rule.evaluate(curr, prev)
        assert alert is None

    def test_no_trigger_without_previous(self):
        rule = budget_anomaly_rule()
        curr = GrowthMetrics(spend=100.0)
        alert = rule.evaluate(curr, None)
        assert alert is None

    def test_no_trigger_when_previous_spend_zero(self):
        rule = budget_anomaly_rule()
        prev = GrowthMetrics(spend=0.0)
        curr = GrowthMetrics(spend=100.0)
        alert = rule.evaluate(curr, prev)
        assert alert is None


class TestCreateDefaultAlertRules:
    """create_default_alert_rules 测试."""

    def test_returns_four_rules(self):
        rules = create_default_alert_rules()
        assert len(rules) == 4

    def test_all_rules_have_names(self):
        rules = create_default_alert_rules()
        names = {r.name for r in rules}
        assert "roas_drop_30" in names
        assert "connector_failure" in names
        assert "execution_anomaly" in names
        assert "budget_anomaly" in names

    def test_all_rules_are_enabled(self):
        rules = create_default_alert_rules()
        for r in rules:
            assert r.enabled is True

    def test_all_rules_have_conditions(self):
        rules = create_default_alert_rules()
        for r in rules:
            assert r.condition is not None