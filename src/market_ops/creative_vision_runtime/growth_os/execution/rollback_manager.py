"""E12.7.4 Rollback Manager — 自动回滚管理器.

支持: rollback(task), restore_previous_state(), 回滚历史记录.
"""

from __future__ import annotations

from typing import Any

from .models import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionTask,
    RollbackRecord,
    TaskStatus,
)
from .module_adapter import (
    CreativeAdapter,
    ExperimentAdapter,
    ModuleAdapter,
    PortfolioAdapter,
    ResourceAdapter,
    SafetyAdapter,
)


class RollbackManager:
    """回滚管理器 — 自动回滚已执行的任务."""

    def __init__(self):
        self._adapters: dict[str, ModuleAdapter] = {}
        self._history: list[RollbackRecord] = []
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        self.register_adapter("creative", CreativeAdapter())
        self.register_adapter("experiment", ExperimentAdapter())
        self.register_adapter("resource", ResourceAdapter())
        self.register_adapter("portfolio", PortfolioAdapter())
        self.register_adapter("safety", SafetyAdapter())

    def register_adapter(self, name: str, adapter: ModuleAdapter) -> None:
        self._adapters[name] = adapter

    # ── Properties ────────────────────────────────────────────

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self._history if r.rollback_success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self._history if not r.rollback_success)

    # ── Adapter Resolution ────────────────────────────────────

    def _find_adapter(self, task: ExecutionTask) -> ModuleAdapter | None:
        for adapter in self._adapters.values():
            if adapter.can_handle(task):
                return adapter
        return None

    # ── Rollback Operations ───────────────────────────────────

    def rollback(self, task: ExecutionTask) -> RollbackRecord:
        """回滚单个任务."""
        previous_state = task.parameters.copy() if task.parameters else {}

        adapter = self._find_adapter(task)
        if adapter is None:
            record = RollbackRecord(
                task_id=task.task_id,
                strategy_id=task.strategy_id,
                previous_state=previous_state,
                rollback_success=False,
                error=f"No adapter found for task type: {task.task_type.value}",
            )
            self._history.append(record)
            task.status = TaskStatus.FAILED
            return record

        # Save previous state from result if available
        if task.result:
            previous_state["result_output"] = task.result.output

        result = adapter.rollback(task)

        record = RollbackRecord(
            task_id=task.task_id,
            strategy_id=task.strategy_id,
            previous_state=previous_state,
            rollback_success=result.success,
            error=result.error,
        )

        self._history.append(record)

        if result.success:
            task.status = TaskStatus.ROLLED_BACK
        else:
            task.status = TaskStatus.FAILED

        return record

    def rollback_tasks(self, tasks: list[ExecutionTask]) -> list[RollbackRecord]:
        """回滚一组任务."""
        return [self.rollback(t) for t in tasks]

    def rollback_plan(self, plan: ExecutionPlan) -> list[RollbackRecord]:
        """回滚整个计划中的已执行任务（逆序）."""
        records: list[RollbackRecord] = []
        # Rollback in reverse order: last executed first
        executed = [t for t in plan.tasks if t.status == TaskStatus.SUCCESS]
        for task in reversed(executed):
            records.append(self.rollback(task))
        return records

    def rollback_failed(self, plan: ExecutionPlan) -> list[RollbackRecord]:
        """回滚计划中所有已执行的任务（失败时回滚）."""
        records: list[RollbackRecord] = []
        executed = [t for t in plan.tasks if t.status in {TaskStatus.SUCCESS, TaskStatus.FAILED}]
        for task in reversed(executed):
            records.append(self.rollback(task))
        return records

    def restore_previous_state(self, task: ExecutionTask) -> ExecutionTask | None:
        """恢复任务到之前的状态."""
        history = self.get_history(task.task_id)
        if not history:
            return None

        latest = history[-1]
        if latest.rollback_success and latest.previous_state:
            task.parameters = latest.previous_state
            task.status = TaskStatus.CREATED
            return task

        return None

    # ── History ────────────────────────────────────────────────

    def get_history(self, task_id: str | None = None) -> list[RollbackRecord]:
        """获取回滚历史."""
        if task_id:
            return [r for r in self._history if r.task_id == task_id]
        return list(self._history)

    def get_summary(self) -> dict[str, Any]:
        """获取回滚摘要."""
        return {
            "total_rollbacks": self.history_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": (
                self.success_count / self.history_count if self.history_count > 0 else 0.0
            ),
        }

    def clear_history(self) -> None:
        """清除回滚历史."""
        self._history.clear()