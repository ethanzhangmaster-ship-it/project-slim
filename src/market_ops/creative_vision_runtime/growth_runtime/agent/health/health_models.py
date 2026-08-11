"""E13.7.4.3 Health Models — 健康监控核心数据模型.

扩展 agent_health.py 的基础模型，定义:
  - HealthStatus: 五级健康状态 (HEALTHY / WARNING / DEGRADED / SAFE_MODE / FAILED)
  - HealthMetricCategory: 指标分类 (Runtime / Decision / Execution / Tool)
  - HealthSnapshot: 健康快照 (含分项指标)
  - HealthRule: 健康规则基类
  - HealthRuleResult: 单条规则评估结果
  - HealthEvaluation: 综合评估结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class HealthStatus(str, Enum):
    """健康状态 — 五级状态.

    HEALTHY:   所有指标正常，Agent 全功能运行
    WARNING:   部分指标接近阈值，需关注但不影响运行
    DEGRADED:  部分指标异常，自动降级部分功能
    SAFE_MODE: 严重异常，只读模式，禁止写操作
    FAILED:    致命异常，Agent 完全停止
    """
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    SAFE_MODE = "safe_mode"
    FAILED = "failed"


class HealthMetricCategory(str, Enum):
    """健康指标分类."""
    RUNTIME = "runtime"       # 运行时指标 (循环次数、心跳、耗时)
    DECISION = "decision"     # 决策指标 (置信度、决策次数)
    EXECUTION = "execution"   # 执行指标 (成功率、回滚率)
    TOOL = "tool"             # 工具指标 (API 成功率、超时、限流)
    MEMORY = "memory"         # 记忆指标 (增长、泄漏)


class AlertLevel(str, Enum):
    """告警级别."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """告警类型."""
    EXECUTION_FAILURE = "execution_failure"
    TOOL_FAILURE = "tool_failure"
    DECISION_DRIFT = "decision_drift"
    API_TIMEOUT = "api_timeout"
    RATE_LIMIT = "rate_limit"
    MEMORY_LEAK = "memory_leak"
    CYCLE_TIMEOUT = "cycle_timeout"
    SAFE_MODE_ACTIVATED = "safe_mode_activated"


# ═══════════════════════════════════════════════════════════════
# Status severity (用于取最严重状态)
# ═══════════════════════════════════════════════════════════════

HEALTH_STATUS_SEVERITY: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.WARNING: 1,
    HealthStatus.DEGRADED: 2,
    HealthStatus.SAFE_MODE: 3,
    HealthStatus.FAILED: 4,
}


def most_severe_status(statuses: list[HealthStatus]) -> HealthStatus:
    """取最严重的健康状态."""
    if not statuses:
        return HealthStatus.HEALTHY
    return max(statuses, key=lambda s: HEALTH_STATUS_SEVERITY.get(s, 0))


# ═══════════════════════════════════════════════════════════════
# Metric Definitions
# ═══════════════════════════════════════════════════════════════


@dataclass
class MetricDefinition:
    """指标定义.

    Attributes:
        key: 指标键
        name: 指标名称
        category: 指标分类
        unit: 单位
        direction: "higher_is_better" 或 "lower_is_better"
        warning_threshold: 警告阈值
        critical_threshold: 严重阈值
        description: 指标说明
    """
    key: str = ""
    name: str = ""
    category: HealthMetricCategory = HealthMetricCategory.RUNTIME
    unit: str = ""
    direction: str = "higher_is_better"
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# Health Snapshot
# ═══════════════════════════════════════════════════════════════


@dataclass
class RuntimeHealth:
    """运行时健康指标."""
    cycle_count: int = 0
    cycle_duration_avg: float = 0.0
    last_heartbeat: str = ""
    failed_cycles: int = 0
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_count": self.cycle_count,
            "cycle_duration_avg": self.cycle_duration_avg,
            "last_heartbeat": self.last_heartbeat,
            "failed_cycles": self.failed_cycles,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class DecisionHealth:
    """决策健康指标."""
    decision_count: int = 0
    average_confidence: float = 0.0
    low_confidence_rate: float = 0.0
    decision_latency_avg: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_count": self.decision_count,
            "average_confidence": self.average_confidence,
            "low_confidence_rate": self.low_confidence_rate,
            "decision_latency_avg": self.decision_latency_avg,
        }


@dataclass
class ExecutionHealth:
    """执行健康指标."""
    execution_success_rate: float = 1.0
    rollback_rate: float = 0.0
    failure_rate: float = 0.0
    total_executions: int = 0
    consecutive_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_success_rate": self.execution_success_rate,
            "rollback_rate": self.rollback_rate,
            "failure_rate": self.failure_rate,
            "total_executions": self.total_executions,
            "consecutive_errors": self.consecutive_errors,
        }


@dataclass
class ToolHealth:
    """工具健康指标."""
    api_success_rate: float = 1.0
    timeout_count: int = 0
    rate_limit_count: int = 0
    total_api_calls: int = 0
    avg_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_success_rate": self.api_success_rate,
            "timeout_count": self.timeout_count,
            "rate_limit_count": self.rate_limit_count,
            "total_api_calls": self.total_api_calls,
            "avg_latency_ms": self.avg_latency_ms,
        }


@dataclass
class HealthSnapshot:
    """健康快照 — 单次健康检查的完整结果.

    Attributes:
        snapshot_id: 快照 ID
        timestamp: 检查时间
        status: 综合健康状态
        runtime: 运行时健康
        decision: 决策健康
        execution: 执行健康
        tool: 工具健康
        warnings: 警告信息
        errors: 错误信息
        recommendations: 建议操作
        triggered_rules: 触发的规则名称
        rule_results: 规则评估详情
    """
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: HealthStatus = HealthStatus.HEALTHY

    runtime: RuntimeHealth = field(default_factory=RuntimeHealth)
    decision: DecisionHealth = field(default_factory=DecisionHealth)
    execution: ExecutionHealth = field(default_factory=ExecutionHealth)
    tool: ToolHealth = field(default_factory=ToolHealth)

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    rule_results: list[HealthRuleResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "runtime": self.runtime.to_dict(),
            "decision": self.decision.to_dict(),
            "execution": self.execution.to_dict(),
            "tool": self.tool.to_dict(),
            "warnings": self.warnings,
            "errors": self.errors,
            "recommendations": self.recommendations,
            "triggered_rules": self.triggered_rules,
        }


# ═══════════════════════════════════════════════════════════════
# Health Rule
# ═══════════════════════════════════════════════════════════════


@dataclass
class HealthRuleResult:
    """健康规则评估结果."""
    rule_id: str = ""
    rule_name: str = ""
    triggered: bool = False
    status: HealthStatus = HealthStatus.HEALTHY
    reason: str = ""
    category: HealthMetricCategory = HealthMetricCategory.RUNTIME

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "triggered": self.triggered,
            "status": self.status.value,
            "reason": self.reason,
            "category": self.category.value,
        }


@dataclass
class HealthRule:
    """健康规则基类.

    Attributes:
        rule_id: 规则 ID
        name: 规则名称
        description: 规则描述
        category: 指标分类
        priority: 优先级 (数字越小越优先)
        enabled: 是否启用
        condition: 条件函数 (HealthSnapshot) -> bool
        reason_template: 触发原因模板
        target_status: 触发后的目标状态
    """
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: HealthMetricCategory = HealthMetricCategory.RUNTIME
    priority: int = 50
    enabled: bool = True
    condition: Callable[[HealthSnapshot], bool] | None = None
    reason_template: str = ""
    target_status: HealthStatus = HealthStatus.WARNING

    def evaluate(self, snapshot: HealthSnapshot) -> HealthRuleResult:
        """评估规则.

        Args:
            snapshot: 健康快照

        Returns:
            HealthRuleResult: 评估结果
        """
        if not self.enabled:
            return HealthRuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                triggered=False,
                category=self.category,
            )

        triggered = False
        if self.condition:
            try:
                triggered = self.condition(snapshot)
            except Exception:
                triggered = False

        if not triggered:
            return HealthRuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                triggered=False,
                status=HealthStatus.HEALTHY,
                category=self.category,
            )

        return HealthRuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            triggered=True,
            status=self.target_status,
            reason=self.reason_template,
            category=self.category,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority,
            "enabled": self.enabled,
            "target_status": self.target_status.value,
        }


# ═══════════════════════════════════════════════════════════════
# Health Evaluation
# ═══════════════════════════════════════════════════════════════


@dataclass
class HealthEvaluation:
    """健康评估结果 — HealthMonitor.evaluate() 的返回值.

    Attributes:
        evaluation_id: 评估 ID
        snapshot: 健康快照
        status: 最终状态
        previous_status: 上一次状态
        status_changed: 状态是否变化
        requires_safe_mode: 是否需要进入安全模式
        requires_alert: 是否需要告警
        timestamp: 评估时间
    """
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    snapshot: HealthSnapshot = field(default_factory=HealthSnapshot)
    status: HealthStatus = HealthStatus.HEALTHY
    previous_status: HealthStatus = HealthStatus.HEALTHY
    status_changed: bool = False
    requires_safe_mode: bool = False
    requires_alert: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "snapshot": self.snapshot.to_dict(),
            "status": self.status.value,
            "previous_status": self.previous_status.value,
            "status_changed": self.status_changed,
            "requires_safe_mode": self.requires_safe_mode,
            "requires_alert": self.requires_alert,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# Alert
# ═══════════════════════════════════════════════════════════════


@dataclass
class Alert:
    """告警.

    Attributes:
        alert_id: 告警 ID
        level: 告警级别
        alert_type: 告警类型
        message: 告警消息
        source: 告警来源
        snapshot: 关联的健康快照
        created_at: 创建时间
        resolved_at: 解决时间
        is_resolved: 是否已解决
        resolution_note: 解决备注
    """
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: AlertLevel = AlertLevel.WARNING
    alert_type: AlertType = AlertType.EXECUTION_FAILURE
    message: str = ""
    source: str = "health_monitor"
    snapshot: HealthSnapshot | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    is_resolved: bool = False
    resolution_note: str = ""

    def resolve(self, note: str = "") -> None:
        """解决告警."""
        self.is_resolved = True
        self.resolved_at = datetime.now(timezone.utc).isoformat()
        self.resolution_note = note

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "alert_type": self.alert_type.value,
            "message": self.message,
            "source": self.source,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "is_resolved": self.is_resolved,
            "resolution_note": self.resolution_note,
        }


# ═══════════════════════════════════════════════════════════════
# Safe Mode Policy
# ═══════════════════════════════════════════════════════════════


@dataclass
class SafeModePolicy:
    """安全模式行为策略.

    定义在 SAFE_MODE 下 Agent 的允许/禁止行为。

    Attributes:
        allowed_actions: 安全模式下允许的动作
        blocked_actions: 安全模式下禁止的动作
        auto_recovery_conditions: 自动恢复条件
        require_manual_approval: 是否需要人工审批才能退出安全模式
    """
    allowed_actions: list[str] = field(default_factory=lambda: [
        "analyze", "generate_report", "monitor", "read_data",
    ])
    blocked_actions: list[str] = field(default_factory=lambda: [
        "create_campaign", "update_budget", "scale_budget",
        "change_targeting", "change_bidding", "pause_campaign",
        "create_creative", "mutate_creative",
    ])
    auto_recovery_conditions: list[str] = field(default_factory=list)
    require_manual_approval: bool = True

    def is_action_allowed(self, action_type: str) -> bool:
        """检查动作是否在安全模式下允许."""
        return action_type in self.allowed_actions

    def is_action_blocked(self, action_type: str) -> bool:
        """检查动作是否在安全模式下被禁止."""
        return action_type in self.blocked_actions

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_actions": self.allowed_actions,
            "blocked_actions": self.blocked_actions,
            "auto_recovery_conditions": self.auto_recovery_conditions,
            "require_manual_approval": self.require_manual_approval,
        }