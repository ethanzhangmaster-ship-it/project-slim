"""E14.1.3 Task Protocol — 多 Agent 任务协议.

任务协议定义 Agent 间任务分配、执行和追踪的标准:
  - TaskStatus: 任务生命周期
  - GrowthTask: 任务实体 (可分解为子任务)
  - TaskAssignment: 任务分配记录
  - TaskResult: 任务执行结果
  - TaskTracker: 任务追踪器 (查询进度、依赖)
  - TaskDecomposer: 目标分解器 (business goal → 子任务)

设计原则:
  - 任务可分解为子任务 (hierarchical)
  - 任务有明确的所有者和截止时间
  - 任务执行结果可追溯
  - 支持依赖关系 (A → B → C)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .agent_message import AgentIdentity, AgentRole, MessagePriority


# ═══════════════════════════════════════════════════════════════
# Task Status
# ═══════════════════════════════════════════════════════════════


class TaskStatus(str, Enum):
    """任务生命周期状态."""
    PENDING = "pending"          # 待分配
    ASSIGNED = "assigned"        # 已分配
    ACCEPTED = "accepted"        # 已接受
    IN_PROGRESS = "in_progress"  # 执行中
    BLOCKED = "blocked"          # 被阻塞 (依赖未满足)
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消
    REJECTED = "rejected"        # 被拒绝


class TaskPriority(str, Enum):
    """任务优先级."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════
# Growth Task
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthTask:
    """增长任务 — 可被分配给 Agent 的工作单元.

    Attributes:
        task_id: 任务 ID
        parent_task_id: 父任务 ID (层级分解)
        title: 任务标题
        description: 任务描述
        goal: 关联的增长目标
        assigned_to: 分配给哪个 Agent (role 或 identity)
        assigned_role: 目标角色
        priority: 优先级
        status: 当前状态
        expected_outcome: 预期结果
        success_criteria: 成功标准
        deadline: 截止时间
        estimated_duration_minutes: 预估耗时
        dependencies: 依赖的任务 ID 列表
        subtasks: 子任务 ID 列表
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: str = ""
    title: str = ""
    description: str = ""
    goal: str = ""
    assigned_to: str = ""         # Agent ID
    assigned_role: AgentRole | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    expected_outcome: str = ""
    success_criteria: str = ""
    deadline: str = ""
    estimated_duration_minutes: float = 0.0
    dependencies: list[str] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_leaf(self) -> bool:
        """是否为叶子任务 (无子任务)."""
        return len(self.subtasks) == 0

    @property
    def is_root(self) -> bool:
        """是否为根任务."""
        return not self.parent_task_id

    @property
    def is_overdue(self) -> bool:
        """是否过期."""
        if not self.deadline:
            return False
        return datetime.now(timezone.utc).isoformat() > self.deadline

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "title": self.title,
            "description": self.description,
            "goal": self.goal,
            "assigned_to": self.assigned_to,
            "assigned_role": self.assigned_role.value if self.assigned_role else None,
            "priority": self.priority.value,
            "status": self.status.value,
            "expected_outcome": self.expected_outcome,
            "success_criteria": self.success_criteria,
            "deadline": self.deadline,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "dependencies": self.dependencies,
            "subtasks": self.subtasks,
            "is_leaf": self.is_leaf,
            "is_root": self.is_root,
            "is_overdue": self.is_overdue,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Task Assignment
# ═══════════════════════════════════════════════════════════════


@dataclass
class TaskAssignment:
    """任务分配 — 记录任务分配事件.

    Attributes:
        assignment_id: 分配 ID
        task_id: 任务 ID
        assigned_by: 分配者 (Supervisor)
        assigned_to: 被分配者 (Agent)
        assigned_at: 分配时间
        accepted_at: 接受时间
        rejected_reason: 拒绝原因
        metadata: 扩展元数据
    """
    assignment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    assigned_by: str = ""
    assigned_to: str = ""
    assigned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    accepted_at: str = ""
    rejected_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "assigned_by": self.assigned_by,
            "assigned_to": self.assigned_to,
            "assigned_at": self.assigned_at,
            "accepted_at": self.accepted_at,
            "rejected_reason": self.rejected_reason,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Task Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class TaskResult:
    """任务结果 — Agent 完成任务后的汇报.

    Attributes:
        result_id: 结果 ID
        task_id: 关联任务 ID
        completed_by: 完成者 ID
        status: 完成状态
        summary: 结果摘要
        output: 输出数据
        metrics_impact: 指标影响
        learnings: 经验教训
        duration_seconds: 耗时
        errors: 错误信息
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    completed_by: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    summary: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    metrics_impact: dict[str, float] = field(default_factory=dict)
    learnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "task_id": self.task_id,
            "completed_by": self.completed_by,
            "status": self.status.value,
            "summary": self.summary,
            "output": self.output,
            "metrics_impact": self.metrics_impact,
            "learnings": self.learnings,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════
# Task Tracker
# ═══════════════════════════════════════════════════════════════


class TaskTracker:
    """任务追踪器 — 管理所有任务的状态和进度.

    职责:
      - 创建/分配/更新任务
      - 查询任务进度
      - 检查依赖关系
      - 汇总任务统计
    """

    def __init__(self):
        self._tasks: dict[str, GrowthTask] = {}
        self._assignments: dict[str, TaskAssignment] = {}
        self._results: dict[str, TaskResult] = {}

    # ── 任务管理 ──────────────────────────────────────────────

    def create_task(self, task: GrowthTask) -> GrowthTask:
        """创建任务."""
        self._tasks[task.task_id] = task
        return task

    def create_subtask(
        self,
        parent: GrowthTask,
        title: str,
        description: str = "",
        assigned_role: AgentRole | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> GrowthTask:
        """创建子任务."""
        subtask = GrowthTask(
            parent_task_id=parent.task_id,
            title=title,
            description=description,
            assigned_role=assigned_role or parent.assigned_role,
            priority=priority,
            goal=parent.goal,
        )
        self._tasks[subtask.task_id] = subtask
        parent.subtasks.append(subtask.task_id)
        return subtask

    def assign_task(self, task_id: str, assigned_to: str, assigned_by: str = "") -> TaskAssignment:
        """分配任务."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.assigned_to = assigned_to
        task.status = TaskStatus.ASSIGNED

        assignment = TaskAssignment(
            task_id=task_id,
            assigned_by=assigned_by,
            assigned_to=assigned_to,
        )
        self._assignments[assignment.assignment_id] = assignment
        return assignment

    def update_task_status(self, task_id: str, status: TaskStatus) -> GrowthTask:
        """更新任务状态."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = status
        if status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.now(timezone.utc).isoformat()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.now(timezone.utc).isoformat()

        return task

    def complete_task(self, task_id: str, result: TaskResult) -> None:
        """完成任务并记录结果."""
        task = self.update_task_status(task_id, result.status)
        self._results[result.result_id] = result

        # 检查父任务是否全部完成
        if task.parent_task_id:
            parent = self._tasks.get(task.parent_task_id)
            if parent and self._all_subtasks_done(parent.task_id):
                parent.status = TaskStatus.COMPLETED
                parent.completed_at = datetime.now(timezone.utc).isoformat()

    def _all_subtasks_done(self, task_id: str) -> bool:
        """检查所有子任务是否完成."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        return all(
            self._tasks[st].status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
            for st in task.subtasks
            if st in self._tasks
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_task(self, task_id: str) -> GrowthTask | None:
        """获取任务."""
        return self._tasks.get(task_id)

    def get_subtasks(self, task_id: str) -> list[GrowthTask]:
        """获取子任务."""
        task = self._tasks.get(task_id)
        if not task:
            return []
        return [self._tasks[st] for st in task.subtasks if st in self._tasks]

    def get_root_tasks(self) -> list[GrowthTask]:
        """获取所有根任务."""
        return [t for t in self._tasks.values() if t.is_root]

    def get_tasks_by_status(self, status: TaskStatus) -> list[GrowthTask]:
        """按状态查询任务."""
        return [t for t in self._tasks.values() if t.status == status]

    def get_tasks_by_agent(self, agent_id: str) -> list[GrowthTask]:
        """按 Agent 查询任务."""
        return [t for t in self._tasks.values() if t.assigned_to == agent_id]

    def get_tasks_by_role(self, role: AgentRole) -> list[GrowthTask]:
        """按角色查询任务."""
        return [t for t in self._tasks.values() if t.assigned_role == role]

    def get_pending_tasks(self) -> list[GrowthTask]:
        """获取待分配任务."""
        return self.get_tasks_by_status(TaskStatus.PENDING)

    def get_blocked_tasks(self) -> list[GrowthTask]:
        """获取被阻塞的任务."""
        return self.get_tasks_by_status(TaskStatus.BLOCKED)

    def get_ready_tasks(self) -> list[GrowthTask]:
        """获取就绪任务 (依赖已满足)."""
        ready = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            if self._dependencies_met(task):
                ready.append(task)
        return ready

    def _dependencies_met(self, task: GrowthTask) -> bool:
        """检查依赖是否满足."""
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if not dep or dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def get_result(self, task_id: str) -> TaskResult | None:
        """获取任务结果."""
        for result in self._results.values():
            if result.task_id == task_id:
                return result
        return None

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取任务追踪统计."""
        total = len(self._tasks)
        if total == 0:
            return {"total_tasks": 0}

        status_counts = {}
        for task in self._tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

        return {
            "total_tasks": total,
            "total_assignments": len(self._assignments),
            "total_results": len(self._results),
            "status_counts": status_counts,
            "completion_rate": (
                status_counts.get("completed", 0) / total
                if total > 0 else 0
            ),
            "root_tasks": len(self.get_root_tasks()),
            "pending_tasks": status_counts.get("pending", 0),
            "blocked_tasks": status_counts.get("blocked", 0),
        }

    def reset(self) -> None:
        """重置追踪器."""
        self._tasks.clear()
        self._assignments.clear()
        self._results.clear()


# ═══════════════════════════════════════════════════════════════
# Task Decomposer
# ═══════════════════════════════════════════════════════════════


class TaskDecomposer:
    """目标分解器 — 将 Business Goal 分解为可执行的 Agent 子任务.

    职责:
      - 接收高层目标 (如 "本月利润提升30%")
      - 分解为按 Agent 角色的子任务
      - 建立任务依赖关系
    """

    # 默认分解策略: goal → 各角色子任务
    DEFAULT_DECOMPOSITION: dict[AgentRole, list[dict[str, Any]]] = {
        AgentRole.UA: [
            {"title": "Optimize ROAS", "description": "分析并优化广告系列 ROAS"},
            {"title": "Scale winning campaigns", "description": "识别并放大高 ROAS 系列"},
            {"title": "Cut underperforming ads", "description": "暂停低效广告"},
        ],
        AgentRole.CREATIVE: [
            {"title": "Detect creative fatigue", "description": "监控素材疲劳度"},
            {"title": "Generate variants", "description": "基于 winning DNA 生成变体"},
            {"title": "Test new creatives", "description": "投放新素材并收集数据"},
        ],
        AgentRole.MONETIZATION: [
            {"title": "Optimize IAP offers", "description": "优化内购定价和礼包"},
            {"title": "Improve payer conversion", "description": "提升付费转化率"},
            {"title": "Analyze LTV", "description": "分析用户生命周期价值"},
        ],
        AgentRole.PRODUCT: [
            {"title": "Improve D7 retention", "description": "提升第7天留存率"},
            {"title": "Optimize level progression", "description": "优化关卡进度"},
            {"title": "Run engagement events", "description": "策划并执行活动"},
        ],
    }

    def __init__(self, tracker: TaskTracker | None = None):
        self._tracker = tracker or TaskTracker()

    def decompose(
        self,
        goal: str,
        target_roles: list[AgentRole] | None = None,
        custom_decomposition: dict[AgentRole, list[dict[str, Any]]] | None = None,
    ) -> list[GrowthTask]:
        """将 Business Goal 分解为子任务.

        Args:
            goal: 业务目标 (如 "本月利润提升30%")
            target_roles: 目标角色 (默认全部)
            custom_decomposition: 自定义分解策略

        Returns:
            根任务 + 子任务列表
        """
        roles = target_roles or list(self.DEFAULT_DECOMPOSITION.keys())
        decomposition = custom_decomposition or self.DEFAULT_DECOMPOSITION

        # 创建根任务
        root_task = GrowthTask(
            title=f"Goal: {goal}",
            description=goal,
            goal=goal,
            priority=TaskPriority.CRITICAL,
        )
        self._tracker.create_task(root_task)

        # 按角色创建子任务
        for role in roles:
            role_tasks = decomposition.get(role, [])
            for task_spec in role_tasks:
                subtask = self._tracker.create_subtask(
                    parent=root_task,
                    title=task_spec["title"],
                    description=task_spec.get("description", ""),
                    assigned_role=role,
                    priority=TaskPriority.HIGH,
                )
                yield subtask

        yield root_task

    def get_tracker(self) -> TaskTracker:
        """获取关联的 TaskTracker."""
        return self._tracker


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_task_tracker() -> TaskTracker:
    """创建默认任务追踪器."""
    return TaskTracker()


def create_task_decomposer() -> TaskDecomposer:
    """创建默认目标分解器."""
    return TaskDecomposer()