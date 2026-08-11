"""E15.0.11 Metrics Collector — 指标收集器.

支持三种指标类型:
  - Counter:   累计计数 (execution_total, error_total)
  - Gauge:     瞬时值 (pending_approval_count, running_jobs)
  - Histogram: 分布统计 (execution_duration_ms, adapter_latency_ms)

用法:
    collector = MetricsCollector()

    # Counter
    collector.increment("execution_total")
    collector.increment("execution_success_total", labels={"adapter": "meta"})

    # Gauge
    collector.set_gauge("pending_approval_count", 12)

    # Histogram
    collector.observe("execution_duration_ms", 320.0)

    # 查询
    collector.get("execution_total")  # -> 1
    collector.snapshot()  # -> 完整快照
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Counter
# ═══════════════════════════════════════════════════════════════


@dataclass
class Counter:
    """累计计数器 — 只增不减."""

    name: str
    value: int = 0
    labels: dict[str, str] = field(default_factory=dict)

    def inc(self, amount: int = 1) -> None:
        self.value += amount

    def get(self) -> int:
        return self.value

    def reset(self) -> None:
        self.value = 0

    def __repr__(self) -> str:
        return f"Counter({self.name}={self.value})"


# ═══════════════════════════════════════════════════════════════
# Gauge
# ═══════════════════════════════════════════════════════════════


@dataclass
class Gauge:
    """瞬时值 — 可增可减."""

    name: str
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        self.value = value

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        self.value -= amount

    def get(self) -> float:
        return self.value

    def reset(self) -> None:
        self.value = 0.0

    def __repr__(self) -> str:
        return f"Gauge({self.name}={self.value})"


# ═══════════════════════════════════════════════════════════════
# Histogram
# ═══════════════════════════════════════════════════════════════


@dataclass
class Histogram:
    """分布统计 — 记录值分布.

    Attributes:
        name:     指标名称
        values:   所有记录值
        count:    记录次数
        sum:      总和
        min:      最小值
        max:      最大值
        labels:   标签
    """

    name: str
    values: list[float] = field(default_factory=list)
    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    labels: dict[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        self.values.append(value)
        self.count += 1
        self.sum += value
        if value < self.min:
            self.min = value
        if value > self.max:
            self.max = value

    def avg(self) -> float:
        if self.count == 0:
            return 0.0
        return self.sum / self.count

    def p50(self) -> float:
        return self._percentile(50)

    def p90(self) -> float:
        return self._percentile(90)

    def p95(self) -> float:
        return self._percentile(95)

    def p99(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: float) -> float:
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = int(len(sorted_vals) * p / 100.0)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    def snapshot(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "sum": self.sum,
            "avg": self.avg(),
            "min": self.min if self.min != float("inf") else 0,
            "max": self.max if self.max != float("-inf") else 0,
            "p50": self.p50(),
            "p90": self.p90(),
            "p95": self.p95(),
            "p99": self.p99(),
        }

    def reset(self) -> None:
        self.values.clear()
        self.count = 0
        self.sum = 0.0
        self.min = float("inf")
        self.max = float("-inf")

    def __repr__(self) -> str:
        return f"Histogram({self.name}, count={self.count}, avg={self.avg():.1f})"


# ═══════════════════════════════════════════════════════════════
# Metrics Collector
# ═══════════════════════════════════════════════════════════════


class MetricsCollector:
    """E15.0.11 指标收集器 — 统一管理所有指标.

    线程安全: 使用 threading.Lock 保护并发访问.

    用法:
        collector = MetricsCollector()

        # Counter
        collector.increment("execution_total")
        collector.increment("execution_failed", labels={"reason": "timeout"})

        # Gauge
        collector.set_gauge("pending_approval_count", 12)
        collector.inc_gauge("running_jobs", 1)

        # Histogram
        collector.observe("execution_duration_ms", 320.0, labels={"adapter": "meta"})

        # 查询
        collector.snapshot()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    # ── Counter ──────────────────────────────────────────────

    def increment(
        self,
        name: str,
        amount: int = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """增加计数器.

        Args:
            name:   指标名称
            amount: 增量
            labels: 标签
        """
        with self._lock:
            key = self._key(name, labels)
            if key not in self._counters:
                self._counters[key] = Counter(name=name, labels=labels or {})
            self._counters[key].inc(amount)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> int:
        """获取计数器值."""
        with self._lock:
            key = self._key(name, labels)
            counter = self._counters.get(key)
            return counter.get() if counter else 0

    # ── Gauge ────────────────────────────────────────────────

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """设置瞬时值.

        Args:
            name:   指标名称
            value:  值
            labels: 标签
        """
        with self._lock:
            key = self._key(name, labels)
            if key not in self._gauges:
                self._gauges[key] = Gauge(name=name, labels=labels or {})
            self._gauges[key].set(value)

    def inc_gauge(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """增加瞬时值."""
        with self._lock:
            key = self._key(name, labels)
            if key not in self._gauges:
                self._gauges[key] = Gauge(name=name, labels=labels or {})
            self._gauges[key].inc(amount)

    def dec_gauge(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """减少瞬时值."""
        with self._lock:
            key = self._key(name, labels)
            if key not in self._gauges:
                self._gauges[key] = Gauge(name=name, labels=labels or {})
            self._gauges[key].dec(amount)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """获取瞬时值."""
        with self._lock:
            key = self._key(name, labels)
            gauge = self._gauges.get(key)
            return gauge.get() if gauge else 0.0

    # ── Histogram ────────────────────────────────────────────

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """记录分布值.

        Args:
            name:   指标名称
            value:  值
            labels: 标签
        """
        with self._lock:
            key = self._key(name, labels)
            if key not in self._histograms:
                self._histograms[key] = Histogram(name=name, labels=labels or {})
            self._histograms[key].observe(value)

    def get_histogram(self, name: str, labels: dict[str, str] | None = None) -> dict[str, Any]:
        """获取直方图快照."""
        with self._lock:
            key = self._key(name, labels)
            hist = self._histograms.get(key)
            return hist.snapshot() if hist else {}

    # ── Snapshot ─────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """获取完整指标快照."""
        with self._lock:
            counters = {
                k: {"value": c.value, "labels": c.labels}
                for k, c in self._counters.items()
            }
            gauges = {
                k: {"value": g.value, "labels": g.labels}
                for k, g in self._gauges.items()
            }
            histograms = {
                k: h.snapshot()
                for k, h in self._histograms.items()
            }

        return {
            "counters": counters,
            "gauges": gauges,
            "histograms": histograms,
            "summary": {
                "total_counters": len(counters),
                "total_gauges": len(gauges),
                "total_histograms": len(histograms),
            },
        }

    def reset(self) -> None:
        """重置所有指标."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    # ── Internal ─────────────────────────────────────────────

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def __repr__(self) -> str:
        return (
            f"MetricsCollector(counters={len(self._counters)}, "
            f"gauges={len(self._gauges)}, histograms={len(self._histograms)})"
        )


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsCollector",
]