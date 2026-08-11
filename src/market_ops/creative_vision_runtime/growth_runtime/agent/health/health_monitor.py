"""E13.7.4.3 Health Monitor — 核心健康监控器.

HealthMonitor 是 Agent Health System 的核心，负责:
  - 采集各维度健康指标 (Runtime / Decision / Execution / Tool)
  - 评估健康规则
  - 输出健康状态 (HEALTHY / WARNING / DEGRADED / SAFE_MODE / FAILED)
  - 触发告警
  - 管理 Safe Mode 切换

处理流程:
    HealthMonitor.check()
          ↓
    MetricsCollector.collect_all()
          ↓
    HealthSnapshot
          ↓
    for each HealthRule.evaluate(snapshot)
          ↓
    aggregate → most_severe_status
          ↓
    HealthEvaluation
          ↓
    if status_changed:
        AlertManager.send()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .health_models import (
    HealthEvaluation,
    HealthMetricCategory,
    HealthRule,
    HealthRuleResult,
    HealthSnapshot,
    HealthStatus,
    SafeModePolicy,
    most_severe_status,
)
from .health_metrics import MetricsCollector
from .health_rules import build_default_health_rules


# ═══════════════════════════════════════════════════════════════
# Health Monitor
# ═══════════════════════════════════════════════════════════════


class HealthMonitor:
    """Agent 健康监控器 — 持续监控 Agent 健康状态.

    使用方式:
        >>> monitor = HealthMonitor()
        >>> monitor.collector.execution.record_success()
        >>> evaluation = monitor.check()
        >>> print(evaluation.status)  # HEALTHY

    Attributes:
        collector: 指标采集器
        rules: 健康规则集
        safe_mode_policy: 安全模式行为策略
        history: 健康检查历史
        current_status: 当前健康状态
    """

    def __init__(
        self,
        rules: list[HealthRule] | None = None,
        safe_mode_policy: SafeModePolicy | None = None,
        max_history: int = 200,
    ):
        self.collector = MetricsCollector()
        self._rules: list[HealthRule] = rules if rules is not None else build_default_health_rules()
        self.safe_mode_policy = safe_mode_policy or SafeModePolicy()
        self._max_history = max_history
        self._history: list[HealthEvaluation] = []
        self._current_status: HealthStatus = HealthStatus.HEALTHY
        self._status_changed_callback: Any = None

    # ── Properties ──────────────────────────────────────────

    @property
    def status(self) -> HealthStatus:
        return self._current_status

    @property
    def is_healthy(self) -> bool:
        return self._current_status == HealthStatus.HEALTHY

    @property
    def is_safe_mode(self) -> bool:
        return self._current_status in (HealthStatus.SAFE_MODE, HealthStatus.FAILED)

    @property
    def is_degraded(self) -> bool:
        return self._current_status in (HealthStatus.DEGRADED, HealthStatus.SAFE_MODE, HealthStatus.FAILED)

    @property
    def rules(self) -> list[HealthRule]:
        return list(self._rules)

    @property
    def history(self) -> list[HealthEvaluation]:
        return list(self._history)

    # ── Callback ────────────────────────────────────────────

    def on_status_changed(self, callback: Any) -> None:
        """注册状态变更回调.

        callback 签名: def callback(old_status: HealthStatus, new_status: HealthStatus, evaluation: HealthEvaluation)
        """
        self._status_changed_callback = callback

    # ── Rule Management ─────────────────────────────────────

    def add_rule(self, rule: HealthRule) -> None:
        """添加规则."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def enable_rule(self, rule_id: str) -> bool:
        for r in self._rules:
            if r.rule_id == rule_id:
                r.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        for r in self._rules:
            if r.rule_id == rule_id:
                r.enabled = False
                return True
        return False

    # ── Core Check ──────────────────────────────────────────

    def check(self) -> HealthEvaluation:
        """执行一次完整健康检查.

        流程:
          1. 采集所有指标 → HealthSnapshot
          2. 评估所有规则 → HealthRuleResult[]
          3. 聚合最严重状态 → HealthStatus
          4. 检测状态变更
          5. 记录历史

        Returns:
            HealthEvaluation: 健康评估结果
        """
        # 1. 采集指标
        snapshot = self.collector.collect_all()

        # 2. 评估规则
        rule_results: list[HealthRuleResult] = []
        triggered_rules: list[str] = []
        statuses: list[HealthStatus] = []
        warnings: list[str] = []
        errors: list[str] = []
        recommendations: list[str] = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            result = rule.evaluate(snapshot)
            rule_results.append(result)

            if result.triggered:
                triggered_rules.append(result.rule_name)
                statuses.append(result.status)
                reason = f"[{result.rule_name}] {result.reason}"

                if result.status == HealthStatus.WARNING:
                    warnings.append(reason)
                elif result.status in (HealthStatus.DEGRADED, HealthStatus.SAFE_MODE, HealthStatus.FAILED):
                    errors.append(reason)

                if result.status == HealthStatus.SAFE_MODE:
                    recommendations.append("进入安全模式: 暂停自动执行，只生成建议")
                elif result.status == HealthStatus.DEGRADED:
                    recommendations.append("系统降级: 切换模拟模式，减少自主操作")
                elif result.status == HealthStatus.FAILED:
                    recommendations.append("Agent 停止运行，等待人工介入")

        # 3. 聚合状态
        if not statuses:
            new_status = HealthStatus.HEALTHY
        else:
            new_status = most_severe_status(statuses)

        # 4. 更新快照
        snapshot.status = new_status
        snapshot.warnings = warnings
        snapshot.errors = errors
        snapshot.recommendations = recommendations
        snapshot.triggered_rules = triggered_rules
        snapshot.rule_results = rule_results

        # 5. 检测状态变更
        previous = self._current_status
        status_changed = new_status != previous
        self._current_status = new_status

        requires_safe_mode = new_status in (HealthStatus.SAFE_MODE, HealthStatus.FAILED)
        requires_alert = status_changed and new_status != HealthStatus.HEALTHY

        evaluation = HealthEvaluation(
            snapshot=snapshot,
            status=new_status,
            previous_status=previous,
            status_changed=status_changed,
            requires_safe_mode=requires_safe_mode,
            requires_alert=requires_alert,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # 6. 记录历史
        self._history.append(evaluation)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 7. 触发回调
        if status_changed and self._status_changed_callback:
            try:
                self._status_changed_callback(previous, new_status, evaluation)
            except Exception:
                pass

        return evaluation

    # ── Safe Mode ───────────────────────────────────────────

    def is_action_allowed_in_safe_mode(self, action_type: str) -> bool:
        """检查动作在安全模式下是否允许.

        Args:
            action_type: 动作类型

        Returns:
            bool: 是否允许
        """
        if not self.is_safe_mode:
            return True
        return self.safe_mode_policy.is_action_allowed(action_type)

    def is_action_blocked_in_safe_mode(self, action_type: str) -> bool:
        """检查动作在安全模式下是否被禁止."""
        if not self.is_safe_mode:
            return False
        return self.safe_mode_policy.is_action_blocked(action_type)

    # ── Query ───────────────────────────────────────────────

    def get_latest(self) -> HealthEvaluation | None:
        """获取最新健康评估."""
        return self._history[-1] if self._history else None

    def get_history(self, n: int = 20) -> list[HealthEvaluation]:
        """获取最近 n 次健康检查历史."""
        return self._history[-n:]

    def get_status_timeline(self) -> list[dict[str, Any]]:
        """获取状态变更时间线."""
        timeline = []
        last_status = None
        for ev in self._history:
            if ev.status != last_status:
                timeline.append({
                    "status": ev.status.value,
                    "timestamp": ev.timestamp,
                    "reason": ev.snapshot.errors[0] if ev.snapshot.errors else "健康检查通过",
                })
                last_status = ev.status
        return timeline

    def get_summary(self) -> dict[str, Any]:
        """获取监控摘要."""
        latest = self.get_latest()
        return {
            "current_status": self._current_status.value,
            "is_safe_mode": self.is_safe_mode,
            "is_degraded": self.is_degraded,
            "rules_count": len(self._rules),
            "enabled_rules_count": len([r for r in self._rules if r.enabled]),
            "check_count": len(self._history),
            "latest_snapshot": latest.snapshot.to_dict() if latest else None,
        }

    def reset(self) -> None:
        """重置监控器."""
        self.collector.reset_all()
        self._history.clear()
        self._current_status = HealthStatus.HEALTHY


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_health_monitor(
    rules: list[HealthRule] | None = None,
    safe_mode_policy: SafeModePolicy | None = None,
) -> HealthMonitor:
    """创建健康监控器的工厂函数."""
    return HealthMonitor(
        rules=rules,
        safe_mode_policy=safe_mode_policy,
    )