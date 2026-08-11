"""Phase 2.2A: Latency Monitor — subscribes to TaskFinished, records latency.

Subscribes to:
  - TaskFinished → reads task from core store, writes latency to obs store

Reads from core GenerationStore (read-only). Writes to ObservabilityStore.
Tracks:
  - Queue wait time (created_at → claim_time)
  - Generation time
  - Total time distribution
  - Percentile breakdown (P50/P90/P95/P99)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .event_bus import EventBus
from .events import TaskFinished
from .observability_store import ObservabilityStore


class LatencyMonitor:
    """Latency analysis — listens to Event Bus, read-only on core GenerationStore."""

    def __init__(self, core_store: Any, obs_store: ObservabilityStore,
                 bus: EventBus | None = None) -> None:
        self._core = core_store
        self._obs = obs_store
        if bus is not None:
            bus.subscribe(TaskFinished, self._on_task_finished)

    def _on_task_finished(self, event: TaskFinished) -> None:
        """Record latency for a completed task from core store."""
        task = self._core.get(event.task_id)
        if task is None or task["status"] != "SUCCESS":
            return

        queue_wait = 0
        generation = task.get("generation_time", 0) * 1000  # convert to ms
        total = generation

        try:
            if task.get("created_at") and task.get("claim_time"):
                created = datetime.fromisoformat(task["created_at"])
                claimed = datetime.fromisoformat(task["claim_time"])
                queue_wait = (claimed - created).total_seconds() * 1000
                total += queue_wait
        except (ValueError, TypeError):
            pass

        self._obs.record_latency(
            task_id=event.task_id,
            queue_wait_ms=queue_wait,
            generation_ms=generation,
            total_ms=total,
        )

    def record_task_latency(self, task_id: str) -> None:
        """Manual record (for backward compatibility, e.g. tests)."""
        task = self._core.get(task_id)
        if task is None or task["status"] != "SUCCESS":
            return

        queue_wait = 0
        generation = task.get("generation_time", 0) * 1000
        total = generation

        try:
            if task.get("created_at") and task.get("claim_time"):
                created = datetime.fromisoformat(task["created_at"])
                claimed = datetime.fromisoformat(task["claim_time"])
                queue_wait = (claimed - created).total_seconds() * 1000
                total += queue_wait
        except (ValueError, TypeError):
            pass

        self._obs.record_latency(
            task_id=task_id,
            queue_wait_ms=queue_wait,
            generation_ms=generation,
            total_ms=total,
        )

    def get_stats(self, hours: int = 24) -> dict[str, Any]:
        return self._obs.get_latency_stats(hours)

    def get_distribution(self, hours: int = 24) -> dict[str, Any]:
        """Get latency distribution with percentiles."""
        stats = self._obs.get_latency_stats(hours)
        return {
            "count": stats["count"],
            "avg_total_ms": stats["avg_total_ms"],
            "avg_generation_ms": stats["avg_generation_ms"],
            "avg_queue_wait_ms": stats["avg_queue_wait_ms"],
            "percentiles": stats.get("percentiles", {}),
        }