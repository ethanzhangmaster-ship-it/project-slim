"""Priority Queue"""
import heapq
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from ..orchestrator.generation_task import GenerationTask
from ..orchestrator.generation_state import GenerationStatus


@dataclass(order=True)
class PriorityItem:
    priority: int = 0
    task_id: str = field(compare=False, default="")
    sequence: int = field(compare=False, default=0)


class PriorityQueue:
    """优先级队列 - 优先级高的先出 (priority 数值大 = 优先级高)"""

    def __init__(self):
        self._heap: List[PriorityItem] = []
        self._task_map: Dict[str, GenerationTask] = {}
        self._counter: int = 0

    def enqueue(self, task: GenerationTask) -> bool:
        if task.task_id in self._task_map:
            return False
        task.transition_to(GenerationStatus.QUEUED)
        self._counter += 1
        item = PriorityItem(
            priority=-task.priority,
            task_id=task.task_id,
            sequence=self._counter,
        )
        heapq.heappush(self._heap, item)
        self._task_map[task.task_id] = task
        return True

    def dequeue(self) -> Optional[GenerationTask]:
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.task_id in self._task_map:
                task = self._task_map.pop(item.task_id)
                task.transition_to(GenerationStatus.SUBMITTED)
                return task
        return None

    def peek(self) -> Optional[GenerationTask]:
        while self._heap:
            if self._heap[0].task_id in self._task_map:
                return self._task_map[self._heap[0].task_id]
            heapq.heappop(self._heap)
        return None

    def size(self) -> int:
        return len(self._task_map)

    def is_empty(self) -> bool:
        return len(self._task_map) == 0

    def remove(self, task_id: str) -> bool:
        if task_id not in self._task_map:
            return False
        del self._task_map[task_id]
        return True

    def update_priority(self, task_id: str, new_priority: int) -> bool:
        if task_id not in self._task_map:
            return False
        task = self._task_map[task_id]
        task.priority = new_priority
        self._counter += 1
        item = PriorityItem(
            priority=-new_priority,
            task_id=task_id,
            sequence=self._counter,
        )
        heapq.heappush(self._heap, item)
        return True

    def clear(self):
        self._heap.clear()
        self._task_map.clear()
        self._counter = 0
