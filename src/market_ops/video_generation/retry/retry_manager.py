"""Retry Manager"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .retry_policy import RetryPolicy
from ..orchestrator.generation_task import GenerationTask
from ..orchestrator.generation_state import GenerationStatus


@dataclass
class RetryStats:
    total_retries: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    platform_switches: int = 0


class RetryManager:
    """重试管理器 - 处理失败任务的重试和平台切换"""

    def __init__(self, policy: RetryPolicy = None):
        self.policy = policy or RetryPolicy()
        self.stats = RetryStats()
        self._retry_history: Dict[str, list] = {}

    def should_retry(self, task: GenerationTask, error: str) -> bool:
        if task.retry_count >= self.policy.max_retries:
            return False
        return self.policy.should_retry(error, task.retry_count)

    def retry(self, task: GenerationTask, error: str) -> Optional[GenerationTask]:
        if not self.should_retry(task, error):
            return None

        task.retry_count += 1
        task.error = None
        task.progress = 0.0
        task.transition_to(GenerationStatus.RETRYING)
        task.transition_to(GenerationStatus.QUEUED)

        if task.task_id not in self._retry_history:
            self._retry_history[task.task_id] = []
        self._retry_history[task.task_id].append({
            "retry_number": task.retry_count,
            "error": error,
            "delay": self.policy.get_delay(task.retry_count),
        })

        self.stats.total_retries += 1
        return task

    def switch_platform(self, task: GenerationTask, new_platform: str) -> GenerationTask:
        task.platform = new_platform
        task.retry_count = 0
        task.error = None
        task.progress = 0.0
        task.transition_to(GenerationStatus.RETRYING)
        task.transition_to(GenerationStatus.QUEUED)
        self.stats.platform_switches += 1
        return task

    def get_delay(self, task: GenerationTask) -> float:
        return self.policy.get_delay(task.retry_count)

    def get_retry_history(self, task_id: str) -> list:
        return self._retry_history.get(task_id, [])

    def mark_success(self, task_id: str):
        if task_id in self._retry_history:
            self.stats.successful_retries += 1

    def mark_failed(self, task_id: str):
        if task_id in self._retry_history:
            self.stats.failed_retries += 1
