"""E15.1.3 Task Scheduler — DAG 依赖感知 + 优先级 + 条件调度.

TaskScheduler 是 Workflow 执行引擎的「调度大脑」，根据:
  1. Task Dependency (DAG 拓扑)
  2. Context State (PAUSED/WAITING)
  3. Approval Status (审批门控)
  4. Task Priority (CRITICAL > HIGH > NORMAL > LOW)
  5. Condition Expression (条件分支)
  6. Failure Recovery (重试/跳过/终止)

自动决定下一步应该执行哪个 Task。

用法:
    scheduler = TaskScheduler(definition, context)

    # 核心调度
    result = scheduler.schedule()
    for task_id in result.next_tasks:
        execute(task_id)

    # 标记完成
    scheduler.complete(task_id, {"roas": 0.48})

    # 标记失败
    resolution = scheduler.fail(task_id, "network error")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from .models import TaskStatus, WorkflowDefinition, WorkflowTask
from .state import TaskExecutionStatus, WorkflowState

if TYPE_CHECKING:
    from .context import ExecutionContext


# ═══════════════════════════════════════════════════════════════
# Task Priority
# ═══════════════════════════════════════════════════════════════


class TaskPriority(int, Enum):
    """E15.1.3 Task 优先级.

    当多个 Workflow 同时竞争或同一层多个 Task 就绪时，
    优先级决定调度顺序。

    int 值越小优先级越高。
    """

    CRITICAL = 1  # 止损/紧急操作 (e.g. stop_loss)
    HIGH = 2      # 高优先级优化 (e.g. budget adjustment)
    NORMAL = 3    # 常规操作 (e.g. creative refresh)
    LOW = 4       # 低优先级 (e.g. report generation)

    @classmethod
    def from_string(cls, value: str) -> "TaskPriority":
        """从字符串解析优先级."""
        mapping = {
            "critical": cls.CRITICAL,
            "high": cls.HIGH,
            "normal": cls.NORMAL,
            "low": cls.LOW,
        }
        return mapping.get(value.lower(), cls.NORMAL)

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> "TaskPriority":
        """从 Task metadata 中提取优先级."""
        priority_str = metadata.get("priority", "normal")
        if isinstance(priority_str, int):
            try:
                return cls(priority_str)
            except ValueError:
                return cls.NORMAL
        return cls.from_string(str(priority_str))


# ═══════════════════════════════════════════════════════════════
# Task Schedule Status
# ═══════════════════════════════════════════════════════════════


class TaskScheduleStatus(str, Enum):
    """E15.1.3 Task 在调度器视角下的状态.

    将 TaskExecutionStatus + 依赖条件 + 审批状态 + 条件 综合为一个调度决策状态。
    """

    READY = "ready"                    # 所有依赖已满足，可立即执行
    BLOCKED = "blocked"                # 上游依赖未满足
    WAITING_APPROVAL = "waiting_approval"  # 依赖满足，但需要审批
    CONDITION_NOT_MET = "condition_not_met"  # 依赖满足，但条件表达式为 False
    RUNNING = "running"                # 正在执行中
    COMPLETED = "completed"            # 已完成
    FAILED = "failed"                  # 失败
    SKIPPED = "skipped"                # 被跳过
    WAITING_RETRY = "waiting_retry"    # 等待重试 (失败但可重试)


# ═══════════════════════════════════════════════════════════════
# Failure Resolution
# ═══════════════════════════════════════════════════════════════


class FailureAction(str, Enum):
    """E15.1.3 失败恢复动作."""

    RETRY = "retry"                       # 重试该任务
    SKIP = "skip"                         # 跳过该任务，继续下游
    SKIP_DOWNSTREAM = "skip_downstream"   # 跳过该任务及其所有下游
    FAIL_WORKFLOW = "fail_workflow"       # 终止整个 Workflow


@dataclass
class FailureResolution:
    """E15.1.3 失败恢复决策.

    Attributes:
        action:         恢复动作
        reason:         决策原因
        retry_delay_ms: 重试延迟 (毫秒), 仅 RETRY 时有效
    """

    action: FailureAction = FailureAction.FAIL_WORKFLOW
    reason: str = ""
    retry_delay_ms: int = 0


# ═══════════════════════════════════════════════════════════════
# Schedule Result
# ═══════════════════════════════════════════════════════════════


class ScheduleState(str, Enum):
    """E15.1.3 调度结果状态."""

    READY = "ready"           # 有可执行任务
    RUNNING = "running"       # 有任务正在执行
    WAITING = "waiting"       # 等待 (审批 / 暂停 / 外部事件)
    BLOCKED = "blocked"       # 所有可执行路径被阻塞
    COMPLETED = "completed"   # 所有任务已完成
    FAILED = "failed"         # 存在不可恢复的失败


@dataclass
class TaskScheduleInfo:
    """E15.1.3 单个 Task 的调度信息.

    Attributes:
        task_id:           任务 ID
        task_name:         任务名称
        status:            调度状态
        depends_on:        依赖的任务 ID 列表
        requires_approval: 是否需要审批
        priority:          任务优先级
        reason:            当前状态的原因
        retry_current:     当前重试次数
        retry_max:         最大重试次数
    """

    task_id: str = ""
    task_name: str = ""
    status: TaskScheduleStatus = TaskScheduleStatus.BLOCKED
    depends_on: list[str] = field(default_factory=list)
    requires_approval: bool = False
    priority: TaskPriority = TaskPriority.NORMAL
    reason: str = ""
    retry_current: int = 0
    retry_max: int = 0


@dataclass
class ScheduleResult:
    """E15.1.3 调度结果.

    一次调度调用的完整输出，包含:
      - 下一步应执行的任务
      - 阻塞/等待/失败的任务详情
      - 整体调度状态

    Attributes:
        next_tasks:             下一步要执行的任务 ID 列表 (按优先级排序)
        blocked_tasks:          被依赖阻塞的任务
        waiting_approval_tasks: 等待审批的任务
        condition_not_met_tasks: 条件未满足的任务
        failed_tasks:           失败的任务
        completed_tasks:        已完成的任务
        running_tasks:          正在执行的任务
        state:                  整体调度状态
        reason:                 状态说明
    """

    next_tasks: list[str] = field(default_factory=list)
    blocked_tasks: list[TaskScheduleInfo] = field(default_factory=list)
    waiting_approval_tasks: list[TaskScheduleInfo] = field(default_factory=list)
    condition_not_met_tasks: list[TaskScheduleInfo] = field(default_factory=list)
    failed_tasks: list[TaskScheduleInfo] = field(default_factory=list)
    completed_tasks: list[TaskScheduleInfo] = field(default_factory=list)
    running_tasks: list[TaskScheduleInfo] = field(default_factory=list)
    state: ScheduleState = ScheduleState.READY
    reason: str = ""

    def has_next(self) -> bool:
        """是否有可执行的任务."""
        return len(self.next_tasks) > 0

    def is_terminal(self) -> bool:
        """是否已到达终止状态."""
        return self.state in {ScheduleState.COMPLETED, ScheduleState.FAILED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_tasks": self.next_tasks,
            "blocked_tasks": [
                {
                    "task_id": t.task_id,
                    "task_name": t.task_name,
                    "status": t.status.value,
                    "reason": t.reason,
                }
                for t in self.blocked_tasks
            ],
            "waiting_approval_tasks": [
                {
                    "task_id": t.task_id,
                    "task_name": t.task_name,
                    "reason": t.reason,
                }
                for t in self.waiting_approval_tasks
            ],
            "condition_not_met_tasks": [
                {
                    "task_id": t.task_id,
                    "task_name": t.task_name,
                    "reason": t.reason,
                }
                for t in self.condition_not_met_tasks
            ],
            "failed_tasks": [
                {
                    "task_id": t.task_id,
                    "task_name": t.task_name,
                    "reason": t.reason,
                    "retry_current": t.retry_current,
                    "retry_max": t.retry_max,
                }
                for t in self.failed_tasks
            ],
            "completed_tasks": [t.task_id for t in self.completed_tasks],
            "running_tasks": [t.task_id for t in self.running_tasks],
            "state": self.state.value,
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════════
# Task Scheduler
# ═══════════════════════════════════════════════════════════════


class TaskScheduler:
    """E15.1.3 Task 调度器 — DAG + Priority + Condition + Approval + Recovery.

    调度器是 Workflow 执行引擎的「大脑」，负责在每一次 tick 中决定
    哪些 Task 可以执行、哪些需要等待、哪些需要重试或终止。

    调度决策流程:
      1. 检查 Context 状态 (PAUSED/WAITING → 阻止新调度)
      2. 遍历所有未完成 Task, 检查依赖是否满足
      3. 依赖满足的 Task 检查审批状态
      4. 依赖满足的 Task 评估条件表达式
      5. 按优先级排序就绪任务
      6. 失败的 Task 应用失败恢复策略
      7. 返回 ScheduleResult

    Attributes:
        definition:  Workflow 静态模板 (DAG 结构)
        context:     运行时执行上下文 (状态 + 变量)
    """

    def __init__(self, definition: WorkflowDefinition, context: ExecutionContext) -> None:
        if definition is None:
            raise ValueError("definition cannot be None")
        if context is None:
            raise ValueError("context cannot be None")

        self.definition = definition
        self.context = context

    # ── Core API ──────────────────────────────────────────────

    def schedule(self) -> ScheduleResult:
        """调度入口 — 获取下一步应执行的任务.

        这是调度器的核心方法，每次调用返回当前状态下的调度决策。
        就绪任务按优先级排序 (CRITICAL > HIGH > NORMAL > LOW)。

        Returns:
            ScheduleResult: 包含下一步任务和完整调度状态
        """
        result = self._raw_schedule()
        # 按优先级排序就绪任务
        if result.next_tasks:
            result.next_tasks = self._order_by_priority(result.next_tasks)
        return result

    def get_next_tasks(self) -> ScheduleResult:
        """获取下一步应执行的任务 (别名，兼容旧 API)."""
        return self.schedule()

    def complete(self, task_id: str, result: dict[str, Any] | None = None) -> ScheduleResult:
        """标记 Task 完成并返回新的调度结果.

        Args:
            task_id: 完成的任务 ID
            result:  任务输出数据

        Returns:
            ScheduleResult: 更新后的调度结果
        """
        self.context.complete_task(task_id, result)
        return self.schedule()

    def fail(self, task_id: str, error: str = "") -> FailureResolution:
        """标记 Task 失败并返回恢复策略.

        Args:
            task_id: 失败的任务 ID
            error:   错误信息

        Returns:
            FailureResolution: 失败恢复决策
        """
        self.context.fail_task(task_id, error)
        return self.resolve_failure(task_id)

    def get_ready_tasks(self) -> list[WorkflowTask]:
        """获取所有就绪任务 (按优先级排序)."""
        result = self.schedule()
        ready_tasks: list[WorkflowTask] = []
        for task_id in result.next_tasks:
            task = self.definition.get_task(task_id)
            if task is not None:
                ready_tasks.append(task)
        return ready_tasks

    def can_proceed(self) -> bool:
        """检查 Workflow 是否可以继续执行."""
        result = self.schedule()
        return result.state in {
            ScheduleState.READY,
            ScheduleState.RUNNING,
            ScheduleState.WAITING,
        }

    # ── Task Status ───────────────────────────────────────────

    def get_task_schedule_status(self, task_id: str) -> TaskScheduleStatus:
        """获取单个 Task 的调度状态."""
        info = self._build_task_schedule_info(task_id)
        if info is None:
            raise ValueError(f"Task '{task_id}' not found in workflow")
        return info.status

    def get_task_schedule_info(self, task_id: str) -> TaskScheduleInfo | None:
        """获取单个 Task 的调度信息详情."""
        return self._build_task_schedule_info(task_id)

    def get_all_task_schedule_infos(self) -> list[TaskScheduleInfo]:
        """获取所有 Task 的调度信息."""
        return self._build_task_schedule_infos()

    # ── Failure Recovery ─────────────────────────────────────

    def resolve_failure(self, task_id: str) -> FailureResolution:
        """决定失败任务的恢复策略.

        决策逻辑:
          1. 如果还有重试次数 → RETRY
          2. 如果任务本身是可选的 → SKIP
          3. 如果重试耗尽 → 检查下游
             - 无下游 → SKIP
             - 有关键下游 → SKIP_DOWNSTREAM
             - 全部可选下游 → SKIP

        Args:
            task_id: 失败的任务 ID

        Returns:
            FailureResolution: 恢复决策
        """
        task = self.definition.get_task(task_id)
        if task is None:
            return FailureResolution(
                action=FailureAction.FAIL_WORKFLOW,
                reason=f"Task '{task_id}' not found in workflow",
            )

        task_state = self.context.get_task_state(task_id)
        if task_state is None:
            return FailureResolution(
                action=FailureAction.FAIL_WORKFLOW,
                reason=f"No execution state for task '{task_id}'",
            )

        # 1. 可重试
        if task_state.can_retry():
            remaining = task_state.retry_max - task_state.retry_current
            return FailureResolution(
                action=FailureAction.RETRY,
                reason=f"Task has {remaining} retry attempt(s) remaining",
                retry_delay_ms=0,
            )

        # 2. 重试耗尽 — 如果任务本身是可选的，直接 SKIP
        if self._is_task_optional(task):
            return FailureResolution(
                action=FailureAction.SKIP,
                reason="Task is optional — skipping unconditionally",
            )

        # 3. 检查下游
        downstream = self.definition.get_downstream_tasks(task_id)

        if not downstream:
            return FailureResolution(
                action=FailureAction.SKIP,
                reason="No downstream tasks depend on this task",
            )

        critical_downstream = [
            t for t in downstream
            if not self._is_task_optional(t)
        ]

        if critical_downstream:
            return FailureResolution(
                action=FailureAction.SKIP_DOWNSTREAM,
                reason=f"{len(critical_downstream)} critical downstream task(s) would be blocked",
            )
        else:
            return FailureResolution(
                action=FailureAction.SKIP,
                reason="All downstream tasks are optional or can proceed independently",
            )

    def can_retry(self, task_id: str) -> bool:
        """检查任务是否可以重试."""
        resolution = self.resolve_failure(task_id)
        return resolution.action == FailureAction.RETRY

    # ── Internal: Core Scheduling Logic ───────────────────────

    def _raw_schedule(self) -> ScheduleResult:
        """核心调度逻辑 (不含优先级排序)."""
        ctx_state = self.context.state

        if ctx_state.is_terminal():
            if ctx_state == WorkflowState.SUCCESS:
                return ScheduleResult(
                    state=ScheduleState.COMPLETED,
                    reason="Workflow already completed successfully",
                )
            elif ctx_state == WorkflowState.FAILED:
                return ScheduleResult(
                    state=ScheduleState.FAILED,
                    reason="Workflow has failed",
                )
            else:
                return ScheduleResult(
                    state=ScheduleState.FAILED,
                    reason=f"Workflow is in terminal state: {ctx_state.value}",
                )

        if ctx_state == WorkflowState.PAUSED:
            return ScheduleResult(
                state=ScheduleState.WAITING,
                reason="Workflow is paused",
            )

        if ctx_state == WorkflowState.WAITING:
            return ScheduleResult(
                state=ScheduleState.WAITING,
                reason="Workflow is waiting for external event (approval/input)",
            )

        all_info = self._build_task_schedule_infos()

        ready = [t for t in all_info if t.status == TaskScheduleStatus.READY]
        running = [t for t in all_info if t.status == TaskScheduleStatus.RUNNING]
        blocked = [t for t in all_info if t.status == TaskScheduleStatus.BLOCKED]
        waiting_approval = [t for t in all_info if t.status == TaskScheduleStatus.WAITING_APPROVAL]
        condition_not_met = [t for t in all_info if t.status == TaskScheduleStatus.CONDITION_NOT_MET]
        waiting_retry = [t for t in all_info if t.status == TaskScheduleStatus.WAITING_RETRY]
        failed = [t for t in all_info if t.status == TaskScheduleStatus.FAILED]
        completed = [t for t in all_info if t.status == TaskScheduleStatus.COMPLETED]
        skipped = [t for t in all_info if t.status == TaskScheduleStatus.SKIPPED]

        total = len(all_info)
        terminal_count = len(completed) + len(skipped) + len(failed)

        if terminal_count == total:
            if failed:
                return ScheduleResult(
                    next_tasks=[],
                    blocked_tasks=blocked,
                    waiting_approval_tasks=waiting_approval,
                    condition_not_met_tasks=condition_not_met,
                    failed_tasks=failed,
                    completed_tasks=completed + skipped,
                    running_tasks=running,
                    state=ScheduleState.FAILED,
                    reason=f"{len(failed)} task(s) failed with no recovery possible",
                )
            else:
                return ScheduleResult(
                    next_tasks=[],
                    completed_tasks=completed + skipped,
                    running_tasks=running,
                    state=ScheduleState.COMPLETED,
                    reason="All tasks completed",
                )

        if ready:
            return ScheduleResult(
                next_tasks=[t.task_id for t in ready],
                blocked_tasks=blocked,
                waiting_approval_tasks=waiting_approval,
                condition_not_met_tasks=condition_not_met,
                failed_tasks=failed + waiting_retry,
                completed_tasks=completed + skipped,
                running_tasks=running,
                state=ScheduleState.READY,
                reason=f"{len(ready)} task(s) ready to execute",
            )

        if running:
            return ScheduleResult(
                next_tasks=[],
                blocked_tasks=blocked,
                waiting_approval_tasks=waiting_approval,
                condition_not_met_tasks=condition_not_met,
                failed_tasks=failed + waiting_retry,
                completed_tasks=completed + skipped,
                running_tasks=running,
                state=ScheduleState.RUNNING,
                reason=f"{len(running)} task(s) currently executing",
            )

        if waiting_approval:
            return ScheduleResult(
                next_tasks=[],
                blocked_tasks=blocked,
                waiting_approval_tasks=waiting_approval,
                condition_not_met_tasks=condition_not_met,
                failed_tasks=failed + waiting_retry,
                completed_tasks=completed + skipped,
                running_tasks=running,
                state=ScheduleState.WAITING,
                reason=f"{len(waiting_approval)} task(s) waiting for approval",
            )

        if condition_not_met:
            return ScheduleResult(
                next_tasks=[],
                blocked_tasks=blocked,
                waiting_approval_tasks=waiting_approval,
                condition_not_met_tasks=condition_not_met,
                failed_tasks=failed + waiting_retry,
                completed_tasks=completed + skipped,
                running_tasks=running,
                state=ScheduleState.BLOCKED,
                reason=f"{len(condition_not_met)} task(s) condition not met",
            )

        return ScheduleResult(
            next_tasks=[],
            blocked_tasks=blocked,
            waiting_approval_tasks=waiting_approval,
            condition_not_met_tasks=condition_not_met,
            failed_tasks=failed + waiting_retry,
            completed_tasks=completed + skipped,
            running_tasks=running,
            state=ScheduleState.BLOCKED,
            reason="All pending tasks are blocked by dependencies",
        )

    def _order_by_priority(self, task_ids: list[str]) -> list[str]:
        """按优先级排序就绪任务 ID 列表 (CRITICAL 优先)."""
        if len(task_ids) <= 1:
            return task_ids

        def _priority_key(tid: str) -> int:
            task = self.definition.get_task(tid)
            if task is None:
                return TaskPriority.NORMAL.value
            return TaskPriority.from_metadata(task.metadata).value

        return sorted(task_ids, key=_priority_key)

    # ── Internal: Task Schedule Info ──────────────────────────

    def _build_task_schedule_infos(self) -> list[TaskScheduleInfo]:
        """构建所有 Task 的调度信息列表."""
        infos: list[TaskScheduleInfo] = []
        for task in self.definition.tasks:
            info = self._build_task_schedule_info(task.task_id)
            if info is not None:
                infos.append(info)
        return infos

    def _build_task_schedule_info(self, task_id: str) -> TaskScheduleInfo | None:
        """构建单个 Task 的调度信息."""
        task = self.definition.get_task(task_id)
        if task is None:
            return None

        exec_state = self.context.get_task_state(task_id)

        info = TaskScheduleInfo(
            task_id=task_id,
            task_name=task.name,
            depends_on=list(task.depends_on),
            requires_approval=task.requires_approval,
            priority=TaskPriority.from_metadata(task.metadata),
            retry_max=task.retry_count,
        )

        if exec_state is not None:
            info.retry_current = exec_state.retry_current

        if exec_state is None:
            deps_satisfied = self._are_dependencies_satisfied(task)
            if deps_satisfied:
                info = self._apply_condition_and_approval(task, info)
            else:
                info.status = TaskScheduleStatus.BLOCKED
                info.reason = self._get_blocked_reason(task)
        elif exec_state.status == TaskExecutionStatus.PENDING:
            deps_satisfied = self._are_dependencies_satisfied(task)
            if not deps_satisfied:
                info.status = TaskScheduleStatus.BLOCKED
                info.reason = self._get_blocked_reason(task)
            else:
                info = self._apply_condition_and_approval(task, info)
        elif exec_state.status == TaskExecutionStatus.RUNNING:
            info.status = TaskScheduleStatus.RUNNING
            info.reason = "Task is executing"
        elif exec_state.status == TaskExecutionStatus.COMPLETED:
            info.status = TaskScheduleStatus.COMPLETED
            info.reason = "Task completed successfully"
        elif exec_state.status == TaskExecutionStatus.FAILED:
            if exec_state.can_retry():
                info.status = TaskScheduleStatus.WAITING_RETRY
                info.reason = f"Failed but can retry ({exec_state.retry_current}/{exec_state.retry_max})"
            else:
                info.status = TaskScheduleStatus.FAILED
                info.reason = f"All retries exhausted ({exec_state.retry_max})"
        elif exec_state.status == TaskExecutionStatus.SKIPPED:
            info.status = TaskScheduleStatus.SKIPPED
            info.reason = "Task was skipped"
        elif exec_state.status == TaskExecutionStatus.TIMEOUT:
            if exec_state.can_retry():
                info.status = TaskScheduleStatus.WAITING_RETRY
                info.reason = f"Timed out but can retry ({exec_state.retry_current}/{exec_state.retry_max})"
            else:
                info.status = TaskScheduleStatus.FAILED
                info.reason = "Task timed out and retries exhausted"
        elif exec_state.status == TaskExecutionStatus.WAITING:
            info.status = TaskScheduleStatus.WAITING_APPROVAL
            info.reason = "Task is waiting for external event"

        return info

    def _apply_condition_and_approval(
        self, task: WorkflowTask, info: TaskScheduleInfo
    ) -> TaskScheduleInfo:
        """依赖满足后，依次检查条件表达式和审批状态."""
        # 1. 检查条件表达式
        if not self._evaluate_condition(task):
            info.status = TaskScheduleStatus.CONDITION_NOT_MET
            info.reason = f"Condition not met: {self._get_condition_source(task)}"
            return info

        # 2. 检查审批
        if task.requires_approval and not self._is_approval_granted(task.task_id):
            info.status = TaskScheduleStatus.WAITING_APPROVAL
            info.reason = "Awaiting human approval"
            return info

        info.status = TaskScheduleStatus.READY
        info.reason = "Ready to execute"
        return info

    # ── Internal: Condition Evaluation ────────────────────────

    def _evaluate_condition(self, task: WorkflowTask) -> bool:
        """评估 Task 的条件表达式.

        支持三种条件来源 (优先级从高到低):
          1. metadata["condition"] — Callable[[ExecutionContext], bool]
          2. metadata["condition_expr"] — 字符串表达式 (如 "roas < 0.5")
          3. 无条件 → 默认 True

        字符串表达式支持:
          - 简单比较: "roas < 0.5", "fatigue > 0.7"
          - 变量引用: 从 context.variables 中读取
        """
        # 1. Callable 条件
        condition_callable = task.metadata.get("condition")
        if callable(condition_callable):
            try:
                return bool(condition_callable(self.context))
            except Exception:
                return False

        # 2. 字符串表达式
        condition_expr = task.metadata.get("condition_expr")
        if condition_expr and isinstance(condition_expr, str):
            return self._evaluate_expression(condition_expr)

        # 3. 无条件
        return True

    def _evaluate_expression(self, expr: str) -> bool:
        """评估简单字符串条件表达式.

        支持格式: "<variable> <op> <value>"
        例如: "roas < 0.5", "fatigue >= 0.7", "budget == 5000"

        Args:
            expr: 条件表达式字符串

        Returns:
            bool: 表达式结果
        """
        # 解析表达式: var op value
        match = re.match(
            r"^\s*(\w+)\s*(==|!=|>=|<=|>|<)\s*([\d.]+)\s*$", expr
        )
        if not match:
            return False

        var_name = match.group(1)
        operator = match.group(2)
        try:
            threshold = float(match.group(3))
        except ValueError:
            return False

        # 从 context 中获取变量值
        var_value = self.context.get_variable(var_name)
        if var_value is None:
            # 也尝试从 outputs 中查找
            for output in self.context.outputs.values():
                if var_name in output:
                    var_value = output[var_name]
                    break

        if var_value is None:
            return False

        try:
            var_value = float(var_value)
        except (ValueError, TypeError):
            return False

        # 执行比较
        if operator == "==":
            return var_value == threshold
        elif operator == "!=":
            return var_value != threshold
        elif operator == ">=":
            return var_value >= threshold
        elif operator == "<=":
            return var_value <= threshold
        elif operator == ">":
            return var_value > threshold
        elif operator == "<":
            return var_value < threshold

        return False

    def _get_condition_source(self, task: WorkflowTask) -> str:
        """获取条件表达式源文本."""
        condition_callable = task.metadata.get("condition")
        if callable(condition_callable):
            return "<lambda>"
        condition_expr = task.metadata.get("condition_expr")
        if condition_expr and isinstance(condition_expr, str):
            return condition_expr
        return "none"

    # ── Internal: Dependency & Approval ───────────────────────

    def _are_dependencies_satisfied(self, task: WorkflowTask) -> bool:
        """检查任务的所有依赖是否已满足 (完成或跳过)."""
        if not task.depends_on:
            return True

        for dep_id in task.depends_on:
            dep_state = self.context.get_task_state(dep_id)
            if dep_state is None:
                return False
            if dep_state.status not in {
                TaskExecutionStatus.COMPLETED,
                TaskExecutionStatus.SKIPPED,
            }:
                return False
        return True

    def _get_blocked_reason(self, task: WorkflowTask) -> str:
        """获取任务被阻塞的原因详情."""
        if not task.depends_on:
            return "Unknown reason"

        blocked_by: list[str] = []
        for dep_id in task.depends_on:
            dep_state = self.context.get_task_state(dep_id)
            if dep_state is None:
                blocked_by.append(f"{dep_id}(not started)")
            elif dep_state.status == TaskExecutionStatus.PENDING:
                blocked_by.append(f"{dep_id}(pending)")
            elif dep_state.status == TaskExecutionStatus.RUNNING:
                blocked_by.append(f"{dep_id}(running)")
            elif dep_state.status == TaskExecutionStatus.FAILED:
                blocked_by.append(f"{dep_id}(failed)")
            elif dep_state.status == TaskExecutionStatus.WAITING:
                blocked_by.append(f"{dep_id}(waiting)")
            elif dep_state.status == TaskExecutionStatus.TIMEOUT:
                blocked_by.append(f"{dep_id}(timeout)")

        if not blocked_by:
            return "Unknown reason"

        return f"Blocked by: {', '.join(blocked_by)}"

    def _is_approval_granted(self, task_id: str) -> bool:
        """检查任务的审批是否已通过."""
        approval_ctx = self.context.get_approval_context()
        if not approval_ctx:
            return False
        return (
            approval_ctx.get("task_id") == task_id
            and approval_ctx.get("status") == "approved"
        )

    def _is_task_optional(self, task: WorkflowTask) -> bool:
        """判断任务是否可选 (失败不影响下游)."""
        return task.metadata.get("optional", False)


# ═══════════════════════════════════════════════════════════════
# Backward Compatibility
# ═══════════════════════════════════════════════════════════════

DAGScheduler = TaskScheduler  # 向后兼容别名


__all__ = [
    "TaskPriority",
    "TaskScheduleStatus",
    "TaskScheduleInfo",
    "ScheduleState",
    "ScheduleResult",
    "FailureAction",
    "FailureResolution",
    "TaskScheduler",
    "DAGScheduler",
]