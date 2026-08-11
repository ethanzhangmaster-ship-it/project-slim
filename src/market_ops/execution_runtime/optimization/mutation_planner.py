"""E10.2 Phase 5 — Mutation Planner.

Converts OptimizationDecisions into ExecutionTasks that the
E10.1 ExecutionEngine can execute. This is the bridge between
the optimization layer and the runtime execution layer.

Flow:
    OptimizationDecision
        │
        ▼
    MutationPlanner
        │
        ├── ScaleController (for SCALE)
        ├── KillController  (for KILL/WATCH)
        │
        ▼
    ExecutionTask
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import (
    ExecutionTask,
    ExecutionTarget,
    ActionType,
)
from market_ops.execution_runtime.optimization_schema import (
    OptimizationDecision,
    MutationPlan,
)
from market_ops.execution_runtime.optimization.scale_controller import ScaleController
from market_ops.execution_runtime.optimization.kill_controller import KillController


class MutationPlanner:
    """Converts optimization decisions into executable tasks.

    Orchestrates ScaleController and KillController to
    produce ExecutionTasks for the runtime engine.

    Args:
        scale_controller: ScaleController instance.
        kill_controller: KillController instance.
    """

    def __init__(
        self,
        scale_controller: ScaleController | None = None,
        kill_controller: KillController | None = None,
    ) -> None:
        self._scaler = scale_controller or ScaleController()
        self._killer = kill_controller or KillController()

    def plan(
        self,
        decision: OptimizationDecision,
        current_budget: float = 100.0,
        current_status: str = "ACTIVE",
    ) -> MutationPlan:
        """Create a MutationPlan from an OptimizationDecision.

        Args:
            decision: OptimizationDecision with action.
            current_budget: Current campaign daily budget.
            current_status: Current campaign status.

        Returns:
            MutationPlan ready for execution.
        """
        if decision.action == ActionType.SCALE.value:
            return self._scaler.plan_scale(decision, current_budget)
        elif decision.action == ActionType.KILL.value:
            return self._killer.plan_kill(decision, current_status)
        elif decision.action == ActionType.RETEST.value:
            return self._killer.plan_retest(decision)
        else:
            return self._killer.plan_watch(decision, current_status, current_budget)

    def to_execution_task(
        self,
        plan: MutationPlan,
        creative_id: str = "",
    ) -> ExecutionTask:
        """Convert a MutationPlan to an ExecutionTask.

        Args:
            plan: MutationPlan with budget/status changes.
            creative_id: Associated creative ID.

        Returns:
            ExecutionTask ready for the ExecutionEngine.
        """
        metrics = {
            "mutation_type": plan.mutation_type,
            "status_before": plan.status_before,
            "status_after": plan.status_after,
            "source_campaign_id": plan.source_campaign_id,
        }

        return ExecutionTask(
            creative_id=creative_id or plan.campaign_id,
            action_type=plan.action,
            budget_change={
                "before": plan.budget_before,
                "after": plan.budget_after,
                "delta": plan.budget_delta,
            },
            target_platform=ExecutionTarget.META_ADS.value,
            target_object=plan.campaign_id,
        )

    def plan_and_create_task(
        self,
        decision: OptimizationDecision,
        current_budget: float = 100.0,
        current_status: str = "ACTIVE",
        creative_id: str = "",
    ) -> tuple[MutationPlan, ExecutionTask]:
        """Plan a mutation and create the corresponding ExecutionTask.

        Convenience method that combines plan() and to_execution_task().

        Args:
            decision: OptimizationDecision.
            current_budget: Current campaign budget.
            current_status: Current campaign status.
            creative_id: Associated creative ID.

        Returns:
            Tuple of (MutationPlan, ExecutionTask).
        """
        plan = self.plan(decision, current_budget, current_status)
        task = self.to_execution_task(plan, creative_id)
        return plan, task