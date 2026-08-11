"""E12.7.4 Execution Controller — 总控制器.

流程: GrowthStrategy → Generate Execution Plan → Safety Check → Execute → Monitor → Result.
"""

from __future__ import annotations

from typing import Any

from ..strategy.models import (
    ActionType,
    GrowthStrategy,
    StrategyAction,
    StrategyTemplateType,
)
from .execution_engine import ExecutionEngine
from .execution_monitor import ExecutionMonitor
from .models import (
    ApprovalStatus,
    ExecutionPlan,
    ExecutionTask,
    TargetModule,
    TaskStatus,
    TaskType,
)
from .rollback_manager import RollbackManager
from .task_dispatcher import TaskDispatcher


# Map StrategyAction → TaskType
_ACTION_TO_TASK_TYPE: dict[ActionType, TaskType] = {
    ActionType.CREATE_CREATIVE: TaskType.CREATE_CREATIVE,
    ActionType.MUTATE_DNA: TaskType.CREATIVE_MUTATION,
    ActionType.REFRESH_CREATIVE: TaskType.REFRESH_CREATIVE,
    ActionType.LAUNCH_EXPERIMENT: TaskType.EXPERIMENT_START,
    ActionType.EVALUATE_EXPERIMENT: TaskType.EXPERIMENT_EVALUATE,
    ActionType.INCREASE_BUDGET: TaskType.BUDGET_INCREASE,
    ActionType.DECREASE_BUDGET: TaskType.BUDGET_DECREASE,
    ActionType.REALLOCATE_BUDGET: TaskType.BUDGET_REALLOCATE,
    ActionType.EXPAND_AUDIENCE: TaskType.AUDIENCE_EXPAND,
    ActionType.SUNSET_PRODUCT: TaskType.SUNSET_PRODUCT,
    ActionType.CUSTOM: TaskType.CUSTOM,
}

# Map ActionType → TargetModule
_ACTION_TO_MODULE: dict[ActionType, TargetModule] = {
    ActionType.CREATE_CREATIVE: TargetModule.E11_EVOLUTION,
    ActionType.MUTATE_DNA: TargetModule.E11_EVOLUTION,
    ActionType.REFRESH_CREATIVE: TargetModule.E11_EVOLUTION,
    ActionType.LAUNCH_EXPERIMENT: TargetModule.E12_4_EXPERIMENT,
    ActionType.EVALUATE_EXPERIMENT: TargetModule.E12_4_EXPERIMENT,
    ActionType.INCREASE_BUDGET: TargetModule.E12_6_2_RESOURCE,
    ActionType.DECREASE_BUDGET: TargetModule.E12_6_2_RESOURCE,
    ActionType.REALLOCATE_BUDGET: TargetModule.E12_6_2_RESOURCE,
    ActionType.EXPAND_AUDIENCE: TargetModule.E12_6_5_PORTFOLIO,
    ActionType.SUNSET_PRODUCT: TargetModule.E12_6_3_SAFETY,
    ActionType.CUSTOM: TargetModule.E12_6_3_SAFETY,
}


class ExecutionController:
    """执行控制器 — Growth OS 的执行大脑.

    完整流程:
      1. 从 GrowthStrategy 生成 ExecutionPlan
      2. 安全检查 (Safety Check)
      3. 执行 (Execute)
      4. 监控 (Monitor)
      5. 返回结果
    """

    def __init__(
        self,
        engine: ExecutionEngine | None = None,
        monitor: ExecutionMonitor | None = None,
        rollback: RollbackManager | None = None,
    ):
        self._engine = engine or ExecutionEngine()
        self._monitor = monitor or ExecutionMonitor()
        self._rollback = rollback or RollbackManager()

    @property
    def engine(self) -> ExecutionEngine:
        return self._engine

    @property
    def monitor(self) -> ExecutionMonitor:
        return self._monitor

    @property
    def rollback(self) -> RollbackManager:
        return self._rollback

    # ── Strategy → Execution Plan ─────────────────────────────

    def strategy_to_tasks(self, strategy: GrowthStrategy) -> list[ExecutionTask]:
        """将 GrowthStrategy 的 actions 转换为 ExecutionTask 列表."""
        tasks: list[ExecutionTask] = []
        prev_task_id: str | None = None

        for action in strategy.actions:
            task_type = _ACTION_TO_TASK_TYPE.get(action.action_type, TaskType.CUSTOM)
            target_module = _ACTION_TO_MODULE.get(action.action_type, TargetModule.E11_EVOLUTION)

            deps = [prev_task_id] if prev_task_id else []
            task = ExecutionTask(
                strategy_id=strategy.strategy_id,
                product_id=strategy.product_id,
                task_type=task_type,
                target_module=target_module,
                parameters=action.parameters,
                priority=action.priority,
                dependencies=deps,
            )
            tasks.append(task)
            prev_task_id = task.task_id

        return tasks

    def generate_plan(self, strategy: GrowthStrategy) -> ExecutionPlan:
        """从 GrowthStrategy 生成 ExecutionPlan."""
        tasks = self.strategy_to_tasks(strategy)
        return self._engine.create_plan(
            tasks=tasks,
            strategy_id=strategy.strategy_id,
            product_id=strategy.product_id,
            risk_score=strategy.risk_score,
        )

    def generate_plans(
        self, strategies: list[GrowthStrategy],
    ) -> list[ExecutionPlan]:
        """从多个 GrowthStrategy 生成 ExecutionPlan 列表."""
        return [self.generate_plan(s) for s in strategies]

    # ── Safety Check ──────────────────────────────────────────

    def safety_check(self, plan: ExecutionPlan) -> bool:
        """安全检查 — 检查计划是否安全可执行."""
        if plan.risk_score > 0.90:
            return False
        if plan.approval_status == ApprovalStatus.REJECTED:
            return False
        return True

    def approve(self, plan: ExecutionPlan) -> ExecutionPlan:
        """审批通过."""
        return self._engine.approve_plan(plan)

    def reject(self, plan: ExecutionPlan) -> ExecutionPlan:
        """拒绝计划."""
        return self._engine.reject_plan(plan)

    # ── Execute ───────────────────────────────────────────────

    def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        """执行计划."""
        if not self.safety_check(plan):
            plan.approval_status = ApprovalStatus.REJECTED
            return plan

        plan = self._engine.approve_plan(plan)
        return self._engine.execute(plan)

    def execute_strategy(self, strategy: GrowthStrategy) -> ExecutionPlan:
        """从策略直接执行."""
        plan = self.generate_plan(strategy)
        return self.execute(plan)

    def execute_strategies(
        self, strategies: list[GrowthStrategy],
    ) -> list[ExecutionPlan]:
        """执行多个策略."""
        plans = self.generate_plans(strategies)
        return [self.execute(p) for p in plans]

    # ── Monitor ───────────────────────────────────────────────

    def monitor_plan(self, plan: ExecutionPlan) -> dict[str, Any]:
        """监控计划执行."""
        events = self._monitor.watch_plan(plan)
        status = self._engine.get_plan_status(plan)
        return {
            "status": status,
            "events": [e.to_dict() for e in events],
            "alert_count": self._monitor.alert_count,
        }

    # ── Rollback ──────────────────────────────────────────────

    def rollback_plan(self, plan: ExecutionPlan) -> list[dict[str, Any]]:
        """回滚计划."""
        records = self._rollback.rollback_plan(plan)
        return [r.to_dict() for r in records]

    def rollback_failed(self, plan: ExecutionPlan) -> list[dict[str, Any]]:
        """回滚计划中所有已执行的任务."""
        records = self._rollback.rollback_failed(plan)
        return [r.to_dict() for r in records]

    # ── Full Pipeline ─────────────────────────────────────────

    def run(
        self,
        strategy: GrowthStrategy,
        *,
        auto_rollback: bool = False,
    ) -> dict[str, Any]:
        """完整执行管线: Plan → Safety Check → Execute → Monitor → Result.

        Args:
            strategy: 增长策略
            auto_rollback: 失败时是否自动回滚

        Returns:
            包含 plan, monitor_result, rollback_records 的字典
        """
        # Step 1: Generate plan
        plan = self.generate_plan(strategy)

        # Step 2: Safety check
        if not self.safety_check(plan):
            return {
                "plan": plan.to_dict(),
                "executed": False,
                "reason": "Safety check failed",
                "monitor": {},
                "rollback": [],
            }

        # Step 3: Execute
        plan = self.execute(plan)

        # Step 4: Monitor
        monitor_result = self.monitor_plan(plan)

        # Step 5: Auto-rollback on failure
        rollback_result: list[dict[str, Any]] = []
        if auto_rollback and plan.has_failures:
            rollback_result = self.rollback_failed(plan)

        return {
            "plan": plan.to_dict(),
            "executed": True,
            "monitor": monitor_result,
            "rollback": rollback_result,
        }

    def run_batch(
        self,
        strategies: list[GrowthStrategy],
        *,
        auto_rollback: bool = False,
    ) -> list[dict[str, Any]]:
        """批量执行多个策略."""
        return [self.run(s, auto_rollback=auto_rollback) for s in strategies]

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """获取控制器摘要."""
        return {
            "engine": self._engine.get_summary(),
            "monitor": self._monitor.get_summary(),
            "rollback": self._rollback.get_summary(),
        }