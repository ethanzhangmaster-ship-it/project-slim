"""Job Queue - 生产级任务队列"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque


@dataclass
class Job:
    """任务对象"""
    job_id: str = ""
    type: str = "video_generation"
    priority: str = "P1"
    platform: str = "kling"
    payload: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "type": self.type,
            "priority": self.priority,
            "platform": self.platform,
            "payload": self.payload,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobQueue:
    """任务队列"""

    def __init__(self):
        self._queue: deque = deque()
        self._jobs: Dict[str, Job] = {}

    def enqueue(self, job: Job) -> bool:
        if job.job_id in self._jobs:
            return False
        job.status = "queued"
        self._queue.append(job.job_id)
        self._jobs[job.job_id] = job
        return True

    def dequeue(self) -> Optional[Job]:
        if not self._queue:
            return None
        job_id = self._queue.popleft()
        job = self._jobs.get(job_id)
        if job:
            job.status = "processing"
            job.updated_at = datetime.now().isoformat()
        return job

    def peek(self) -> Optional[Job]:
        if not self._queue:
            return None
        return self._jobs.get(self._queue[0])

    def size(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def complete_job(self, job_id: str):
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = "completed"
            job.updated_at = datetime.now().isoformat()

    def fail_job(self, job_id: str):
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = "failed"
            job.updated_at = datetime.now().isoformat()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queued": self.size(),
            "total_jobs": len(self._jobs),
        }