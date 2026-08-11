"""Phase 2.2A: Worker Observer — heartbeat tracking, offline detection.

Subscribes to:
  - WorkerRegistered → register in observability.db
  - WorkerHeartbeat   → update heartbeat timestamp
  - TaskFinished       → increment tasks_completed
  - TaskFailed         → increment tasks_failed

Single responsibility: worker health monitoring.
"""

from __future__ import annotations

from typing import Any

from ..event_bus import EventBus
from ..events import WorkerRegistered, WorkerHeartbeat, TaskFinished, TaskFailed
from ..observability_store import ObservabilityStore


class WorkerObserver:
    """Tracks worker health via Event Bus subscription."""

    HEARTBEAT_INTERVAL = 10
    OFFLINE_THRESHOLD = 30

    def __init__(self, store: ObservabilityStore) -> None:
        self._store = store

    def _subscribe(self, bus: EventBus) -> None:
        bus.subscribe(WorkerRegistered, self._on_worker_registered)
        bus.subscribe(WorkerHeartbeat, self._on_heartbeat)
        bus.subscribe(TaskFinished, self._on_task_finished)
        bus.subscribe(TaskFailed, self._on_task_failed)

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

    # ── Public API ──

    def get_all(self) -> list[dict[str, Any]]:
        return self._store.get_workers()

    def get_offline(self) -> list[str]:
        workers = self._store.get_workers()
        return [w["worker_id"] for w in workers if not w.get("online", False)]

    def summary(self) -> dict[str, Any]:
        workers = self.get_all()
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