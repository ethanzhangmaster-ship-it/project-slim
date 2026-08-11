from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum


class RetryStrategy(Enum):
    IMMEDIATE = "immediate"
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class RetryPolicy:
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_errors: List[str] = field(default_factory=list)

    def calculate_delay(self, attempt: int) -> float:
        if attempt <= 0:
            return 0.0

        delay = self.initial_delay_seconds

        if self.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        elif self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.initial_delay_seconds
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.initial_delay_seconds * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.initial_delay_seconds * (self.backoff_multiplier ** (attempt - 1))

        delay = min(delay, self.max_delay_seconds)

        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)

        return round(delay, 2)

    def should_retry(self, error: str, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if not self.retryable_errors:
            return True
        return any(err.lower() in error.lower() for err in self.retryable_errors)


@dataclass
class RetryRecord:
    task_id: str
    attempt: int
    error: str
    retry_at: datetime
    delay_seconds: float
    policy_used: str


class RetryEngine:
    def __init__(self, default_policy: RetryPolicy = None):
        self.default_policy = default_policy or RetryPolicy()
        self.policies: Dict[str, RetryPolicy] = {}
        self.retry_queue: List[RetryRecord] = []
        self.retry_history: Dict[str, List[RetryRecord]] = {}

    def set_policy(self, task_type: str, policy: RetryPolicy):
        self.policies[task_type] = policy

    def get_policy(self, task_type: str) -> RetryPolicy:
        return self.policies.get(task_type, self.default_policy)

    def schedule_retry(
        self,
        task_id: str,
        task_type: str,
        error: str,
        attempt: int,
    ) -> Optional[RetryRecord]:
        policy = self.get_policy(task_type)

        if not policy.should_retry(error, attempt):
            return None

        delay = policy.calculate_delay(attempt)
        retry_at = datetime.now() + timedelta(seconds=delay)

        record = RetryRecord(
            task_id=task_id,
            attempt=attempt + 1,
            error=error,
            retry_at=retry_at,
            delay_seconds=delay,
            policy_used=policy.strategy.value,
        )

        self.retry_queue.append(record)

        if task_id not in self.retry_history:
            self.retry_history[task_id] = []
        self.retry_history[task_id].append(record)

        return record

    def get_due_retries(self, now: datetime = None) -> List[RetryRecord]:
        if now is None:
            now = datetime.now()

        due = [r for r in self.retry_queue if r.retry_at <= now]
        self.retry_queue = [r for r in self.retry_queue if r.retry_at > now]
        return sorted(due, key=lambda r: r.retry_at)

    def get_retry_count(self, task_id: str) -> int:
        return len(self.retry_history.get(task_id, []))

    def get_retry_history(self, task_id: str) -> List[RetryRecord]:
        return self.retry_history.get(task_id, [])

    def clear_task_retries(self, task_id: str):
        self.retry_queue = [r for r in self.retry_queue if r.task_id != task_id]
        if task_id in self.retry_history:
            del self.retry_history[task_id]

    def get_queue_size(self) -> int:
        return len(self.retry_queue)

    def get_stats(self) -> Dict[str, Any]:
        total_retries = sum(len(h) for h in self.retry_history.values())
        tasks_with_retries = len(self.retry_history)
        return {
            "queue_size": len(self.retry_queue),
            "total_retries": total_retries,
            "tasks_with_retries": tasks_with_retries,
            "avg_retries_per_task": round(total_retries / tasks_with_retries, 2) if tasks_with_retries > 0 else 0,
        }
