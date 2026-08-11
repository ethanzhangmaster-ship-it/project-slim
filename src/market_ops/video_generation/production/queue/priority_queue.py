"""Priority Queue - 生产级优先级队列"""
import heapq
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .job_queue import Job


# 优先级映射
PRIORITY_ORDER = {
    "P0": 0,  # 最高优先级 - Production Creative
    "P1": 1,  # 中优先级 - Experiment
    "P2": 2,  # 低优先级 - Exploration
}


@dataclass(order=True)
class PriorityItem:
    priority: int = 0
    sequence: int = field(compare=False, default=0)
    job_id: str = field(compare=False, default="")


class PriorityQueue:
    """优先级队列"""

    def __init__(self):
        self._heap: List[PriorityItem] = []
        self._jobs: Dict[str, Job] = {}
        self._counter: int = 0

    def enqueue(self, job: Job) -> bool:
        if job.job_id in self._jobs:
            return False
        job.status = "queued"
        self._counter += 1
        priority_value = PRIORITY_ORDER.get(job.priority, 1)
        item = PriorityItem(
            priority=priority_value,
            sequence=self._counter,
            job_id=job.job_id,
        )
        heapq.heappush(self._heap, item)
        self._jobs[job.job_id] = job
        return True

    def dequeue(self) -> Optional[Job]:
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.job_id in self._jobs:
                job = self._jobs.pop(item.job_id)
                job.status = "processing"
                job.updated_at = datetime.now().isoformat()
                return job
        return None

    def peek(self) -> Optional[Job]:
        while self._heap:
            if self._heap[0].job_id in self._jobs:
                return self._jobs[self._heap[0].job_id]
            heapq.heappop(self._heap)
        return None

    def size(self) -> int:
        return len(self._jobs)

    def is_empty(self) -> bool:
        return len(self._jobs) == 0

    def update_priority(self, job_id: str, new_priority: str) -> bool:
        if job_id not in self._jobs:
            return False
        job = self._jobs[job_id]
        job.priority = new_priority
        job.updated_at = datetime.now().isoformat()
        self._counter += 1
        priority_value = PRIORITY_ORDER.get(new_priority, 1)
        item = PriorityItem(
            priority=priority_value,
            sequence=self._counter,
            job_id=job_id,
        )
        heapq.heappush(self._heap, item)
        return True

    def get_stats(self) -> Dict[str, Any]:
        by_priority = {"P0": 0, "P1": 0, "P2": 0}
        for job in self._jobs.values():
            by_priority[job.priority] = by_priority.get(job.priority, 0) + 1
        return {
            "total": self.size(),
            "by_priority": by_priority,
        }