"""E15.3.4 Performance Monitor — 性能监控.

监控 Operator 自身表现，收集中间决策和执行指标。

指标来源:
  - Decision Loop:  决策准确率、推理质量
  - Execution:      执行成功率、延迟
  - Memory:         记忆命中率、模式利用率
  - Planning:       规划成功率、模板匹配率

用法:
    monitor = PerformanceMonitor()
    metrics = monitor.collect_metrics()
    degraded = monitor.get_degraded()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    MetricSeverity,
    OptimizationMetric,
    TrendDirection,
)


# ═══════════════════════════════════════════════════════════════
# Metric Definitions
# ═══════════════════════════════════════════════════════════════

# 内置监控指标定义
BUILTIN_METRICS: dict[str, dict[str, Any]] = {
    "decision_accuracy": {
        "target": 0.85,
        "baseline": 0.50,
        "source": "decision_loop",
        "description": "决策准确率 - 实际执行结果的正确决策比例",
    },
    "execution_success_rate": {
        "target": 0.90,
        "baseline": 0.50,
        "source": "execution",
        "description": "执行成功率 - 成功完成的任务比例",
    },
    "reasoning_confidence": {
        "target": 0.80,
        "baseline": 0.50,
        "source": "reasoning",
        "description": "推理置信度 - 推理引擎输出的平均置信度",
    },
    "memory_hit_rate": {
        "target": 0.70,
        "baseline": 0.30,
        "source": "memory",
        "description": "记忆命中率 - 模式匹配成功的比例",
    },
    "strategy_success_rate": {
        "target": 0.75,
        "baseline": 0.40,
        "source": "action_selection",
        "description": "策略成功率 - 选择策略的执行成功率",
    },
    "planning_match_rate": {
        "target": 0.80,
        "baseline": 0.50,
        "source": "planning",
        "description": "规划匹配率 - 模板匹配成功率",
    },
    "risk_approval_rate": {
        "target": 0.70,
        "baseline": 0.50,
        "source": "risk_engine",
        "description": "风险审批率 - 通过风险检查的动作比例",
    },
    "reward_prediction_error": {
        "target": 0.10,
        "baseline": 0.30,
        "source": "action_selection",
        "description": "收益预测误差 - 预测收益与实际收益的偏差 (越低越好)",
    },
}


# ═══════════════════════════════════════════════════════════════
# Performance Monitor
# ═══════════════════════════════════════════════════════════════


class PerformanceMonitor:
    """E15.3.4 性能监控器 — 收集和管理 Operator 性能指标.

    用法:
        monitor = PerformanceMonitor()
        monitor.record("decision_accuracy", 0.72)
        metrics = monitor.collect_metrics()
    """

    def __init__(self):
        self._metrics: dict[str, OptimizationMetric] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._max_history: int = 100

    # ── Record ──────────────────────────────────────────────────

    def record(
        self,
        metric_name: str,
        value: float,
        source: str = "",
        timestamp: str | None = None,
    ) -> OptimizationMetric:
        """记录一个指标值.

        Args:
            metric_name: 指标名称
            value:       当前值
            source:      数据来源
            timestamp:   时间戳

        Returns:
            OptimizationMetric
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        # 获取或创建指标
        if metric_name not in self._metrics:
            self._metrics[metric_name] = self._create_metric(metric_name, value, source)

        metric = self._metrics[metric_name]
        metric.current_value = value
        metric.source = source or metric.source
        metric.updated_at = ts

        # 记录历史
        if metric_name not in self._history:
            self._history[metric_name] = []
        self._history[metric_name].append({
            "value": value,
            "timestamp": ts,
        })
        if len(self._history[metric_name]) > self._max_history:
            self._history[metric_name] = self._history[metric_name][-self._max_history:]

        # 更新趋势和严重度
        self._update_trend_and_severity(metric)

        return metric

    def record_batch(
        self, metrics: dict[str, float], source: str = ""
    ) -> list[OptimizationMetric]:
        """批量记录指标."""
        results = []
        for name, value in metrics.items():
            results.append(self.record(name, value, source))
        return results

    def _create_metric(
        self, name: str, value: float, source: str
    ) -> OptimizationMetric:
        """创建指标实例."""
        info = BUILTIN_METRICS.get(name, {})
        return OptimizationMetric(
            metric_name=name,
            current_value=value,
            target_value=info.get("target", 0.80),
            baseline_value=info.get("baseline", 0.50),
            source=source or info.get("source", ""),
            trend=TrendDirection.UNKNOWN,
            severity=MetricSeverity.NORMAL,
        )

    # ── Trend & Severity ────────────────────────────────────────

    def _update_trend_and_severity(self, metric: OptimizationMetric) -> None:
        """更新趋势和严重程度."""
        history = self._history.get(metric.metric_name, [])
        if len(history) < 3:
            metric.trend = TrendDirection.UNKNOWN
            metric.severity = MetricSeverity.NORMAL
            return

        # 取最近 5 个点计算趋势
        recent = history[-5:]
        values = [p["value"] for p in recent]

        # 简单线性回归判断趋势
        n = len(values)
        if n < 2:
            metric.trend = TrendDirection.UNKNOWN
        else:
            x_mean = sum(range(n)) / n
            y_mean = sum(values) / n
            numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            if denominator == 0:
                slope = 0.0
            else:
                slope = numerator / denominator

            if slope > 0.01:
                metric.trend = TrendDirection.IMPROVING
            elif slope < -0.01:
                metric.trend = TrendDirection.DECLINING
            else:
                metric.trend = TrendDirection.STABLE

        # 计算严重程度
        gap = metric.gap()
        if gap <= 0:
            metric.severity = MetricSeverity.GOOD
        elif gap < 0.2:
            metric.severity = MetricSeverity.NORMAL
        elif gap < 0.5:
            metric.severity = MetricSeverity.WARNING
        else:
            metric.severity = MetricSeverity.CRITICAL

    # ── Collect ─────────────────────────────────────────────────

    def collect_metrics(self) -> list[OptimizationMetric]:
        """收集所有指标."""
        return list(self._metrics.values())

    def get_metric(self, name: str) -> OptimizationMetric | None:
        """获取指定指标."""
        return self._metrics.get(name)

    def get_degraded(self) -> list[OptimizationMetric]:
        """获取已退化的指标."""
        return [m for m in self._metrics.values() if m.is_degraded()]

    def get_history(self, metric_name: str) -> list[dict[str, Any]]:
        """获取指标历史."""
        return list(self._history.get(metric_name, []))

    def get_summary(self) -> dict[str, Any]:
        """获取摘要."""
        metrics = self.collect_metrics()
        return {
            "total_metrics": len(metrics),
            "degraded_count": len(self.get_degraded()),
            "avg_gap": sum(m.gap() for m in metrics) / len(metrics) if metrics else 0.0,
            "metrics": {m.metric_name: m.to_dict() for m in metrics},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self) -> None:
        """重置所有指标."""
        self._metrics.clear()
        self._history.clear()


__all__ = ["BUILTIN_METRICS", "PerformanceMonitor"]