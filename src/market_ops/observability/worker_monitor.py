"""Phase 2.2A: Worker Monitor — subscribes to Event Bus, tracks worker health.

Subscribes to:
  - WorkerRegistered → register in observability.db
  - WorkerHeartbeat   → update heartbeat timestamp
  - TaskFinished       → increment tasks_completed
  - TaskFailed         → increment tasks_failed

Read-only on core production data. All state in observability.db.
"""

from __future__ import annotations

from typing import Any

from .event_bus import EventBus
from .events import (
    WorkerRegistered,
    WorkerHeartbeat,
    TaskFinished,
    TaskFailed,
)
from .observability_store import ObservabilityStore


class WorkerMonitor:
    """Heartbeat-based worker health monitor. Listens to Event Bus."""

    HEARTBEAT_INTERVAL = 10   # seconds between heartbeats
    OFFLINE_THRESHOLD = 30    # seconds without heartbeat = offline

    def __init__(self, store: ObservabilityStore, bus: EventBus | None = None) -> None:
        self._store = store
        self._bus = bus
        if bus is not None:
            self._subscribe(bus)

    def _subscribe(self, bus: EventBus) -> None:
        """Subscribe to relevant events on the bus."""
        bus.subscribe(WorkerRegistered, self._on_worker_registered)
        bus.subscribe(WorkerHeartbeat, self._on_heartbeat)
        bus.subscribe(TaskFinished, self._on_task_finished)
        bus.subscribe(TaskFailed, self._on_task_failed)

    # ── Event handlers ──

    def _on_worker_registered(self, event: WorkerRegistered) -> None:
        self._store.register_worker(event.worker_id)

    def _on_heartbeat(self, event: WorkerHeartbeat) -> None:
        self._store.heartbeat(
            event.worker_id, event.status,
            event.current_task, event.last_error,
        )

    def _on_task_finished(self, event: TaskFinished) -> None:
        self._store.increment_completed(event.worker_id)

    def _on_task_failed(self, event: TaskFailed) -> None:
        self._store.increment_failed(event.worker_id)

    # ── Public API (for dashboard) ──

    def get_all_workers(self) -> list[dict[str, Any]]:
        return self._store.get_workers()

    def get_offline_workers(self) -> list[str]:
        workers = self._store.get_workers()
        return [w["worker_id"] for w in workers if not w.get("online", False)]

    def summary(self) -> dict[str, Any]:
        workers = self.get_all_workers()
        online = sum(1 for w in workers if w.get("online", False))
        statuses = {}
        for w in workers:
            statuses[w["status"]] = statuses.get(w["status"], 0) + 1
        return {
            "total": len(workers),
            "online": online,
            "offline": len(workers) - online,
            "statuses": statuses,
            "workers": workers,
        }