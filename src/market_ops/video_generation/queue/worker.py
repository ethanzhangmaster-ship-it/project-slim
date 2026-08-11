"""Worker - 队列消费者"""
import time
import threading
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass, field

from .priority_queue import PriorityQueue
from ..orchestrator.generation_task import GenerationTask
from ..orchestrator.generation_state import GenerationStatus


@dataclass
class WorkerStats:
    total_processed: int = 0
    total_success: int = 0
    total_failed: int = 0


class Worker:
    """工作线程 - 消费队列中的任务"""

    def __init__(self, queue: PriorityQueue, name: str = "worker-0"):
        self.queue = queue
        self.name = name
        self.stats = WorkerStats()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._task_handler: Optional[Callable[[GenerationTask], bool]] = None

    def set_task_handler(self, handler: Callable[[GenerationTask], bool]):
        self._task_handler = handler

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while self._running:
            task = self.queue.dequeue()
            if not task:
                time.sleep(0.1)
                continue

            success = self._process_task(task)
            self.stats.total_processed += 1
            if success:
                self.stats.total_success += 1
            else:
                self.stats.total_failed += 1

    def _process_task(self, task: GenerationTask) -> bool:
        if self._task_handler:
            try:
                return self._task_handler(task)
            except Exception:
                task.transition_to(GenerationStatus.FAILED)
                return False
        task.transition_to(GenerationStatus.COMPLETED)
        return True

    def is_running(self) -> bool:
        return self._running
