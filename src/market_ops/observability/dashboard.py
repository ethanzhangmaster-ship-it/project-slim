"""Phase 2.2A Final: Generation Dashboard — reads only from SnapshotService.current.

Displays:
  - Queue status
  - Worker health
  - Production stats
  - Performance (latency percentiles)
  - Cost summary
  - Recent alerts

Reads from SnapshotService (cached aggregated view).
Dashboard is independent of individual observers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.generation_store import GenerationStore
from .observability_store import ObservabilityStore
from .observers.worker_observer import WorkerObserver
from .observers.queue_observer import QueueObserver
from .observers.latency_observer import LatencyObserver
from .snapshot_service import SnapshotService


class GenerationDashboard:
    """Unified real-time dashboard — reads only from SnapshotService."""

    def __init__(
        self,
        core_db: str | Path = "output/creative_analysis/generations.db",
        obs_db: str | Path = "output/creative_analysis/observability.db",
    ) -> None:
        self._core = GenerationStore(db_path=core_db)
        self._obs = ObservabilityStore(db_path=obs_db)
        self._worker_observer = WorkerObserver(store=self._obs)
        self._queue_observer = QueueObserver(store=self._core)
        self._latency_observer = LatencyObserver(core_store=self._core, obs_store=self._obs)
        self._snapshot = SnapshotService(
            core_store=self._core,
            obs_store=self._obs,
            worker_observer=self._worker_observer,
            latency_observer=self._latency_observer,
            queue_observer=self._queue_observer,
        )

    def render(self) -> str:
        """Render the full dashboard as a string."""
        snap = self._snapshot.current
        lines = []

        lines.append("=" * 65)
        lines.append("  LOVART PRODUCTION DASHBOARD")
        lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 65)

        # ── Queue ──
        q = snap["queue"]
        qd = q["depth"]
        p = snap["production"]
        lines.append("")
        lines.append("  Queue")
        lines.append("  ─" * 25)
        lines.append(f"  Pending : {qd['pending']:<8}  Claim   : {qd['claim']}")
        lines.append(f"  Running : {qd['processing']:<8}  Retry   : {qd['retry']}")
        lines.append(f"  Failed  : {qd['failed']:<8}  Success : {p['images']}")

        oldest = q.get("oldest_pending")
        if oldest:
            wait_m = oldest["wait_seconds"] / 60
            lines.append(f"  Oldest pending: {oldest['task_id'][:16]} ({wait_m:.1f}m)")

        # ── Workers ──
        w = snap["workers"]
        lines.append("")
        lines.append("  Workers")
        lines.append("  ─" * 25)
        for wk in w["workers"]:
            online_str = "ONLINE" if wk.get("online", False) else "OFFLINE"
            task_str = wk.get("current_task", "")[:20] or "-"
            lines.append(f"  {wk['worker_id']:<12} {online_str:<8} {wk['status']:<10} {task_str}")

        # ── Production ──
        lines.append("")
        lines.append("  Production")
        lines.append("  ─" * 25)
        lines.append(f"  Images         {p['images']}")
        lines.append(f"  Success Rate   {p['success_rate']:.1f}%")

        retry = p.get("retry_analysis", {})
        lines.append(f"  Retry Rate     {retry.get('retry_success_rate', 0):.1f}%")
        lines.append(f"  Failure Rate   {p['failure_rate']:.1f}%")

        # ── Performance ──
        perf = snap["performance"]
        lines.append("")
        lines.append("  Performance")
        lines.append("  ─" * 25)
        lines.append(f"  Avg Generation    {perf['avg_generation_time']:.1f}s")
        wait_times = q.get("wait_times", {})
        lines.append(f"  Avg Queue Wait    {wait_times.get('avg_wait', 0):.1f}s")
        lines.append(f"  Throughput        {snap['throughput'].get('images_per_hour', 0):.0f} images/hour")

        lat = perf["latency"]
        pct = lat.get("percentiles", {})
        if pct:
            lines.append(f"  Total Latency     P50={pct.get('p50', 0):.0f}ms P90={pct.get('p90', 0):.0f}ms P95={pct.get('p95', 0):.0f}ms")

        # ── Cost ──
        c = snap["cost"]
        lines.append("")
        lines.append("  Cost")
        lines.append("  ─" * 25)
        lines.append(f"  Total         ${c['total']:.2f}")
        lines.append(f"  Average/Image ${c['average']:.3f}")

        # ── Alerts ──
        alerts = snap["alerts"]
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
        """Take a full snapshot for trend analysis."""
        self._obs.snapshot_current_state(self._core.get_stats())

    @property
    def snapshot_service(self) -> SnapshotService:
        return self._snapshot