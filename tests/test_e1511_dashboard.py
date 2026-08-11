"""E15.0.11 Dashboard 测试 — 仪表盘聚合器测试.

测试覆盖:
  - DashboardAggregator 创建
  - get_dashboard 完整聚合
  - 执行统计 (execution)
  - 审批统计 (approval)
  - 适配器统计 (adapter)
  - 告警统计 (alerts)
  - 追踪统计 (traces)
  - 各子 API 独立查询
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.observability.alerts import (
    AlertEngine,
    AlertRule,
    AlertSeverity,
)
from market_ops.creative_vision_runtime.growth_runtime.observability.dashboard import (
    DashboardAggregator,
)
from market_ops.creative_vision_runtime.growth_runtime.observability.events import (
    EventBus,
    ExecutionEventType,
)
from market_ops.creative_vision_runtime.growth_runtime.observability.metrics import (
    MetricsCollector,
)
from market_ops.creative_vision_runtime.growth_runtime.observability.tracer import (
    SpanStatus,
    TraceManager,
)


class TestDashboardAggregator:
    """DashboardAggregator 单元测试."""

    def setup_method(self):
        self.bus = EventBus()
        self.metrics = MetricsCollector()
        self.alerts = AlertEngine(collector=self.metrics)
        self.tracer = TraceManager()
        self.agg = DashboardAggregator(
            bus=self.bus,
            metrics=self.metrics,
            alerts=self.alerts,
            tracer=self.tracer,
        )

    # ── Creation ─────────────────────────────────────────────

    def test_create_with_defaults(self):
        agg = DashboardAggregator()
        assert agg.stats()["has_bus"] is True
        assert agg.stats()["has_metrics"] is True

    def test_create_with_all_components(self):
        agg = DashboardAggregator(
            bus=self.bus,
            metrics=self.metrics,
            alerts=self.alerts,
            tracer=self.tracer,
        )
        assert agg.stats()["has_bus"] is True
        assert agg.stats()["has_metrics"] is True
        assert agg.stats()["has_alerts"] is True
        assert agg.stats()["has_tracer"] is True

    def test_create_without_alerts_and_tracer(self):
        agg = DashboardAggregator(bus=self.bus, metrics=self.metrics)
        assert agg.stats()["has_alerts"] is False
        assert agg.stats()["has_tracer"] is False

    # ── Full Dashboard ───────────────────────────────────────

    def test_get_dashboard_structure(self):
        dashboard = self.agg.get_dashboard()
        assert "execution" in dashboard
        assert "approval" in dashboard
        assert "adapter" in dashboard
        assert "alerts" in dashboard
        assert "traces" in dashboard

    def test_get_dashboard_without_alerts(self):
        agg = DashboardAggregator(bus=self.bus, metrics=self.metrics)
        dashboard = agg.get_dashboard()
        assert dashboard["alerts"]["active"] == 0

    def test_get_dashboard_without_tracer(self):
        agg = DashboardAggregator(bus=self.bus, metrics=self.metrics)
        dashboard = agg.get_dashboard()
        assert dashboard["traces"]["total_traces"] == 0

    # ── Execution Section ────────────────────────────────────

    def test_execution_summary(self):
        self.metrics.increment("execution_total", 100)
        self.metrics.increment("execution_success", 95)
        self.metrics.increment("execution_failed", 5)

        summary = self.agg.get_execution_summary()
        assert summary["total"] == 100
        assert summary["success"] == 95
        assert summary["failed"] == 5
        assert summary["success_rate"] == 0.95

    def test_execution_summary_zero_total(self):
        summary = self.agg.get_execution_summary()
        assert summary["total"] == 0
        assert summary["success_rate"] == 0.0

    def test_execution_duration_included(self):
        self.metrics.observe("execution_duration_ms", 100)
        self.metrics.observe("execution_duration_ms", 200)
        summary = self.agg.get_execution_summary()
        assert summary["duration"]["count"] == 2
        assert summary["duration"]["avg"] == 150.0

    def test_execution_blocked(self):
        self.metrics.increment("execution_blocked", 3)
        summary = self.agg.get_execution_summary()
        assert summary["blocked"] == 3

    # ── Approval Section ─────────────────────────────────────

    def test_approval_summary(self):
        self.metrics.set_gauge("pending_approval_count", 12)
        self.metrics.increment("approval_approved", 50)
        self.metrics.increment("approval_rejected", 5)
        self.metrics.increment("approval_expired", 2)

        summary = self.agg.get_approval_summary()
        assert summary["pending"] == 12
        assert summary["approved"] == 50
        assert summary["rejected"] == 5
        assert summary["expired"] == 2

    def test_approval_rate(self):
        self.metrics.increment("approval_approved", 90)
        self.metrics.increment("approval_rejected", 10)
        summary = self.agg.get_approval_summary()
        assert summary["approval_rate"] == 0.9

    def test_approval_wait_time(self):
        self.metrics.observe("approval_wait_time_ms", 5000)
        self.metrics.observe("approval_wait_time_ms", 10000)
        summary = self.agg.get_approval_summary()
        assert summary["wait_time_ms"]["count"] == 2

    # ── Adapter Section ──────────────────────────────────────

    def test_adapter_summary(self):
        self.metrics.increment("adapter_success", 8, labels={"adapter": "meta"})
        self.metrics.increment("adapter_total", 10, labels={"adapter": "meta"})
        self.metrics.observe("adapter_latency_ms", 100, labels={"adapter": "meta"})

        summary = self.agg.get_adapter_summary()
        assert "meta" in summary
        assert summary["meta"]["success_rate"] == 0.8
        assert summary["meta"]["latency"]["count"] == 1

    def test_adapter_summary_empty(self):
        summary = self.agg.get_adapter_summary()
        assert isinstance(summary, dict)

    # ── Alerts Section ───────────────────────────────────────

    def test_alerts_summary(self):
        self.alerts.add_rule(
            AlertRule(name="r1", metric="m1", threshold=0, operator=">", severity=AlertSeverity.CRITICAL)
        )
        self.metrics.increment("m1", 1)
        self.alerts.check()

        summary = self.agg.get_alert_summary()
        assert summary["active"] == 1
        assert summary["rules"] == 1
        assert summary["by_severity"]["critical"] == 1

    def test_alerts_summary_no_alerts_engine(self):
        agg = DashboardAggregator(bus=self.bus, metrics=self.metrics)
        summary = agg.get_alert_summary()
        assert summary["active"] == 0
        assert summary["rules"] == 0

    # ── Traces Section ───────────────────────────────────────

    def test_traces_summary(self):
        ctx = self.tracer.start_trace()
        span = self.tracer.start_span(ctx, "test")
        self.tracer.finish_span(span, SpanStatus.SUCCESS)

        summary = self.agg.get_trace_summary()
        assert summary["total_traces"] == 1
        assert summary["total_spans"] == 1

    def test_traces_summary_no_tracer(self):
        agg = DashboardAggregator(bus=self.bus, metrics=self.metrics)
        summary = agg.get_trace_summary()
        assert summary["total_traces"] == 0

    # ── Sub-APIs ─────────────────────────────────────────────

    def test_get_execution_summary(self):
        summary = self.agg.get_execution_summary()
        assert "total" in summary
        assert "success" in summary
        assert "failed" in summary

    def test_get_approval_summary(self):
        summary = self.agg.get_approval_summary()
        assert "pending" in summary
        assert "approved" in summary

    def test_get_adapter_summary(self):
        summary = self.agg.get_adapter_summary()
        assert isinstance(summary, dict)

    def test_get_alert_summary(self):
        summary = self.agg.get_alert_summary()
        assert "active" in summary

    def test_get_trace_summary(self):
        summary = self.agg.get_trace_summary()
        assert "total_traces" in summary

    # ── Integration ──────────────────────────────────────────

    def test_integration_all_components(self):
        """集成测试: 所有组件协同工作."""
        # 模拟一次完整执行
        self.metrics.increment("execution_total", 152)
        self.metrics.increment("execution_success", 145)
        self.metrics.increment("execution_failed", 7)

        self.metrics.set_gauge("pending_approval_count", 12)

        self.metrics.increment("adapter_success", 98, labels={"adapter": "meta"})
        self.metrics.increment("adapter_total", 100, labels={"adapter": "meta"})
        self.metrics.observe("adapter_latency_ms", 320, labels={"adapter": "meta"})

        self.alerts.add_rule(
            AlertRule(name="r1", metric="execution_failed_rate", threshold=0.04, operator=">")
        )
        self.alerts.check()

        ctx = self.tracer.start_trace()
        span = self.tracer.start_span(ctx, "execution")
        self.tracer.finish_span(span)

        dashboard = self.agg.get_dashboard()

        assert dashboard["execution"]["total"] == 152
        assert dashboard["execution"]["success"] == 145
        assert dashboard["execution"]["failed"] == 7
        assert dashboard["execution"]["success_rate"] == pytest.approx(0.9539, 0.01)

        assert dashboard["approval"]["pending"] == 12

        assert dashboard["adapter"]["meta"]["success_rate"] == 0.98

        assert dashboard["alerts"]["active"] == 1
        assert dashboard["traces"]["total_traces"] == 1