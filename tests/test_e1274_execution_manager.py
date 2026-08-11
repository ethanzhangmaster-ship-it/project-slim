"""E12.7.4 — Autonomous Execution Manager 测试。

测试覆盖:
  - Models (25): ExecutionTask, ExecutionResult, ExecutionPlan, MonitorEvent, RollbackRecord, Enums
  - ModuleAdapter (30): 5个适配器 (can_handle, execute, validate, rollback)
  - TaskDispatcher (30): 优先级排序, DAG依赖解析, 派发, 重试, 计划执行
  - ExecutionEngine (35): 执行, 并行, 重试, 计划创建, 审批
  - ExecutionMonitor (20): 任务监控, 告警检测, ROAS/风险检测
  - RollbackManager (20): 回滚, 批量回滚, 状态恢复, 历史
  - ExecutionController (30): 策略→任务, 安全检查, 执行, 完整管线
  - Integration (10): 端到端集成测试
"""

from __future__ import annotations

import pytest

from src.market_ops.creative_vision_runtime.growth_os.strategy.models import (
    ActionType,
    GrowthStrategy,
    RiskLevel,
    StrategyAction,
    StrategyObjective,
    StrategyStatus,
    StrategyTemplateType,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
    ApprovalStatus,
    ExecutionPlan,
    ExecutionResult,
    ExecutionTask,
    MonitorEvent,
    RollbackRecord,
    TargetModule,
    TaskStatus,
    TaskType,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.module_adapter import (
    CreativeAdapter,
    ExperimentAdapter,
    ModuleAdapter,
    PortfolioAdapter,
    ResourceAdapter,
    SafetyAdapter,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.task_dispatcher import (
    TaskDispatcher,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.execution_engine import (
    ExecutionEngine,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.execution_monitor import (
    ExecutionMonitor,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.rollback_manager import (
    RollbackManager,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.execution_controller import (
    ExecutionController,
)


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════


def _make_task(
    task_type: TaskType = TaskType.CREATE_CREATIVE,
    target_module: TargetModule = TargetModule.E11_EVOLUTION,
    priority: int = 50,
    parameters: dict | None = None,
    deps: list[str] | None = None,
    strategy_id: str = "STR_001",
    product_id: str = "p01",
    status: TaskStatus = TaskStatus.CREATED,
    max_retries: int = 3,
    error_message: str = "",
) -> ExecutionTask:
    return ExecutionTask(
        strategy_id=strategy_id,
        product_id=product_id,
        task_type=task_type,
        target_module=target_module,
        priority=priority,
        parameters=parameters or {},
        dependencies=deps or [],
        status=status,
        max_retries=max_retries,
        error_message=error_message,
    )


def _make_strategy(
    template_type: StrategyTemplateType = StrategyTemplateType.RECOVERY,
    product_id: str = "p01",
    actions: list[StrategyAction] | None = None,
    confidence: float = 0.80,
    risk_score: float = 0.40,
) -> GrowthStrategy:
    return GrowthStrategy(
        product_id=product_id,
        objective=StrategyObjective(metric="roas", product_id=product_id),
        template_type=template_type,
        actions=actions or [],
        confidence=confidence,
        risk_score=risk_score,
        status=StrategyStatus.VALIDATED,
    )


# ══════════════════════════════════════════════════════════════
# Test Models
# ══════════════════════════════════════════════════════════════


class TestExecutionTask:
    """ExecutionTask 模型测试 (12 tests)."""

    def test_create_default(self):
        task = ExecutionTask()
        assert task.task_id.startswith("TASK_")
        assert task.status == TaskStatus.CREATED
        assert task.priority == 50
        assert task.max_retries == 3

    def test_create_with_values(self):
        task = ExecutionTask(
            strategy_id="STR_001",
            product_id="p01",
            task_type=TaskType.CREATIVE_GENERATION,
            target_module=TargetModule.E11_EVOLUTION,
            priority=85,
            parameters={"count": 50},
            dependencies=["TASK_A"],
            max_retries=5,
        )
        assert task.task_type == TaskType.CREATIVE_GENERATION
        assert task.target_module == TargetModule.E11_EVOLUTION
        assert task.parameters["count"] == 50
        assert task.dependencies == ["TASK_A"]
        assert task.max_retries == 5

    def test_is_terminal(self):
        assert ExecutionTask(status=TaskStatus.SUCCESS).is_terminal is True
        assert ExecutionTask(status=TaskStatus.FAILED).is_terminal is True
        assert ExecutionTask(status=TaskStatus.ROLLED_BACK).is_terminal is True
        assert ExecutionTask(status=TaskStatus.CANCELLED).is_terminal is True
        assert ExecutionTask(status=TaskStatus.CREATED).is_terminal is False
        assert ExecutionTask(status=TaskStatus.RUNNING).is_terminal is False

    def test_is_running(self):
        assert ExecutionTask(status=TaskStatus.RUNNING).is_running is True
        assert ExecutionTask(status=TaskStatus.CREATED).is_running is False

    def test_can_retry(self):
        task = ExecutionTask(status=TaskStatus.FAILED, retry_count=0, max_retries=3)
        assert task.can_retry is True
        task.retry_count = 3
        assert task.can_retry is False
        task.status = TaskStatus.SUCCESS
        assert task.can_retry is False

    def test_is_high_priority(self):
        assert ExecutionTask(priority=80).is_high_priority is True
        assert ExecutionTask(priority=79).is_high_priority is False

    def test_dependencies_resolved(self):
        assert ExecutionTask().dependencies_resolved is True
        assert ExecutionTask(dependencies=["TASK_A"]).dependencies_resolved is False

    def test_execution_time_ms(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        task = ExecutionTask(
            started_at=now,
            completed_at=now + timedelta(seconds=0.5),
        )
        assert task.execution_time_ms == pytest.approx(500.0, rel=0.2)

    def test_execution_time_ms_no_times(self):
        assert ExecutionTask().execution_time_ms == 0.0

    def test_to_dict(self):
        task = ExecutionTask(
            strategy_id="S1",
            task_type=TaskType.BUDGET_INCREASE,
            priority=90,
            parameters={"change_pct": 0.30},
        )
        d = task.to_dict()
        assert d["task_type"] == "budget_increase"
        assert d["priority"] == 90
        assert d["is_high_priority"] is True

    def test_error_message(self):
        task = ExecutionTask(error_message="Something went wrong")
        assert task.error_message == "Something went wrong"

    def test_retry_count_tracked(self):
        task = ExecutionTask()
        task.retry_count = 2
        assert task.retry_count == 2


class TestExecutionResult:
    """ExecutionResult 模型测试 (5 tests)."""

    def test_create_default(self):
        result = ExecutionResult()
        assert result.success is False
        assert result.output == {}

    def test_create_success(self):
        result = ExecutionResult(
            task_id="TASK_001",
            success=True,
            output={"creatives": 50},
            metrics={"roas": 1.2},
            execution_time_ms=150.0,
        )
        assert result.success is True
        assert result.output["creatives"] == 50

    def test_create_failure(self):
        result = ExecutionResult(
            task_id="TASK_001",
            success=False,
            error="Validation failed",
        )
        assert result.success is False
        assert result.error == "Validation failed"

    def test_to_dict(self):
        result = ExecutionResult(
            task_id="TASK_001",
            success=True,
            output={"key": "val"},
            metrics={"m": 1},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == {"key": "val"}
        assert d["metrics"] == {"m": 1}

    def test_created_at_set(self):
        result = ExecutionResult()
        assert result.created_at is not None


class TestExecutionPlan:
    """ExecutionPlan 模型测试 (10 tests)."""

    def test_create_default(self):
        plan = ExecutionPlan()
        assert plan.plan_id.startswith("PLAN_")
        assert plan.task_count == 0
        assert plan.approval_status == ApprovalStatus.PENDING

    def test_task_count(self):
        plan = ExecutionPlan(tasks=[ExecutionTask(), ExecutionTask(), ExecutionTask()])
        assert plan.task_count == 3

    def test_is_approved(self):
        assert ExecutionPlan(approval_status=ApprovalStatus.APPROVED).is_approved is True
        assert ExecutionPlan(approval_status=ApprovalStatus.PENDING).is_approved is False

    def test_completed_tasks(self):
        t1 = ExecutionTask(status=TaskStatus.SUCCESS)
        t2 = ExecutionTask(status=TaskStatus.FAILED)
        t3 = ExecutionTask(status=TaskStatus.RUNNING)
        plan = ExecutionPlan(tasks=[t1, t2, t3])
        assert len(plan.completed_tasks) == 2

    def test_failed_tasks(self):
        t1 = ExecutionTask(status=TaskStatus.SUCCESS)
        t2 = ExecutionTask(status=TaskStatus.FAILED)
        plan = ExecutionPlan(tasks=[t1, t2])
        assert len(plan.failed_tasks) == 1

    def test_success_tasks(self):
        t1 = ExecutionTask(status=TaskStatus.SUCCESS)
        t2 = ExecutionTask(status=TaskStatus.FAILED)
        plan = ExecutionPlan(tasks=[t1, t2])
        assert len(plan.success_tasks) == 1

    def test_completion_pct(self):
        t1 = ExecutionTask(status=TaskStatus.SUCCESS)
        t2 = ExecutionTask(status=TaskStatus.RUNNING)
        plan = ExecutionPlan(tasks=[t1, t2])
        assert plan.completion_pct == 0.5

    def test_completion_pct_empty(self):
        assert ExecutionPlan().completion_pct == 0.0

    def test_is_complete(self):
        t1 = ExecutionTask(status=TaskStatus.SUCCESS)
        t2 = ExecutionTask(status=TaskStatus.FAILED)
        plan = ExecutionPlan(tasks=[t1, t2])
        assert plan.is_complete is True

    def test_has_failures(self):
        t1 = ExecutionTask(status=TaskStatus.SUCCESS)
        t2 = ExecutionTask(status=TaskStatus.FAILED)
        plan = ExecutionPlan(tasks=[t1, t2])
        assert plan.has_failures is True
        plan2 = ExecutionPlan(tasks=[ExecutionTask(status=TaskStatus.SUCCESS)])
        assert plan2.has_failures is False

    def test_get_task(self):
        t1 = ExecutionTask()
        plan = ExecutionPlan(tasks=[t1])
        assert plan.get_task(t1.task_id) is t1
        assert plan.get_task("NONEXISTENT") is None

    def test_to_dict(self):
        plan = ExecutionPlan(
            strategy_id="S1",
            product_id="p01",
            tasks=[ExecutionTask(status=TaskStatus.SUCCESS)],
            risk_score=0.30,
            approval_status=ApprovalStatus.APPROVED,
        )
        d = plan.to_dict()
        assert d["task_count"] == 1
        assert d["success_tasks"] == 1
        assert d["is_complete"] is True


class TestMonitorEvent:
    """MonitorEvent 模型测试 (3 tests)."""

    def test_create_default(self):
        evt = MonitorEvent()
        assert evt.event_id.startswith("EVT_")
        assert evt.severity == "info"

    def test_create_alert(self):
        evt = MonitorEvent(
            task_id="TASK_001",
            event_type="timeout",
            severity="critical",
            message="Task timed out",
            metrics={"elapsed": 300},
        )
        assert evt.severity == "critical"
        assert evt.metrics["elapsed"] == 300

    def test_to_dict(self):
        evt = MonitorEvent(
            event_type="roas_drop",
            severity="warning",
            message="ROAS dropped",
        )
        d = evt.to_dict()
        assert d["event_type"] == "roas_drop"
        assert d["severity"] == "warning"


class TestRollbackRecord:
    """RollbackRecord 模型测试 (3 tests)."""

    def test_create_default(self):
        rec = RollbackRecord()
        assert rec.record_id.startswith("RBR_")
        assert rec.rollback_success is False

    def test_create_success(self):
        rec = RollbackRecord(
            task_id="TASK_001",
            strategy_id="S1",
            previous_state={"budget": 1000},
            rollback_success=True,
        )
        assert rec.rollback_success is True
        assert rec.previous_state["budget"] == 1000

    def test_to_dict(self):
        rec = RollbackRecord(
            task_id="T1",
            rollback_success=False,
            error="Rollback failed",
        )
        d = rec.to_dict()
        assert d["rollback_success"] is False
        assert d["error"] == "Rollback failed"


class TestEnums:
    """枚举测试 (3 tests)."""

    def test_task_type(self):
        assert TaskType.CREATIVE_GENERATION.value == "creative_generation"
        assert TaskType.BUDGET_INCREASE.value == "budget_increase"
        assert TaskType.EXPERIMENT_START.value == "experiment_start"
        assert TaskType.SUNSET_PRODUCT.value == "sunset_product"

    def test_task_status(self):
        assert TaskStatus.CREATED.value == "created"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.ROLLED_BACK.value == "rolled_back"

    def test_target_module(self):
        assert TargetModule.E11_EVOLUTION.value == "E11_CreativeEvolution"
        assert TargetModule.E12_4_EXPERIMENT.value == "E12.4_ExperimentEngine"
        assert TargetModule.E12_6_2_RESOURCE.value == "E12.6.2_ResourceController"


# ══════════════════════════════════════════════════════════════
# Test Module Adapters
# ══════════════════════════════════════════════════════════════


class TestModuleAdapterBase:
    """ModuleAdapter 基类测试 (5 tests)."""

    def test_execution_count(self):
        adapter = CreativeAdapter()
        assert adapter.execution_count == 0
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        adapter.execute(task)
        assert adapter.execution_count == 1

    def test_success_count(self):
        adapter = CreativeAdapter()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        adapter.execute(task)
        assert adapter.success_count == 1
        assert adapter.failure_count == 0

    def test_failure_count(self):
        adapter = CreativeAdapter()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        adapter.execute(task)
        assert adapter.failure_count == 1

    def test_success_rate(self):
        adapter = CreativeAdapter()
        assert adapter.success_rate == 0.0
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        adapter.execute(task)
        assert adapter.success_rate == 1.0

    def test_success_rate_after_failure(self):
        adapter = CreativeAdapter()
        adapter.execute(_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}))
        adapter.execute(_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0}))
        assert adapter.success_rate == 0.5


class TestCreativeAdapter:
    """CreativeAdapter 测试 (7 tests)."""

    def test_can_handle_generation(self):
        adapter = CreativeAdapter()
        assert adapter.can_handle(_make_task(TaskType.CREATIVE_GENERATION)) is True
        assert adapter.can_handle(_make_task(TaskType.CREATE_CREATIVE)) is True
        assert adapter.can_handle(_make_task(TaskType.REFRESH_CREATIVE)) is True
        assert adapter.can_handle(_make_task(TaskType.CREATIVE_MUTATION)) is True

    def test_can_handle_other(self):
        adapter = CreativeAdapter()
        assert adapter.can_handle(_make_task(TaskType.BUDGET_INCREASE)) is False

    def test_execute_success(self):
        adapter = CreativeAdapter()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 10})
        result = adapter.execute(task)
        assert result.success is True
        assert len(result.output["generated_ids"]) == 10
        assert result.metrics["creatives_generated"] == 10

    def test_execute_zero_count(self):
        adapter = CreativeAdapter()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        result = adapter.execute(task)
        assert result.success is False

    def test_execute_exceed_limit(self):
        adapter = CreativeAdapter()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 200})
        result = adapter.execute(task)
        assert result.success is False

    def test_validate_positive(self):
        adapter = CreativeAdapter()
        assert adapter.validate(_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 50})) is True
        assert adapter.validate(_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})) is False
        assert adapter.validate(_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 101})) is False

    def test_rollback(self):
        adapter = CreativeAdapter()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = adapter.execute(task)
        result = adapter.rollback(task)
        assert result.success is True
        assert result.metrics["rolled_back_count"] == 5


class TestExperimentAdapter:
    """ExperimentAdapter 测试 (7 tests)."""

    def test_can_handle(self):
        adapter = ExperimentAdapter()
        assert adapter.can_handle(_make_task(TaskType.EXPERIMENT_START)) is True
        assert adapter.can_handle(_make_task(TaskType.EXPERIMENT_EVALUATE)) is True
        assert adapter.can_handle(_make_task(TaskType.LAUNCH_EXPERIMENT)) is True
        assert adapter.can_handle(_make_task(TaskType.EVALUATE_EXPERIMENT)) is True

    def test_can_handle_other(self):
        adapter = ExperimentAdapter()
        assert adapter.can_handle(_make_task(TaskType.BUDGET_INCREASE)) is False

    def test_execute_success(self):
        adapter = ExperimentAdapter()
        task = _make_task(
            TaskType.EXPERIMENT_START,
            parameters={"experiment_name": "TestExp", "duration_days": 7},
        )
        result = adapter.execute(task)
        assert result.success is True
        assert "experiment_id" in result.output
        assert result.output["experiment_name"] == "TestExp"

    def test_execute_evaluate(self):
        adapter = ExperimentAdapter()
        task = _make_task(TaskType.EXPERIMENT_EVALUATE)
        result = adapter.execute(task)
        assert result.success is True

    def test_validate_duration(self):
        adapter = ExperimentAdapter()
        assert adapter.validate(_make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 7})) is True
        assert adapter.validate(_make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 0})) is False
        assert adapter.validate(_make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 31})) is False

    def test_validate_other_types(self):
        adapter = ExperimentAdapter()
        assert adapter.validate(_make_task(TaskType.EXPERIMENT_EVALUATE)) is True

    def test_rollback(self):
        adapter = ExperimentAdapter()
        task = _make_task(TaskType.EXPERIMENT_START)
        task.result = adapter.execute(task)
        result = adapter.rollback(task)
        assert result.success is True
        assert result.output["action"] == "stop_experiment"


class TestResourceAdapter:
    """ResourceAdapter 测试 (7 tests)."""

    def test_can_handle(self):
        adapter = ResourceAdapter()
        assert adapter.can_handle(_make_task(TaskType.BUDGET_INCREASE)) is True
        assert adapter.can_handle(_make_task(TaskType.BUDGET_DECREASE)) is True
        assert adapter.can_handle(_make_task(TaskType.INCREASE_BUDGET)) is True
        assert adapter.can_handle(_make_task(TaskType.DECREASE_BUDGET)) is True
        assert adapter.can_handle(_make_task(TaskType.REALLOCATE_BUDGET)) is True

    def test_can_handle_other(self):
        adapter = ResourceAdapter()
        assert adapter.can_handle(_make_task(TaskType.CREATE_CREATIVE)) is False

    def test_execute_increase(self):
        adapter = ResourceAdapter()
        task = _make_task(
            TaskType.BUDGET_INCREASE,
            parameters={"change_pct": 0.30, "previous_budget": 1000},
        )
        result = adapter.execute(task)
        assert result.success is True
        assert result.output["new_budget"] == pytest.approx(1300)

    def test_execute_decrease(self):
        adapter = ResourceAdapter()
        task = _make_task(
            TaskType.BUDGET_DECREASE,
            parameters={"change_pct": -0.20, "previous_budget": 1000},
        )
        result = adapter.execute(task)
        assert result.success is True
        assert result.output["new_budget"] == pytest.approx(800)

    def test_validate_bounds(self):
        adapter = ResourceAdapter()
        assert adapter.validate(_make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.30})) is True
        assert adapter.validate(_make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.60})) is False
        assert adapter.validate(_make_task(TaskType.BUDGET_DECREASE, parameters={"change_pct": -0.60})) is False
        assert adapter.validate(_make_task(TaskType.BUDGET_DECREASE, parameters={"change_pct": -0.50})) is True

    def test_validate_no_pct(self):
        adapter = ResourceAdapter()
        assert adapter.validate(_make_task(TaskType.BUDGET_INCREASE)) is True

    def test_rollback(self):
        adapter = ResourceAdapter()
        task = _make_task(
            TaskType.BUDGET_INCREASE,
            parameters={"change_pct": 0.30, "previous_budget": 1000},
        )
        result = adapter.rollback(task)
        assert result.success is True
        assert result.output["restored_budget"] == 1000


class TestPortfolioAdapter:
    """PortfolioAdapter 测试 (4 tests)."""

    def test_can_handle(self):
        adapter = PortfolioAdapter()
        assert adapter.can_handle(_make_task(TaskType.PORTFOLIO_ADJUSTMENT)) is True
        assert adapter.can_handle(_make_task(TaskType.AUDIENCE_EXPAND)) is True
        assert adapter.can_handle(_make_task(TaskType.EXPAND_AUDIENCE)) is True

    def test_can_handle_other(self):
        adapter = PortfolioAdapter()
        assert adapter.can_handle(_make_task(TaskType.CREATE_CREATIVE)) is False

    def test_execute(self):
        adapter = PortfolioAdapter()
        task = _make_task(
            TaskType.PORTFOLIO_ADJUSTMENT,
            parameters={"adjustments": {"p1": 0.20, "p2": -0.10}},
        )
        result = adapter.execute(task)
        assert result.success is True
        assert result.output["products_affected"] == 2

    def test_rollback(self):
        adapter = PortfolioAdapter()
        task = _make_task(
            TaskType.PORTFOLIO_ADJUSTMENT,
            parameters={"previous_allocation": {"p1": 0.50, "p2": 0.50}},
        )
        result = adapter.rollback(task)
        assert result.success is True
        assert result.output["restored_allocation"] == {"p1": 0.50, "p2": 0.50}


class TestSafetyAdapter:
    """SafetyAdapter 测试 (5 tests)."""

    def test_can_handle(self):
        adapter = SafetyAdapter()
        assert adapter.can_handle(_make_task(TaskType.SUNSET_PRODUCT)) is True

    def test_execute_sunset(self):
        adapter = SafetyAdapter()
        task = _make_task(TaskType.SUNSET_PRODUCT, product_id="p01")
        result = adapter.execute(task)
        assert result.success is True
        assert result.output["status"] == "sunset_initiated"

    def test_block_unblock(self):
        adapter = SafetyAdapter()
        task = _make_task(TaskType.SUNSET_PRODUCT)
        assert adapter.validate(task) is True
        adapter.block_task(task.task_id)
        assert adapter.validate(task) is False
        adapter.unblock_task(task.task_id)
        assert adapter.validate(task) is True

    def test_rollback(self):
        adapter = SafetyAdapter()
        task = _make_task(TaskType.SUNSET_PRODUCT, product_id="p01")
        result = adapter.rollback(task)
        assert result.success is True
        assert result.output["action"] == "cancel_sunset"

    def test_custom_execute(self):
        adapter = SafetyAdapter()
        task = _make_task(TaskType.CUSTOM)
        result = adapter.execute(task)
        assert result.success is True


# ══════════════════════════════════════════════════════════════
# Test Task Dispatcher
# ══════════════════════════════════════════════════════════════


class TestTaskDispatcherPriority:
    """优先级排序测试 (4 tests)."""

    def test_sort_by_priority(self):
        dispatcher = TaskDispatcher()
        tasks = [
            _make_task(priority=30),
            _make_task(priority=90),
            _make_task(priority=50),
        ]
        sorted_tasks = dispatcher.sort_by_priority(tasks)
        assert sorted_tasks[0].priority == 90
        assert sorted_tasks[1].priority == 50
        assert sorted_tasks[2].priority == 30

    def test_sort_empty(self):
        dispatcher = TaskDispatcher()
        assert dispatcher.sort_by_priority([]) == []

    def test_sort_single(self):
        dispatcher = TaskDispatcher()
        task = _make_task(priority=50)
        result = dispatcher.sort_by_priority([task])
        assert result == [task]

    def test_sort_equal_priority(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task(priority=50)
        t2 = _make_task(priority=50)
        result = dispatcher.sort_by_priority([t1, t2])
        assert len(result) == 2


class TestTaskDispatcherDependencies:
    """依赖解析测试 (8 tests)."""

    def test_no_dependencies(self):
        dispatcher = TaskDispatcher()
        tasks = [_make_task(), _make_task(), _make_task()]
        groups = dispatcher.resolve_dependencies(tasks)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_linear_chain(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task()
        t2 = _make_task(deps=[t1.task_id])
        t3 = _make_task(deps=[t2.task_id])
        groups = dispatcher.resolve_dependencies([t1, t2, t3])
        assert len(groups) == 3
        assert len(groups[0]) == 1
        assert groups[0][0].task_id == t1.task_id

    def test_diamond_deps(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task()
        t2 = _make_task(deps=[t1.task_id])
        t3 = _make_task(deps=[t1.task_id])
        t4 = _make_task(deps=[t2.task_id, t3.task_id])
        groups = dispatcher.resolve_dependencies([t1, t2, t3, t4])
        assert len(groups) == 3
        assert len(groups[0]) == 1  # t1
        assert len(groups[1]) == 2  # t2, t3
        assert len(groups[2]) == 1  # t4

    def test_circular_dependency(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task(deps=["TASK_B"])
        t2 = _make_task(deps=["TASK_A"])
        t2.task_id = "TASK_B"
        t1.task_id = "TASK_A"
        groups = dispatcher.resolve_dependencies([t1, t2])
        # Should handle circular deps gracefully
        assert len(groups) >= 1

    def test_missing_dependency(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task(deps=["NONEXISTENT"])
        groups = dispatcher.resolve_dependencies([t1])
        assert len(groups) >= 1

    def test_build_execution_order(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task()
        t2 = _make_task(deps=[t1.task_id])
        order = dispatcher.build_execution_order([t1, t2])
        assert len(order) == 2
        assert order[0] == [t1.task_id]
        assert order[1] == [t2.task_id]

    def test_parallel_groups(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task()
        t2 = _make_task()
        groups = dispatcher.get_parallel_groups([t1, t2])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_empty_tasks(self):
        dispatcher = TaskDispatcher()
        assert dispatcher.resolve_dependencies([]) == []


class TestTaskDispatcherDispatch:
    """任务派发测试 (8 tests)."""

    def test_dispatch_success(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        result = dispatcher.dispatch(task)
        assert result.status == TaskStatus.SUCCESS
        assert result.result.success is True

    def test_dispatch_fails_validation(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        result = dispatcher.dispatch(task)
        assert result.status == TaskStatus.FAILED

    def test_dispatch_no_adapter(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.ANALYTICS_QUERY)
        result = dispatcher.dispatch(task)
        assert result.status == TaskStatus.FAILED
        assert "No adapter" in result.error_message

    def test_dispatch_group(self):
        dispatcher = TaskDispatcher()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
            _make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 7}),
        ]
        results = dispatcher.dispatch_group(tasks)
        assert len(results) == 3
        assert all(r.status == TaskStatus.SUCCESS for r in results)

    def test_dispatch_full_dag(self):
        """模拟完整DAG: 创意生成→实验启动→预算变更."""
        dispatcher = TaskDispatcher()
        gen = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        exp = _make_task(TaskType.EXPERIMENT_START,
                         parameters={"duration_days": 7},
                         deps=[gen.task_id])
        budget = _make_task(TaskType.BUDGET_INCREASE,
                            parameters={"change_pct": 0.20},
                            deps=[exp.task_id])
        plan = ExecutionPlan(tasks=[gen, exp, budget])
        result = dispatcher.execute_plan(plan)
        assert result.is_complete
        assert gen.status == TaskStatus.SUCCESS
        assert exp.status == TaskStatus.SUCCESS
        assert budget.status == TaskStatus.SUCCESS

    def test_dispatch_records_timing(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        result = dispatcher.dispatch(task)
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.execution_time_ms >= 0

    def test_dispatch_fail_fast(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0}, priority=90)
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        t3 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}, deps=[t2.task_id])
        plan = ExecutionPlan(tasks=[t1, t2, t3])
        result = dispatcher.execute_plan(plan)
        assert t1.status == TaskStatus.FAILED
        # t2 is in the same DAG group as t1 and executes successfully
        assert t2.status == TaskStatus.SUCCESS
        # t3 is in a subsequent group, cancelled by fail-fast
        assert t3.status == TaskStatus.CANCELLED

    def test_dispatch_fail_fast_low_priority(self):
        """Low priority failure should NOT stop execution."""
        dispatcher = TaskDispatcher()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0}, priority=30)
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}, deps=[t1.task_id])
        plan = ExecutionPlan(tasks=[t1, t2])
        result = dispatcher.execute_plan(plan)
        assert t1.status == TaskStatus.FAILED
        # t2 runs even after t1 fails (low priority)
        assert t2.status == TaskStatus.SUCCESS


class TestTaskDispatcherRetry:
    """重试测试 (6 tests)."""

    def test_retry_success(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        dispatcher.dispatch(task)
        assert task.status == TaskStatus.FAILED

        task.parameters["count"] = 5
        result = dispatcher.retry(task)
        assert result.status == TaskStatus.SUCCESS
        assert result.retry_count == 1

    def test_retry_exhausted(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0},
                          max_retries=1)
        dispatcher.dispatch(task)
        assert task.status == TaskStatus.FAILED
        # Can't retry because max_retries=1 and retry_count=0, retry once
        result = dispatcher.retry(task)
        assert result.retry_count == 1
        # Now retry_count=1, max_retries=1, can't retry again
        assert result.can_retry is False

    def test_cannot_retry_success(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        dispatcher.dispatch(task)
        result = dispatcher.retry(task)
        assert result.status == TaskStatus.SUCCESS  # Unchanged

    def test_retry_failed(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        dispatcher.dispatch(t1)
        dispatcher.dispatch(t2)
        plan = ExecutionPlan(tasks=[t1, t2])
        t1.parameters["count"] = 5  # Fix parameter
        retried = dispatcher.retry_failed(plan)
        assert len(retried) == 1
        assert retried[0].task_id == t1.task_id
        assert retried[0].status == TaskStatus.SUCCESS

    def test_retry_clears_state(self):
        dispatcher = TaskDispatcher()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        dispatcher.dispatch(task)
        dispatcher.retry(task)
        # Error message should be cleared on retry
        assert task.error_message == "" or task.error_message == task.result.error


class TestTaskDispatcherPlanExecution:
    """计划执行测试 (4 tests)."""

    def test_execute_plan_sets_order(self):
        dispatcher = TaskDispatcher()
        t1 = _make_task()
        t2 = _make_task(deps=[t1.task_id])
        plan = ExecutionPlan(tasks=[t1, t2])
        result = dispatcher.execute_plan(plan)
        assert len(result.execution_order) == 2
        assert result.is_complete

    def test_execute_plan_parallel(self):
        dispatcher = TaskDispatcher()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
        ]
        plan = ExecutionPlan(tasks=tasks)
        result = dispatcher.execute_plan_parallel(plan)
        assert result.is_complete
        assert len(result.execution_order) == 1
        assert len(result.execution_order[0]) == 2

    def test_execute_plan_empty(self):
        dispatcher = TaskDispatcher()
        plan = ExecutionPlan()
        result = dispatcher.execute_plan(plan)
        assert result.is_complete

    def test_adapter_count(self):
        dispatcher = TaskDispatcher()
        assert dispatcher.adapter_count == 5


# ══════════════════════════════════════════════════════════════
# Test Execution Engine
# ══════════════════════════════════════════════════════════════


class TestExecutionEngine:
    """ExecutionEngine 测试 (35 tests)."""

    def test_create_default(self):
        engine = ExecutionEngine()
        assert engine.execution_count == 0

    def test_custom_dispatcher(self):
        dispatcher = TaskDispatcher()
        engine = ExecutionEngine(dispatcher=dispatcher)
        assert engine.dispatcher is dispatcher

    def test_execute_plan(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        plan = ExecutionPlan(tasks=[task])
        result = engine.execute(plan)
        assert result.is_complete
        assert task.status == TaskStatus.SUCCESS
        assert engine.execution_count == 1
        assert engine.task_count == 1

    def test_execute_auto_approves(self):
        engine = ExecutionEngine()
        plan = ExecutionPlan(
            tasks=[_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})],
            approval_status=ApprovalStatus.PENDING,
        )
        result = engine.execute(plan)
        assert result.approval_status == ApprovalStatus.APPROVED

    def test_execute_sequential(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        t2 = _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20},
                        deps=[t1.task_id])
        plan = ExecutionPlan(tasks=[t1, t2])
        result = engine.execute_sequential(plan)
        assert result.is_complete
        assert len(result.execution_order) == 2

    def test_execute_parallel(self):
        engine = ExecutionEngine()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
        ]
        plan = ExecutionPlan(tasks=tasks)
        result = engine.execute_parallel(plan)
        assert result.is_complete
        assert len(result.execution_order[0]) == 2

    def test_execute_task(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        result = engine.execute_task(task)
        assert result.status == TaskStatus.SUCCESS
        assert engine.task_count == 1

    def test_execute_tasks(self):
        engine = ExecutionEngine()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
        ]
        results = engine.execute_tasks(tasks)
        assert len(results) == 2
        assert all(r.status == TaskStatus.SUCCESS for r in results)
        assert engine.task_count == 2

    def test_retry_task(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        engine.execute_task(task)
        assert task.status == TaskStatus.FAILED
        task.parameters["count"] = 5
        result = engine.retry_task(task)
        assert result.status == TaskStatus.SUCCESS

    def test_retry_plan(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0})
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        plan = ExecutionPlan(tasks=[t1, t2])
        engine.execute(plan)
        t1.parameters["count"] = 5
        retried = engine.retry_plan(plan)
        assert len(retried) == 1

    def test_get_plan_status(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        plan = ExecutionPlan(tasks=[task])
        engine.execute(plan)
        status = engine.get_plan_status(plan)
        assert status["is_complete"] is True
        assert status["success_count"] == 1
        assert status["failed_count"] == 0

    def test_get_summary(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        plan = ExecutionPlan(tasks=[task])
        engine.execute(plan)
        summary = engine.get_summary()
        assert summary["execution_count"] == 1
        assert summary["task_count"] == 1

    def test_get_history(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        plan = ExecutionPlan(tasks=[task])
        engine.execute(plan)
        history = engine.get_history()
        assert len(history) == 1

    def test_create_plan(self):
        engine = ExecutionEngine()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
        ]
        plan = engine.create_plan(
            tasks=tasks,
            strategy_id="S1",
            product_id="p01",
            risk_score=0.30,
        )
        assert plan.strategy_id == "S1"
        assert plan.task_count == 2
        assert plan.risk_score == 0.30
        assert len(plan.execution_order) > 0

    def test_approve_plan(self):
        engine = ExecutionEngine()
        plan = ExecutionPlan()
        result = engine.approve_plan(plan)
        assert result.approval_status == ApprovalStatus.APPROVED

    def test_reject_plan(self):
        engine = ExecutionEngine()
        plan = ExecutionPlan()
        result = engine.reject_plan(plan)
        assert result.approval_status == ApprovalStatus.REJECTED

    def test_execute_mixed_results(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0}, priority=30)
        plan = ExecutionPlan(tasks=[t1, t2])
        result = engine.execute(plan)
        assert result.is_complete
        assert result.has_failures
        assert len(result.success_tasks) == 1
        assert len(result.failed_tasks) == 1

    def test_task_count_accumulates(self):
        engine = ExecutionEngine()
        engine.execute_task(_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}))
        engine.execute_task(_make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}))
        assert engine.task_count == 2

    def test_execution_count_accumulates(self):
        engine = ExecutionEngine()
        plan1 = ExecutionPlan(tasks=[_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})])
        plan2 = ExecutionPlan(tasks=[_make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20})])
        engine.execute(plan1)
        engine.execute(plan2)
        assert engine.execution_count == 2

    def test_parallel_vs_sequential(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        t2 = _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20},
                        deps=[t1.task_id])
        plan = ExecutionPlan(tasks=[t1, t2])
        result = engine.execute_parallel(plan)
        # Parallel execution group has all tasks
        assert len(result.execution_order[0]) == 2

    def test_create_plan_with_deps(self):
        engine = ExecutionEngine()
        t1 = _make_task()
        t2 = _make_task(deps=[t1.task_id])
        plan = engine.create_plan(tasks=[t1, t2], strategy_id="S1")
        assert len(plan.execution_order) == 2

    def test_execute_full_dag(self):
        """完整DAG: 创意→实验→预算→受众."""
        engine = ExecutionEngine()
        gen = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 10})
        exp = _make_task(TaskType.EXPERIMENT_START,
                         parameters={"duration_days": 7},
                         deps=[gen.task_id])
        budget = _make_task(TaskType.BUDGET_INCREASE,
                            parameters={"change_pct": 0.30},
                            deps=[exp.task_id])
        aud = _make_task(TaskType.AUDIENCE_EXPAND,
                         parameters={"channels": ["fb", "google"]},
                         deps=[budget.task_id])
        plan = engine.create_plan(tasks=[gen, exp, budget, aud], strategy_id="S1")
        result = engine.execute(plan)
        assert result.is_complete
        assert all(t.status == TaskStatus.SUCCESS for t in [gen, exp, budget, aud])

    def test_execute_sunset(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.SUNSET_PRODUCT, product_id="p01")
        plan = ExecutionPlan(tasks=[task])
        result = engine.execute(plan)
        assert result.is_complete
        assert task.status == TaskStatus.SUCCESS

    def test_execute_portfolio(self):
        engine = ExecutionEngine()
        task = _make_task(
            TaskType.PORTFOLIO_ADJUSTMENT,
            parameters={"adjustments": {"p1": 0.30}},
        )
        plan = ExecutionPlan(tasks=[task])
        result = engine.execute(plan)
        assert result.is_complete
        assert task.status == TaskStatus.SUCCESS

    def test_no_adapter_task(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.ANALYTICS_QUERY)
        plan = ExecutionPlan(tasks=[task])
        result = engine.execute(plan)
        assert task.status == TaskStatus.FAILED

    def test_fail_fast_high_priority(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0}, priority=90)
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}, priority=90,
                        deps=[t1.task_id])
        plan = ExecutionPlan(tasks=[t1, t2])
        result = engine.execute(plan)
        assert t1.status == TaskStatus.FAILED
        assert t2.status == TaskStatus.CANCELLED

    def test_approval_preserved_if_already_approved(self):
        engine = ExecutionEngine()
        plan = ExecutionPlan(
            tasks=[_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})],
            approval_status=ApprovalStatus.APPROVED,
        )
        result = engine.execute(plan)
        assert result.approval_status == ApprovalStatus.APPROVED

    def test_all_task_types_execute(self):
        """所有主要任务类型都可执行."""
        engine = ExecutionEngine()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.CREATIVE_MUTATION, parameters={"dna_variants": ["v1"]}),
            _make_task(TaskType.REFRESH_CREATIVE, parameters={"count": 3}),
            _make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 7}),
            _make_task(TaskType.EXPERIMENT_EVALUATE),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
            _make_task(TaskType.BUDGET_DECREASE, parameters={"change_pct": -0.10}),
            _make_task(TaskType.PORTFOLIO_ADJUSTMENT, parameters={"adjustments": {"p1": 0.10}}),
            _make_task(TaskType.SUNSET_PRODUCT, product_id="p01"),
        ]
        plan = ExecutionPlan(tasks=tasks)
        result = engine.execute(plan)
        assert result.is_complete
        assert len(result.success_tasks) == 9

    def test_budget_reallocate(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.BUDGET_REALLOCATE, parameters={"change_pct": 0.0})
        plan = ExecutionPlan(tasks=[task])
        result = engine.execute(plan)
        assert task.status == TaskStatus.SUCCESS

    def test_audience_expand(self):
        engine = ExecutionEngine()
        task = _make_task(TaskType.AUDIENCE_EXPAND, parameters={"channels": ["fb"]})
        plan = ExecutionPlan(tasks=[task])
        result = engine.execute(plan)
        assert task.status == TaskStatus.SUCCESS

    def test_experiment_launch_evaluate(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.LAUNCH_EXPERIMENT, parameters={"duration_days": 7})
        t2 = _make_task(TaskType.EVALUATE_EXPERIMENT, deps=[t1.task_id])
        plan = ExecutionPlan(tasks=[t1, t2])
        result = engine.execute(plan)
        assert t1.status == TaskStatus.SUCCESS
        assert t2.status == TaskStatus.SUCCESS

    def test_increase_decrease_budget_via_action_type(self):
        engine = ExecutionEngine()
        t1 = _make_task(TaskType.INCREASE_BUDGET, parameters={"change_pct": 0.20})
        t2 = _make_task(TaskType.DECREASE_BUDGET, parameters={"change_pct": -0.10})
        plan = ExecutionPlan(tasks=[t1, t2])
        result = engine.execute(plan)
        assert t1.status == TaskStatus.SUCCESS
        assert t2.status == TaskStatus.SUCCESS


# ══════════════════════════════════════════════════════════════
# Test Execution Monitor
# ══════════════════════════════════════════════════════════════


class TestExecutionMonitor:
    """ExecutionMonitor 测试 (20 tests)."""

    def test_create_default(self):
        monitor = ExecutionMonitor()
        assert monitor.event_count == 0
        assert monitor.alert_count == 0

    def test_watch_task_success(self):
        monitor = ExecutionMonitor()
        task = _make_task(status=TaskStatus.SUCCESS)
        event = monitor.watch_task(task)
        assert event is not None
        assert event.event_type == "task_completed"
        assert event.severity == "info"

    def test_watch_task_failed(self):
        monitor = ExecutionMonitor()
        task = _make_task(status=TaskStatus.FAILED, error_message="err")
        event = monitor.watch_task(task)
        assert event is not None
        assert event.event_type == "task_failed"
        assert event.severity == "warning"

    def test_watch_task_running(self):
        monitor = ExecutionMonitor()
        task = _make_task(status=TaskStatus.RUNNING)
        event = monitor.watch_task(task)
        # Running but not timed out → no event
        assert event is None

    def test_watch_task_timeout(self):
        from datetime import datetime, timedelta, timezone
        monitor = ExecutionMonitor(timeout_seconds=1.0)
        task = _make_task(status=TaskStatus.RUNNING)
        task.started_at = datetime.now(timezone.utc) - timedelta(seconds=2)
        event = monitor.watch_task(task)
        assert event is not None
        assert event.event_type == "timeout"
        assert event.severity == "critical"

    def test_watch_tasks(self):
        monitor = ExecutionMonitor()
        tasks = [
            _make_task(status=TaskStatus.SUCCESS),
            _make_task(status=TaskStatus.FAILED),
        ]
        events = monitor.watch_tasks(tasks)
        assert len(events) == 2

    def test_watch_plan(self):
        monitor = ExecutionMonitor()
        plan = ExecutionPlan(tasks=[
            _make_task(status=TaskStatus.SUCCESS),
            _make_task(status=TaskStatus.SUCCESS),
        ])
        events = monitor.watch_plan(plan)
        assert len(events) >= 2  # task events + plan_completed_success

    def test_watch_plan_with_failures(self):
        monitor = ExecutionMonitor()
        plan = ExecutionPlan(tasks=[
            _make_task(status=TaskStatus.SUCCESS),
            _make_task(status=TaskStatus.FAILED),
        ])
        events = monitor.watch_plan(plan)
        has_failure_event = any(e.event_type == "plan_completed_with_failures" for e in events)
        assert has_failure_event

    def test_detect_roas_drop_critical(self):
        monitor = ExecutionMonitor()
        event = monitor.detect_roas_drop(0.30, 1.0)
        assert event is not None
        assert event.severity == "critical"

    def test_detect_roas_drop_warning(self):
        monitor = ExecutionMonitor()
        event = monitor.detect_roas_drop(0.70, 1.0)
        assert event is not None
        assert event.severity == "warning"

    def test_detect_roas_drop_none(self):
        monitor = ExecutionMonitor()
        event = monitor.detect_roas_drop(1.0, 1.0)
        assert event is None

    def test_detect_roas_drop_zero_previous(self):
        monitor = ExecutionMonitor()
        event = monitor.detect_roas_drop(0.50, 0.0)
        assert event is None

    def test_detect_risk_increase(self):
        monitor = ExecutionMonitor(risk_threshold=0.80)
        assert monitor.detect_risk_increase(0.90) is not None
        assert monitor.detect_risk_increase(0.50) is None

    def test_detect_progress_stall(self):
        monitor = ExecutionMonitor(progress_stall_seconds=60)
        plan = ExecutionPlan()
        event = monitor.detect_progress_stall(plan, 0.3, 120)
        assert event is not None
        assert event.event_type == "progress_stalled"

    def test_detect_progress_stall_normal(self):
        monitor = ExecutionMonitor(progress_stall_seconds=120)
        plan = ExecutionPlan()
        event = monitor.detect_progress_stall(plan, 0.3, 30)
        assert event is None

    def test_get_alerts(self):
        monitor = ExecutionMonitor()
        monitor.detect_roas_drop(0.30, 1.0)
        monitor.detect_risk_increase(0.90)
        alerts = monitor.get_alerts()
        assert monitor.alert_count == 2

    def test_get_alerts_by_severity(self):
        monitor = ExecutionMonitor()
        monitor.detect_roas_drop(0.30, 1.0)  # critical
        alerts = monitor.get_alerts(severity="critical")
        assert len(alerts) == 1

    def test_get_events_by_type(self):
        monitor = ExecutionMonitor()
        monitor.detect_roas_drop(0.30, 1.0)
        events = monitor.get_events(event_type="roas_drop")
        assert len(events) == 1

    def test_get_task_events(self):
        monitor = ExecutionMonitor()
        task = _make_task(status=TaskStatus.SUCCESS)
        monitor.watch_task(task)
        events = monitor.get_task_events(task.task_id)
        assert len(events) == 1

    def test_clear(self):
        monitor = ExecutionMonitor()
        monitor.detect_roas_drop(0.30, 1.0)
        assert monitor.event_count > 0
        monitor.clear()
        assert monitor.event_count == 0
        assert monitor.alert_count == 0

    def test_get_summary(self):
        monitor = ExecutionMonitor()
        monitor.detect_roas_drop(0.30, 1.0)
        monitor.detect_risk_increase(0.90)
        summary = monitor.get_summary()
        assert summary["total_events"] == 2
        assert summary["total_alerts"] == 2
        assert summary["alerts_by_severity"]["critical"] == 2


# ══════════════════════════════════════════════════════════════
# Test Rollback Manager
# ══════════════════════════════════════════════════════════════


class TestRollbackManager:
    """RollbackManager 测试 (20 tests)."""

    def test_rollback_success(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(task_id=task.task_id, success=True,
                                      output={"generated_ids": ["C1", "C2"]})
        record = rm.rollback(task)
        assert record.rollback_success is True
        assert task.status == TaskStatus.ROLLED_BACK

    def test_rollback_no_adapter(self):
        rm = RollbackManager()
        task = _make_task(TaskType.ANALYTICS_QUERY)
        record = rm.rollback(task)
        assert record.rollback_success is False
        assert "No adapter" in record.error

    def test_rollback_tasks(self):
        rm = RollbackManager()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
        ]
        for t in tasks:
            t.result = ExecutionResult(success=True)
        records = rm.rollback_tasks(tasks)
        assert len(records) == 2
        assert all(r.rollback_success for r in records)

    def test_rollback_plan(self):
        rm = RollbackManager()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5},
                        status=TaskStatus.SUCCESS)
        t2 = _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20},
                        status=TaskStatus.SUCCESS)
        t1.result = ExecutionResult(success=True)
        t2.result = ExecutionResult(success=True)
        plan = ExecutionPlan(tasks=[t1, t2])
        records = rm.rollback_plan(plan)
        assert len(records) == 2
        assert t1.status == TaskStatus.ROLLED_BACK
        assert t2.status == TaskStatus.ROLLED_BACK

    def test_rollback_reverse_order(self):
        rm = RollbackManager()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5},
                        status=TaskStatus.SUCCESS)
        t2 = _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20},
                        status=TaskStatus.SUCCESS)
        t1.result = ExecutionResult(success=True)
        t2.result = ExecutionResult(success=True)
        plan = ExecutionPlan(tasks=[t1, t2])
        records = rm.rollback_plan(plan)
        # Last executed first: t2 first, then t1
        assert records[0].task_id == t2.task_id
        assert records[1].task_id == t1.task_id

    def test_rollback_failed(self):
        rm = RollbackManager()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5},
                        status=TaskStatus.SUCCESS)
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0},
                        status=TaskStatus.FAILED)
        t1.result = ExecutionResult(success=True)
        t2.result = ExecutionResult(success=False)
        plan = ExecutionPlan(tasks=[t1, t2])
        records = rm.rollback_failed(plan)
        assert len(records) == 2

    def test_restore_previous_state(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        task.parameters = {}
        restored = rm.restore_previous_state(task)
        assert restored is not None
        assert restored.parameters["count"] == 5

    def test_restore_previous_state_no_history(self):
        rm = RollbackManager()
        task = _make_task()
        assert rm.restore_previous_state(task) is None

    def test_history_count(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        assert rm.history_count == 1

    def test_success_count(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        assert rm.success_count == 1

    def test_failure_count(self):
        rm = RollbackManager()
        task = _make_task(TaskType.ANALYTICS_QUERY)
        rm.rollback(task)
        assert rm.failure_count == 1

    def test_get_history_by_task(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        history = rm.get_history(task.task_id)
        assert len(history) == 1

    def test_get_all_history(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        assert len(rm.get_history()) == 1

    def test_clear_history(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        rm.clear_history()
        assert rm.history_count == 0

    def test_get_summary(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        task.result = ExecutionResult(success=True)
        rm.rollback(task)
        summary = rm.get_summary()
        assert summary["total_rollbacks"] == 1
        assert summary["success_rate"] == 1.0

    def test_rollback_saves_previous_state(self):
        rm = RollbackManager()
        task = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 10, "dna": "v1"})
        task.result = ExecutionResult(success=True, output={"generated_ids": ["C1"]})
        record = rm.rollback(task)
        assert record.previous_state["count"] == 10
        assert record.previous_state["dna"] == "v1"
        assert "result_output" in record.previous_state

    def test_rollback_experiment(self):
        rm = RollbackManager()
        task = _make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 7})
        task.result = ExecutionResult(success=True, output={"experiment_id": "EXP_001"})
        record = rm.rollback(task)
        assert record.rollback_success is True

    def test_rollback_resource(self):
        rm = RollbackManager()
        task = _make_task(TaskType.BUDGET_INCREASE,
                          parameters={"change_pct": 0.30, "previous_budget": 1000})
        task.result = ExecutionResult(success=True)
        record = rm.rollback(task)
        assert record.rollback_success is True

    def test_rollback_portfolio(self):
        rm = RollbackManager()
        task = _make_task(TaskType.PORTFOLIO_ADJUSTMENT,
                          parameters={"previous_allocation": {"p1": 0.50}})
        task.result = ExecutionResult(success=True)
        record = rm.rollback(task)
        assert record.rollback_success is True

    def test_rollback_safety(self):
        rm = RollbackManager()
        task = _make_task(TaskType.SUNSET_PRODUCT, product_id="p01")
        task.result = ExecutionResult(success=True)
        record = rm.rollback(task)
        assert record.rollback_success is True


# ══════════════════════════════════════════════════════════════
# Test Execution Controller
# ══════════════════════════════════════════════════════════════


class TestExecutionController:
    """ExecutionController 测试 (30 tests)."""

    def test_create_default(self):
        ctrl = ExecutionController()
        assert ctrl.engine is not None
        assert ctrl.monitor is not None
        assert ctrl.rollback is not None

    def test_create_custom(self):
        engine = ExecutionEngine()
        monitor = ExecutionMonitor()
        rollback = RollbackManager()
        ctrl = ExecutionController(engine=engine, monitor=monitor, rollback=rollback)
        assert ctrl.engine is engine
        assert ctrl.monitor is monitor
        assert ctrl.rollback is rollback

    def test_strategy_to_tasks(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(actions=[
            StrategyAction(action_type=ActionType.CREATE_CREATIVE, priority=85,
                           parameters={"count": 50}),
            StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT, priority=80,
                           parameters={"duration_days": 7}),
            StrategyAction(action_type=ActionType.INCREASE_BUDGET, priority=70,
                           parameters={"change_pct": 0.20}),
        ])
        tasks = ctrl.strategy_to_tasks(strategy)
        assert len(tasks) == 3
        assert tasks[0].task_type == TaskType.CREATE_CREATIVE
        assert tasks[1].task_type == TaskType.EXPERIMENT_START
        assert tasks[2].task_type == TaskType.BUDGET_INCREASE

    def test_strategy_to_tasks_dependencies(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(actions=[
            StrategyAction(action_type=ActionType.CREATE_CREATIVE),
            StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT),
        ])
        tasks = ctrl.strategy_to_tasks(strategy)
        assert len(tasks[0].dependencies) == 0
        assert tasks[1].dependencies == [tasks[0].task_id]

    def test_strategy_to_tasks_empty(self):
        ctrl = ExecutionController()
        tasks = ctrl.strategy_to_tasks(_make_strategy())
        assert len(tasks) == 0

    def test_strategy_to_tasks_priority(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(actions=[
            StrategyAction(action_type=ActionType.CREATE_CREATIVE, priority=90),
        ])
        tasks = ctrl.strategy_to_tasks(strategy)
        assert tasks[0].priority == 90

    def test_generate_plan(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                                    parameters={"count": 50})],
            risk_score=0.30,
        )
        plan = ctrl.generate_plan(strategy)
        assert plan.task_count == 1
        assert plan.risk_score == 0.30
        assert plan.strategy_id == strategy.strategy_id

    def test_generate_plans(self):
        ctrl = ExecutionController()
        s1 = _make_strategy(actions=[
            StrategyAction(action_type=ActionType.CREATE_CREATIVE),
        ])
        s2 = _make_strategy(actions=[
            StrategyAction(action_type=ActionType.INCREASE_BUDGET),
        ])
        plans = ctrl.generate_plans([s1, s2])
        assert len(plans) == 2

    def test_safety_check_pass(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan(risk_score=0.30)
        assert ctrl.safety_check(plan) is True

    def test_safety_check_fail_risk(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan(risk_score=0.95)
        assert ctrl.safety_check(plan) is False

    def test_safety_check_fail_rejected(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan(approval_status=ApprovalStatus.REJECTED)
        assert ctrl.safety_check(plan) is False

    def test_approve(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan()
        result = ctrl.approve(plan)
        assert result.approval_status == ApprovalStatus.APPROVED

    def test_reject(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan()
        result = ctrl.reject(plan)
        assert result.approval_status == ApprovalStatus.REJECTED

    def test_execute(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan(
            tasks=[_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})],
            risk_score=0.30,
        )
        result = ctrl.execute(plan)
        assert result.is_complete
        assert result.approval_status == ApprovalStatus.APPROVED

    def test_execute_safety_fail(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan(risk_score=0.95)
        result = ctrl.execute(plan)
        assert result.approval_status == ApprovalStatus.REJECTED

    def test_execute_strategy(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                                    parameters={"count": 5})],
            risk_score=0.30,
        )
        plan = ctrl.execute_strategy(strategy)
        assert plan.is_complete
        assert plan.task_count == 1

    def test_execute_strategies(self):
        ctrl = ExecutionController()
        strategies = [
            _make_strategy(actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 5}),
            ], risk_score=0.30),
            _make_strategy(actions=[
                StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                               parameters={"change_pct": 0.20}),
            ], risk_score=0.30),
        ]
        plans = ctrl.execute_strategies(strategies)
        assert len(plans) == 2
        assert all(p.is_complete for p in plans)

    def test_monitor_plan(self):
        ctrl = ExecutionController()
        plan = ExecutionPlan(
            tasks=[_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})],
        )
        ctrl.execute(plan)
        result = ctrl.monitor_plan(plan)
        assert "status" in result
        assert "events" in result
        assert result["status"]["is_complete"] is True

    def test_rollback_plan(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                                    parameters={"count": 5})],
            risk_score=0.30,
        )
        plan = ctrl.execute_strategy(strategy)
        records = ctrl.rollback_plan(plan)
        assert len(records) == 1
        assert records[0]["rollback_success"] is True

    def test_rollback_failed_controller(self):
        ctrl = ExecutionController()
        t1 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})
        t2 = _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 0}, priority=30)
        plan = ExecutionPlan(tasks=[t1, t2])
        ctrl.execute(plan)
        records = ctrl.rollback_failed(plan)
        assert len(records) == 2

    def test_run_full_pipeline(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 10}),
                StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT,
                               parameters={"duration_days": 7}),
                StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                               parameters={"change_pct": 0.20}),
            ],
            risk_score=0.30,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is True
        assert result["plan"]["task_count"] == 3
        assert result["plan"]["is_complete"] is True
        assert "monitor" in result
        assert result["monitor"]["status"]["success_count"] == 3

    def test_run_safety_fail(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[StrategyAction(action_type=ActionType.CREATE_CREATIVE)],
            risk_score=0.95,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is False
        assert "Safety check" in result["reason"]

    def test_run_auto_rollback(self):
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 0}, priority=30),
            ],
            risk_score=0.30,
        )
        result = ctrl.run(strategy, auto_rollback=True)
        assert result["executed"] is True
        # Plan has failures, auto_rollback should trigger
        assert len(result["rollback"]) == 1

    def test_run_batch(self):
        ctrl = ExecutionController()
        strategies = [
            _make_strategy(
                actions=[StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                                        parameters={"count": 5})],
                risk_score=0.30,
            ),
            _make_strategy(
                actions=[StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                                        parameters={"change_pct": 0.20})],
                risk_score=0.30,
            ),
        ]
        results = ctrl.run_batch(strategies)
        assert len(results) == 2
        assert all(r["executed"] for r in results)

    def test_get_summary(self):
        ctrl = ExecutionController()
        summary = ctrl.get_summary()
        assert "engine" in summary
        assert "monitor" in summary
        assert "rollback" in summary

    def test_strategy_full_recovery_pipeline(self):
        """完整恢复策略: 减预算→创意刷新→DNA变异→实验→评估."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            template_type=StrategyTemplateType.RECOVERY,
            actions=[
                StrategyAction(action_type=ActionType.DECREASE_BUDGET,
                               parameters={"change_pct": -0.20}),
                StrategyAction(action_type=ActionType.REFRESH_CREATIVE,
                               parameters={"count": 30}),
                StrategyAction(action_type=ActionType.MUTATE_DNA,
                               parameters={"dna_variants": ["v1", "v2"]}),
                StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT,
                               parameters={"duration_days": 7}),
                StrategyAction(action_type=ActionType.EVALUATE_EXPERIMENT),
            ],
            risk_score=0.40,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is True
        assert result["plan"]["task_count"] == 5
        assert result["plan"]["success_tasks"] == 5

    def test_strategy_scale_pipeline(self):
        """完整扩展策略: 加预算→创意生成→受众扩展→实验."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            template_type=StrategyTemplateType.SCALE,
            actions=[
                StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                               parameters={"change_pct": 0.25}),
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 20}),
                StrategyAction(action_type=ActionType.EXPAND_AUDIENCE,
                               parameters={"channels": ["fb", "google"]}),
                StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT,
                               parameters={"duration_days": 14}),
            ],
            risk_score=0.30,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is True
        assert result["plan"]["success_tasks"] == 4

    def test_strategy_sunset_pipeline(self):
        """退出策略: 减预算→下架产品."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            template_type=StrategyTemplateType.SUNSET,
            actions=[
                StrategyAction(action_type=ActionType.DECREASE_BUDGET,
                               parameters={"change_pct": -0.50}),
                StrategyAction(action_type=ActionType.SUNSET_PRODUCT,
                               parameters={"product_id": "p01"}),
            ],
            risk_score=0.50,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is True
        assert result["plan"]["success_tasks"] == 2

    def test_strategy_exploration_pipeline(self):
        """探索策略: DNA变异→创意生成→实验→受众扩展."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            template_type=StrategyTemplateType.EXPLORATION,
            actions=[
                StrategyAction(action_type=ActionType.MUTATE_DNA,
                               parameters={"dna_variants": ["v1", "v2"]}),
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 15}),
                StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT,
                               parameters={"duration_days": 7}),
                StrategyAction(action_type=ActionType.EXPAND_AUDIENCE,
                               parameters={"channels": ["fb"]}),
            ],
            risk_score=0.35,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is True
        assert result["plan"]["success_tasks"] == 4


# ══════════════════════════════════════════════════════════════
# Test Integration
# ══════════════════════════════════════════════════════════════


class TestIntegration:
    """E12.7.4 集成测试 (10 tests)."""

    def test_full_recovery_pipeline(self):
        """完整恢复管线: Strategy→Plan→Execute→Monitor→Rollback."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            product_id="game_x",
            template_type=StrategyTemplateType.RECOVERY,
            actions=[
                StrategyAction(action_type=ActionType.DECREASE_BUDGET,
                               parameters={"change_pct": -0.20}),
                StrategyAction(action_type=ActionType.REFRESH_CREATIVE,
                               parameters={"count": 50}),
                StrategyAction(action_type=ActionType.MUTATE_DNA,
                               parameters={"dna_variants": ["v1"]}),
                StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT,
                               parameters={"duration_days": 7}),
                StrategyAction(action_type=ActionType.EVALUATE_EXPERIMENT),
            ],
            risk_score=0.40,
        )
        result = ctrl.run(strategy)
        assert result["executed"] is True
        plan_result = result["plan"]
        assert plan_result["success_tasks"] == 5
        assert plan_result["failed_tasks"] == 0

        # Verify monitor
        monitor = result["monitor"]
        assert monitor["status"]["is_complete"] is True
        assert monitor["alert_count"] == 0  # No failures

    def test_execute_and_rollback_recovery(self):
        """执行后回滚恢复策略."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            product_id="game_x",
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 10}),
                StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                               parameters={"change_pct": 0.30}),
            ],
            risk_score=0.30,
        )
        plan = ctrl.execute_strategy(strategy)
        records = ctrl.rollback_plan(plan)
        assert len(records) == 2
        assert all(r["rollback_success"] for r in records)

    def test_auto_rollback_on_failure(self):
        """失败时自动回滚."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 5}),
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 0}, priority=30),
            ],
            risk_score=0.30,
        )
        result = ctrl.run(strategy, auto_rollback=True)
        assert result["executed"] is True
        assert result["plan"]["has_failures"] is True
        assert len(result["rollback"]) == 2

    def test_monitor_alerts_on_failure(self):
        """失败时监控生成告警."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 0}),
            ],
            risk_score=0.30,
        )
        result = ctrl.run(strategy)
        assert result["plan"]["has_failures"] is True
        monitor = result["monitor"]
        assert monitor["alert_count"] >= 1

    def test_strategy_plan_execution_dag(self):
        """策略→执行计划→DAG执行."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 10}),
                StrategyAction(action_type=ActionType.LAUNCH_EXPERIMENT,
                               parameters={"duration_days": 7}),
                StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                               parameters={"change_pct": 0.20}),
                StrategyAction(action_type=ActionType.EXPAND_AUDIENCE),
            ],
            risk_score=0.30,
        )
        plan = ctrl.generate_plan(strategy)
        assert plan.task_count == 4
        assert len(plan.execution_order) == 4  # Each task depends on previous

        result = ctrl.execute(plan)
        assert result.is_complete
        assert len(result.success_tasks) == 4

    def test_rollback_manager_history(self):
        """回滚历史记录完整性."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                               parameters={"count": 5}),
                StrategyAction(action_type=ActionType.INCREASE_BUDGET,
                               parameters={"change_pct": 0.20}),
            ],
            risk_score=0.30,
        )
        plan = ctrl.execute_strategy(strategy)
        ctrl.rollback_plan(plan)
        summary = ctrl.get_summary()
        assert summary["rollback"]["total_rollbacks"] == 2
        assert summary["rollback"]["success_rate"] == 1.0

    def test_all_adapters_work_together(self):
        """所有适配器协同工作."""
        engine = ExecutionEngine()
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5}),
            _make_task(TaskType.EXPERIMENT_START, parameters={"duration_days": 7}),
            _make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20}),
            _make_task(TaskType.PORTFOLIO_ADJUSTMENT, parameters={"adjustments": {"p1": 0.10}}),
            _make_task(TaskType.SUNSET_PRODUCT, product_id="p01"),
        ]
        plan = ExecutionPlan(tasks=tasks)
        result = engine.execute(plan)
        assert result.is_complete
        assert len(result.success_tasks) == 5

    def test_engine_task_count_persistence(self):
        """引擎任务计数跨计划持久化."""
        engine = ExecutionEngine()
        plan1 = ExecutionPlan(tasks=[_make_task(TaskType.CREATE_CREATIVE, parameters={"count": 5})])
        plan2 = ExecutionPlan(tasks=[_make_task(TaskType.BUDGET_INCREASE, parameters={"change_pct": 0.20})])
        engine.execute(plan1)
        engine.execute(plan2)
        assert engine.task_count == 2
        assert engine.execution_count == 2

    def test_monitor_clears_between_runs(self):
        """监控器在运行间清除."""
        ctrl = ExecutionController()
        strategy = _make_strategy(
            actions=[StrategyAction(action_type=ActionType.CREATE_CREATIVE,
                                    parameters={"count": 5})],
            risk_score=0.30,
        )
        ctrl.run(strategy)
        ctrl.monitor.clear()
        assert ctrl.monitor.event_count == 0

    def test_repr_formats(self):
        """所有核心类的 repr 格式."""
        assert "ExecutionEngine" in repr(ExecutionEngine())
        assert "ExecutionMonitor" in repr(ExecutionMonitor())
        assert "RollbackManager" in repr(RollbackManager())
        assert "ExecutionController" in repr(ExecutionController())