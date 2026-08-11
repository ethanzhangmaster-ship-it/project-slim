"""Phase 2.2A Final: Snapshot Service — aggregated view with memory cache.

Dashboard reads only from SnapshotService, never from individual observers.
SnapshotService aggregates data from all observers and caches in memory.

Cache TTL: 0.5s (Dashboard refreshes at most 2x/sec).
Adding a new observer → only SnapshotService changes, Dashboard stays unchanged.
"""

from __future__ import annotations

import time
import threading
from typing import Any

from .observability_store import ObservabilityStore
from .observers.worker_observer import WorkerObserver
from .observers.queue_observer import QueueObserver
from .observers.latency_observer import LatencyObserver


class SnapshotService:
    """Unified read model with memory cache. Aggregates all observers."""

    CACHE_TTL = 0.5  # seconds

    def __init__(
        self,
        core_store: Any,
        obs_store: ObservabilityStore,
        worker_observer: WorkerObserver,
        latency_observer: LatencyObserver,
        queue_observer: QueueObserver,
    ) -> None:
        self._core = core_store
        self._obs = obs_store
        self._worker = worker_observer
        self._latency = latency_observer
        self._queue = queue_observer

        # Cache
        self._cache: dict[str, Any] | None = None
        self._cache_at: float = 0.0
        self._cache_lock = threading.Lock()

    def get_snapshot(self, force: bool = False) -> dict[str, Any]:
        """Return a complete snapshot. Uses cache unless force=True or TTL expired."""
        now = time.time()
        with self._cache_lock:
            if not force and self._cache is not None and (now - self._cache_at) < self.CACHE_TTL:
                return self._cache

        core = self._core.get_stats()
        snapshot = {
            "queue": self._queue.summary(),
            "workers": self._worker.summary(),
            "production": {
                "images": core["success_count"],
                "success_rate": core["success_rate"],
                "retry_analysis": core.get("retry_analysis", {}),
                "failure_rate": (core["failed_count"] / max(core["total"], 1) * 100),
            },
            "performance": {
                "avg_generation_time": core["avg_generation_time"],
                "latency": self._latency.get_stats(hours=24),
            },
            "cost": {
                "total": core["total_cost"],
                "average": core["total_cost"] / max(core["success_count"], 1),
            },
            "throughput": self._obs.get_throughput(hours=1),
            "alerts": self._obs.get_recent_alerts(limit=5),
        }

        with self._cache_lock:
            self._cache = snapshot
            self._cache_at = now

        return snapshot

    def invalidate(self) -> None:
        """Force next get_snapshot() to rebuild from scratch."""
        with self._cache_lock:
            self._cache = None
            self._cache_at = 0.0

    @property
    def current(self) -> dict[str, Any]:
        """Alias for get_snapshot()."""
        return self.get_snapshot()