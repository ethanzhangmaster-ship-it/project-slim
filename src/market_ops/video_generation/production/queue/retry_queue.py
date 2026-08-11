"""Retry Queue - 重试队列"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .job_queue import Job


@dataclass
class RetryEntry:
    job: Job = field(default_factory=Job)
    retry_at: str = ""
    delay_seconds: float = 0.0


class RetryQueue:
    """重试队列 - 管理失败任务的重试"""

    def __init__(self, default_delay: float = 30.0):
        self._queue: List[RetryEntry] = []
        self.default_delay = default_delay

    def add(self, job: Job, delay: float = None) -> bool:
        if job.retry_count >= job.max_retries:
            return False
        delay = delay or self.default_delay * (job.retry_count + 1)
        retry_at = datetime.now().isoformat()
        job.retry_count += 1
        job.status = "retrying"
        job.updated_at = retry_at
        self._queue.append(RetryEntry(
            job=job,
            retry_at=retry_at,
            delay_seconds=delay,
        ))
        return True

    def get_ready(self) -> List[Job]:
        ready = []
        now = datetime.now()
        remaining = []
        for entry in self._queue:
            scheduled = datetime.fromisoformat(entry.retry_at)
            elapsed = (now - scheduled).total_seconds()
            if elapsed >= entry.delay_seconds:
                ready.append(entry.job)
            else:
                remaining.append(entry)
        self._queue = remaining
        return ready

    def size(self) -> int:
        return len(self._queue)

    def clear(self):
        self._queue.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "pending_retries": self.size(),
            "total_retries": sum(e.job.retry_count for e in self._queue),
        }