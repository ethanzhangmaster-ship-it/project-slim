"""E15.1.2 Workflow State — 运行时状态模型.

定义 Workflow 执行时的状态枚举和 Task 执行状态记录:
  - WorkflowState:  Workflow 实例运行时状态 (更细粒度)
  - TaskExecutionState: 单个 Task 的运行时执行记录
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Workflow State
# ═══════════════════════════════════════════════════════════════


class WorkflowState(str, Enum):
    """E15.1.2 Workflow 运行时状态 — 更细粒度的生命周期.

    与 E15.1.1 WorkflowStatus 的关系:
      - WorkflowStatus: 粗粒度 (CREATED/RUNNING/SUCCESS/FAILED/CANCELLED)
      - WorkflowState:  细粒度 (增加 PAUSED/WAITING 状态)
    """

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def from_workflow_status(cls, status: Any) -> "WorkflowState":
        """从 E15.1.1 WorkflowStatus 转换."""
        mapping = {
            "created": cls.CREATED,
            "running": cls.RUNNING,
            "waiting_approval": cls.WAITING,
            "success": cls.SUCCESS,
            "failed": cls.FAILED,
            "cancelled": cls.CANCELLED,
        }
        val = status.value if hasattr(status, "value") else str(status)
        return mapping.get(val, cls.CREATED)

    def is_terminal(self) -> bool:
        return self in {WorkflowState.SUCCESS, WorkflowState.FAILED, WorkflowState.CANCELLED}

    def is_active(self) -> bool:
        return self in {WorkflowState.RUNNING, WorkflowState.WAITING, WorkflowState.PAUSED}


# ═══════════════════════════════════════════════════════════════
# Task Execution State
# ═══════════════════════════════════════════════════════════════


class TaskExecutionStatus(str, Enum):
    """Task 运行时执行状态."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class TaskExecutionState:
    """E15.1.2 单个 Task 的运行时执行记录.

    记录一个 Task 从开始到结束的完整状态:
      - 当前状态
      - 执行时间
      - 输出结果
      - 重试信息
      - 错误信息

    Attributes:
        task_id:       关联的 WorkflowTask.task_id
        task_name:     任务名称
        status:        当前执行状态
        started_at:    开始时间
        completed_at:  完成时间
        duration_ms:   耗时 (毫秒)
        output:        输出结果
        error:         错误信息
        retry_current: 当前重试次数
        retry_max:     最大重试次数
        metadata:      扩展元数据
    """

    task_id: str = ""
    task_name: str = ""
    status: TaskExecutionStatus = TaskExecutionStatus.PENDING
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    retry_current: int = 0
    retry_max: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.status = TaskExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()

    def complete(self, output: dict[str, Any] | None = None) -> None:
        self.status = TaskExecutionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if output is not None:
            self.output = output
        self._calc_duration()

    def fail(self, error: str = "") -> None:
        self.status = TaskExecutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.error = error
        self._calc_duration()

    def skip(self, reason: str = "") -> None:
        self.status = TaskExecutionStatus.SKIPPED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if reason:
            self.error = reason
        self._calc_duration()

    def timeout(self) -> None:
        self.status = TaskExecutionStatus.TIMEOUT
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self._calc_duration()

    def wait(self) -> None:
        self.status = TaskExecutionStatus.WAITING

    def can_retry(self) -> bool:
        return self.retry_current < self.retry_max

    def retry(self) -> None:
        self.retry_current += 1
        self.status = TaskExecutionStatus.PENDING
        self.error = ""

    def is_terminal(self) -> bool:
        return self.status in {
            TaskExecutionStatus.COMPLETED,
            TaskExecutionStatus.FAILED,
            TaskExecutionStatus.SKIPPED,
            TaskExecutionStatus.TIMEOUT,
        }

    def _calc_duration(self) -> None:
        if self.started_at and self.completed_at:
            try:
                start = datetime.fromisoformat(self.started_at)
                end = datetime.fromisoformat(self.completed_at)
                self.duration_ms = (end - start).total_seconds() * 1000
            except (ValueError, TypeError):
                self.duration_ms = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "output": self.output,
            "error": self.error,
            "retry_current": self.retry_current,
            "retry_max": self.retry_max,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskExecutionState":
        return cls(
            task_id=data.get("task_id", ""),
            task_name=data.get("task_name", ""),
            status=TaskExecutionStatus(data.get("status", "pending")),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            duration_ms=data.get("duration_ms", 0.0),
            output=data.get("output", {}),
            error=data.get("error", ""),
            retry_current=data.get("retry_current", 0),
            retry_max=data.get("retry_max", 0),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"TaskExecutionState(task={self.task_name}, "
            f"status={self.status.value}, output_keys={list(self.output.keys())})"
        )


__all__ = [
    "WorkflowState",
    "TaskExecutionStatus",
    "TaskExecutionState",
]