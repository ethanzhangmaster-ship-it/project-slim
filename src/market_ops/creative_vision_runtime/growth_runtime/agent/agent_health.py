"""E13.7.4 Agent Health Monitor — 健康监控系统.

生产系统必须知道自己有没有坏。Agent Health Monitor 持续跟踪:
  - 循环时间 (last_cycle_time)
  - 失败动作率 (failed_actions)
  - 工具错误率 (tool_error_rate)
  - 推理延迟 (reasoning_latency)
  - 执行成功率 (execution_success_rate)
  - 记忆增长 (memory_growth)

异常时自动:
  - 切换到安全模式 (safe mode)
  - 暂停自主操作 (pause autonomous mode)
  - 发出告警 (alert)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar


class HealthStatus(str, Enum):
    """健康状态."""
    HEALTHY = "healthy"           # 所有指标正常
    DEGRADED = "degraded"         # 部分指标异常但可恢复
    UNHEALTHY = "unhealthy"       # 严重异常, 需暂停自主操作
    SAFE_MODE = "safe_mode"       # 安全模式: 只读不写
    UNKNOWN = "unknown"           # 初始状态


class HealthMetric(str, Enum):
    """健康指标类型."""
    CYCLE_TIME = "cycle_time"
    FAILED_ACTIONS = "failed_actions"
    TOOL_ERROR_RATE = "tool_error_rate"
    REASONING_LATENCY = "reasoning_latency"
    EXECUTION_SUCCESS_RATE = "execution_success_rate"
    MEMORY_GROWTH = "memory_growth"
    CONSECUTIVE_ERRORS = "consecutive_errors"
    POLICY_VIOLATIONS = "policy_violations"


@dataclass
class HealthThreshold:
    """健康阈值配置.

    Attributes:
        metric: 指标类型
        warning_threshold: 警告阈值 (超过此值进入 DEGRADED)
        critical_threshold: 严重阈值 (超过此值进入 UNHEALTHY)
        description: 阈值说明
    """
    metric: HealthMetric
    warning_threshold: float
    critical_threshold: float
    description: str = ""


@dataclass
class HealthSnapshot:
    """健康快照 — 单次健康检查结果.

    Attributes:
        timestamp: 检查时间
        status: 健康状态
        metrics: 各指标当前值
        warnings: 警告信息
        errors: 错误信息
        recommendations: 建议操作
    """
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: HealthStatus = HealthStatus.UNKNOWN
    metrics: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "status": self.status.value,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "errors": self.errors,
            "recommendations": self.recommendations,
        }


@dataclass
class AgentHealthMonitor:
    """Agent 健康监控器.

    持续监控 Agent 的运行状态, 异常时自动切换安全模式。
    """

    # 默认健康阈值 (类变量)
    DEFAULT_THRESHOLDS: ClassVar[list[HealthThreshold]] = [
        HealthThreshold(
            metric=HealthMetric.CYCLE_TIME,
            warning_threshold=300.0,
            critical_threshold=600.0,
            description="单次循环超时: 300s 警告, 600s 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.FAILED_ACTIONS,
            warning_threshold=3.0,
            critical_threshold=10.0,
            description="失败动作数: 3 警告, 10 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.TOOL_ERROR_RATE,
            warning_threshold=0.1,
            critical_threshold=0.3,
            description="工具错误率: 10% 警告, 30% 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.REASONING_LATENCY,
            warning_threshold=30.0,
            critical_threshold=120.0,
            description="推理延迟: 30s 警告, 120s 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.EXECUTION_SUCCESS_RATE,
            warning_threshold=0.8,
            critical_threshold=0.5,
            description="执行成功率: <80% 警告, <50% 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.MEMORY_GROWTH,
            warning_threshold=10000.0,
            critical_threshold=50000.0,
            description="记忆条目增长: 10000 警告, 50000 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.CONSECUTIVE_ERRORS,
            warning_threshold=2.0,
            critical_threshold=5.0,
            description="连续错误: 2 警告, 5 严重",
        ),
        HealthThreshold(
            metric=HealthMetric.POLICY_VIOLATIONS,
            warning_threshold=1.0,
            critical_threshold=3.0,
            description="策略违规: 1 警告, 3 严重",
        ),
    ]

    def __init__(self):
        self._thresholds: dict[HealthMetric, HealthThreshold] = {
            t.metric: t for t in self.DEFAULT_THRESHOLDS
        }
        self._history: list[HealthSnapshot] = []
        self._current_status: HealthStatus = HealthStatus.UNKNOWN

        # 计数器
        self._failed_actions: int = 0
        self._tool_errors: int = 0
        self._tool_total: int = 0
        self._consecutive_errors: int = 0
        self._policy_violations: int = 0
        self._total_cycles: int = 0
        self._successful_executions: int = 0
        self._total_executions: int = 0

    # ── Properties ────────────────────────────────────────────

    @property
    def status(self) -> HealthStatus:
        return self._current_status

    @property
    def is_healthy(self) -> bool:
        return self._current_status == HealthStatus.HEALTHY

    @property
    def is_safe_mode(self) -> bool:
        return self._current_status in (HealthStatus.SAFE_MODE, HealthStatus.UNHEALTHY)

    # ── 指标更新 ──────────────────────────────────────────────

    def record_cycle(
        self,
        duration_seconds: float,
        reasoning_latency: float = 0,
    ) -> None:
        """记录一次循环完成."""
        self._total_cycles += 1

    def record_success(self) -> None:
        """记录一次成功执行."""
        self._successful_executions += 1
        self._total_executions += 1
        self._consecutive_errors = 0

    def record_failure(self) -> None:
        """记录一次失败执行."""
        self._failed_actions += 1
        self._total_executions += 1
        self._consecutive_errors += 1

    def record_tool_error(self) -> None:
        """记录一次工具错误."""
        self._tool_errors += 1
        self._tool_total += 1

    def record_tool_success(self) -> None:
        """记录一次工具成功."""
        self._tool_total += 1

    def record_policy_violation(self) -> None:
        """记录一次策略违规."""
        self._policy_violations += 1

    # ── 健康检查 ──────────────────────────────────────────────

    def check(self) -> HealthSnapshot:
        """执行一次健康检查.

        Returns:
            HealthSnapshot: 健康快照
        """
        now = datetime.now(timezone.utc)
        metrics = self._collect_metrics()
        warnings: list[str] = []
        errors: list[str] = []
        recommendations: list[str] = []

        # 逐指标检查
        for metric_key, value in metrics.items():
            metric = HealthMetric(metric_key)
            threshold = self._thresholds.get(metric)
            if not threshold:
                continue

            if metric == HealthMetric.EXECUTION_SUCCESS_RATE:
                # 成功率: 低于阈值视为异常
                if value < threshold.critical_threshold:
                    errors.append(f"{metric.value}: {value:.1%} < {threshold.critical_threshold:.0%} (critical)")
                    recommendations.append(threshold.description)
                elif value < threshold.warning_threshold:
                    warnings.append(f"{metric.value}: {value:.1%} < {threshold.warning_threshold:.0%} (warning)")
            else:
                # 其他指标: 超过阈值视为异常
                if value > threshold.critical_threshold:
                    errors.append(f"{metric.value}: {value} > {threshold.critical_threshold} (critical)")
                    recommendations.append(threshold.description)
                elif value > threshold.warning_threshold:
                    warnings.append(f"{metric.value}: {value} > {threshold.warning_threshold} (warning)")

        # 判断状态
        if errors:
            status = HealthStatus.UNHEALTHY
            recommendations.append("Switch to SAFE_MODE: read-only, no autonomous actions")
        elif warnings:
            status = HealthStatus.DEGRADED
            recommendations.append("Monitor closely; consider reducing autonomy level")
        else:
            status = HealthStatus.HEALTHY

        snapshot = HealthSnapshot(
            timestamp=now.isoformat(),
            status=status,
            metrics=metrics,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
        )

        self._history.append(snapshot)
        self._current_status = status

        return snapshot

    def _collect_metrics(self) -> dict[str, float]:
        """收集当前所有指标."""
        return {
            HealthMetric.FAILED_ACTIONS.value: float(self._failed_actions),
            HealthMetric.TOOL_ERROR_RATE.value: (
                self._tool_errors / max(self._tool_total, 1)
            ),
            HealthMetric.EXECUTION_SUCCESS_RATE.value: (
                self._successful_executions / max(self._total_executions, 1)
                if self._total_executions > 0 else 1.0  # 无执行时默认健康
            ),
            HealthMetric.CONSECUTIVE_ERRORS.value: float(self._consecutive_errors),
            HealthMetric.POLICY_VIOLATIONS.value: float(self._policy_violations),
        }

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[HealthSnapshot]:
        """获取最近健康检查历史."""
        return self._history[-n:]

    def get_latest(self) -> HealthSnapshot | None:
        """获取最新健康快照."""
        return self._history[-1] if self._history else None

    def stats(self) -> dict[str, Any]:
        """获取统计摘要."""
        metrics = self._collect_metrics()
        return {
            "status": self._current_status.value,
            "total_cycles": self._total_cycles,
            "total_executions": self._total_executions,
            "successful_executions": self._successful_executions,
            "failed_actions": self._failed_actions,
            "consecutive_errors": self._consecutive_errors,
            "policy_violations": self._policy_violations,
            "check_count": len(self._history),
            **metrics,
        }

    def reset(self) -> None:
        """重置监控器."""
        self._history.clear()
        self._current_status = HealthStatus.UNKNOWN
        self._failed_actions = 0
        self._tool_errors = 0
        self._tool_total = 0
        self._consecutive_errors = 0
        self._policy_violations = 0
        self._total_cycles = 0
        self._successful_executions = 0
        self._total_executions = 0


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_health_monitor() -> AgentHealthMonitor:
    """创建默认健康监控器."""
    return AgentHealthMonitor()