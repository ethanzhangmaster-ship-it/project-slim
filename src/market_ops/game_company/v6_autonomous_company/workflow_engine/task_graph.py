from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    attempt: int = 1


@dataclass
class TaskNode:
    task_id: str
    name: str
    task_type: str
    handler: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    priority: int = 0
    timeout_seconds: int = 3600
    max_retries: int = 3
    retry_policy: str = "exponential_backoff"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }


class TaskGraph:
    def __init__(self, workflow_name: str = "default"):
        self.workflow_name = workflow_name
        self.tasks: Dict[str, TaskNode] = {}
        self.adjacency_list: Dict[str, List[str]] = {}

    def add_task(self, task: TaskNode) -> TaskNode:
        self.tasks[task.task_id] = task
        if task.task_id not in self.adjacency_list:
            self.adjacency_list[task.task_id] = []
        return task

    def add_dependency(self, task_id: str, dependency_id: str):
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        if dependency_id not in self.tasks:
            raise ValueError(f"Task {dependency_id} not found")
        if dependency_id not in self.tasks[task_id].dependencies:
            self.tasks[task_id].dependencies.append(dependency_id)
        if task_id not in self.adjacency_list[dependency_id]:
            self.adjacency_list[dependency_id].append(task_id)

    def get_ready_tasks(self) -> List[TaskNode]:
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            deps_met = all(
                self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
                if dep_id in self.tasks
            )
            if deps_met and task.dependencies:
                task.status = TaskStatus.READY
                ready.append(task)
            elif not task.dependencies:
                task.status = TaskStatus.READY
                ready.append(task)
        return sorted(ready, key=lambda t: t.priority, reverse=True)

    def get_task(self, task_id: str) -> Optional[TaskNode]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskNode]:
        return list(self.tasks.values())

    def get_completed_tasks(self) -> List[TaskNode]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> List[TaskNode]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]

    def get_running_tasks(self) -> List[TaskNode]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]

    def is_complete(self) -> bool:
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.CANCELLED)
            for t in self.tasks.values()
        )

    def is_success(self) -> bool:
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for t in self.tasks.values()
        )

    def get_progress(self) -> Dict[str, Any]:
        total = len(self.tasks)
        completed = len(self.get_completed_tasks())
        failed = len(self.get_failed_tasks())
        running = len(self.get_running_tasks())
        pending = total - completed - failed - running
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "progress": self.get_progress(),
        }
