"""V4.4 Checkpoint Manager — save and resume execution state.

Ran halfway, machine lost power → resume from Checkpoint 287.
Auto-saves task states at configurable intervals.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import Checkpoint, RuntimeTask, TaskStatus


class CheckpointManager:
    """Checkpoint-based task execution recovery."""

    def __init__(self, enabled: bool = True, max_checkpoints: int = 10) -> None:
        self._enabled = enabled
        self._max_checkpoints = max_checkpoints
        self._checkpoints: dict[str, list[Checkpoint]] = {}  # workflow_id → [checkpoints]
        self._checkpoint_counter: int = 0

    def save(self, workflow_id: str, tasks: list[RuntimeTask],
             task_states: dict[str, Any] | None = None) -> Checkpoint:
        """Save a checkpoint of current execution state.

        Args:
            workflow_id: Workflow identifier.
            tasks: All tasks with their current states.
            task_states: Additional task state data.

        Returns:
            The created Checkpoint.
        """
        if not self._enabled:
            return Checkpoint()

        self._checkpoint_counter += 1
        checkpoint = Checkpoint(
            checkpoint_id=f"ckpt_{self._checkpoint_counter}",
            workflow_id=workflow_id,
            completed_tasks=[t.task_id for t in tasks if t.status == TaskStatus.COMPLETED],
            failed_tasks=[t.task_id for t in tasks if t.status == TaskStatus.FAILED],
            task_states=task_states or {},
            created_at=time.time(),
        )

        if workflow_id not in self._checkpoints:
            self._checkpoints[workflow_id] = []

        self._checkpoints[workflow_id].append(checkpoint)

        # Enforce max checkpoints
        if len(self._checkpoints[workflow_id]) > self._max_checkpoints:
            self._checkpoints[workflow_id] = self._checkpoints[workflow_id][-self._max_checkpoints:]

        return checkpoint

    def load(self, workflow_id: str) -> Checkpoint | None:
        """Load the latest checkpoint for a workflow.

        Returns:
            The latest Checkpoint, or None if none exists.
        """
        checkpoints = self._checkpoints.get(workflow_id, [])
        if checkpoints:
            return checkpoints[-1]
        return None

    def load_by_id(self, checkpoint_id: str) -> Checkpoint | None:
        """Load a specific checkpoint by ID."""
        for ckpts in self._checkpoints.values():
            for ckpt in ckpts:
                if ckpt.checkpoint_id == checkpoint_id:
                    return ckpt
        return None

    def get_checkpoint_count(self, workflow_id: str) -> int:
        """Get number of checkpoints for a workflow."""
        return len(self._checkpoints.get(workflow_id, []))

    def get_all_checkpoints(self, workflow_id: str) -> list[Checkpoint]:
        """Get all checkpoints for a workflow."""
        return list(self._checkpoints.get(workflow_id, []))

    def clear(self, workflow_id: str) -> None:
        """Clear all checkpoints for a workflow."""
        self._checkpoints.pop(workflow_id, None)

    def clear_all(self) -> None:
        """Clear all checkpoints."""
        self._checkpoints.clear()
        self._checkpoint_counter = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value