"""E15.0.11 Dashboard Aggregator — 仪表盘数据聚合器.

提供系统状态聚合 API，回答:
  > 系统整体运行状态如何？

聚合来自 EventBus / MetricsCollector / AlertEngine / TraceManager 的数据，
输出统一 JSON 格式供 Dashboard 消费。

用法:
    agg = DashboardAggregator(bus=event_bus, metrics=collector, alerts=engine, tracer=tracer)
    dashboard = agg.get_dashboard()
    # -> {"execution": {...}, "approval": {...}, "adapter": {...}, "alerts": {...}, "traces": {...}}
"""

from __future__ import annotations

from typing import Any

from .alerts import AlertEngine
from .events import EventBus
from .metrics import MetricsCollector
from .tracer import TraceManager


# ═══════════════════════════════════════════════════════════════
# Dashboard Aggregator
# ═══════════════════════════════════════════════════════════════


class DashboardAggregator:
    """E15.0.11 仪表盘聚合器 — 聚合系统可观测性数据.

    用法:
        agg = DashboardAggregator(bus=event_bus, metrics=collector)
        dashboard = agg.get_dashboard()
        print(dashboard["execution"]["total"])
    """

    def __init__(
        self,
        bus: EventBus | None = None,
        metrics: MetricsCollector | None = None,
        alerts: AlertEngine | None = None,
        tracer: TraceManager | None = None,
    ):
        self._bus = bus or EventBus()
        self._metrics = metrics or MetricsCollector()
        self._alerts = alerts
        self._tracer = tracer

    # ── Dashboard Methods ────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """获取完整仪表盘数据.

        Returns:
            dict: 包含 execution / approval / adapter / alerts / traces 的聚合数据
        """
        return {
            "execution": self._get_execution_section(),
            "approval": self._get_approval_section(),
            "adapter": self._get_adapter_section(),
            "alerts": self._get_alerts_section(),
            "traces": self._get_traces_section(),
        }

    def get_execution_summary(self) -> dict[str, Any]:
        """仅获取执行摘要."""
        return self._get_execution_section()

    def get_approval_summary(self) -> dict[str, Any]:
        """仅获取审批摘要."""
        return self._get_approval_section()

    def get_adapter_summary(self) -> dict[str, Any]:
        """仅获取适配器摘要."""
        return self._get_adapter_section()

    def get_alert_summary(self) -> dict[str, Any]:
        """仅获取告警摘要."""
        return self._get_alerts_section()

    def get_trace_summary(self) -> dict[str, Any]:
        """仅获取追踪摘要."""
        return self._get_traces_section()

    # ── Section Builders ─────────────────────────────────────

    def _get_execution_section(self) -> dict[str, Any]:
        """构建执行统计部分."""
        total = self._metrics.get_counter("execution_total")
        success = self._metrics.get_counter("execution_success")
        failed = self._metrics.get_counter("execution_failed")
        blocked = self._metrics.get_counter("execution_blocked")

        success_rate = 0.0
        if total > 0:
            success_rate = round(success / total, 4)

        duration = self._metrics.get_histogram("execution_duration_ms")

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "blocked": blocked,
            "success_rate": success_rate,
            "duration": duration,
        }

    def _get_approval_section(self) -> dict[str, Any]:
        """构建审批统计部分."""
        pending = self._metrics.get_gauge("pending_approval_count")
        approved = self._metrics.get_counter("approval_approved")
        rejected = self._metrics.get_counter("approval_rejected")
        expired = self._metrics.get_counter("approval_expired")

        total = approved + rejected + 0  # 不包含 pending
        approval_rate = round(approved / max(total, 1), 4)

        wait_time = self._metrics.get_histogram("approval_wait_time_ms")

        return {
            "pending": int(pending),
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
            "approval_rate": approval_rate,
            "wait_time_ms": wait_time,
        }

    def _get_adapter_section(self) -> dict[str, Any]:
        """构建适配器统计部分."""
        adapters: dict[str, Any] = {}

        # 从指标中提取各适配器数据
        # 遍历 histograms 查找按 adapter 标签分组的数据
        snapshot = self._metrics.snapshot()
        for key, hist_data in snapshot.get("histograms", {}).items():
            if key.startswith("adapter_latency_ms"):
                # 解析 adapter 名称
                adapter_name = "unknown"
                if "{" in key and "}" in key:
                    label_part = key[key.index("{") + 1:key.index("}")]
                    for pair in label_part.split(","):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            if k == "adapter":
                                adapter_name = v
                                break

                adapters[adapter_name] = {
                    "latency": hist_data,
                    "success_rate": self._get_adapter_success_rate(adapter_name),
                }

        return adapters

    def _get_alerts_section(self) -> dict[str, Any]:
        """构建告警统计部分."""
        if self._alerts is None:
            return {"active": 0, "by_severity": {}, "rules": 0}

        stats = self._alerts.stats()
        return {
            "active": stats["active_alerts"],
            "by_severity": stats["by_severity"],
            "by_state": stats["by_state"],
            "total_alerts": stats["total_alerts"],
            "rules": stats["total_rules"],
        }

    def _get_traces_section(self) -> dict[str, Any]:
        """构建追踪统计部分."""
        if self._tracer is None:
            return {"total_traces": 0, "total_spans": 0, "active_spans": 0}

        stats = self._tracer.stats()
        return {
            "total_traces": stats["total_traces"],
            "total_spans": stats["total_spans"],
            "active_spans": stats["active_spans"],
            "by_status": stats["by_status"],
        }

    # ── Helpers ──────────────────────────────────────────────

    def _get_adapter_success_rate(self, adapter_name: str) -> float:
        """计算特定适配器的成功率."""
        success = self._metrics.get_counter(
            "adapter_success", labels={"adapter": adapter_name}
        )
        total = self._metrics.get_counter(
            "adapter_total", labels={"adapter": adapter_name}
        )
        if total > 0:
            return round(success / total, 4)
        return 0.0

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "has_bus": self._bus is not None,
            "has_metrics": self._metrics is not None,
            "has_alerts": self._alerts is not None,
            "has_tracer": self._tracer is not None,
        }

    def __repr__(self) -> str:
        return (
            f"DashboardAggregator(bus={self._bus is not None}, "
            f"metrics={self._metrics is not None}, "
            f"alerts={self._alerts is not None}, "
            f"tracer={self._tracer is not None})"
        )


__all__ = ["DashboardAggregator"]