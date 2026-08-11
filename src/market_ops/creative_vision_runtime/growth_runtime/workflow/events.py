"""E15.1.2 Context Events — 上下文事件.

定义 ExecutionContext 生命周期中的事件类型，用于:
  - Observability 集成 (E15.0.11)
  - 事件驱动架构
  - 审计追踪

用法:
    from workflow.events import ContextEventType, ContextEvent

    event = ContextEvent(
        event_type=ContextEventType.CONTEXT_CREATED,
        context_id="ctx_001",
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ContextEventType(str, Enum):
    """E15.1.2 上下文事件类型."""

    # Context 生命周期
    CONTEXT_CREATED = "context_created"
    CONTEXT_STARTED = "context_started"
    CONTEXT_PAUSED = "context_paused"
    CONTEXT_RESUMED = "context_resumed"
    CONTEXT_WAITING = "context_waiting"
    CONTEXT_COMPLETED = "context_completed"
    CONTEXT_FAILED = "context_failed"
    CONTEXT_CANCELLED = "context_cancelled"

    # Task 状态变更
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_SKIPPED = "task_skipped"
    TASK_RETRY = "task_retry"
    TASK_TIMEOUT = "task_timeout"

    # Variable 变更
    VARIABLE_SET = "variable_set"
    OUTPUT_RECORDED = "output_recorded"

    # 审批
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"

    # E15.1.3 调度器事件
    TASK_SCHEDULED = "task_scheduled"          # Task 被调度器选中执行
    TASK_READY = "task_ready"                  # Task 依赖满足，进入就绪状态
    TASK_BLOCKED = "task_blocked"              # Task 被依赖阻塞
    TASK_CONDITION_NOT_MET = "task_condition_not_met"  # Task 条件不满足
    WORKFLOW_PROGRESSED = "workflow_progressed"  # Workflow 整体进度更新


@dataclass
class ContextEvent:
    """E15.1.2 上下文事件.

    Attributes:
        event_id:     事件唯一标识
        event_type:   事件类型
        context_id:   关联的 ExecutionContext ID
        workflow_id:  Workflow ID
        task_id:      关联的 Task ID (可选)
        timestamp:    事件时间戳
        payload:      事件负载
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: ContextEventType = ContextEventType.CONTEXT_CREATED
    context_id: str = ""
    workflow_id: str = ""
    task_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "context_id": self.context_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextEvent":
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=ContextEventType(data.get("event_type", "context_created")),
            context_id=data.get("context_id", ""),
            workflow_id=data.get("workflow_id", ""),
            task_id=data.get("task_id", ""),
            timestamp=data.get("timestamp", ""),
            payload=data.get("payload", {}),
        )

    def __repr__(self) -> str:
        return (
            f"ContextEvent(type={self.event_type.value}, "
            f"context={self.context_id[:8]}..., task={self.task_id[:8] if self.task_id else '...'}...)"
        )


__all__ = ["ContextEventType", "ContextEvent"]