"""V4.4 Metrics Collector — latency, TPS, memory, GPU, queue metrics.

Collects and aggregates runtime performance metrics.
Supports: latency percentiles, throughput, resource usage, queue stats.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import RuntimeMetrics


class MetricsCollector:
    """Collects and aggregates runtime performance metrics."""

    def __init__(self, window_size: int = 100) -> None:
        self._window_size = window_size
        self._task_latencies: list[float] = []         # seconds
        self._task_completions: list[float] = []       # timestamps
        self._current_metrics = RuntimeMetrics()
        self._history: list[RuntimeMetrics] = []
        self._task_states: dict[str, str] = {}          # task_id → status
        self._resource_samples: list[dict[str, float]] = []

    def record_task_start(self, task_id: str, task_name: str = "") -> None:
        """Record a task starting execution."""
        self._task_states[task_id] = "running"

    def record_task_complete(self, task_id: str, latency: float) -> None:
        """Record a task completing successfully.

        Args:
            task_id: Task identifier.
            latency: Task execution time in seconds.
        """
        self._task_states[task_id] = "completed"
        self._task_latencies.append(latency)
        self._task_completions.append(time.time())

        # Trim to window size
        if len(self._task_latencies) > self._window_size:
            self._task_latencies = self._task_latencies[-self._window_size:]
        if len(self._task_completions) > self._window_size:
            self._task_completions = self._task_completions[-self._window_size:]

    def record_task_fail(self, task_id: str, error: str = "") -> None:
        """Record a task failing."""
        self._task_states[task_id] = "failed"

    def record_task_pending(self, task_id: str) -> None:
        """Record a task entering the pending state."""
        self._task_states[task_id] = "pending"

    def record_resource_usage(self, cpu: float = 0.0, gpu: float = 0.0,
                              memory: float = 0.0, disk: float = 0.0) -> None:
        """Record current resource usage."""
        self._resource_samples.append({
            "cpu": cpu,
            "gpu": gpu,
            "memory": memory,
            "disk": disk,
            "timestamp": time.time(),
        })
        if len(self._resource_samples) > self._window_size:
            self._resource_samples = self._resource_samples[-self._window_size:]

    def collect(self, queue_length: int = 0,
                queue_wait_time: float = 0.0) -> RuntimeMetrics:
        """Collect current metrics snapshot.

        Args:
            queue_length: Current task queue length.
            queue_wait_time: Average queue wait time in seconds.

        Returns:
            RuntimeMetrics snapshot.
        """
        # Task counts
        tasks_pending = sum(1 for s in self._task_states.values() if s == "pending")
        tasks_running = sum(1 for s in self._task_states.values() if s == "running")
        tasks_completed = sum(1 for s in self._task_states.values() if s == "completed")
        tasks_failed = sum(1 for s in self._task_states.values() if s == "failed")

        # Latency percentiles
        avg_latency = self._calc_avg_latency()
        p95_latency = self._calc_percentile(95)
        p99_latency = self._calc_percentile(99)

        # Throughput (tasks/sec over the window)
        throughput = self._calc_throughput()

        # Resource averages
        cpu_avg, gpu_avg, mem_avg, disk_avg = self._calc_resource_avg()

        metrics = RuntimeMetrics(
            timestamp=time.time(),
            tasks_pending=tasks_pending,
            tasks_running=tasks_running,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            avg_latency=avg_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            throughput=throughput,
            cpu_usage=cpu_avg,
            gpu_usage=gpu_avg,
            memory_usage=mem_avg,
            disk_usage=disk_avg,
            queue_length=queue_length,
            queue_wait_time=queue_wait_time,
        )

        self._current_metrics = metrics
        self._history.append(metrics)

        if len(self._history) > self._window_size:
            self._history = self._history[-self._window_size:]

        return metrics

    def get_current_metrics(self) -> RuntimeMetrics:
        """Get the latest metrics snapshot."""
        return self._current_metrics

    def get_history(self, limit: int = 50) -> list[RuntimeMetrics]:
        """Get metrics history."""
        return self._history[-limit:]

    def get_summary(self) -> dict[str, Any]:
        """Get a human-readable metrics summary."""
        m = self._current_metrics
        return {
            "tasks": {
                "pending": m.tasks_pending,
                "running": m.tasks_running,
                "completed": m.tasks_completed,
                "failed": m.tasks_failed,
                "success_rate": round(
                    m.tasks_completed / max(1, m.tasks_completed + m.tasks_failed) * 100, 1
                ),
            },
            "performance": {
                "avg_latency_ms": round(m.avg_latency * 1000, 1),
                "p95_latency_ms": round(m.p95_latency * 1000, 1),
                "p99_latency_ms": round(m.p99_latency * 1000, 1),
                "throughput_tps": round(m.throughput, 2),
            },
            "resources": {
                "cpu_pct": round(m.cpu_usage * 100, 1),
                "gpu_pct": round(m.gpu_usage * 100, 1),
                "memory_pct": round(m.memory_usage * 100, 1),
                "disk_pct": round(m.disk_usage * 100, 1),
            },
            "queue": {
                "length": m.queue_length,
                "wait_time_ms": round(m.queue_wait_time * 1000, 1),
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._task_latencies.clear()
        self._task_completions.clear()
        self._task_states.clear()
        self._resource_samples.clear()
        self._history.clear()
        self._current_metrics = RuntimeMetrics()

    # ── Internal calculations ──────────────────────────────

    def _calc_avg_latency(self) -> float:
        if not self._task_latencies:
            return 0.0
        return sum(self._task_latencies) / len(self._task_latencies)

    def _calc_percentile(self, pct: int) -> float:
        """Calculate latency percentile."""
        if not self._task_latencies:
            return 0.0
        sorted_latencies = sorted(self._task_latencies)
        index = int(len(sorted_latencies) * pct / 100)
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]

    def _calc_throughput(self) -> float:
        """Calculate throughput (tasks/sec) over the window."""
        if len(self._task_completions) < 2:
            return 0.0
        window_start = self._task_completions[0]
        window_end = self._task_completions[-1]
        duration = window_end - window_start
        if duration <= 0:
            return 0.0
        return (len(self._task_completions) - 1) / duration

    def _calc_resource_avg(self) -> tuple[float, float, float, float]:
        """Calculate average resource usage."""
        if not self._resource_samples:
            return 0.0, 0.0, 0.0, 0.0
        n = len(self._resource_samples)
        cpu_sum = sum(s["cpu"] for s in self._resource_samples)
        gpu_sum = sum(s["gpu"] for s in self._resource_samples)
        mem_sum = sum(s["memory"] for s in self._resource_samples)
        disk_sum = sum(s["disk"] for s in self._resource_samples)
        return cpu_sum / n, gpu_sum / n, mem_sum / n, disk_sum / n