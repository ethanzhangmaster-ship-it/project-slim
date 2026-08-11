"""Worker Manager"""
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass, field

from .async_worker import AsyncWorker, WorkerConfig, WorkerStats


@dataclass
class WorkerPoolStats:
    total_workers: int = 0
    active_workers: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0


class WorkerManager:
    """工作者池管理器"""

    def __init__(self):
        self._workers: Dict[str, AsyncWorker] = {}

    def add_worker(self, name: str, config: WorkerConfig = None):
        if name in self._workers:
            raise ValueError(f"Worker '{name}' already exists")
        worker = AsyncWorker(config or WorkerConfig(name=name))
        self._workers[name] = worker
        return worker

    def get_worker(self, name: str) -> AsyncWorker:
        return self._workers.get(name)

    def remove_worker(self, name: str):
        if name in self._workers:
            del self._workers[name]

    def list_workers(self) -> List[str]:
        return list(self._workers.keys())

    async def start_all(self):
        tasks = [worker.start() for worker in self._workers.values()]
        await asyncio.gather(*tasks)

    async def stop_all(self):
        for worker in self._workers.values():
            await worker.stop()

    async def submit_to_worker(self, worker_name: str, task_id: str, payload: Dict[str, Any]) -> Any:
        worker = self.get_worker(worker_name)
        if not worker:
            raise ValueError(f"Worker '{worker_name}' not found")
        return await worker.submit_task(task_id, payload)

    def get_pool_stats(self) -> WorkerPoolStats:
        stats = WorkerPoolStats(total_workers=len(self._workers))
        for worker in self._workers.values():
            w_stats = worker.get_stats()
            stats.total_tasks += w_stats.total_tasks
            stats.completed_tasks += w_stats.completed_tasks
            stats.failed_tasks += w_stats.failed_tasks
            if worker.is_busy():
                stats.active_workers += 1
        return stats

    def get_least_busy(self) -> str:
        if not self._workers:
            return ""
        return min(self._workers.keys(), key=lambda k: len(self._workers[k]._tasks))
