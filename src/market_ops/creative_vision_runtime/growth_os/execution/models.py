"""E12.7.4 Execution Models — ExecutionTask, ExecutionPlan, ExecutionResult."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    """执行任务类型."""
    CREATIVE_GENERATION = "creative_generation"
    CREATIVE_MUTATION = "creative_mutation"
    CREATE_CREATIVE = "create_creative"
    REFRESH_CREATIVE = "refresh_creative"
    EXPERIMENT_START = "experiment_start"
    EXPERIMENT_EVALUATE = "experiment_evaluate"
    EXPERIMENT_STOP = "experiment_stop"
    LAUNCH_EXPERIMENT = "launch_experiment"
    EVALUATE_EXPERIMENT = "evaluate_experiment"
    BUDGET_INCREASE = "budget_increase"
    BUDGET_DECREASE = "budget_decrease"
    BUDGET_REALLOCATE = "budget_reallocate"
    INCREASE_BUDGET = "increase_budget"
    DECREASE_BUDGET = "decrease_budget"
    REALLOCATE_BUDGET = "reallocate_budget"
    PORTFOLIO_ADJUSTMENT = "portfolio_adjustment"
    AUDIENCE_EXPAND = "audience_expand"
    EXPAND_AUDIENCE = "expand_audience"
    ANALYTICS_QUERY = "analytics_query"
    SUNSET_PRODUCT = "sunset_product"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    """任务执行状态."""
    CREATED = "created"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    """审批状态."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TargetModule(str, Enum):
    """目标模块."""
    E11_EVOLUTION = "E11_CreativeEvolution"
    E12_4_EXPERIMENT = "E12.4_ExperimentEngine"
    E12_6_2_RESOURCE = "E12.6.2_ResourceController"
    E12_6_3_SAFETY = "E12.6.3_SafetyGovernor"
    E12_6_5_PORTFOLIO = "E12.6.5_PortfolioOptimizer"
    E12_6_4_CROSS_PRODUCT = "E12.6.4_CrossProduct"
    E12_6_5_GROWTH_BRAIN = "E12.6.5_GrowthBrain"


@dataclass
class ExecutionTask:
    """单个执行任务.

    代表一个需要被底层模块执行的具体操作。
    """

    task_id: str = field(default_factory=lambda: f"TASK_{uuid.uuid4().hex[:8].upper()}")
    strategy_id: str = ""
    product_id: str = ""
    task_type: TaskType = TaskType.CUSTOM
    target_module: TargetModule = TargetModule.E11_EVOLUTION
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 50
    status: TaskStatus = TaskStatus.CREATED
    dependencies: list[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: ExecutionResult | None = None
    error_message: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.SUCCESS, TaskStatus.FAILED,
                                TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED}

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING

    @property
    def can_retry(self) -> bool:
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries

    @property
    def dependencies_resolved(self) -> bool:
        return len(self.dependencies) == 0

    @property
    def is_high_priority(self) -> bool:
        return self.priority >= 80

    @property
    def execution_time_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "strategy_id": self.strategy_id,
            "product_id": self.product_id,
            "task_type": self.task_type.value,
            "target_module": self.target_module.value,
            "parameters": self.parameters,
            "priority": self.priority,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "is_terminal": self.is_terminal,
            "is_high_priority": self.is_high_priority,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
        }


@dataclass
class ExecutionResult:
    """任务执行结果."""

    task_id: str = ""
    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    execution_time_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "metrics": self.metrics,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ExecutionPlan:
    """执行计划 — 包含一组有序的 ExecutionTask."""

    plan_id: str = field(default_factory=lambda: f"PLAN_{uuid.uuid4().hex[:8].upper()}")
    strategy_id: str = ""
    product_id: str = ""
    tasks: list[ExecutionTask] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)
    estimated_cost: float = 0.0
    risk_score: float = 0.0
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    parallel_groups: list[list[str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def is_approved(self) -> bool:
        return self.approval_status == ApprovalStatus.APPROVED

    @property
    def completed_tasks(self) -> list[ExecutionTask]:
        return [t for t in self.tasks if t.is_terminal]

    @property
    def failed_tasks(self) -> list[ExecutionTask]:
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    @property
    def success_tasks(self) -> list[ExecutionTask]:
        return [t for t in self.tasks if t.status == TaskStatus.SUCCESS]

    @property
    def completion_pct(self) -> float:
        if not self.tasks:
            return 0.0
        return len(self.completed_tasks) / len(self.tasks)

    @property
    def is_complete(self) -> bool:
        return all(t.is_terminal for t in self.tasks)

    @property
    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def get_task(self, task_id: str) -> ExecutionTask | None:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "product_id": self.product_id,
            "task_count": self.task_count,
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "success_tasks": len(self.success_tasks),
            "completion_pct": round(self.completion_pct, 4),
            "estimated_cost": self.estimated_cost,
            "risk_score": self.risk_score,
            "approval_status": self.approval_status.value,
            "is_complete": self.is_complete,
            "has_failures": self.has_failures,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class MonitorEvent:
    """监控事件."""

    event_id: str = field(default_factory=lambda: f"EVT_{uuid.uuid4().hex[:8].upper()}")
    task_id: str = ""
    plan_id: str = ""
    event_type: str = ""
    severity: str = "info"
    message: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "metrics": self.metrics,
        }


@dataclass
class RollbackRecord:
    """回滚记录."""

    record_id: str = field(default_factory=lambda: f"RBR_{uuid.uuid4().hex[:8].upper()}")
    task_id: str = ""
    strategy_id: str = ""
    previous_state: dict[str, Any] = field(default_factory=dict)
    rollback_success: bool = False
    error: str = ""
    rolled_back_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "strategy_id": self.strategy_id,
            "rollback_success": self.rollback_success,
            "error": self.error,
            "previous_state": self.previous_state,
        }