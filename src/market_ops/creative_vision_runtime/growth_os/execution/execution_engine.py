"""E12.7.4 Execution Engine — 核心执行器，协调 TaskDispatcher 执行 ExecutionPlan."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    ApprovalStatus,
    ExecutionPlan,
    ExecutionTask,
    TaskStatus,
)
from .task_dispatcher import TaskDispatcher


class ExecutionEngine:
    """核心执行器 — 接收 ExecutionPlan，驱动 TaskDispatcher 执行."""

    def __init__(self, dispatcher: TaskDispatcher | None = None):
        self._dispatcher = dispatcher or TaskDispatcher()
        self._execution_history: list[ExecutionPlan] = []
        self._task_count: int = 0

    @property
    def dispatcher(self) -> TaskDispatcher:
        return self._dispatcher

    @property
    def execution_count(self) -> int:
        return len(self._execution_history)

    @property
    def task_count(self) -> int:
        return self._task_count

    # ── Plan Execution ────────────────────────────────────────

    def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        """执行整个计划."""
        if not plan.is_approved:
            plan.approval_status = ApprovalStatus.APPROVED

        self._task_count += plan.task_count

        result = self._dispatcher.execute_plan(plan)
        self._execution_history.append(result)
        return result

    def execute_sequential(self, plan: ExecutionPlan) -> ExecutionPlan:
        """按依赖顺序执行."""
        if not plan.is_approved:
            plan.approval_status = ApprovalStatus.APPROVED

        self._task_count += plan.task_count
        result = self._dispatcher.execute_plan(plan)
        self._execution_history.append(result)
        return result

    def execute_parallel(self, plan: ExecutionPlan) -> ExecutionPlan:
        """并行执行所有任务."""
        if not plan.is_approved:
            plan.approval_status = ApprovalStatus.APPROVED

        self._task_count += plan.task_count
        result = self._dispatcher.execute_plan_parallel(plan)
        self._execution_history.append(result)
        return result

    # ── Single Task ───────────────────────────────────────────

    def execute_task(self, task: ExecutionTask) -> ExecutionTask:
        """执行单个任务."""
        self._task_count += 1
        return self._dispatcher.dispatch(task)

    def execute_tasks(self, tasks: list[ExecutionTask]) -> list[ExecutionTask]:
        """执行一组任务."""
        self._task_count += len(tasks)
        return self._dispatcher.dispatch_group(tasks)

    # ── Retry ─────────────────────────────────────────────────

    def retry_task(self, task: ExecutionTask) -> ExecutionTask:
        """重试单个任务."""
        return self._dispatcher.retry(task)

    def retry_plan(self, plan: ExecutionPlan) -> list[ExecutionTask]:
        """重试计划中的失败任务."""
        return self._dispatcher.retry_failed(plan)

    # ── Status ────────────────────────────────────────────────

    def get_plan_status(self, plan: ExecutionPlan) -> dict[str, Any]:
        """获取计划执行状态."""
        return {
            "plan_id": plan.plan_id,
            "is_complete": plan.is_complete,
            "completion_pct": plan.completion_pct,
            "success_count": len(plan.success_tasks),
            "failed_count": len(plan.failed_tasks),
            "total_tasks": plan.task_count,
            "has_failures": plan.has_failures,
        }

    def get_summary(self) -> dict[str, Any]:
        """获取执行引擎摘要."""
        return {
            "execution_count": self.execution_count,
            "task_count": self.task_count,
            "adapter_count": self._dispatcher.adapter_count,
        }

    def get_history(self) -> list[dict[str, Any]]:
        """获取执行历史."""
        return [p.to_dict() for p in self._execution_history]

    # ── Plan Builder ──────────────────────────────────────────

    def create_plan(
        self,
        tasks: list[ExecutionTask],
        strategy_id: str = "",
        product_id: str = "",
        risk_score: float = 0.0,
    ) -> ExecutionPlan:
        """创建执行计划."""
        plan = ExecutionPlan(
            strategy_id=strategy_id,
            product_id=product_id,
            tasks=tasks,
            risk_score=risk_score,
        )
        plan.execution_order = self._dispatcher.build_execution_order(tasks)
        plan.parallel_groups = self._dispatcher.get_parallel_groups(tasks)
        return plan

    def approve_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """审批通过执行计划."""
        plan.approval_status = ApprovalStatus.APPROVED
        return plan

    def reject_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """拒绝执行计划."""
        plan.approval_status = ApprovalStatus.REJECTED
        return plan