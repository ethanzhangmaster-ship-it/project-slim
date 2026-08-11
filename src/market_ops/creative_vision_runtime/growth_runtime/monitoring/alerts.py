"""E15.0.5 Alerting — 报警系统.

报警规则:
  - ROAS 下降 30%
  - Connector 失败
  - 执行异常
  - 预算异常
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from .metrics import GrowthMetrics


class AlertSeverity(str, Enum):
    """报警严重程度."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


@dataclass
class Alert:
    """报警记录."""
    alert_id: str = field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:12]}")
    severity: AlertSeverity = AlertSeverity.INFO
    rule_name: str = ""
    message: str = ""
    game_id: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "rule_name": self.rule_name,
            "message": self.message,
            "game_id": self.game_id,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


@dataclass
class AlertRule:
    """报警规则.

    Attributes:
        name:        规则名称
        description: 规则描述
        severity:    报警等级
        condition:   条件函数 (metrics, previous_metrics) -> bool
        message_fn:  消息生成函数 (metrics) -> str
        enabled:     是否启用
        cooldown_minutes: 冷却时间 (分钟内不重复报警)
    """

    name: str = ""
    description: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    condition: Callable[[GrowthMetrics, GrowthMetrics | None], bool] | None = None
    message_fn: Callable[[GrowthMetrics], str] | None = None
    enabled: bool = True
    cooldown_minutes: int = 60

    def evaluate(
        self,
        current: GrowthMetrics,
        previous: GrowthMetrics | None = None,
    ) -> Alert | None:
        """评估规则."""
        if not self.enabled or self.condition is None:
            return None

        try:
            if self.condition(current, previous):
                message = self.message_fn(current) if self.message_fn else self.description
                return Alert(
                    severity=self.severity,
                    rule_name=self.name,
                    message=message,
                    game_id=current.game_id,
                    metrics={"current": current.to_dict()},
                )
        except Exception:
            pass
        return None


class AlertManager:
    """报警管理器 — 管理报警规则和报警历史.

    用法:
        manager = AlertManager()
        manager.add_rule(ROAS_DROP_RULE)
        manager.add_rule(CONNECTOR_FAILURE_RULE)
        alerts = manager.evaluate(current_metrics, previous_metrics)
    """

    def __init__(self):
        self._rules: list[AlertRule] = []
        self._alerts: list[Alert] = []
        self._last_alert_time: dict[str, str] = {}  # rule_name → last_alert_time
        self._notify_handler: Callable[[Alert], None] | None = None

    # ── Rule Management ──────────────────────────────────────

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def enable_rule(self, name: str) -> bool:
        for r in self._rules:
            if r.name == name:
                r.enabled = True
                return True
        return False

    def disable_rule(self, name: str) -> bool:
        for r in self._rules:
            if r.name == name:
                r.enabled = False
                return True
        return False

    @property
    def rules(self) -> list[AlertRule]:
        return list(self._rules)

    # ── Notification ─────────────────────────────────────────

    def on_alert(self, handler: Callable[[Alert], None]) -> None:
        """注册报警通知回调."""
        self._notify_handler = handler

    # ── Evaluate ─────────────────────────────────────────────

    def evaluate(
        self,
        current: GrowthMetrics,
        previous: GrowthMetrics | None = None,
    ) -> list[Alert]:
        """评估所有规则，返回触发的报警.

        Args:
            current:  当前指标
            previous: 上一次指标 (用于变化检测)

        Returns:
            触发的报警列表
        """
        triggered: list[Alert] = []
        now = datetime.now(timezone.utc)

        for rule in self._rules:
            # 检查冷却时间
            last_time = self._last_alert_time.get(rule.name)
            if last_time:
                try:
                    last = datetime.fromisoformat(last_time)
                    if (now - last).total_seconds() < rule.cooldown_minutes * 60:
                        continue
                except (ValueError, TypeError):
                    pass

            alert = rule.evaluate(current, previous)
            if alert:
                self._alerts.append(alert)
                self._last_alert_time[rule.name] = now.isoformat()
                triggered.append(alert)

                if self._notify_handler:
                    try:
                        self._notify_handler(alert)
                    except Exception:
                        pass

        return triggered

    # ── Query ────────────────────────────────────────────────

    def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        result = self._alerts
        if severity:
            result = [a for a in result if a.severity == severity]
        if acknowledged is not None:
            result = [a for a in result if a.acknowledged == acknowledged]
        return result

    def get_recent(self, n: int = 20) -> list[Alert]:
        return self._alerts[-n:]

    def get_unacknowledged(self) -> list[Alert]:
        return [a for a in self._alerts if not a.acknowledged]

    def acknowledge(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a.alert_id == alert_id:
                a.acknowledged = True
                return True
        return False

    def acknowledge_all(self) -> int:
        count = 0
        for a in self._alerts:
            if not a.acknowledged:
                a.acknowledged = True
                count += 1
        return count

    # ── Statistics ───────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_alerts": len(self._alerts),
            "unacknowledged": len(self.get_unacknowledged()),
            "by_severity": {
                s.value: len([a for a in self._alerts if a.severity == s])
                for s in AlertSeverity
            },
            "rules_count": len(self._rules),
            "enabled_rules": len([r for r in self._rules if r.enabled]),
        }

    def reset(self) -> None:
        self._alerts.clear()
        self._last_alert_time.clear()


# ═══════════════════════════════════════════════════════════════
# Built-in Alert Rules
# ═══════════════════════════════════════════════════════════════


def roas_drop_rule(threshold: float = -0.30) -> AlertRule:
    """ROAS 下降 30% 报警."""
    def _condition(current: GrowthMetrics, previous: GrowthMetrics | None) -> bool:
        if previous is None or previous.roas == 0:
            return False
        change = (current.roas - previous.roas) / previous.roas
        return change <= threshold

    def _message(current: GrowthMetrics) -> str:
        return f"ROAS dropped to {current.roas:.2f}"

    return AlertRule(
        name="roas_drop_30",
        description="ROAS下降超过30%",
        severity=AlertSeverity.CRITICAL,
        condition=_condition,
        message_fn=_message,
        cooldown_minutes=30,
    )


def connector_failure_rule() -> AlertRule:
    """Connector 失败报警."""
    def _condition(current: GrowthMetrics, _previous: GrowthMetrics | None) -> bool:
        return current.action_failed > 0 and current.action_success == 0

    def _message(current: GrowthMetrics) -> str:
        return f"All actions failed: {current.action_failed} failures"

    return AlertRule(
        name="connector_failure",
        description="Connector连接失败",
        severity=AlertSeverity.CRITICAL,
        condition=_condition,
        message_fn=_message,
        cooldown_minutes=15,
    )


def execution_anomaly_rule(max_failures: int = 3) -> AlertRule:
    """执行异常报警."""
    def _condition(current: GrowthMetrics, _previous: GrowthMetrics | None) -> bool:
        return current.action_failed >= max_failures

    def _message(current: GrowthMetrics) -> str:
        return f"Execution anomaly: {current.action_failed} consecutive failures"

    return AlertRule(
        name="execution_anomaly",
        description="执行异常：连续失败",
        severity=AlertSeverity.WARNING,
        condition=_condition,
        message_fn=_message,
        cooldown_minutes=30,
    )


def budget_anomaly_rule(max_spend_change_pct: float = 0.50) -> AlertRule:
    """预算异常报警."""
    def _condition(current: GrowthMetrics, previous: GrowthMetrics | None) -> bool:
        if previous is None or previous.spend == 0:
            return False
        change = abs(current.spend - previous.spend) / previous.spend
        return change > max_spend_change_pct

    def _message(current: GrowthMetrics) -> str:
        return f"Budget anomaly: spend changed significantly"

    return AlertRule(
        name="budget_anomaly",
        description="预算异常：花费变化过大",
        severity=AlertSeverity.WARNING,
        condition=_condition,
        message_fn=_message,
        cooldown_minutes=60,
    )


def create_default_alert_rules() -> list[AlertRule]:
    """创建默认报警规则集."""
    return [
        roas_drop_rule(),
        connector_failure_rule(),
        execution_anomaly_rule(),
        budget_anomaly_rule(),
    ]