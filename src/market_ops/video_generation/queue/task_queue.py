"""Task Queue"""
from typing import List, Optional, Dict, Any
from collections import deque
from dataclasses import dataclass, field

from ..orchestrator.generation_task import GenerationTask
from ..orchestrator.generation_state import GenerationStatus


class TaskQueue:
    """FIFO 任务队列"""

    def __init__(self):
        self._queue: deque = deque()
        self._task_map: Dict[str, GenerationTask] = {}

    def enqueue(self, task: GenerationTask) -> bool:
        if task.task_id in self._task_map:
            return False
        task.transition_to(GenerationStatus.QUEUED)
        self._queue.append(task.task_id)
        self._task_map[task.task_id] = task
        return True

    def dequeue(self) -> Optional[GenerationTask]:
        if not self._queue:
            return None
        task_id = self._queue.popleft()
        task = self._task_map.pop(task_id, None)
        if task:
            task.transition_to(GenerationStatus.SUBMITTED)
        return task

    def peek(self) -> Optional[GenerationTask]:
        if not self._queue:
            return None
        return self._task_map.get(self._queue[0])

    def size(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def remove(self, task_id: str) -> bool:
        if task_id not in self._task_map:
            return False
        self._queue = deque(tid for tid in self._queue if tid != task_id)
        del self._task_map[task_id]
        return True

    def clear(self):
        self._queue.clear()
        self._task_map.clear()
