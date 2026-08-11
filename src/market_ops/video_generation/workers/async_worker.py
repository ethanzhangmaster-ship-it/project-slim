"""Async Worker"""
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class WorkerStats:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_duration: float = 0.0


@dataclass
class WorkerConfig:
    name: str = "worker"
    max_concurrent: int = 5
    poll_interval: float = 1.0
    timeout: int = 300


class AsyncWorker:
    """异步工作者"""

    def __init__(self, config: WorkerConfig = None):
        self.config = config or WorkerConfig()
        self.stats = WorkerStats()
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._task_handler: Optional[Callable[[Dict[str, Any]], Any]] = None

    def set_task_handler(self, handler: Callable[[Dict[str, Any]], Any]):
        self._task_handler = handler

    async def start(self):
        self._running = True
        await self._run()

    async def stop(self):
        self._running = False
        for task_id, task in list(self._tasks.items()):
            task.cancel()
            del self._tasks[task_id]

    async def _run(self):
        while self._running:
            await asyncio.sleep(self.config.poll_interval)

    async def submit_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        async with self._semaphore:
            task = asyncio.create_task(self._process_task(task_id, payload))
            self._tasks[task_id] = task
            try:
                result = await asyncio.wait_for(task, timeout=self.config.timeout)
                return result
            finally:
                self._tasks.pop(task_id, None)

    async def _process_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        self.stats.total_tasks += 1
        start_time = time.time()

        try:
            if self._task_handler:
                result = await self._task_handler(payload) if asyncio.iscoroutinefunction(self._task_handler) else self._task_handler(payload)
            else:
                result = {"task_id": task_id, "status": "completed"}

            self.stats.completed_tasks += 1
            return result
        except Exception as e:
            self.stats.failed_tasks += 1
            return {"task_id": task_id, "status": "failed", "error": str(e)}
        finally:
            duration = time.time() - start_time
            self.stats.avg_duration = (self.stats.avg_duration * (self.stats.total_tasks - 1) + duration) / self.stats.total_tasks

    def get_stats(self) -> WorkerStats:
        return self.stats

    def is_busy(self) -> bool:
        return len(self._tasks) >= self.config.max_concurrent
