"""Generation Orchestrator Core"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .generation_task import GenerationTask
from .generation_state import GenerationStatus
from .execution_context import ExecutionContext


@dataclass
class OrchestratorStats:
    total_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_cost: float = 0.0


class GenerationOrchestrator:
    """生成任务编排器"""

    def __init__(self):
        self._tasks: Dict[str, GenerationTask] = {}
        self._stats = OrchestratorStats()

    def create_task(
        self,
        blueprint_id: str,
        scene_id: str,
        platform: str,
        prompt: Dict[str, Any],
        priority: int = 5,
        metadata: Dict[str, Any] = None,
    ) -> GenerationTask:
        task = GenerationTask(
            blueprint_id=blueprint_id,
            scene_id=scene_id,
            platform=platform,
            prompt=prompt,
            priority=priority,
            metadata=metadata or {},
        )
        self._tasks[task.task_id] = task
        self._stats.total_tasks += 1
        return task

    def get_task(self, task_id: str) -> Optional[GenerationTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: GenerationStatus = None) -> List[GenerationTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def submit_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if task.transition_to(GenerationStatus.QUEUED):
            self._stats.active_tasks += 1
            return True
        return False

    def start_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if task.transition_to(GenerationStatus.SUBMITTED):
            return task.transition_to(GenerationStatus.GENERATING)
        return False

    def complete_task(self, task_id: str, result: Dict[str, Any] = None, cost: float = 0.0) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if task.transition_to(GenerationStatus.COMPLETED):
            if result:
                task.result = result
            task.cost = cost
            self._stats.completed_tasks += 1
            self._stats.active_tasks -= 1
            self._stats.total_cost += cost
            return True
        return False

    def fail_task(self, task_id: str, error: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if task.transition_to(GenerationStatus.FAILED):
            task.error = error
            self._stats.failed_tasks += 1
            self._stats.active_tasks -= 1
            return True
        return False

    def retry_task(self, task_id: str) -> Optional[GenerationTask]:
        task = self.get_task(task_id)
        if not task:
            return None
        if task.retry_count >= task.max_retries:
            return None
        if task.status in {GenerationStatus.FAILED, GenerationStatus.GENERATING}:
            task.retry_count += 1
            task.error = None
            task.progress = 0.0
            task.transition_to(GenerationStatus.RETRYING)
            task.transition_to(GenerationStatus.QUEUED)
            return task
        return None

    def get_stats(self) -> OrchestratorStats:
        return self._stats

    def create_execution_context(self, task_id: str) -> Optional[ExecutionContext]:
        task = self.get_task(task_id)
        if not task:
            return None
        return ExecutionContext(task=task)
