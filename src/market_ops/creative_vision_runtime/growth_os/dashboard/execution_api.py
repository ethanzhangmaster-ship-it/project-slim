"""E12.7.7 Execution API — 执行状态查看与控制."""

from __future__ import annotations

from typing import Any

from ..execution.execution_controller import ExecutionController
from ..execution.models import ExecutionPlan, ExecutionTask, TaskStatus

from .models import TaskView


class ExecutionAPI:
    """执行 API — 查看执行状态和控制任务.

    提供:
      - get_running_tasks():   获取运行中任务
      - get_task_detail():     任务详情
      - approve_task():        审批任务
      - cancel_task():         取消任务
      - rollback_task():       回滚任务
      - get_execution_summary(): 执行摘要
    """

    def __init__(self, executor: ExecutionController | None = None):
        self._executor = executor or ExecutionController()
        self._query_count: int = 0
        self._plans: dict[str, ExecutionPlan] = {}

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── Running Tasks ─────────────────────────────────────────

    def get_running_tasks(self, product_id: str = "") -> list[TaskView]:
        """获取运行中任务."""
        self._query_count += 1

        result: list[TaskView] = []
        for plan in self._plans.values():
            for task in plan.tasks:
                if product_id and task.product_id != product_id:
                    continue
                if task.status in {TaskStatus.RUNNING, TaskStatus.CREATED, TaskStatus.APPROVED}:
                    result.append(self._task_to_view(task))

        return result

    def get_all_tasks(self, product_id: str = "") -> list[TaskView]:
        """获取所有任务."""
        self._query_count += 1

        result: list[TaskView] = []
        for plan in self._plans.values():
            for task in plan.tasks:
                if product_id and task.product_id != product_id:
                    continue
                result.append(self._task_to_view(task))

        return result

    def get_task_detail(self, task_id: str) -> dict[str, Any] | None:
        """获取任务详情."""
        self._query_count += 1

        for plan in self._plans.values():
            for task in plan.tasks:
                if task.task_id == task_id:
                    return {
                        **self._task_to_view(task).to_dict(),
                        "dependencies": task.dependencies,
                        "parameters": task.parameters,
                        "plan_id": plan.plan_id,
                    }
        return None

    # ── Task Control ──────────────────────────────────────────

    def approve_task(self, task_id: str, plan_id: str | None = None) -> bool:
        """审批任务."""
        self._query_count += 1

        if plan_id:
            plan = self._plans.get(plan_id)
            if plan:
                self._executor.approve(plan)
                return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """取消任务."""
        self._query_count += 1

        for plan in self._plans.values():
            for task in plan.tasks:
                if task.task_id == task_id and task.status in {TaskStatus.CREATED, TaskStatus.APPROVED, TaskStatus.RUNNING}:
                    task.status = TaskStatus.CANCELLED
                    return True
        return False

    def rollback_task(self, task_id: str) -> bool:
        """回滚任务."""
        self._query_count += 1

        for plan in self._plans.values():
            for task in plan.tasks:
                if task.task_id == task_id:
                    task.status = TaskStatus.ROLLED_BACK
                    return True
        return False

    # ── Plan Management ───────────────────────────────────────

    def register_plan(self, plan: ExecutionPlan) -> None:
        """注册执行计划."""
        self._plans[plan.plan_id] = plan

    def get_execution_summary(self) -> dict[str, Any]:
        """获取执行摘要."""
        self._query_count += 1

        all_tasks: list[TaskView] = []
        for plan in self._plans.values():
            for task in plan.tasks:
                all_tasks.append(self._task_to_view(task))

        total = len(all_tasks)
        running = sum(1 for t in all_tasks if t.status == "running")
        completed = sum(1 for t in all_tasks if t.status == "success")
        failed = sum(1 for t in all_tasks if t.status == "failed")
        pending = sum(1 for t in all_tasks if t.status == "created")

        return {
            "total_tasks": total,
            "running": running,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "total_plans": len(self._plans),
            "executor_summary": self._executor.get_summary(),
        }

    # ── Helpers ───────────────────────────────────────────────

    def _task_to_view(self, task: ExecutionTask) -> TaskView:
        """将 ExecutionTask 转换为 TaskView."""
        progress = 0.0
        if task.status == TaskStatus.SUCCESS:
            progress = 1.0
        elif task.status == TaskStatus.RUNNING:
            progress = 0.7
        elif task.status == TaskStatus.FAILED:
            progress = 1.0

        return TaskView(
            task_id=task.task_id,
            task_type=task.task_type.value if task.task_type else "",
            product_id=task.product_id,
            status=task.status.value if task.status else "pending",
            progress=progress,
            target_module=task.target_module.value if task.target_module else "",
            strategy_id=task.strategy_id,
            created_at=task.created_at.isoformat() if task.created_at else "",
            started_at=task.started_at.isoformat() if task.started_at else "",
            completed_at=task.completed_at.isoformat() if task.completed_at else "",
        )

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "query_count": self._query_count,
            "plans_registered": len(self._plans),
        }