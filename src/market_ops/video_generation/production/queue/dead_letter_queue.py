"""Dead Letter Queue - 死信队列"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .job_queue import Job


@dataclass
class DeadLetterEntry:
    job: Job = field(default_factory=Job)
    reason: str = ""
    failed_at: str = ""
    final_status: str = "failed"


class DeadLetterQueue:
    """死信队列 - 存放重试次数耗尽的任务"""

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = Path(__file__).resolve().parent / "dead_letter.json"
        self.storage_path = Path(storage_path)
        self._entries: List[DeadLetterEntry] = []

    def add(self, job: Job, reason: str = "") -> bool:
        entry = DeadLetterEntry(
            job=job,
            reason=reason,
            failed_at=datetime.now().isoformat(),
            final_status="max_retries_exceeded",
        )
        self._entries.append(entry)
        self._save()
        return True

    def get_entries(self, limit: int = 100) -> List[DeadLetterEntry]:
        return self._entries[:limit]

    def get_job(self, job_id: str) -> Optional[DeadLetterEntry]:
        for entry in self._entries:
            if entry.job.job_id == job_id:
                return entry
        return None

    def remove(self, job_id: str) -> bool:
        for i, entry in enumerate(self._entries):
            if entry.job.job_id == job_id:
                self._entries.pop(i)
                self._save()
                return True
        return False

    def reprocess(self, job_id: str) -> Optional[Job]:
        entry = self.get_job(job_id)
        if entry:
            job = entry.job
            job.retry_count = 0
            job.status = "reprocessing"
            self.remove(job_id)
            return job
        return None

    def _save(self):
        data = [
            {
                "job": entry.job.to_dict(),
                "reason": entry.reason,
                "failed_at": entry.failed_at,
                "final_status": entry.final_status,
            }
            for entry in self._entries
        ]
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def size(self) -> int:
        return len(self._entries)

    def clear(self):
        self._entries.clear()
        self._save()

    def get_stats(self) -> Dict[str, Any]:
        by_reason = {}
        for entry in self._entries:
            by_reason[entry.reason] = by_reason.get(entry.reason, 0) + 1
        return {
            "total": self.size(),
            "by_reason": by_reason,
        }