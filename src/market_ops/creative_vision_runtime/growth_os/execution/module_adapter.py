"""E12.7.4 Module Adapter Layer — 抽象适配器接口 + 5个具体适配器.

避免 Growth OS 直接耦合 E11/E12 底层模块。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import (
    ExecutionResult,
    ExecutionTask,
    TaskStatus,
    TaskType,
)


class ModuleAdapter(ABC):
    """模块适配器抽象基类.

    每个底层模块（E11/E12.4/E12.6.2/E12.6.5）都有一个对应的适配器。
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._execution_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0

    @property
    def execution_count(self) -> int:
        return self._execution_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_rate(self) -> float:
        if self._execution_count == 0:
            return 0.0
        return self._success_count / self._execution_count

    @abstractmethod
    def can_handle(self, task: ExecutionTask) -> bool:
        """判断此适配器能否处理该任务."""
        ...

    @abstractmethod
    def execute(self, task: ExecutionTask) -> ExecutionResult:
        """执行任务并返回结果."""
        ...

    @abstractmethod
    def validate(self, task: ExecutionTask) -> bool:
        """验证任务参数是否合法."""
        ...

    @abstractmethod
    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        """回滚已执行的任务."""
        ...

    def _record_success(self) -> None:
        self._execution_count += 1
        self._success_count += 1

    def _record_failure(self) -> None:
        self._execution_count += 1
        self._failure_count += 1

    def _make_result(
        self,
        task: ExecutionTask,
        success: bool,
        output: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        error: str = "",
        execution_time_ms: float = 0.0,
    ) -> ExecutionResult:
        if success:
            self._record_success()
        else:
            self._record_failure()
        return ExecutionResult(
            task_id=task.task_id,
            success=success,
            output=output or {},
            metrics=metrics or {},
            error=error,
            execution_time_ms=execution_time_ms,
        )


class CreativeAdapter(ModuleAdapter):
    """创意适配器 — 连接 E11 Evolution Engine.

    处理: creative_generation, creative_mutation, create_creative, refresh_creative
    """

    def __init__(self):
        super().__init__(name="CreativeAdapter")

    def can_handle(self, task: ExecutionTask) -> bool:
        return task.task_type in {
            TaskType.CREATIVE_GENERATION,
            TaskType.CREATIVE_MUTATION,
            TaskType.CREATE_CREATIVE,
            TaskType.REFRESH_CREATIVE,
        }

    def execute(self, task: ExecutionTask) -> ExecutionResult:
        if not self.validate(task):
            return self._make_result(task, False, error="Task validation failed")

        count = task.parameters.get("count", 1)
        output = {
            "module": "E11_CreativeEvolution",
            "action": task.task_type.value,
            "generated_ids": [f"CREATIVE_{i:04d}" for i in range(count)],
            "count": count,
        }
        metrics = {
            "creatives_generated": count,
            "dna_variants": task.parameters.get("dna_variants", []),
        }
        return self._make_result(task, True, output=output, metrics=metrics)

    def validate(self, task: ExecutionTask) -> bool:
        if task.task_type in {TaskType.CREATIVE_GENERATION, TaskType.CREATE_CREATIVE}:
            count = task.parameters.get("count", 0)
            if count <= 0:
                return False
            if count > 100:
                return False
        return True

    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        if task.result and task.result.success:
            generated_ids = task.result.output.get("generated_ids", [])
            return self._make_result(
                task, True,
                output={"rolled_back_ids": generated_ids, "action": "delete_creatives"},
                metrics={"rolled_back_count": len(generated_ids)},
            )
        return self._make_result(
            task, False,
            error="No successful result to rollback",
        )


class ExperimentAdapter(ModuleAdapter):
    """实验适配器 — 连接 E12.4 Experiment Engine.

    处理: experiment_start, experiment_evaluate, experiment_stop
    """

    def __init__(self):
        super().__init__(name="ExperimentAdapter")

    def can_handle(self, task: ExecutionTask) -> bool:
        return task.task_type in {
            TaskType.EXPERIMENT_START,
            TaskType.EXPERIMENT_EVALUATE,
            TaskType.EXPERIMENT_STOP,
            TaskType.LAUNCH_EXPERIMENT,
            TaskType.EVALUATE_EXPERIMENT,
        }

    def execute(self, task: ExecutionTask) -> ExecutionResult:
        if not self.validate(task):
            return self._make_result(task, False, error="Task validation failed")

        experiment_name = task.parameters.get("experiment_name", "unnamed")
        duration_days = task.parameters.get("duration_days", 7)
        output = {
            "module": "E12.4_ExperimentEngine",
            "action": task.task_type.value,
            "experiment_id": f"EXP_{task.task_id[:8]}",
            "experiment_name": experiment_name,
            "duration_days": duration_days,
        }
        metrics = {
            "variant_count": task.parameters.get("variant_count", 2),
            "sample_size": task.parameters.get("sample_size", 5000),
        }
        return self._make_result(task, True, output=output, metrics=metrics)

    def validate(self, task: ExecutionTask) -> bool:
        if task.task_type == TaskType.EXPERIMENT_START:
            duration = task.parameters.get("duration_days", 0)
            if duration < 1 or duration > 30:
                return False
        return True

    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        exp_id = task.result.output.get("experiment_id", "") if task.result else ""
        return self._make_result(
            task, True,
            output={"rolled_back_experiment": exp_id, "action": "stop_experiment"},
        )


class ResourceAdapter(ModuleAdapter):
    """资源适配器 — 连接 E12.6.2 Resource Controller.

    处理: budget_increase, budget_decrease, budget_reallocate
    """

    def __init__(self):
        super().__init__(name="ResourceAdapter")

    def can_handle(self, task: ExecutionTask) -> bool:
        return task.task_type in {
            TaskType.BUDGET_INCREASE,
            TaskType.BUDGET_DECREASE,
            TaskType.BUDGET_REALLOCATE,
            TaskType.INCREASE_BUDGET,
            TaskType.DECREASE_BUDGET,
            TaskType.REALLOCATE_BUDGET,
        }

    def execute(self, task: ExecutionTask) -> ExecutionResult:
        if not self.validate(task):
            return self._make_result(task, False, error="Task validation failed")

        change_pct = task.parameters.get("change_pct", 0.0)
        output = {
            "module": "E12.6.2_ResourceController",
            "action": task.task_type.value,
            "change_pct": change_pct,
            "previous_budget": task.parameters.get("previous_budget", 0),
            "new_budget": task.parameters.get("previous_budget", 0) * (1 + change_pct),
        }
        metrics = {
            "budget_change_pct": change_pct,
            "product_id": task.product_id,
        }
        return self._make_result(task, True, output=output, metrics=metrics)

    def validate(self, task: ExecutionTask) -> bool:
        change_pct = task.parameters.get("change_pct", 0.0)
        # Budget change must be within [-50%, +50%]
        if change_pct < -0.50 or change_pct > 0.50:
            return False
        return True

    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        prev_budget = task.parameters.get("previous_budget", 0)
        return self._make_result(
            task, True,
            output={"restored_budget": prev_budget, "action": "rollback_budget"},
        )


class PortfolioAdapter(ModuleAdapter):
    """投资组合适配器 — 连接 E12.6.5 Portfolio Optimizer.

    处理: portfolio_adjustment
    """

    def __init__(self):
        super().__init__(name="PortfolioAdapter")

    def can_handle(self, task: ExecutionTask) -> bool:
        return task.task_type in {
            TaskType.PORTFOLIO_ADJUSTMENT,
            TaskType.AUDIENCE_EXPAND,
            TaskType.EXPAND_AUDIENCE,
        }

    def execute(self, task: ExecutionTask) -> ExecutionResult:
        if not self.validate(task):
            return self._make_result(task, False, error="Task validation failed")

        adjustments = task.parameters.get("adjustments", {})
        output = {
            "module": "E12.6.5_PortfolioOptimizer",
            "action": task.task_type.value,
            "adjustments": adjustments,
            "products_affected": len(adjustments),
        }
        metrics = {
            "total_budget_shift": sum(abs(v) for v in adjustments.values()),
        }
        return self._make_result(task, True, output=output, metrics=metrics)

    def validate(self, task: ExecutionTask) -> bool:
        return True

    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        previous = task.parameters.get("previous_allocation", {})
        return self._make_result(
            task, True,
            output={"restored_allocation": previous, "action": "rollback_portfolio"},
        )


class SafetyAdapter(ModuleAdapter):
    """安全适配器 — 连接 E12.6.3 Safety Governor.

    处理: 所有任务的安全检查，以及 sunset_product
    """

    def __init__(self):
        super().__init__(name="SafetyAdapter")
        self._blocked_tasks: list[str] = []

    def can_handle(self, task: ExecutionTask) -> bool:
        return task.task_type in {
            TaskType.SUNSET_PRODUCT,
            TaskType.CUSTOM,
        }

    def execute(self, task: ExecutionTask) -> ExecutionResult:
        if not self.validate(task):
            return self._make_result(task, False, error="Safety check failed")

        if task.task_type == TaskType.SUNSET_PRODUCT:
            return self._make_result(
                task, True,
                output={
                    "module": "E12.6.3_SafetyGovernor",
                    "action": "sunset_product",
                    "product_id": task.product_id,
                    "status": "sunset_initiated",
                },
                metrics={"products_sunset": 1},
            )

        return self._make_result(task, True, output={"module": "E12.6.3_SafetyGovernor"})

    def validate(self, task: ExecutionTask) -> bool:
        return task.task_id not in self._blocked_tasks

    def rollback(self, task: ExecutionTask) -> ExecutionResult:
        return self._make_result(
            task, True,
            output={"action": "cancel_sunset", "product_id": task.product_id},
        )

    def block_task(self, task_id: str) -> None:
        self._blocked_tasks.append(task_id)

    def unblock_task(self, task_id: str) -> None:
        if task_id in self._blocked_tasks:
            self._blocked_tasks.remove(task_id)