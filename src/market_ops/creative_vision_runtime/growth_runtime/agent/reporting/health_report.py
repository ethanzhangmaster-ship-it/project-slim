"""E13.7.4.4 Health Report — 健康报告生成器.

健康报告汇总 Agent 运行状态:
  - 当前健康状态 (HEALTHY/WARNING/DEGRADED/SAFE_MODE/FAILED)
  - 多维指标 (Runtime / Decision / Execution / Tool)
  - 触发规则 (哪些规则异常)
  - 告警状态 (活跃告警)
  - 建议 (Recommendations)

连接:
  - E13.7.4.3 Health Monitor: 健康数据源
  - E13.7.4.3 Alert Manager: 告警数据源
"""

from __future__ import annotations

from .report_models import (
    ReportSection,
    ReportMetric,
    ReportType,
)


# ═══════════════════════════════════════════════════════════════
# HealthReportBuilder
# ═══════════════════════════════════════════════════════════════


class HealthReportBuilder:
    """健康报告生成器.

    使用方式:
        builder = HealthReportBuilder()
        builder.set_status("WARNING")
        builder.add_runtime_metrics(cycle_count=100, ...)
        builder.add_triggered_rules(["execution_failure", ...])
        builder.add_recommendation("暂停自动执行")
        section = builder.build()
    """

    def __init__(self):
        self._status: str = "healthy"
        self._previous_status: str = ""
        self._status_changed: bool = False
        self._runtime_metrics: dict[str, float] = {}
        self._decision_metrics: dict[str, float] = {}
        self._execution_metrics: dict[str, float] = {}
        self._tool_metrics: dict[str, float] = {}
        self._triggered_rules: list[str] = []
        self._warnings: list[str] = []
        self._errors: list[str] = []
        self._recommendations: list[str] = []
        self._active_alerts: int = 0
        self._critical_alerts: int = 0

    def set_status(
        self,
        status: str,
        previous_status: str = "",
        status_changed: bool = False,
    ) -> "HealthReportBuilder":
        """设置健康状态."""
        self._status = status
        self._previous_status = previous_status
        self._status_changed = status_changed
        return self

    def add_runtime_metrics(self, **kwargs: float) -> "HealthReportBuilder":
        """添加运行时指标."""
        self._runtime_metrics.update(kwargs)
        return self

    def add_decision_metrics(self, **kwargs: float) -> "HealthReportBuilder":
        """添加决策指标."""
        self._decision_metrics.update(kwargs)
        return self

    def add_execution_metrics(self, **kwargs: float) -> "HealthReportBuilder":
        """添加执行指标."""
        self._execution_metrics.update(kwargs)
        return self

    def add_tool_metrics(self, **kwargs: float) -> "HealthReportBuilder":
        """添加工具指标."""
        self._tool_metrics.update(kwargs)
        return self

    def add_triggered_rules(self, rules: list[str]) -> "HealthReportBuilder":
        """添加触发的规则."""
        self._triggered_rules.extend(rules)
        return self

    def add_warnings(self, warnings: list[str]) -> "HealthReportBuilder":
        """添加警告信息."""
        self._warnings.extend(warnings)
        return self

    def add_errors(self, errors: list[str]) -> "HealthReportBuilder":
        """添加错误信息."""
        self._errors.extend(errors)
        return self

    def add_recommendation(self, recommendation: str) -> "HealthReportBuilder":
        """添加建议."""
        self._recommendations.append(recommendation)
        return self

    def set_alerts(self, active: int = 0, critical: int = 0) -> "HealthReportBuilder":
        """设置告警计数."""
        self._active_alerts = active
        self._critical_alerts = critical
        return self

    def build(self) -> ReportSection:
        """构建 ReportSection."""
        content_lines = []

        # 状态头
        status_emoji = {
            "healthy": "🟢",
            "warning": "🟡",
            "degraded": "🟠",
            "safe_mode": "🔴",
            "failed": "⛔",
        }.get(self._status, "⚪")

        content_lines.append(f"### Status: {status_emoji} {self._status.upper()}")
        content_lines.append("")
        if self._status_changed:
            content_lines.append(f"> Changed from {self._previous_status} → {self._status}")
            content_lines.append("")

        # 告警
        if self._active_alerts > 0:
            content_lines.append(f"**Alerts**: {self._active_alerts} active ({self._critical_alerts} critical)")
            content_lines.append("")

        # 各维度指标
        for category, label, metrics in [
            ("Runtime", "Runtime Metrics", self._runtime_metrics),
            ("Decision", "Decision Metrics", self._decision_metrics),
            ("Execution", "Execution Metrics", self._execution_metrics),
            ("Tool", "Tool Metrics", self._tool_metrics),
        ]:
            if metrics:
                content_lines.append(f"#### {label}")
                content_lines.append("")
                content_lines.append("| Metric | Value |")
                content_lines.append("|--------|-------|")
                for name, value in metrics.items():
                    if isinstance(value, float) and value <= 1.0 and "rate" in name.lower():
                        content_lines.append(f"| {name} | {value:.1%} |")
                    else:
                        content_lines.append(f"| {name} | {value:.2f} |")
                content_lines.append("")

        # 触发规则
        if self._triggered_rules:
            content_lines.append("#### Triggered Rules")
            content_lines.append("")
            for rule in self._triggered_rules:
                content_lines.append(f"- {rule}")
            content_lines.append("")

        # 警告和错误
        if self._warnings:
            content_lines.append("#### Warnings")
            content_lines.append("")
            for w in self._warnings:
                content_lines.append(f"- {w}")
            content_lines.append("")

        if self._errors:
            content_lines.append("#### Errors")
            content_lines.append("")
            for e in self._errors:
                content_lines.append(f"- {e}")
            content_lines.append("")

        # 建议
        if self._recommendations:
            content_lines.append("#### Recommendations")
            content_lines.append("")
            for r in self._recommendations:
                content_lines.append(f"- {r}")
            content_lines.append("")

        content = "\n".join(content_lines)

        # 聚合 metrics
        all_metrics: list[ReportMetric] = []
        for name, value in self._runtime_metrics.items():
            all_metrics.append(ReportMetric(name=f"runtime_{name}", value=value))
        for name, value in self._execution_metrics.items():
            all_metrics.append(ReportMetric(name=f"execution_{name}", value=value))
        for name, value in self._tool_metrics.items():
            all_metrics.append(ReportMetric(name=f"tool_{name}", value=value))
        for name, value in self._decision_metrics.items():
            all_metrics.append(ReportMetric(name=f"decision_{name}", value=value))

        # 摘要
        summary = f"Agent Health: {self._status.upper()}"
        if self._triggered_rules:
            summary += f" ({len(self._triggered_rules)} rules triggered)"
        if self._active_alerts:
            summary += f" | {self._active_alerts} alerts"

        # 置信度: 健康状态映射
        health_confidence = {
            "healthy": 1.0,
            "warning": 0.7,
            "degraded": 0.5,
            "safe_mode": 0.3,
            "failed": 0.0,
        }.get(self._status, 0.5)

        section = ReportSection(
            type=ReportType.HEALTH,
            title="Agent Health Summary",
            content=content,
            summary=summary,
            metrics=all_metrics,
            confidence=health_confidence,
        )

        return section


# ═══════════════════════════════════════════════════════════════
# Helper: Create Health Report from Health Monitor
# ═══════════════════════════════════════════════════════════════


def create_health_report(
    status: str,
    triggered_rules: list[str] | None = None,
    warnings: list[str] | None = None,
    recommendations: list[str] | None = None,
    active_alerts: int = 0,
    critical_alerts: int = 0,
    **metrics: dict[str, float],
) -> ReportSection:
    """快捷创建健康报告.

    Args:
        status: 健康状态
        triggered_rules: 触发的规则列表
        warnings: 警告列表
        recommendations: 建议列表
        active_alerts: 活跃告警数
        critical_alerts: 严重告警数
        **metrics: 各类指标 (runtime_metrics, decision_metrics, etc.)

    Returns:
        ReportSection: 健康报告 section
    """
    builder = HealthReportBuilder()
    builder.set_status(status)

    if triggered_rules:
        builder.add_triggered_rules(triggered_rules)
    if warnings:
        builder.add_warnings(warnings)
    if recommendations:
        for r in recommendations:
            builder.add_recommendation(r)

    builder.set_alerts(active=active_alerts, critical=critical_alerts)

    if "runtime_metrics" in metrics:
        builder.add_runtime_metrics(**metrics["runtime_metrics"])
    if "decision_metrics" in metrics:
        builder.add_decision_metrics(**metrics["decision_metrics"])
    if "execution_metrics" in metrics:
        builder.add_execution_metrics(**metrics["execution_metrics"])
    if "tool_metrics" in metrics:
        builder.add_tool_metrics(**metrics["tool_metrics"])

    return builder.build()