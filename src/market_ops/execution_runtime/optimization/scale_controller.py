"""E10.2 Phase 5 — Scale Controller.

Handles safe budget scaling operations. Inherits BudgetGuard
from Phase 3 to enforce the 30% max increase rule.

Scale formula:
    new_budget = current_budget * (1 + min(scale_ratio, 0.30))

Ensures:
    - Never exceeds MAX_SCALE_RATIO (30%)
    - Within daily spend cap
    - Above minimum budget floor
"""

from __future__ import annotations

from market_ops.execution_runtime.budget_guard import BudgetGuard, BudgetGuardResult
from market_ops.execution_runtime.optimization_schema import (
    OptimizationDecision,
    MutationPlan,
)
from market_ops.execution_runtime.schemas import ActionType


class ScaleController:
    """Controls safe budget scaling.

    Wraps BudgetGuard from Phase 3 to apply scale decisions
    safely. Produces MutationPlans with validated budget changes.

    Args:
        max_scale_ratio: Maximum budget increase ratio (default 0.30 = 30%).
        budget_guard: Optional custom BudgetGuard instance.
    """

    def __init__(
        self,
        max_scale_ratio: float = 0.30,
        budget_guard: BudgetGuard | None = None,
    ) -> None:
        self._max_scale_ratio = max_scale_ratio
        self._guard = budget_guard or BudgetGuard(max_scale_ratio=max_scale_ratio)

    def plan_scale(
        self,
        decision: OptimizationDecision,
        current_budget: float,
        current_spend: float = 0.0,
    ) -> MutationPlan:
        """Create a MutationPlan for a SCALE decision.

        Args:
            decision: OptimizationDecision with SCALE action.
            current_budget: Current daily budget.
            current_spend: Current daily spend.

        Returns:
            MutationPlan with validated budget change.
        """
        # Calculate target budget
        target_budget = round(current_budget * (1.0 + self._max_scale_ratio), 2)

        # Validate through BudgetGuard
        result = self._guard.check(current_budget, target_budget, current_spend)
        if not result.allowed:
            target_budget = result.capped_budget

        delta = round(target_budget - current_budget, 2)

        return MutationPlan(
            campaign_id=decision.campaign_id,
            decision_id=decision.decision_id,
            mutation_type="BUDGET_CHANGE",
            action=ActionType.SCALE.value,
            budget_before=current_budget,
            budget_after=target_budget,
            budget_delta=delta,
            expected_gain=decision.expected_impact,
        )

    def get_max_budget(self, current_budget: float) -> float:
        """Get the maximum allowed budget after scaling.

        Args:
            current_budget: Current daily budget.

        Returns:
            Maximum allowed budget.
        """
        return round(current_budget * (1.0 + self._max_scale_ratio), 2)

    @property
    def max_scale_ratio(self) -> float:
        return self._max_scale_ratio