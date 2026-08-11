"""Phase 2.2A: Generation Dashboard — unified real-time observability.

Displays:
  - Queue status (pending/claim/processing/retry/failed)
  - Worker health (online/offline, current task)
  - Production stats (success rate, throughput)
  - Performance (avg generation time, queue wait)
  - Cost summary
  - Recent alerts

Read-only on core production data. All state via observability.db.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..generation_store import GenerationStore
from .observability_store import ObservabilityStore
from .worker_monitor import WorkerMonitor
from .queue_metrics import QueueMetrics
from .latency_monitor import LatencyMonitor


class GenerationDashboard:
    """Unified real-time dashboard for Lovart production system."""

    def __init__(
        self,
        core_db: str | Path = "output/creative_analysis/generations.db",
        obs_db: str | Path = "output/creative_analysis/observability.db",
    ) -> None:
        self._core = GenerationStore(db_path=core_db)
        self._obs = ObservabilityStore(db_path=obs_db)
        self._worker = WorkerMonitor(store=self._obs)
        self._queue = QueueMetrics(store=self._core)
        self._latency = LatencyMonitor(core_store=self._core, obs_store=self._obs)

    def render(self) -> str:
        """Render the full dashboard as a string."""
        lines = []
        core = self._core.get_stats()
        queue_summary = self._queue.summary()
        worker_summary = self._worker.summary()
        latency_stats = self._latency.get_stats(hours=24)
        throughput = self._obs.get_throughput(hours=1)
        alerts = self._obs.get_recent_alerts(limit=5)

        # Header
        lines.append("=" * 65)
        lines.append("  LOVART PRODUCTION DASHBOARD")
        lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 65)

        # ── Queue ──
        lines.append("")
        lines.append("  Queue")
        lines.append("  ─" * 25)
        depth = queue_summary["depth"]
        lines.append(f"  Pending : {depth['pending']:<8}  Claim   : {depth['claim']}")
        lines.append(f"  Running : {depth['processing']:<8}  Retry   : {depth['retry']}")
        lines.append(f"  Failed  : {depth['failed']:<8}  Success : {core['success_count']}")

        oldest = queue_summary.get("oldest_pending")
        if oldest:
            wait_m = oldest["wait_seconds"] / 60
            lines.append(f"  Oldest pending: {oldest['task_id'][:16]} ({wait_m:.1f}m)")

        # ── Workers ──
        lines.append("")
        lines.append("  Workers")
        lines.append("  ─" * 25)
        for w in worker_summary["workers"]:
            online_str = "ONLINE" if w.get("online", False) else "OFFLINE"
            task_str = w.get("current_task", "")[:20] or "-"
            lines.append(f"  {w['worker_id']:<12} {online_str:<8} {w['status']:<10} {task_str}")

        # ── Production ──
        lines.append("")
        lines.append("  Production")
        lines.append("  ─" * 25)
        lines.append(f"  Images         {core['success_count']}")
        lines.append(f"  Success Rate   {core['success_rate']:.1f}%")

        retry = core.get("retry_analysis", {})
        retry_rate = retry.get("retry_success_rate", 0)
        lines.append(f"  Retry Rate     {retry_rate:.1f}%")
        lines.append(f"  Failure Rate   {(core['failed_count'] / max(core['total'], 1) * 100):.1f}%")

        # ── Performance ──
        lines.append("")
        lines.append("  Performance")
        lines.append("  ─" * 25)
        lines.append(f"  Avg Generation    {core['avg_generation_time']:.1f}s")
        wait_times = queue_summary.get("wait_times", {})
        lines.append(f"  Avg Queue Wait    {wait_times.get('avg_wait', 0):.1f}s")
        lines.append(f"  Throughput        {throughput.get('images_per_hour', 0):.0f} images/hour")

        # Latency percentiles
        pct = latency_stats.get("percentiles", {})
        if pct:
            lines.append(f"  Total Latency     P50={pct.get('p50', 0):.0f}ms P90={pct.get('p90', 0):.0f}ms P95={pct.get('p95', 0):.0f}ms")

        # ── Cost ──
        lines.append("")
        lines.append("  Cost")
        lines.append("  ─" * 25)
        lines.append(f"  Total         ${core['total_cost']:.2f}")
        avg_cost = core["total_cost"] / max(core["success_count"], 1)
        lines.append(f"  Average/Image ${avg_cost:.3f}")

        # ── Alerts ──
        if alerts:
            lines.append("")
            lines.append("  Recent Alerts")
            lines.append("  ─" * 25)
            for a in alerts[:3]:
                sev = a["severity"][:4]
                lines.append(f"  [{sev}] {a['category']}: {a['message'][:50]}")

        lines.append("")
        lines.append("=" * 65)
        return "\n".join(lines)

    def snapshot(self) -> None:
        """Take a snapshot of current state for trend analysis."""
        core = self._core.get_stats()
        self._obs.snapshot_current_state(core)

    def worker(self) -> WorkerMonitor:
        return self._worker

    def queue(self) -> QueueMetrics:
        return self._queue

    def latency(self) -> LatencyMonitor:
        return self._latency