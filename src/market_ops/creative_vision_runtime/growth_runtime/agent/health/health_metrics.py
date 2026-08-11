"""E13.7.4.3 Health Metrics — 指标采集器.

从 Runtime 各组件采集健康指标:
  - RuntimeMetricsCollector: 运行时指标 (循环、心跳、耗时)
  - DecisionMetricsCollector: 决策指标 (置信度、决策次数)
  - ExecutionMetricsCollector: 执行指标 (成功率、回滚率)
  - ToolMetricsCollector: 工具指标 (API 成功率、超时、限流)

每个 Collector 独立采集，HealthMonitor 聚合所有指标。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .health_models import (
    DecisionHealth,
    ExecutionHealth,
    HealthMetricCategory,
    HealthSnapshot,
    RuntimeHealth,
    ToolHealth,
)


# ═══════════════════════════════════════════════════════════════
# Runtime Metrics Collector
# ═══════════════════════════════════════════════════════════════


class RuntimeMetricsCollector:
    """运行时指标采集器.

    跟踪:
      - 循环次数
      - 平均循环耗时
      - 最后心跳时间
      - 失败循环数
      - 运行时长
    """

    def __init__(self):
        self._cycle_count: int = 0
        self._cycle_durations: list[float] = []
        self._failed_cycles: int = 0
        self._last_heartbeat: str = ""
        self._start_time: str = ""

    def record_cycle_start(self) -> None:
        """记录循环开始."""
        if not self._start_time:
            self._start_time = datetime.now(timezone.utc).isoformat()

    def record_cycle_complete(self, duration_seconds: float) -> None:
        """记录循环完成.

        Args:
            duration_seconds: 循环耗时 (秒)
        """
        self._cycle_count += 1
        self._cycle_durations.append(duration_seconds)
        self._last_heartbeat = datetime.now(timezone.utc).isoformat()

    def record_cycle_failed(self) -> None:
        """记录循环失败."""
        self._failed_cycles += 1

    def collect(self) -> RuntimeHealth:
        """采集运行时健康指标.

        Returns:
            RuntimeHealth: 运行时健康指标
        """
        avg_duration = 0.0
        if self._cycle_durations:
            recent = self._cycle_durations[-100:]  # 最近 100 次
            avg_duration = sum(recent) / len(recent)

        uptime = 0.0
        if self._start_time:
            try:
                start = datetime.fromisoformat(self._start_time)
                uptime = (datetime.now(timezone.utc) - start).total_seconds()
            except Exception:
                pass

        return RuntimeHealth(
            cycle_count=self._cycle_count,
            cycle_duration_avg=avg_duration,
            last_heartbeat=self._last_heartbeat,
            failed_cycles=self._failed_cycles,
            uptime_seconds=uptime,
        )

    def reset(self) -> None:
        self._cycle_count = 0
        self._cycle_durations = []
        self._failed_cycles = 0
        self._last_heartbeat = ""
        self._start_time = ""


# ═══════════════════════════════════════════════════════════════
# Decision Metrics Collector
# ═══════════════════════════════════════════════════════════════


class DecisionMetricsCollector:
    """决策指标采集器.

    跟踪:
      - 决策次数
      - 平均置信度
      - 低置信度比例
      - 决策延迟
    """

    def __init__(self, low_confidence_threshold: float = 0.7):
        self._decision_count: int = 0
        self._confidences: list[float] = []
        self._latencies: list[float] = []
        self._low_confidence_threshold = low_confidence_threshold

    def record_decision(self, confidence: float, latency_ms: float = 0.0) -> None:
        """记录一次决策.

        Args:
            confidence: 决策置信度 [0, 1]
            latency_ms: 决策延迟 (毫秒)
        """
        self._decision_count += 1
        self._confidences.append(confidence)
        self._latencies.append(latency_ms)

    def collect(self) -> DecisionHealth:
        """采集决策健康指标.

        Returns:
            DecisionHealth: 决策健康指标
        """
        avg_confidence = 0.0
        if self._confidences:
            recent = self._confidences[-100:]
            avg_confidence = sum(recent) / len(recent)

        low_count = sum(1 for c in self._confidences[-100:] if c < self._low_confidence_threshold)
        low_rate = low_count / max(len(self._confidences[-100:]), 1)

        avg_latency = 0.0
        if self._latencies:
            recent_lat = self._latencies[-100:]
            avg_latency = sum(recent_lat) / len(recent_lat)

        return DecisionHealth(
            decision_count=self._decision_count,
            average_confidence=avg_confidence,
            low_confidence_rate=low_rate,
            decision_latency_avg=avg_latency,
        )

    def reset(self) -> None:
        self._decision_count = 0
        self._confidences = []
        self._latencies = []


# ═══════════════════════════════════════════════════════════════
# Execution Metrics Collector
# ═══════════════════════════════════════════════════════════════


class ExecutionMetricsCollector:
    """执行指标采集器.

    连接 E13.6 Execution Engine:
      - 执行成功率
      - 回滚率
      - 失败率
      - 连续错误数
    """

    def __init__(self):
        self._total_executions: int = 0
        self._successful_executions: int = 0
        self._failed_executions: int = 0
        self._rollbacks: int = 0
        self._consecutive_errors: int = 0

    def record_success(self) -> None:
        """记录成功执行."""
        self._total_executions += 1
        self._successful_executions += 1
        self._consecutive_errors = 0

    def record_failure(self) -> None:
        """记录失败执行."""
        self._total_executions += 1
        self._failed_executions += 1
        self._consecutive_errors += 1

    def record_rollback(self) -> None:
        """记录回滚."""
        self._rollbacks += 1

    def collect(self) -> ExecutionHealth:
        """采集执行健康指标.

        Returns:
            ExecutionHealth: 执行健康指标
        """
        total = max(self._total_executions, 1)
        return ExecutionHealth(
            execution_success_rate=(
                self._successful_executions / total
                if self._total_executions > 0 else 1.0
            ),
            rollback_rate=self._rollbacks / total,
            failure_rate=self._failed_executions / total,
            total_executions=self._total_executions,
            consecutive_errors=self._consecutive_errors,
        )

    def reset(self) -> None:
        self._total_executions = 0
        self._successful_executions = 0
        self._failed_executions = 0
        self._rollbacks = 0
        self._consecutive_errors = 0


# ═══════════════════════════════════════════════════════════════
# Tool Metrics Collector
# ═══════════════════════════════════════════════════════════════


class ToolMetricsCollector:
    """工具指标采集器.

    连接 E13.7.1 Tool Adapter:
      - API 成功率
      - 超时次数
      - 限流次数
      - 平均延迟
    """

    def __init__(self):
        self._total_api_calls: int = 0
        self._successful_api_calls: int = 0
        self._timeout_count: int = 0
        self._rate_limit_count: int = 0
        self._latencies_ms: list[float] = []

    def record_api_call(self, success: bool, latency_ms: float = 0.0) -> None:
        """记录一次 API 调用.

        Args:
            success: 是否成功
            latency_ms: 延迟 (毫秒)
        """
        self._total_api_calls += 1
        if success:
            self._successful_api_calls += 1
        self._latencies_ms.append(latency_ms)

    def record_timeout(self) -> None:
        """记录 API 超时."""
        self._timeout_count += 1

    def record_rate_limit(self) -> None:
        """记录 API 限流."""
        self._rate_limit_count += 1

    def collect(self) -> ToolHealth:
        """采集工具健康指标.

        Returns:
            ToolHealth: 工具健康指标
        """
        total = max(self._total_api_calls, 1)
        avg_lat = 0.0
        if self._latencies_ms:
            recent = self._latencies_ms[-100:]
            avg_lat = sum(recent) / len(recent)

        # 无 API 调用时默认健康
        success_rate = self._successful_api_calls / total if self._total_api_calls > 0 else 1.0

        return ToolHealth(
            api_success_rate=success_rate,
            timeout_count=self._timeout_count,
            rate_limit_count=self._rate_limit_count,
            total_api_calls=self._total_api_calls,
            avg_latency_ms=avg_lat,
        )

    def reset(self) -> None:
        self._total_api_calls = 0
        self._successful_api_calls = 0
        self._timeout_count = 0
        self._rate_limit_count = 0
        self._latencies_ms = []


# ═══════════════════════════════════════════════════════════════
# Metrics Aggregator
# ═══════════════════════════════════════════════════════════════


class MetricsCollector:
    """指标采集聚合器 — 统一管理所有 Collector.

    使用方式:
        >>> collector = MetricsCollector()
        >>> collector.runtime.record_cycle_complete(5.0)
        >>> collector.execution.record_success()
        >>> snapshot = collector.collect_all()
    """

    def __init__(self):
        self.runtime = RuntimeMetricsCollector()
        self.decision = DecisionMetricsCollector()
        self.execution = ExecutionMetricsCollector()
        self.tool = ToolMetricsCollector()

    def collect_all(self) -> HealthSnapshot:
        """采集所有指标并生成健康快照.

        Returns:
            HealthSnapshot: 完整健康快照 (status 待 Monitor 评估)
        """
        return HealthSnapshot(
            runtime=self.runtime.collect(),
            decision=self.decision.collect(),
            execution=self.execution.collect(),
            tool=self.tool.collect(),
        )

    def reset_all(self) -> None:
        """重置所有采集器."""
        self.runtime.reset()
        self.decision.reset()
        self.execution.reset()
        self.tool.reset()