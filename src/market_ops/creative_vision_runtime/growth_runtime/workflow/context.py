"""E15.1.2 Execution Context — 运行时执行上下文.

ExecutionContext 是 Workflow Runtime 的「运行时记忆」:
  - 变量管理: 跨 Task 传递运行时数据
  - 任务状态: 追踪每个 Task 的执行进度
  - 输出传递: Task A 输出 → Task B 输入
  - 序列化: 支持 Storage 持久化和恢复

设计原则:
  - Definition 是模板 → Context 是实例
  - Context 可变 (运行时状态) — Definition 不可变
  - 支持断点恢复: 所有状态可序列化/反序列化

用法:
    ctx = ExecutionContext(
        workflow_id="campaign_optimizer",
        instance_id="wf_20260729_001",
        variables={"game": "P04", "campaign": "fb_android", "budget": 5000},
    )

    # 开始执行
    ctx.start()

    # 记录 Task 输出
    ctx.record_output("analyze", {"roas": 0.48, "fatigue": 0.76})

    # 下游 Task 读取
    analysis = ctx.get_output("analyze")
    fatigue = analysis["fatigue"]  # 0.76
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import TaskStatus, WorkflowDefinition, WorkflowInstance
from .state import TaskExecutionState, TaskExecutionStatus, WorkflowState


# ═══════════════════════════════════════════════════════════════
# Execution Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionContext:
    """E15.1.2 执行上下文 — Workflow 运行时记忆.

    与 WorkflowInstance 的关系:
      - WorkflowInstance: 轻量 (跟踪整体状态)
      - ExecutionContext: 重量 (包含变量、任务状态、输出)

    Attributes:
        context_id:     上下文唯一标识
        workflow_id:    关联的 WorkflowDefinition ID
        instance_id:    关联的 WorkflowInstance ID
        state:          当前 Workflow 状态
        variables:      运行时变量 (跨 Task 共享)
        task_states:    各 Task 执行状态
        outputs:        各 Task 输出结果 (按 task_id 索引)
        metadata:       执行元数据 (触发者、来源等)
        created_at:     创建时间
        updated_at:     更新时间
        paused_at:      暂停时间
        resumed_at:     恢复时间
    """

    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_name: str = ""
    instance_id: str = ""
    state: WorkflowState = WorkflowState.CREATED
    variables: dict[str, Any] = field(default_factory=dict)
    task_states: dict[str, TaskExecutionState] = field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    paused_at: str = ""
    resumed_at: str = ""

    # ── Factory ──────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        workflow_id: str,
        instance_id: str = "",
        workflow_name: str = "",
        variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionContext":
        """创建新的执行上下文."""
        return cls(
            workflow_id=workflow_id,
            instance_id=instance_id or str(uuid.uuid4()),
            workflow_name=workflow_name,
            variables=variables or {},
            metadata=metadata or {},
        )

    @classmethod
    def from_definition(
        cls,
        definition: WorkflowDefinition,
        instance_id: str = "",
        variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionContext":
        """从 WorkflowDefinition 创建上下文 (自动初始化 Task 状态)."""
        ctx = cls(
            workflow_id=definition.workflow_id,
            workflow_name=definition.name,
            instance_id=instance_id or str(uuid.uuid4()),
            variables=variables or {},
            metadata=metadata or {},
        )
        for task in definition.tasks:
            ctx.task_states[task.task_id] = TaskExecutionState(
                task_id=task.task_id,
                task_name=task.name,
                retry_max=task.retry_count,
            )
        return ctx

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        """标记上下文开始执行."""
        self.state = WorkflowState.RUNNING
        self._touch()

    def pause(self) -> None:
        """暂停执行."""
        self.state = WorkflowState.PAUSED
        self.paused_at = datetime.now(timezone.utc).isoformat()
        self._touch()

    def resume(self) -> None:
        """恢复执行."""
        self.state = WorkflowState.RUNNING
        self.resumed_at = datetime.now(timezone.utc).isoformat()
        self._touch()

    def wait(self) -> None:
        """等待外部事件 (如审批)."""
        self.state = WorkflowState.WAITING
        self._touch()

    def complete(self) -> None:
        """标记成功完成."""
        self.state = WorkflowState.SUCCESS
        self._touch()

    def fail(self, error: str = "") -> None:
        """标记失败."""
        self.state = WorkflowState.FAILED
        if error:
            self.metadata["error"] = error
        self._touch()

    def cancel(self) -> None:
        """取消执行."""
        self.state = WorkflowState.CANCELLED
        self._touch()

    def is_terminal(self) -> bool:
        return self.state.is_terminal()

    def is_active(self) -> bool:
        return self.state.is_active()

    # ── Variable Management ──────────────────────────────────

    def set_variable(self, key: str, value: Any) -> None:
        """设置运行时变量."""
        self.variables[key] = value
        self._touch()

    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取运行时变量."""
        return self.variables.get(key, default)

    def set_variables(self, **kwargs: Any) -> None:
        """批量设置变量."""
        self.variables.update(kwargs)
        self._touch()

    def get_variables(self) -> dict[str, Any]:
        """获取所有变量."""
        return dict(self.variables)

    # ── Task State Management ────────────────────────────────

    def get_task_state(self, task_id: str) -> TaskExecutionState | None:
        """获取指定 Task 的执行状态."""
        return self.task_states.get(task_id)

    def init_task_state(
        self,
        task_id: str,
        task_name: str = "",
        retry_max: int = 0,
    ) -> TaskExecutionState:
        """初始化或获取 Task 执行状态."""
        if task_id not in self.task_states:
            self.task_states[task_id] = TaskExecutionState(
                task_id=task_id,
                task_name=task_name,
                retry_max=retry_max,
            )
        self._touch()
        return self.task_states[task_id]

    def update_task_state(self, task_id: str, status: TaskExecutionStatus) -> TaskExecutionState | None:
        """更新 Task 执行状态."""
        state = self.task_states.get(task_id)
        if state is None:
            return None
        state.status = status
        self._touch()
        return state

    def start_task(self, task_id: str) -> TaskExecutionState | None:
        """标记 Task 开始执行."""
        state = self.task_states.get(task_id)
        if state is None:
            return None
        state.start()
        self._touch()
        return state

    def complete_task(self, task_id: str, output: dict[str, Any] | None = None) -> TaskExecutionState | None:
        """标记 Task 完成并记录输出."""
        state = self.task_states.get(task_id)
        if state is None:
            return None
        state.complete(output)
        if output is not None:
            self.outputs[task_id] = output
        self._touch()
        return state

    def fail_task(self, task_id: str, error: str = "") -> TaskExecutionState | None:
        """标记 Task 失败."""
        state = self.task_states.get(task_id)
        if state is None:
            return None
        state.fail(error)
        self._touch()
        return state

    def skip_task(self, task_id: str, reason: str = "") -> TaskExecutionState | None:
        """标记 Task 跳过."""
        state = self.task_states.get(task_id)
        if state is None:
            return None
        state.skip(reason)
        self._touch()
        return state

    def retry_task(self, task_id: str) -> TaskExecutionState | None:
        """重试 Task."""
        state = self.task_states.get(task_id)
        if state is None:
            return None
        if state.can_retry():
            state.retry()
            self._touch()
            return state
        return None

    def get_pending_tasks(self) -> list[TaskExecutionState]:
        """获取所有待执行的 Task."""
        return [
            s for s in self.task_states.values()
            if s.status == TaskExecutionStatus.PENDING
        ]

    def get_running_tasks(self) -> list[TaskExecutionState]:
        """获取所有执行中的 Task."""
        return [
            s for s in self.task_states.values()
            if s.status == TaskExecutionStatus.RUNNING
        ]

    def get_completed_tasks(self) -> list[TaskExecutionState]:
        """获取所有已完成的 Task."""
        return [
            s for s in self.task_states.values()
            if s.status == TaskExecutionStatus.COMPLETED
        ]

    def get_failed_tasks(self) -> list[TaskExecutionState]:
        """获取所有失败的 Task."""
        return [
            s for s in self.task_states.values()
            if s.status == TaskExecutionStatus.FAILED
        ]

    def all_tasks_completed(self) -> bool:
        """是否所有 Task 都已完成."""
        if not self.task_states:
            return False
        return all(
            s.status == TaskExecutionStatus.COMPLETED
            for s in self.task_states.values()
        )

    def has_failed_task(self) -> bool:
        """是否有 Task 失败."""
        return any(
            s.status == TaskExecutionStatus.FAILED
            for s in self.task_states.values()
        )

    # ── Output Management ────────────────────────────────────

    def record_output(self, task_id: str, output: dict[str, Any]) -> None:
        """记录 Task 输出 (跨 Task 数据传递).

        Args:
            task_id: Task ID
            output:  输出数据
        """
        self.outputs[task_id] = output
        self._touch()

    def get_output(self, task_id: str) -> dict[str, Any] | None:
        """获取指定 Task 的输出."""
        return self.outputs.get(task_id)

    def get_all_outputs(self) -> dict[str, dict[str, Any]]:
        """获取所有 Task 输出."""
        return dict(self.outputs)

    # ── Approval Context ─────────────────────────────────────

    def set_approval_context(
        self,
        task_id: str,
        requested_by: str = "",
        risk_level: str = "",
        reason: str = "",
    ) -> None:
        """设置审批上下文."""
        self.metadata["approval"] = {
            "task_id": task_id,
            "requested_by": requested_by,
            "risk_level": risk_level,
            "reason": reason,
        }
        self._touch()

    def get_approval_context(self) -> dict[str, Any]:
        """获取审批上下文."""
        return self.metadata.get("approval", {})

    # ── Progress ─────────────────────────────────────────────

    def progress(self) -> dict[str, Any]:
        """获取执行进度."""
        total = len(self.task_states)
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
            "percentage": round(completed / max(total, 1) * 100, 1),
        }

    def summary(self) -> dict[str, Any]:
        """获取执行摘要."""
        return {
            "context_id": self.context_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "instance_id": self.instance_id,
            "state": self.state.value,
            "progress": self.progress(),
            "variables": self.variables,
            "task_states": {
                tid: ts.to_dict() for tid, ts in self.task_states.items()
            },
            "outputs": self.outputs,
            "metadata": self.metadata,
        }

    # ── Serialization ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "instance_id": self.instance_id,
            "state": self.state.value,
            "variables": self.variables,
            "task_states": {k: v.to_dict() for k, v in self.task_states.items()},
            "outputs": self.outputs,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "paused_at": self.paused_at,
            "resumed_at": self.resumed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionContext":
        task_states = {}
        for k, v in data.get("task_states", {}).items():
            task_states[k] = TaskExecutionState.from_dict(v)
        return cls(
            context_id=data.get("context_id", str(uuid.uuid4())),
            workflow_id=data.get("workflow_id", ""),
            workflow_name=data.get("workflow_name", ""),
            instance_id=data.get("instance_id", ""),
            state=WorkflowState(data.get("state", "created")),
            variables=data.get("variables", {}),
            task_states=task_states,
            outputs=data.get("outputs", {}),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            paused_at=data.get("paused_at", ""),
            resumed_at=data.get("resumed_at", ""),
        )

    # ── Internal ─────────────────────────────────────────────

    def _touch(self) -> None:
        now = datetime.now(timezone.utc)
        ts = now.isoformat()
        # 保证同一微秒内多次 _touch 仍产生不同的时间戳
        # 这对 audit trail / rollback / memory learning 的可信性至关重要
        if ts == self.updated_at:
            from datetime import timedelta
            now = now + timedelta(microseconds=1)
            ts = now.isoformat()
        self.updated_at = ts

    def __repr__(self) -> str:
        progress = self.progress()
        return (
            f"ExecutionContext(wf={self.workflow_name}, state={self.state.value}, "
            f"progress={progress['completed']}/{progress['total']})"
        )


__all__ = ["ExecutionContext"]