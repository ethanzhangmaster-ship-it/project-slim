"""E15.1.1 Workflow Models — 核心数据模型.

定义 Workflow 系统的核心对象:
  - WorkflowStatus:     Workflow 生命周期状态
  - TaskStatus:         Task 执行状态
  - WorkflowTask:       单个执行节点定义
  - WorkflowDefinition: Workflow 静态模板 (DAG)
  - WorkflowInstance:   Workflow 一次真实运行实例
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Workflow Status
# ═══════════════════════════════════════════════════════════════


class WorkflowStatus(str, Enum):
    """Workflow 实例生命周期状态."""
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """单个 Task 执行状态."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════
# Workflow Task
# ═══════════════════════════════════════════════════════════════


@dataclass
class WorkflowTask:
    """E15.1.1 单个执行节点定义.

    WorkflowTask 是 Workflow DAG 中的节点，描述一个执行步骤。

    Attributes:
        task_id:           任务唯一标识
        name:              任务名称
        description:       任务描述
        action_type:       对应的 ActionType (e.g. "update_campaign_budget")
        depends_on:        依赖的任务 ID 列表
        requires_approval: 是否需要人工审批
        approval_threshold: 审批阈值说明 (可选)
        parameters:        任务参数 (灵活 dict)
        timeout_ms:        超时 (毫秒, 0 = 无限制)
        retry_count:       最大重试次数
        metadata:          扩展元数据
    """

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    action_type: str = ""
    depends_on: list[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_threshold: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 0
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "action_type": self.action_type,
            "depends_on": self.depends_on,
            "requires_approval": self.requires_approval,
            "approval_threshold": self.approval_threshold,
            "parameters": self.parameters,
            "timeout_ms": self.timeout_ms,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowTask":
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            action_type=data.get("action_type", ""),
            depends_on=data.get("depends_on", []),
            requires_approval=data.get("requires_approval", False),
            approval_threshold=data.get("approval_threshold", ""),
            parameters=data.get("parameters", {}),
            timeout_ms=data.get("timeout_ms", 0),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"WorkflowTask(id={self.task_id[:8]}..., name={self.name}, "
            f"action={self.action_type}, deps={len(self.depends_on)})"
        )


# ═══════════════════════════════════════════════════════════════
# Workflow Definition
# ═══════════════════════════════════════════════════════════════


@dataclass
class WorkflowDefinition:
    """E15.1.1 Workflow 静态模板 — 声明式流程定义.

    WorkflowDefinition 是 Workflow 的蓝图/模板，描述一个业务流程的
    步骤和依赖关系。每次运行会创建一个 WorkflowInstance。

    与 GitHub Actions Workflow / Airflow DAG / Temporal Workflow 概念一致。

    Attributes:
        workflow_id:   Workflow 唯一标识
        name:          Workflow 名称
        version:       版本号
        description:   描述
        tasks:         任务列表 (DAG 节点)
        metadata:      扩展元数据
        created_at:    创建时间
        updated_at:    更新时间
    """

    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    tasks: list[WorkflowTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── Task Management ──────────────────────────────────────

    def add_task(self, task: WorkflowTask) -> None:
        """添加任务节点."""
        if any(t.task_id == task.task_id for t in self.tasks):
            raise ValueError(f"Task with id '{task.task_id}' already exists")
        self.tasks.append(task)
        self._touch()

    def remove_task(self, task_id: str) -> bool:
        """移除任务节点 (同时清理其他任务的依赖)."""
        task = self.get_task(task_id)
        if task is None:
            return False

        # 清理其他任务对该任务的依赖
        for t in self.tasks:
            if task_id in t.depends_on:
                t.depends_on = [d for d in t.depends_on if d != task_id]

        self.tasks = [t for t in self.tasks if t.task_id != task_id]
        self._touch()
        return True

    def get_task(self, task_id: str) -> WorkflowTask | None:
        """按 ID 获取任务."""
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def get_task_by_name(self, name: str) -> WorkflowTask | None:
        """按名称获取任务."""
        for t in self.tasks:
            if t.name == name:
                return t
        return None

    def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """添加任务依赖: task_id 依赖 depends_on_id.

        Raises:
            ValueError: 任务不存在或依赖关系无效
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")

        dep_task = self.get_task(depends_on_id)
        if dep_task is None:
            raise ValueError(f"Dependency task '{depends_on_id}' not found")

        if depends_on_id not in task.depends_on:
            task.depends_on.append(depends_on_id)
            self._touch()

    def remove_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """移除任务依赖."""
        task = self.get_task(task_id)
        if task is None:
            return False
        if depends_on_id in task.depends_on:
            task.depends_on = [d for d in task.depends_on if d != depends_on_id]
            self._touch()
            return True
        return False

    # ── DAG Query ────────────────────────────────────────────

    def get_entry_tasks(self) -> list[WorkflowTask]:
        """获取入口任务 (无依赖)."""
        return [t for t in self.tasks if not t.depends_on]

    def get_exit_tasks(self) -> list[WorkflowTask]:
        """获取出口任务 (无下游依赖)."""
        all_ids = {t.task_id for t in self.tasks}
        referenced = set()
        for t in self.tasks:
            for dep in t.depends_on:
                referenced.add(dep)
        return [t for t in self.tasks if t.task_id not in referenced]

    def get_downstream_tasks(self, task_id: str) -> list[WorkflowTask]:
        """获取下游任务 (依赖此任务的任务)."""
        return [t for t in self.tasks if task_id in t.depends_on]

    def get_upstream_tasks(self, task_id: str) -> list[WorkflowTask]:
        """获取上游任务 (此任务依赖的任务)."""
        task = self.get_task(task_id)
        if task is None:
            return []
        return [self.get_task(dep) for dep in task.depends_on if self.get_task(dep) is not None]

    # ── Validation ───────────────────────────────────────────

    def validate(self) -> list[str]:
        """验证 Workflow 合法性.

        Returns:
            list[str]: 错误列表 (空列表 = 合法)
        """
        errors: list[str] = []

        task_ids = {t.task_id for t in self.tasks}

        # 检查依赖引用完整性
        for t in self.tasks:
            for dep in t.depends_on:
                if dep not in task_ids:
                    errors.append(f"Task '{t.task_id}' depends on non-existent task '{dep}'")

        # 检查循环依赖
        if self._has_cycle():
            errors.append("Workflow contains circular dependency")

        # 检查空任务列表
        if not self.tasks:
            errors.append("Workflow has no tasks")

        return errors

    def is_valid(self) -> bool:
        """检查 Workflow 是否合法."""
        return len(self.validate()) == 0

    # ── Topological Sort ─────────────────────────────────────

    def topological_order(self) -> list[list[WorkflowTask]]:
        """拓扑排序 — 返回分层执行顺序.

        每一层内的任务可以并行执行。

        Returns:
            list[list[WorkflowTask]]: 分层任务列表

        Raises:
            ValueError: 存在循环依赖
        """
        if self._has_cycle():
            raise ValueError("Cannot compute topological order: circular dependency detected")

        # BFS 分层
        in_degree: dict[str, int] = {t.task_id: len(t.depends_on) for t in self.tasks}
        downstream: dict[str, list[str]] = {t.task_id: [] for t in self.tasks}
        for t in self.tasks:
            for dep in t.depends_on:
                downstream[dep].append(t.task_id)

        layers: list[list[WorkflowTask]] = []
        current: list[str] = [tid for tid, deg in in_degree.items() if deg == 0]

        while current:
            layer = [self.get_task(tid) for tid in current if self.get_task(tid) is not None]
            layers.append(layer)
            next_layer: list[str] = []
            for tid in current:
                for child in downstream[tid]:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_layer.append(child)
            current = next_layer

        return layers

    def flat_topological_order(self) -> list[WorkflowTask]:
        """扁平化拓扑排序."""
        result: list[WorkflowTask] = []
        for layer in self.topological_order():
            result.extend(layer)
        return result

    # ── Serialization ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowDefinition":
        tasks = [WorkflowTask.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            workflow_id=data.get("workflow_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            tasks=tasks,
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    # ── Internal ─────────────────────────────────────────────

    def _has_cycle(self) -> bool:
        """DFS 检测循环依赖."""
        task_ids = {t.task_id for t in self.tasks}
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {tid: WHITE for tid in task_ids}

        def dfs(tid: str) -> bool:
            """Returns True if cycle detected."""
            color[tid] = GRAY
            task = self.get_task(tid)
            if task:
                for dep in task.depends_on:
                    if dep not in color:
                        continue
                    if color[dep] == GRAY:
                        return True
                    if color[dep] == WHITE and dfs(dep):
                        return True
            color[tid] = BLACK
            return False

        for tid in task_ids:
            if color[tid] == WHITE and dfs(tid):
                return True
        return False

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def __repr__(self) -> str:
        return (
            f"WorkflowDefinition(id={self.workflow_id[:8]}..., name={self.name}, "
            f"tasks={len(self.tasks)}, version={self.version})"
        )


# ═══════════════════════════════════════════════════════════════
# Workflow Instance
# ═══════════════════════════════════════════════════════════════


@dataclass
class WorkflowInstance:
    """E15.1.1 Workflow 运行实例 — 一次真实执行.

    WorkflowDefinition 是模板，WorkflowInstance 是模板的一次具体运行。

    Attributes:
        instance_id:   实例唯一标识
        workflow_id:   关联的 WorkflowDefinition ID
        workflow_name: Workflow 名称 (冗余)
        status:        当前状态
        context:       运行上下文 (game_id, campaign_id, 等)
        task_statuses: 各任务执行状态
        started_at:    开始时间
        completed_at:  完成时间
        error:         错误信息
        metadata:      扩展元数据
    """

    instance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_name: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    context: dict[str, Any] = field(default_factory=dict)
    task_statuses: dict[str, TaskStatus] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """标记实例开始运行."""
        self.status = WorkflowStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()

    def complete(self, status: WorkflowStatus = WorkflowStatus.SUCCESS) -> None:
        """标记实例完成."""
        self.status = status
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def fail(self, error: str = "") -> None:
        """标记实例失败."""
        self.status = WorkflowStatus.FAILED
        self.error = error
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def cancel(self) -> None:
        """取消实例."""
        self.status = WorkflowStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        """更新单个 Task 的执行状态."""
        self.task_statuses[task_id] = status

    def get_task_status(self, task_id: str) -> TaskStatus:
        """获取单个 Task 的执行状态."""
        return self.task_statuses.get(task_id, TaskStatus.PENDING)

    def is_terminal(self) -> bool:
        """是否已终止."""
        return self.status in {
            WorkflowStatus.SUCCESS,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "context": self.context,
            "task_statuses": {k: v.value for k, v in self.task_statuses.items()},
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowInstance":
        task_statuses = {}
        for k, v in data.get("task_statuses", {}).items():
            task_statuses[k] = TaskStatus(v)
        return cls(
            instance_id=data.get("instance_id", str(uuid.uuid4())),
            workflow_id=data.get("workflow_id", ""),
            workflow_name=data.get("workflow_name", ""),
            status=WorkflowStatus(data.get("status", "created")),
            context=data.get("context", {}),
            task_statuses=task_statuses,
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"WorkflowInstance(id={self.instance_id[:8]}..., "
            f"workflow={self.workflow_name}, status={self.status.value})"
        )


__all__ = [
    "WorkflowStatus",
    "TaskStatus",
    "WorkflowTask",
    "WorkflowDefinition",
    "WorkflowInstance",
]