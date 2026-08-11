"""Phase 2.2A: Queue Observer — queue depth, wait times, oldest task.

Reads from core GenerationStore (read-only). Polled by Dashboard on demand.
No Event Bus subscription needed — stateless, reads current state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class QueueObserver:
    """Queue observability — read-only on core GenerationStore."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def depth(self) -> dict[str, int]:
        stats = self._store.get_stats()
        return {
            "pending": stats.get("pending_count", 0),
            "claim": stats.get("claim_count", 0),
            "processing": stats.get("processing_count", 0),
            "retry": stats.get("retry_count", 0),
            "failed": stats.get("failed_count", 0),
        }

    def oldest_pending(self) -> dict[str, Any] | None:
        pending = self._store.get_pending(limit=1)
        if not pending:
            return None
        task = pending[0]
        wait_seconds = 0
        try:
            created = datetime.fromisoformat(task["created_at"])
            wait_seconds = (datetime.now(timezone.utc) - created).total_seconds()
        except (ValueError, TypeError):
            pass
        return {
            "task_id": task["id"],
            "creative_id": task["creative_id"],
            "priority": task["priority"],
            "wait_seconds": round(wait_seconds, 1),
        }

    def wait_times(self) -> dict[str, float]:
        all_pending = self._store.get_pending(limit=1000)
        wait_times = []
        for t in all_pending:
            try:
                created = datetime.fromisoformat(t["created_at"])
                wait = (datetime.now(timezone.utc) - created).total_seconds()
                wait_times.append(wait)
            except (ValueError, TypeError):
                pass
        if not wait_times:
            return {"avg_wait": 0, "max_wait": 0, "count": 0}
        return {
            "avg_wait": round(sum(wait_times) / len(wait_times), 1),
            "max_wait": round(max(wait_times), 1),
            "count": len(wait_times),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "depth": self.depth(),
            "oldest_pending": self.oldest_pending(),
            "wait_times": self.wait_times(),
        }