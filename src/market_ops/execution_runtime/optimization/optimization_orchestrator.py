"""E10.2 Phase 5 — Optimization Orchestrator.

Unified orchestration of the full optimization pipeline:
    Feedback → Policy → Planner → ExecutionTask

This is the central entry point for the autonomous optimization
loop. It wires together all Phase 5 components and produces
ready-to-execute tasks for the E10.1 Runtime.

Flow:
    LearningSignal
        │
        ▼
    PolicyEngine.evaluate()
        │
        ▼
    OptimizationDecision
        │
        ▼
    MutationPlanner.plan_and_create_task()
        │
        ▼
    ExecutionTask
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import LearningSignal, ExecutionTask
from market_ops.execution_runtime.optimization_schema import OptimizationDecision, MutationPlan
from market_ops.execution_runtime.optimization.policy_engine import OptimizationPolicy
from market_ops.execution_runtime.optimization.mutation_planner import MutationPlanner
from market_ops.execution_runtime.optimization.scale_controller import ScaleController
from market_ops.execution_runtime.optimization.kill_controller import KillController
from market_ops.execution_runtime.optimization.experiment_allocator import ExperimentAllocator


class OptimizationOrchestrator:
    """Central orchestrator for the autonomous optimization loop.

    Takes LearningSignal feedback and produces ExecutionTasks
    through the full optimization pipeline.

    Args:
        policy: OptimizationPolicy instance.
        planner: MutationPlanner instance.
        allocator: ExperimentAllocator instance.

    Usage:
        orchestrator = OptimizationOrchestrator()
        tasks = orchestrator.optimize(signals)
    """

    def __init__(
        self,
        policy: OptimizationPolicy | None = None,
        planner: MutationPlanner | None = None,
        allocator: ExperimentAllocator | None = None,
    ) -> None:
        self._policy = policy or OptimizationPolicy()
        self._planner = planner or MutationPlanner()
        self._allocator = allocator or ExperimentAllocator()

    def optimize(
        self,
        signal: LearningSignal,
        campaign_id: str = "",
        current_budget: float = 100.0,
        current_status: str = "ACTIVE",
    ) -> tuple[OptimizationDecision, MutationPlan, ExecutionTask]:
        """Run the full optimization pipeline for a single signal.

        Args:
            signal: LearningSignal from feedback loop.
            campaign_id: Platform campaign ID.
            current_budget: Current campaign daily budget.
            current_status: Current campaign status.

        Returns:
            Tuple of (OptimizationDecision, MutationPlan, ExecutionTask).
        """
        # Step 1: Evaluate signal → decision
        decision = self._policy.evaluate(signal, campaign_id)

        # Step 2: Plan mutation → MutationPlan + ExecutionTask
        plan, task = self._planner.plan_and_create_task(
            decision,
            current_budget=current_budget,
            current_status=current_status,
            creative_id=campaign_id,
        )

        return decision, plan, task

    def optimize_batch(
        self,
        signals: list[LearningSignal],
        campaign_ids: list[str] | None = None,
        current_budgets: list[float] | None = None,
    ) -> list[tuple[OptimizationDecision, MutationPlan, ExecutionTask]]:
        """Run the optimization pipeline for multiple signals.

        Args:
            signals: List of LearningSignals.
            campaign_ids: Optional list of campaign IDs.
            current_budgets: Optional list of current budgets.

        Returns:
            List of (OptimizationDecision, MutationPlan, ExecutionTask) tuples.
        """
        if campaign_ids is None:
            campaign_ids = [""] * len(signals)
        if current_budgets is None:
            current_budgets = [100.0] * len(signals)

        results: list[tuple[OptimizationDecision, MutationPlan, ExecutionTask]] = []
        for signal, cid, budget in zip(signals, campaign_ids, current_budgets):
            results.append(self.optimize(signal, cid, budget))
        return results

    def allocate_across_campaigns(
        self,
        campaigns: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """Allocate budget across multiple campaigns.

        Args:
            campaigns: Dict of campaign_id → {"roas": float, "spend": float, "revenue": float}.

        Returns:
            Allocation dict with budget changes per campaign.
        """
        return self._allocator.allocate(campaigns)

    @property
    def policy(self) -> OptimizationPolicy:
        return self._policy

    @property
    def planner(self) -> MutationPlanner:
        return self._planner