"""E15.0.11 Metrics 测试 — 指标收集器测试.

测试覆盖:
  - Counter 创建/递增/重置
  - Gauge 设置/增减/重置
  - Histogram 记录/百分位/快照
  - MetricsCollector 多线程安全
  - 标签支持
  - 快照完整性
"""

from __future__ import annotations

import math
import threading

import pytest

from market_ops.creative_vision_runtime.growth_runtime.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
)


class TestCounter:
    """Counter 单元测试."""

    def test_create_counter(self):
        c = Counter(name="test_total")
        assert c.name == "test_total"
        assert c.value == 0

    def test_inc(self):
        c = Counter(name="test_total")
        c.inc()
        assert c.value == 1
        c.inc(5)
        assert c.value == 6

    def test_reset(self):
        c = Counter(name="test_total", value=100)
        c.reset()
        assert c.value == 0

    def test_labels(self):
        c = Counter(name="test_total", labels={"adapter": "meta"})
        assert c.labels["adapter"] == "meta"


class TestGauge:
    """Gauge 单元测试."""

    def test_set_get(self):
        g = Gauge(name="pending_count")
        g.set(42)
        assert g.get() == 42

    def test_inc_dec(self):
        g = Gauge(name="running_jobs")
        g.set(10)
        g.inc(5)
        assert g.get() == 15
        g.dec(3)
        assert g.get() == 12

    def test_reset(self):
        g = Gauge(name="running_jobs", value=99)
        g.reset()
        assert g.get() == 0.0


class TestHistogram:
    """Histogram 单元测试."""

    def test_observe(self):
        h = Histogram(name="latency_ms")
        h.observe(100)
        h.observe(200)
        h.observe(300)
        assert h.count == 3
        assert h.sum == 600
        assert h.min == 100
        assert h.max == 300

    def test_avg(self):
        h = Histogram(name="latency_ms")
        h.observe(100)
        h.observe(200)
        assert h.avg() == 150.0

    def test_empty_avg(self):
        h = Histogram(name="latency_ms")
        assert h.avg() == 0.0

    def test_percentiles(self):
        h = Histogram(name="latency_ms")
        for i in range(1, 101):
            h.observe(i)
        assert h.p50() == 51  # index 50 of 0-indexed list[1..100] = 51
        assert h.p90() == 91
        assert h.p95() == 96
        assert h.p99() == 100

    def test_single_value_percentile(self):
        h = Histogram(name="latency_ms")
        h.observe(42)
        assert h.p50() == 42
        assert h.p99() == 42

    def test_snapshot(self):
        h = Histogram(name="latency_ms")
        h.observe(100)
        h.observe(200)
        snap = h.snapshot()
        assert snap["count"] == 2
        assert snap["sum"] == 300
        assert snap["avg"] == 150.0
        assert snap["min"] == 100
        assert snap["max"] == 200

    def test_reset(self):
        h = Histogram(name="latency_ms")
        h.observe(100)
        h.reset()
        assert h.count == 0
        assert h.sum == 0.0
        assert h.min == float("inf")
        assert h.max == float("-inf")

    def test_default_min_max_in_snapshot(self):
        h = Histogram(name="latency_ms")
        snap = h.snapshot()
        assert snap["min"] == 0
        assert snap["max"] == 0


class TestMetricsCollector:
    """MetricsCollector 单元测试."""

    def setup_method(self):
        self.collector = MetricsCollector()

    # ── Counter ──────────────────────────────────────────────

    def test_increment(self):
        self.collector.increment("execution_total")
        self.collector.increment("execution_total")
        assert self.collector.get_counter("execution_total") == 2

    def test_increment_with_amount(self):
        self.collector.increment("execution_total", amount=10)
        assert self.collector.get_counter("execution_total") == 10

    def test_increment_with_labels(self):
        self.collector.increment("execution_total", labels={"adapter": "meta"})
        self.collector.increment("execution_total", labels={"adapter": "max"})
        assert self.collector.get_counter("execution_total", {"adapter": "meta"}) == 1
        assert self.collector.get_counter("execution_total", {"adapter": "max"}) == 1

    def test_get_counter_nonexistent(self):
        assert self.collector.get_counter("nonexistent") == 0

    def test_multiple_counters(self):
        self.collector.increment("execution_total", 5)
        self.collector.increment("execution_failed", 2)
        self.collector.increment("execution_success", 3)
        assert self.collector.get_counter("execution_total") == 5
        assert self.collector.get_counter("execution_failed") == 2
        assert self.collector.get_counter("execution_success") == 3

    # ── Gauge ────────────────────────────────────────────────

    def test_set_gauge(self):
        self.collector.set_gauge("pending_approval_count", 12)
        assert self.collector.get_gauge("pending_approval_count") == 12

    def test_inc_gauge(self):
        self.collector.set_gauge("running_jobs", 5)
        self.collector.inc_gauge("running_jobs", 3)
        assert self.collector.get_gauge("running_jobs") == 8

    def test_dec_gauge(self):
        self.collector.set_gauge("running_jobs", 10)
        self.collector.dec_gauge("running_jobs", 4)
        assert self.collector.get_gauge("running_jobs") == 6

    def test_gauge_with_labels(self):
        self.collector.set_gauge("adapter_health", 1.0, labels={"adapter": "meta"})
        self.collector.set_gauge("adapter_health", 0.5, labels={"adapter": "max"})
        assert self.collector.get_gauge("adapter_health", {"adapter": "meta"}) == 1.0
        assert self.collector.get_gauge("adapter_health", {"adapter": "max"}) == 0.5

    def test_get_gauge_nonexistent(self):
        assert self.collector.get_gauge("nonexistent") == 0.0

    # ── Histogram ────────────────────────────────────────────

    def test_observe(self):
        self.collector.observe("execution_duration_ms", 100)
        self.collector.observe("execution_duration_ms", 200)
        self.collector.observe("execution_duration_ms", 300)
        snap = self.collector.get_histogram("execution_duration_ms")
        assert snap["count"] == 3
        assert snap["avg"] == 200.0

    def test_observe_with_labels(self):
        self.collector.observe("adapter_latency_ms", 100, labels={"adapter": "meta"})
        self.collector.observe("adapter_latency_ms", 200, labels={"adapter": "meta"})
        snap = self.collector.get_histogram("adapter_latency_ms", {"adapter": "meta"})
        assert snap["count"] == 2

    def test_get_histogram_nonexistent(self):
        assert self.collector.get_histogram("nonexistent") == {}

    # ── Snapshot ─────────────────────────────────────────────

    def test_snapshot(self):
        self.collector.increment("execution_total", 10)
        self.collector.set_gauge("pending_count", 5)
        self.collector.observe("latency_ms", 100)

        snap = self.collector.snapshot()
        assert "counters" in snap
        assert "gauges" in snap
        assert "histograms" in snap
        assert "summary" in snap
        assert snap["summary"]["total_counters"] >= 1
        assert snap["summary"]["total_gauges"] >= 1
        assert snap["summary"]["total_histograms"] >= 1

    def test_snapshot_counter_structure(self):
        self.collector.increment("execution_total", 42)
        snap = self.collector.snapshot()
        key = "execution_total"
        assert snap["counters"][key]["value"] == 42

    def test_snapshot_gauge_structure(self):
        self.collector.set_gauge("pending_count", 7)
        snap = self.collector.snapshot()
        key = "pending_count"
        assert snap["gauges"][key]["value"] == 7

    # ── Reset ────────────────────────────────────────────────

    def test_reset(self):
        self.collector.increment("execution_total", 10)
        self.collector.set_gauge("pending_count", 5)
        self.collector.observe("latency_ms", 100)
        self.collector.reset()

        assert self.collector.get_counter("execution_total") == 0
        assert self.collector.get_gauge("pending_count") == 0.0
        assert self.collector.get_histogram("latency_ms") == {}

    # ── Thread Safety ────────────────────────────────────────

    def test_thread_safety(self):
        errors: list[Exception] = []

        def worker():
            try:
                for i in range(100):
                    self.collector.increment("concurrent")
                    self.collector.set_gauge("concurrent_gauge", float(i))
                    self.collector.observe("concurrent_latency", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert self.collector.get_counter("concurrent") == 500

    def test_thread_safety_snapshot_during_writes(self):
        """snapshot 期间写入不应导致数据损坏."""
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(100):
                    self.collector.increment("concurrent")
                    self.collector.observe("concurrent_latency", float(i))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    self.collector.snapshot()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    # ── Key uniqueness ───────────────────────────────────────

    def test_key_uniqueness_with_labels(self):
        """相同 name 不同 labels 应产生不同的 key."""
        self.collector.increment("api_calls", labels={"adapter": "meta"})
        self.collector.increment("api_calls", labels={"adapter": "max"})
        self.collector.increment("api_calls")

        assert self.collector.get_counter("api_calls", {"adapter": "meta"}) == 1
        assert self.collector.get_counter("api_calls", {"adapter": "max"}) == 1
        assert self.collector.get_counter("api_calls") == 1

    def test_key_label_order_independent(self):
        """标签顺序不应影响 key."""
        self.collector.increment("api_calls", labels={"adapter": "meta", "env": "prod"})
        self.collector.increment("api_calls", labels={"env": "prod", "adapter": "meta"})
        assert self.collector.get_counter("api_calls", {"adapter": "meta", "env": "prod"}) == 2