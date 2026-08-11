"""P4.5 durable work queue, SLO evaluation and recovery drills."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SLOConfig:
    min_success_rate: float = 0.99
    max_failed_shards: int = 0
    max_cycle_latency_ms: float = 300000.0
    max_queue_depth: int = 1000


@dataclass
class SLOReport:
    healthy: bool
    checks: Dict[str, bool]
    violations: List[str] = field(default_factory=list)


class SLOEvaluator:
    def __init__(self, config: SLOConfig = SLOConfig()): self.config = config

    def evaluate(self, *, success_rate: float, failed_shards: int,
                 latency_ms: float, queue_depth: int) -> SLOReport:
        checks = {
            "success_rate": success_rate >= self.config.min_success_rate,
            "failed_shards": failed_shards <= self.config.max_failed_shards,
            "cycle_latency": latency_ms <= self.config.max_cycle_latency_ms,
            "queue_depth": queue_depth <= self.config.max_queue_depth,
        }
        return SLOReport(all(checks.values()), checks,
                         [name for name, passed in checks.items() if not passed])


@dataclass
class QueueJob:
    job_id: str
    payload: Dict[str, Any]
    attempts: int = 0
    max_attempts: int = 3
    status: str = "pending"


class DurableQueue:
    """Append-only JSONL queue with replay, retry and dead-letter state."""
    def __init__(self, path: str):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(self, job_id: str, payload: Dict[str, Any], max_attempts: int = 3) -> bool:
        if not job_id or max_attempts < 1: raise ValueError("invalid queue job")
        if job_id in self._latest(): return False
        self._append(QueueJob(job_id, dict(payload), max_attempts=max_attempts))
        return True

    def pending(self) -> List[QueueJob]:
        return sorted((j for j in self._latest().values() if j.status == "pending"),
                      key=lambda j: j.job_id)

    def ack(self, job_id: str) -> bool:
        job = self._latest().get(job_id)
        if job is None or job.status != "pending": return False
        job.status = "acked"; self._append(job); return True

    def fail(self, job_id: str) -> bool:
        job = self._latest().get(job_id)
        if job is None or job.status != "pending": return False
        job.attempts += 1
        if job.attempts >= job.max_attempts: job.status = "dead"
        self._append(job); return True

    def depth(self) -> int: return len(self.pending())

    def dead_letters(self) -> List[QueueJob]:
        return sorted((j for j in self._latest().values() if j.status == "dead"),
                      key=lambda j: j.job_id)

    def _append(self, job: QueueJob):
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(job.__dict__, ensure_ascii=False) + "\n")

    def _latest(self) -> Dict[str, QueueJob]:
        out = {}
        if not self.path.exists(): return out
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    data = json.loads(line); out[data["job_id"]] = QueueJob(**data)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
        return out


class RecoveryDrill:
    def __init__(self, backup_manager: Any): self.backup_manager = backup_manager

    def run(self, paths: List[str], restore_target: str) -> Dict[str, Any]:
        archive = self.backup_manager.backup(paths, label="recovery_drill")
        name = Path(archive).name
        restored = self.backup_manager.restore(name, target=restore_target)
        target = Path(restored)
        restored_entries = sorted(p.relative_to(target).as_posix()
                                  for p in target.rglob("*") if p.is_file())
        return {"success": bool(restored_entries), "archive": archive,
                "restore_target": restored, "restored_entries": restored_entries}


__all__ = ["SLOConfig", "SLOReport", "SLOEvaluator", "QueueJob", "DurableQueue", "RecoveryDrill"]
