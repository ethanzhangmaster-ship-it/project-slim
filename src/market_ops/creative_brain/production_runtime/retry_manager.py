"""V4.4 Retry Manager — exponential backoff retry for failed tasks.

Facebook API 500 → retry, retry, retry with exponential backoff.
Configurable: max_retries, base_delay, max_delay, backoff_multiplier.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import RuntimeTask, TaskStatus


class RetryManager:
    """Exponential backoff retry manager."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_multiplier: float = 2.0) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self._retry_history: list[dict[str, Any]] = []

    def should_retry(self, task: RuntimeTask) -> bool:
        """Check if a task should be retried."""
        if task.status == TaskStatus.RETRYING:
            return task.retry_count < task.max_retries
        return task.status == TaskStatus.FAILED and task.retry_count < task.max_retries

    def get_delay(self, task: RuntimeTask) -> float:
        """Calculate retry delay with exponential backoff.

        delay = base_delay * (backoff_multiplier ^ retry_count)
        Capped at max_delay.
        """
        delay = self.base_delay * (self.backoff_multiplier ** task.retry_count)
        return min(delay, self.max_delay)

    def prepare_retry(self, task: RuntimeTask) -> RuntimeTask:
        """Prepare a task for retry.

        Returns the updated task.
        """
        if not self.should_retry(task):
            return task

        delay = self.get_delay(task)
        task.status = TaskStatus.RETRYING
        task.retry_count += 1

        self._retry_history.append({
            "task_id": task.task_id,
            "retry_count": task.retry_count,
            "delay": delay,
            "timestamp": time.time(),
        })

        return task

    def retry_with_backoff(self, task: RuntimeTask,
                           execute_fn) -> tuple[bool, Any]:
        """Execute a task with retry logic.

        Args:
            task: The task to execute.
            execute_fn: Callable(task) → (success, result).

        Returns:
            (success, result_or_error)
        """
        for attempt in range(task.max_retries + 1):
            try:
                success, result = execute_fn(task)
                if success:
                    return True, result
                if attempt < task.max_retries:
                    delay = self.get_delay(task)
                    time.sleep(delay)
                    task.retry_count += 1
            except Exception as e:
                if attempt < task.max_retries:
                    delay = self.get_delay(task)
                    time.sleep(delay)
                    task.retry_count += 1
                else:
                    return False, str(e)

        return False, f"Max retries ({task.max_retries}) exceeded"

    def get_retry_history(self) -> list[dict[str, Any]]:
        return list(self._retry_history)

    def get_stats(self) -> dict[str, Any]:
        """Get retry statistics."""
        return {
            "total_retries": len(self._retry_history),
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
        }