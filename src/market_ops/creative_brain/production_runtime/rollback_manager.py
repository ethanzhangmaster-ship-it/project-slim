"""V4.4 Rollback Manager — automatic rollback on failure.

Knowledge update failed → auto rollback v25 → v24.
No manual intervention needed.

Tracks state snapshots and restores on failure.
"""

from __future__ import annotations

import time
from typing import Any


class RollbackManager:
    """Automatic rollback on task failure."""

    def __init__(self) -> None:
        self._snapshots: dict[str, list[dict[str, Any]]] = {}  # workflow_id → [{state}]
        self._rollback_history: list[dict[str, Any]] = []
        self._active_rollbacks: set[str] = set()

    def snapshot(self, workflow_id: str, state: dict[str, Any]) -> None:
        """Take a snapshot of current state before execution.

        Args:
            workflow_id: Workflow identifier.
            state: Current state to preserve.
        """
        if workflow_id not in self._snapshots:
            self._snapshots[workflow_id] = []

        snapshot = {
            "state": state.copy(),
            "timestamp": time.time(),
            "version": len(self._snapshots[workflow_id]) + 1,
        }
        self._snapshots[workflow_id].append(snapshot)

    def rollback(self, workflow_id: str) -> dict[str, Any] | None:
        """Rollback to the last snapshot.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            The restored state, or None if no snapshot.
        """
        if workflow_id not in self._snapshots:
            return None

        snapshots = self._snapshots[workflow_id]
        if not snapshots:
            return None

        # Remove the failed snapshot (latest) and restore previous
        failed = snapshots.pop()
        if snapshots:
            restored = snapshots[-1]
        else:
            restored = failed  # No previous state, keep the failed one

        self._active_rollbacks.add(workflow_id)
        self._rollback_history.append({
            "workflow_id": workflow_id,
            "from_version": failed["version"],
            "to_version": restored["version"],
            "timestamp": time.time(),
        })

        return restored["state"]

    def rollback_to_version(self, workflow_id: str, version: int) -> dict[str, Any] | None:
        """Rollback to a specific version snapshot."""
        if workflow_id not in self._snapshots:
            return None

        for snap in self._snapshots[workflow_id]:
            if snap["version"] == version:
                self._rollback_history.append({
                    "workflow_id": workflow_id,
                    "to_version": version,
                    "timestamp": time.time(),
                })
                return snap["state"]
        return None

    def get_latest_snapshot(self, workflow_id: str) -> dict[str, Any] | None:
        """Get the latest snapshot without rolling back."""
        snapshots = self._snapshots.get(workflow_id, [])
        if snapshots:
            return snapshots[-1]["state"]
        return None

    def get_snapshot_count(self, workflow_id: str) -> int:
        """Get number of snapshots for a workflow."""
        return len(self._snapshots.get(workflow_id, []))

    def get_rollback_history(self) -> list[dict[str, Any]]:
        return list(self._rollback_history)

    def clear_workflow(self, workflow_id: str) -> None:
        """Clear all snapshots for a workflow."""
        self._snapshots.pop(workflow_id, None)
        self._active_rollbacks.discard(workflow_id)

    def is_in_rollback(self, workflow_id: str) -> bool:
        """Check if a workflow is currently in rollback."""
        return workflow_id in self._active_rollbacks