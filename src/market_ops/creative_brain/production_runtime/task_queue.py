"""V4.4 Task Queue — unified task queue for all runtime tasks.

Priority-based queue with dependency resolution.
Supports: enqueue, dequeue, peek, cancel, status query.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .schemas import RuntimeTask, TaskStatus, TaskPriority


class TaskQueue:
    """Priority-based task queue with dependency awareness."""

    def __init__(self) -> None:
        self._tasks: dict[str, RuntimeTask] = {}  # task_id → task
        # Priority buckets
        self._queues: dict[TaskPriority, list[RuntimeTask]] = defaultdict(list)
        self._completed: set[str] = set()
        self._history: list[dict[str, Any]] = []

    def enqueue(self, task: RuntimeTask) -> None:
        """Add a task to the queue."""
        if task.task_id in self._tasks:
            return
        self._tasks[task.task_id] = task
        task.status = TaskStatus.QUEUED
        self._queues[task.priority].append(task)
        self._history.append({"action": "enqueue", "task_id": task.task_id})

    def enqueue_batch(self, tasks: list[RuntimeTask]) -> None:
        """Add multiple tasks to the queue."""
        for t in tasks:
            self.enqueue(t)

    def dequeue(self, worker_type: str = "") -> RuntimeTask | None:
        """Dequeue the highest priority task whose dependencies are met.

        Args:
            worker_type: Optional worker type filter.

        Returns:
            RuntimeTask or None if no ready task.
        """
        for priority in (TaskPriority.CRITICAL, TaskPriority.HIGH,
                          TaskPriority.NORMAL, TaskPriority.LOW):
            queue = self._queues[priority]
            for i, task in enumerate(queue):
                if self._dependencies_met(task):
                    if not worker_type or task.worker_type.value == worker_type:
                        queue.pop(i)
                        task.status = TaskStatus.RUNNING
                        self._history.append({"action": "dequeue", "task_id": task.task_id})
                        return task
        return None

    def peek(self, task_id: str) -> RuntimeTask | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def complete(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            self._completed.add(task_id)
            self._history.append({"action": "complete", "task_id": task_id})

    def fail(self, task_id: str, error: str = "") -> None:
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = error
            self._history.append({"action": "fail", "task_id": task_id, "error": error})

    def cancel(self, task_id: str) -> None:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            self._history.append({"action": "cancel", "task_id": task_id})

    def retry(self, task_id: str) -> None:
        """Re-queue a failed task for retry."""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.FAILED:
            task.status = TaskStatus.RETRYING
            task.retry_count += 1
            self._queues[task.priority].append(task)
            self._history.append({"action": "retry", "task_id": task_id})

    def _dependencies_met(self, task: RuntimeTask) -> bool:
        """Check if all task dependencies are completed."""
        return all(dep in self._completed for dep in task.dependencies)

    def get_pending_count(self) -> int:
        """Get total pending tasks."""
        return sum(
            1 for t in self._tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RETRYING)
        )

    def get_status_counts(self) -> dict[str, int]:
        """Get task counts by status."""
        counts: dict[str, int] = {}
        for t in self._tasks.values():
            counts[t.status.value] = counts.get(t.status.value, 0) + 1
        return counts

    def get_queue_length(self) -> int:
        """Get total queued tasks."""
        return sum(len(q) for q in self._queues.values())

    def get_all_tasks(self) -> list[RuntimeTask]:
        """Get all tasks."""
        return list(self._tasks.values())

    def clear(self) -> None:
        """Clear all tasks."""
        self._tasks.clear()
        self._queues.clear()
        self._completed.clear()
        self._history.clear()