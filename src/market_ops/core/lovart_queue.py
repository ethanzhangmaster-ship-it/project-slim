"""Phase 2.1.1: Lovart Task Queue — strict state machine.

Manages generation task lifecycle:
  CREATE → PENDING → CLAIM → PROCESSING → SUCCESS
  PROCESSING → RETRY → PENDING → CLAIM → PROCESSING (retry loop)
  PROCESSING → FAILED (exhausted)

Thread-safe, backed by GenerationStore for persistence.
"""

from __future__ import annotations

import random
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .generation_store import GenerationStore, GenerationStatus, PRIORITY_ORDER, RETRY_JITTER


# Backoff delays for retry
RETRY_BACKOFF = [10, 30]  # seconds


class LovartQueue:
    """Thread-safe task queue with strict state machine.

    Usage:
        queue = LovartQueue(store)
        queue.submit("creative_001", "A cute witch...", priority="high")

        # Worker:
        task = queue.claim("worker_01")       # PENDING → CLAIM
        queue.start_processing(task["id"])     # CLAIM → PROCESSING
        # ... generate ...
        queue.complete(task_id, image_path="/out/001.png")
        # or:
        queue.fail(task_id, "timeout", retry=True)   # PROCESSING → RETRY
    """

    def __init__(self, store: GenerationStore) -> None:
        self._store = store
        self._lock = threading.Lock()

    # ── Submit ──

    def submit(
        self,
        creative_id: str,
        prompt: str,
        negative_prompt: str = "",
        priority: str = "normal",
        format: str = "1080x1080",
        dna_source: str = "",
        max_retries: int = 3,
    ) -> str:
        """Submit a generation task. Returns task_id. Status: CREATE → PENDING."""
        if priority not in PRIORITY_ORDER:
            priority = "normal"
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = {
            "id": task_id,
            "creative_id": creative_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "status": "PENDING",
            "priority": priority,
            "format": format,
            "dna_source": dna_source,
            "max_retries": max_retries,
            "retry_count": 0,
        }
        self._store.insert(task)
        return task_id

    def submit_batch(
        self,
        creatives: list[dict[str, Any]],
    ) -> list[str]:
        """Submit multiple tasks. Returns list of task_ids."""
        task_ids = []
        for c in creatives:
            tid = self.submit(
                creative_id=c.get("creative_id", ""),
                prompt=c.get("prompt", ""),
                negative_prompt=c.get("negative_prompt", ""),
                priority=c.get("priority", "normal"),
                format=c.get("format", "1080x1080"),
                dna_source=c.get("dna_source", ""),
                max_retries=c.get("max_retries", 3),
            )
            task_ids.append(tid)
        return task_ids

    # ── Claim (PENDING → CLAIM) ──

    def claim(self, worker_id: str = "") -> dict[str, Any] | None:
        """Claim the next pending task. Transition: PENDING → CLAIM. Returns None if empty."""
        with self._lock:
            pending = self._store.get_pending(limit=1)
            if not pending:
                return None

            task = pending[0]
            claimed = self._store.claim_task(task["id"], worker_id)
            if not claimed:
                return None  # Race condition, another worker took it

            task["status"] = "CLAIM"
            task["claimed_by"] = worker_id
            return task

    def claim_batch(self, count: int, worker_id: str = "") -> list[dict[str, Any]]:
        """Claim up to `count` pending tasks."""
        claimed = []
        for _ in range(count):
            task = self.claim(worker_id)
            if task is None:
                break
            claimed.append(task)
        return claimed

    # ── Start Processing (CLAIM → PROCESSING) ──

    def start_processing(self, task_id: str, worker_id: str = "") -> bool:
        """Transition a claimed task to processing: CLAIM → PROCESSING."""
        return self._store.start_processing(task_id, worker_id)

    # ── Complete (PROCESSING → SUCCESS) ──

    def complete(
        self,
        task_id: str,
        image_path: str = "",
        image_url: str = "",
        generation_time: float = 0,
        cost: float = 0,
        model: str = "lovart",
        quality_score: int = 0,
    ) -> None:
        """Mark a task as successfully completed: PROCESSING → SUCCESS."""
        self._store.update_status(
            task_id,
            "SUCCESS",
            image_path=image_path,
            image_url=image_url,
            generation_time=generation_time,
            cost=cost,
            model=model,
            quality_score=quality_score,
        )

    # ── Fail (PROCESSING → RETRY or FAILED) ──

    def fail(self, task_id: str, error_message: str, retry: bool = True) -> str:
        """Mark a task as failed: PROCESSING → RETRY or FAILED.

        If retry=True and under max_retries: PROCESSING → RETRY (with backoff schedule)
        If exhausted: PROCESSING → FAILED
        """
        task = self._store.get(task_id)
        if task is None:
            return "FAILED"

        new_retry_count = task["retry_count"] + 1
        max_retries = task["max_retries"]

        if retry and new_retry_count < max_retries:
            # Calculate backoff delay with jitter
            delay_idx = min(new_retry_count - 1, len(RETRY_BACKOFF) - 1)
            base_delay = RETRY_BACKOFF[delay_idx]
            jitter = random.uniform(-RETRY_JITTER, RETRY_JITTER)
            delay = max(1, base_delay + jitter)  # minimum 1s

            self._store.schedule_retry(
                task_id,
                retry_count=new_retry_count,
                delay_seconds=delay,
                error=error_message,
            )
            return "RETRY"
        else:
            self._store.update_status(
                task_id,
                "FAILED",
                error_message=error_message,
                last_error=error_message,
                retry_count=new_retry_count,
            )
            return "FAILED"

    # ── Retry → Re-queue (RETRY → PENDING) ──

    def re_queue_retry(self, task_id: str) -> bool:
        """Move a RETRY task back to PENDING after backoff period."""
        task = self._store.get(task_id)
        if task is None or task["status"] != "RETRY":
            return False

        # Check if backoff period has elapsed
        next_retry = task.get("next_retry_time", "")
        if next_retry:
            try:
                retry_dt = datetime.fromisoformat(next_retry)
                if datetime.now(timezone.utc) < retry_dt:
                    return False  # Not yet time
            except (ValueError, TypeError):
                pass

        self._store.update_status(task_id, "PENDING")
        return True

    def re_queue_all_ready(self) -> int:
        """Re-queue all RETRY tasks whose backoff has elapsed."""
        retry_tasks = self._store.get_failed_retryable(limit=100)
        count = 0
        for t in retry_tasks:
            if t["status"] == "RETRY" and self.re_queue_retry(t["id"]):
                count += 1
        return count

    # ── Query ──

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._store.get(task_id)

    def pending_count(self) -> int:
        stats = self._store.get_stats()
        return stats["pending_count"]

    def stats(self) -> dict[str, Any]:
        return self._store.get_stats()

    def reset_stuck(self, max_minutes: int = 10) -> int:
        return self._store.reset_stuck(max_minutes)