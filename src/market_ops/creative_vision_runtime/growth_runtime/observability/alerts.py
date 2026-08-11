"""E15.0.11 Alert Engine — 告警引擎.

基于指标阈值触发告警，回答:
  > 哪些情况需要人介入？

支持:
  - AlertRule:     告警规则定义 (指标 + 阈值 + 操作符)
  - AlertSeverity: 告警严重级别 (CRITICAL / WARNING / INFO)
  - AlertState:    告警状态 (PENDING / ACTIVE / RESOLVED)
  - AlertEngine:   告警引擎 (定期检查指标 → 触发/恢复告警)

用法:
    engine = AlertEngine(collector)

    engine.add_rule(AlertRule(
        name="Execution Failure Spike",
        metric="execution_failed_rate",
        threshold=0.1,
        operator=">",
        severity=AlertSeverity.CRITICAL,
    ))

    # 注入指标后检查
    collector.increment("execution_failed", 15)
    collector.increment("execution_total", 100)
    engine.check()

    for alert in engine.get_active_alerts():
        print(alert)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from .metrics import MetricsCollector


# ═══════════════════════════════════════════════════════════════
# Alert Severity
# ═══════════════════════════════════════════════════════════════


class AlertSeverity(str, Enum):
    """告警严重级别."""
    CRITICAL = "critical"  # 需要立即处理
    WARNING = "warning"    # 需要关注
    INFO = "info"          # 信息通知


# ═══════════════════════════════════════════════════════════════
# Alert State
# ═══════════════════════════════════════════════════════════════


class AlertState(str, Enum):
    """告警状态."""
    PENDING = "pending"    # 等待确认
    ACTIVE = "active"      # 已触发
    RESOLVED = "resolved"  # 已恢复


# ═══════════════════════════════════════════════════════════════
# Alert Rule
# ═══════════════════════════════════════════════════════════════


@dataclass
class AlertRule:
    """告警规则定义.

    Attributes:
        name:      规则名称
        metric:    指标名称 (e.g. "execution_failed_rate")
        threshold: 阈值
        operator:  比较操作符 (">", "<", ">=", "<=", "==")
        severity:  告警严重级别
        labels:    指标标签过滤 (可选)
        metadata:  扩展信息
    """

    name: str
    metric: str
    threshold: float = 0.0
    operator: str = ">"
    severity: AlertSeverity = AlertSeverity.WARNING
    labels: dict[str, str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _VALID_OPERATORS = {">", "<", ">=", "<=", "=="}

    def __post_init__(self):
        if self.operator not in self._VALID_OPERATORS:
            raise ValueError(
                f"Invalid operator '{self.operator}'. Must be one of {self._VALID_OPERATORS}"
            )

    def evaluate(self, value: float) -> bool:
        """评估当前值是否触发规则.

        Args:
            value: 当前指标值

        Returns:
            bool: True 表示触发告警
        """
        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == "==":
            return value == self.threshold
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metric": self.metric,
            "threshold": self.threshold,
            "operator": self.operator,
            "severity": self.severity.value,
            "labels": self.labels,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"AlertRule({self.name}, {self.metric} {self.operator} {self.threshold}, "
            f"severity={self.severity.value})"
        )


# ═══════════════════════════════════════════════════════════════
# Alert
# ═══════════════════════════════════════════════════════════════


@dataclass
class Alert:
    """告警实例.

    Attributes:
        alert_id:    告警唯一标识
        rule:        触发的规则
        value:       触发时的指标值
        state:       当前状态
        triggered_at: 触发时间
        resolved_at: 恢复时间
        check_count: 已检查次数
    """

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule: AlertRule = field(default_factory=lambda: AlertRule(name=""))
    value: float = 0.0
    state: AlertState = AlertState.PENDING
    triggered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    check_count: int = 0

    def resolve(self) -> None:
        """标记告警为已恢复."""
        self.state = AlertState.RESOLVED
        self.resolved_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule": self.rule.to_dict(),
            "value": self.value,
            "state": self.state.value,
            "triggered_at": self.triggered_at,
            "resolved_at": self.resolved_at,
            "check_count": self.check_count,
        }

    @property
    def is_active(self) -> bool:
        return self.state in (AlertState.PENDING, AlertState.ACTIVE)

    def __repr__(self) -> str:
        return (
            f"Alert({self.rule.name}, value={self.value}, "
            f"state={self.state.value})"
        )


# ═══════════════════════════════════════════════════════════════
# Alert Engine
# ═══════════════════════════════════════════════════════════════


class AlertEngine:
    """E15.0.11 告警引擎 — 基于指标阈值触发告警.

    用法:
        engine = AlertEngine(collector)
        engine.add_rule(AlertRule(name="high_failure_rate", metric="execution_failed_rate", threshold=0.1))

        # 采集指标
        collector.increment("execution_failed", 15)
        collector.increment("execution_total", 100)

        # 检查告警
        engine.check()

        for alert in engine.get_active_alerts():
            print(f"ALERT: {alert}")

    Attributes:
        collector:   MetricsCollector 实例
        _rules:     告警规则列表
        _alerts:    告警历史
        _notifiers: 告警通知回调
    """

    def __init__(
        self,
        collector: MetricsCollector | None = None,
        rules: list[AlertRule] | None = None,
    ):
        self._collector = collector or MetricsCollector()
        self._rules: list[AlertRule] = rules or []
        self._alerts: list[Alert] = []
        self._notifiers: list[Callable[[Alert], None]] = []
        self._check_count: int = 0
        self._max_alerts: int = 500

    # ── Rule Management ──────────────────────────────────────

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则."""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """按名称移除告警规则.

        Returns:
            bool: 是否成功移除
        """
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def get_rules(self) -> list[AlertRule]:
        """获取所有规则."""
        return list(self._rules)

    # ── Notifier ─────────────────────────────────────────────

    def register_notifier(self, callback: Callable[[Alert], None]) -> None:
        """注册告警通知回调."""
        self._notifiers.append(callback)

    # ── Check ────────────────────────────────────────────────

    def check(self) -> list[Alert]:
        """检查所有规则，触发或恢复告警.

        Returns:
            list[Alert]: 本轮新触发的告警
        """
        self._check_count += 1
        new_alerts: list[Alert] = []

        for rule in self._rules:
            value = self._get_metric_value(rule)
            triggered = rule.evaluate(value)

            # 查找该规则当前的活跃告警
            active_alert = self._find_active_alert(rule.name)

            if triggered and active_alert is None:
                # 新触发
                alert = Alert(
                    rule=rule,
                    value=value,
                    state=AlertState.ACTIVE,
                    check_count=self._check_count,
                )
                self._alerts.append(alert)
                self._trim()
                new_alerts.append(alert)
                self._notify(alert)

            elif triggered and active_alert is not None:
                # 持续触发 — 更新值
                active_alert.value = value
                active_alert.check_count = self._check_count

            elif not triggered and active_alert is not None:
                # 恢复
                active_alert.resolve()

        return new_alerts

    def check_metric(self, metric_name: str) -> list[Alert]:
        """检查特定指标的告警规则.

        Args:
            metric_name: 指标名称

        Returns:
            list[Alert]: 新触发的告警
        """
        self._check_count += 1
        new_alerts: list[Alert] = []

        for rule in self._rules:
            if rule.metric != metric_name:
                continue

            value = self._get_metric_value(rule)
            triggered = rule.evaluate(value)
            active_alert = self._find_active_alert(rule.name)

            if triggered and active_alert is None:
                alert = Alert(
                    rule=rule,
                    value=value,
                    state=AlertState.ACTIVE,
                    check_count=self._check_count,
                )
                self._alerts.append(alert)
                self._trim()
                new_alerts.append(alert)
                self._notify(alert)

            elif triggered and active_alert is not None:
                active_alert.value = value
                active_alert.check_count = self._check_count

            elif not triggered and active_alert is not None:
                active_alert.resolve()

        return new_alerts

    # ── Query ────────────────────────────────────────────────

    def get_active_alerts(self) -> list[Alert]:
        """获取所有活跃告警 (PENDING + ACTIVE)."""
        return [a for a in self._alerts if a.is_active]

    def get_alerts_by_severity(self, severity: AlertSeverity) -> list[Alert]:
        """按严重级别获取告警."""
        return [a for a in self._alerts if a.rule.severity == severity]

    def get_alert_history(self, limit: int = 50) -> list[Alert]:
        """获取告警历史."""
        return self._alerts[-limit:]

    def acknowledge(self, alert_id: str) -> bool:
        """确认告警 — 将 PENDING 转为 ACTIVE.

        Returns:
            bool: 是否成功确认
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and alert.state == AlertState.PENDING:
                alert.state = AlertState.ACTIVE
                return True
        return False

    def resolve(self, alert_id: str) -> bool:
        """手动恢复告警.

        Returns:
            bool: 是否成功恢复
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and alert.is_active:
                alert.resolve()
                return True
        return False

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        active = self.get_active_alerts()
        return {
            "total_rules": len(self._rules),
            "total_alerts": len(self._alerts),
            "active_alerts": len(active),
            "check_count": self._check_count,
            "by_severity": {
                s.value: len([a for a in active if a.rule.severity == s])
                for s in AlertSeverity
            },
            "by_state": {
                s.value: len([a for a in self._alerts if a.state == s])
                for s in AlertState
            },
        }

    def clear(self) -> None:
        """清空所有告警历史."""
        self._alerts.clear()
        self._check_count = 0

    # ── Internal ─────────────────────────────────────────────

    def _get_metric_value(self, rule: AlertRule) -> float:
        """从 MetricsCollector 中获取指标值.

        支持:
          - Counter: 直接取值
          - Gauge:   直接取值
          - 派生指标: 如 execution_failed_rate = failed / total
        """
        # 尝试作为派生指标
        if rule.metric.endswith("_rate"):
            # 例如 execution_failed_rate → execution_failed / execution_total
            base = rule.metric[:-5]  # 去掉 _rate
            failed = self._collector.get_counter(base, rule.labels)
            total = self._collector.get_counter(
                base.replace("_failed", "_total"), rule.labels
            )
            if total > 0:
                return failed / total
            return 0.0

        # 尝试 Counter
        value = self._collector.get_counter(rule.metric, rule.labels)
        if value > 0:
            return float(value)

        # 尝试 Gauge
        gauge_value = self._collector.get_gauge(rule.metric, rule.labels)
        return gauge_value

    def _find_active_alert(self, rule_name: str) -> Alert | None:
        """查找指定规则的活跃告警."""
        for alert in self._alerts:
            if alert.rule.name == rule_name and alert.is_active:
                return alert
        return None

    def _notify(self, alert: Alert) -> None:
        """通知所有注册的 notifier."""
        for callback in self._notifiers:
            try:
                callback(alert)
            except Exception:
                pass

    def _trim(self) -> None:
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

    def __repr__(self) -> str:
        return (
            f"AlertEngine(rules={len(self._rules)}, "
            f"alerts={len(self._alerts)}, active={len(self.get_active_alerts())})"
        )


# ═══════════════════════════════════════════════════════════════
# Preset Rules
# ═══════════════════════════════════════════════════════════════


def default_alert_rules() -> list[AlertRule]:
    """E15.0.11 默认告警规则集.

    覆盖执行、审批、适配器三层的核心告警场景.
    """
    return [
        AlertRule(
            name="Execution Failure Spike",
            metric="execution_failed_rate",
            threshold=0.1,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        ),
        AlertRule(
            name="Approval Queue Overflow",
            metric="pending_approval_count",
            threshold=100,
            operator=">",
            severity=AlertSeverity.WARNING,
        ),
        AlertRule(
            name="Adapter Error Rate",
            metric="adapter_error_rate",
            threshold=0.05,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        ),
        AlertRule(
            name="High Execution Latency",
            metric="execution_duration_ms",
            threshold=5000,
            operator=">",
            severity=AlertSeverity.WARNING,
        ),
        AlertRule(
            name="Zero Execution Activity",
            metric="execution_total",
            threshold=0,
            operator="==",
            severity=AlertSeverity.INFO,
        ),
        AlertRule(
            name="High Rollback Rate",
            metric="rollback_rate",
            threshold=0.2,
            operator=">",
            severity=AlertSeverity.WARNING,
        ),
    ]


__all__ = [
    "AlertSeverity",
    "AlertState",
    "AlertRule",
    "Alert",
    "AlertEngine",
    "default_alert_rules",
]