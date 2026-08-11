"""E12.7.4 Task Dispatcher — DAG调度 + 优先级排序 + 依赖解析 + 重试."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from .models import ExecutionPlan, ExecutionTask, TaskStatus, TaskType
from .module_adapter import (
    CreativeAdapter,
    ExperimentAdapter,
    ModuleAdapter,
    PortfolioAdapter,
    ResourceAdapter,
    SafetyAdapter,
)


class TaskDispatcher:
    """任务调度器 — 负责优先级排序、依赖解析、并行执行分组、重试."""

    def __init__(self):
        self._adapters: dict[str, ModuleAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """注册默认适配器."""
        self.register_adapter("creative", CreativeAdapter())
        self.register_adapter("experiment", ExperimentAdapter())
        self.register_adapter("resource", ResourceAdapter())
        self.register_adapter("portfolio", PortfolioAdapter())
        self.register_adapter("safety", SafetyAdapter())

    def register_adapter(self, name: str, adapter: ModuleAdapter) -> None:
        self._adapters[name] = adapter

    def get_adapter(self, name: str) -> ModuleAdapter | None:
        return self._adapters.get(name)

    @property
    def adapter_count(self) -> int:
        return len(self._adapters)

    # ── Priority ──────────────────────────────────────────────

    def sort_by_priority(self, tasks: list[ExecutionTask]) -> list[ExecutionTask]:
        """按优先级降序排列."""
        return sorted(tasks, key=lambda t: t.priority, reverse=True)

    # ── Dependency Resolution ─────────────────────────────────

    def resolve_dependencies(self, tasks: list[ExecutionTask]) -> list[list[ExecutionTask]]:
        """解析依赖关系，返回拓扑排序后的执行分组.

        每组内的任务可以并行执行，组间顺序执行。
        """
        task_map = {t.task_id: t for t in tasks}
        in_degree: dict[str, int] = {t.task_id: len(t.dependencies) for t in tasks}
        dependents: dict[str, list[str]] = defaultdict(list)

        for t in tasks:
            for dep_id in t.dependencies:
                if dep_id in task_map:
                    dependents[dep_id].append(t.task_id)

        # Kahn's algorithm
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        groups: list[list[ExecutionTask]] = []

        while queue:
            current_group: list[ExecutionTask] = []
            for _ in range(len(queue)):
                tid = queue.popleft()
                current_group.append(task_map[tid])

            groups.append(current_group)

            for task in current_group:
                for dep_tid in dependents[task.task_id]:
                    in_degree[dep_tid] -= 1
                    if in_degree[dep_tid] == 0:
                        queue.append(dep_tid)

        # Add any remaining tasks with unresolved deps (circular or missing deps)
        remaining = [tid for tid, deg in in_degree.items() if deg > 0]
        if remaining:
            groups.append([task_map[tid] for tid in remaining])

        return groups

    def build_execution_order(self, tasks: list[ExecutionTask]) -> list[list[str]]:
        """构建执行顺序（返回 task_id 分组）."""
        groups = self.resolve_dependencies(tasks)
        return [[t.task_id for t in group] for group in groups]

    def get_parallel_groups(self, tasks: list[ExecutionTask]) -> list[list[str]]:
        """获取可并行执行的任务组."""
        return self.build_execution_order(tasks)

    # ── Adapter Dispatch ──────────────────────────────────────

    def _find_adapter(self, task: ExecutionTask) -> ModuleAdapter | None:
        """根据任务类型找到对应的适配器."""
        for adapter in self._adapters.values():
            if adapter.can_handle(task):
                return adapter
        return None

    def dispatch(self, task: ExecutionTask) -> ExecutionTask:
        """派发单个任务到对应适配器执行."""
        adapter = self._find_adapter(task)
        if adapter is None:
            task.status = TaskStatus.FAILED
            task.error_message = f"No adapter found for task type: {task.task_type.value}"
            task.completed_at = datetime.now(timezone.utc)
            return task

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        result = adapter.execute(task)
        task.result = result
        task.completed_at = datetime.now(timezone.utc)

        if result.success:
            task.status = TaskStatus.SUCCESS
        else:
            task.status = TaskStatus.FAILED
            task.error_message = result.error

        return task

    def dispatch_group(self, tasks: list[ExecutionTask]) -> list[ExecutionTask]:
        """并行执行一组任务."""
        return [self.dispatch(t) for t in tasks]

    # ── Retry ─────────────────────────────────────────────────

    def retry(self, task: ExecutionTask) -> ExecutionTask:
        """重试失败的任务."""
        if not task.can_retry:
            return task

        task.retry_count += 1
        task.status = TaskStatus.CREATED
        task.result = None
        task.error_message = ""
        task.started_at = None
        task.completed_at = None

        return self.dispatch(task)

    def retry_failed(self, plan: ExecutionPlan) -> list[ExecutionTask]:
        """重试计划中所有可重试的失败任务."""
        retried: list[ExecutionTask] = []
        for task in plan.tasks:
            if task.status == TaskStatus.FAILED and task.can_retry:
                retried.append(self.retry(task))
        return retried

    # ── Plan Execution ────────────────────────────────────────

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """按依赖顺序执行整个计划."""
        groups = self.resolve_dependencies(plan.tasks)
        plan.execution_order = [[t.task_id for t in group] for group in groups]

        for group in groups:
            # Sort by priority within each group
            sorted_group = self.sort_by_priority(group)
            self.dispatch_group(sorted_group)

            # If any task in the group failed and can't be retried, stop
            # (fail-fast for critical tasks)
            for task in sorted_group:
                if task.status == TaskStatus.FAILED and task.is_high_priority:
                    # Mark remaining tasks as cancelled
                    for remaining_group in groups[groups.index(group) + 1:]:
                        for t in remaining_group:
                            t.status = TaskStatus.CANCELLED
                    return plan

        return plan

    def execute_plan_parallel(self, plan: ExecutionPlan) -> ExecutionPlan:
        """并行执行整个计划（忽略依赖顺序）."""
        self.sort_by_priority(plan.tasks)
        self.dispatch_group(plan.tasks)
        plan.execution_order = [[t.task_id for t in plan.tasks]]
        return plan