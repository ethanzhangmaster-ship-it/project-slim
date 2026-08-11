"""V4.4 Worker Pool — CPU/GPU/IO worker management.

Manages a pool of workers, assigns tasks based on worker type,
and tracks worker health and utilization.
"""

from __future__ import annotations

from typing import Any

from .schemas import Worker, RuntimeTask, WorkerType, WorkerStatus


class WorkerPool:
    """Worker pool for CPU, GPU, and IO tasks."""

    def __init__(self, cpu_workers: int = 4, gpu_workers: int = 2,
                 io_workers: int = 8) -> None:
        self._workers: dict[str, Worker] = {}
        self._max_concurrent = cpu_workers + gpu_workers + io_workers

        # Create workers
        for i in range(cpu_workers):
            wid = f"cpu_{i}"
            self._workers[wid] = Worker(worker_id=wid, worker_type=WorkerType.CPU)
        for i in range(gpu_workers):
            wid = f"gpu_{i}"
            self._workers[wid] = Worker(worker_id=wid, worker_type=WorkerType.GPU)
        for i in range(io_workers):
            wid = f"io_{i}"
            self._workers[wid] = Worker(worker_id=wid, worker_type=WorkerType.IO)

    def assign_task(self, task: RuntimeTask) -> Worker | None:
        """Assign a task to an available worker of the right type.

        Returns:
            Worker if assigned, None if no worker available.
        """
        for worker in self._workers.values():
            if (worker.worker_type == task.worker_type and
                    worker.status == WorkerStatus.IDLE):
                worker.status = WorkerStatus.BUSY
                worker.current_task = task
                return worker
        return None

    def complete_task(self, worker_id: str, success: bool = True) -> None:
        """Mark a worker's task as complete."""
        worker = self._workers.get(worker_id)
        if worker:
            if success:
                worker.tasks_completed += 1
            else:
                worker.tasks_failed += 1
            worker.status = WorkerStatus.IDLE
            worker.current_task = None

    def get_available(self, worker_type: WorkerType | None = None) -> list[Worker]:
        """Get available workers, optionally filtered by type."""
        available = [
            w for w in self._workers.values()
            if w.status == WorkerStatus.IDLE
        ]
        if worker_type:
            available = [w for w in available if w.worker_type == worker_type]
        return available

    def get_busy_count(self) -> int:
        """Get number of busy workers."""
        return sum(1 for w in self._workers.values() if w.status == WorkerStatus.BUSY)

    def get_available_count(self) -> int:
        """Get number of available workers."""
        return len(self.get_available())

    def get_status(self) -> dict[str, Any]:
        """Get worker pool status."""
        by_type: dict[str, dict[str, int]] = {}
        for w in self._workers.values():
            wt = w.worker_type.value
            if wt not in by_type:
                by_type[wt] = {"total": 0, "busy": 0, "idle": 0}
            by_type[wt]["total"] += 1
            if w.status == WorkerStatus.BUSY:
                by_type[wt]["busy"] += 1
            else:
                by_type[wt]["idle"] += 1

        return {
            "total_workers": len(self._workers),
            "busy": self.get_busy_count(),
            "available": self.get_available_count(),
            "by_type": by_type,
        }

    def get_all_workers(self) -> list[Worker]:
        """Get all workers."""
        return list(self._workers.values())

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent