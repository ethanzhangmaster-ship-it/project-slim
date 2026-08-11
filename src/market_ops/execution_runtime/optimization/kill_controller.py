"""E10.2 Phase 5 — Kill Controller.

Handles campaign termination for underperforming campaigns.
Converts KILL decisions into status-change MutationPlans.

Kill rules:
    ROAS < threshold → PAUSE campaign
    Stops spend immediately
    Records reason for audit trail
"""

from __future__ import annotations

from market_ops.execution_runtime.optimization_schema import (
    OptimizationDecision,
    MutationPlan,
)
from market_ops.execution_runtime.campaign_schema import CampaignStatus
from market_ops.execution_runtime.schemas import ActionType


class KillController:
    """Controls campaign termination.

    Converts KILL decisions into PAUSED status mutations.
    Preserves the reason and expected savings for audit.

    Usage:
        controller = KillController()
        plan = controller.plan_kill(decision, current_status="ACTIVE")
    """

    def plan_kill(
        self,
        decision: OptimizationDecision,
        current_status: str = CampaignStatus.ACTIVE.value,
    ) -> MutationPlan:
        """Create a MutationPlan for a KILL decision.

        Args:
            decision: OptimizationDecision with KILL action.
            current_status: Current campaign status.

        Returns:
            MutationPlan with PAUSED status change.
        """
        return MutationPlan(
            campaign_id=decision.campaign_id,
            decision_id=decision.decision_id,
            mutation_type="STATUS_CHANGE",
            action=ActionType.KILL.value,
            status_before=current_status,
            status_after=CampaignStatus.PAUSED.value,
            expected_gain=decision.expected_impact,
        )

    def plan_watch(
        self,
        decision: OptimizationDecision,
        current_status: str = CampaignStatus.ACTIVE.value,
        current_budget: float = 0.0,
    ) -> MutationPlan:
        """Create a no-op MutationPlan for a WATCH decision.

        Args:
            decision: OptimizationDecision with WATCH action.
            current_status: Current campaign status.
            current_budget: Current daily budget.

        Returns:
            MutationPlan with no change (monitor).
        """
        return MutationPlan(
            campaign_id=decision.campaign_id,
            decision_id=decision.decision_id,
            mutation_type="NO_CHANGE",
            action=ActionType.WATCH.value,
            budget_before=current_budget,
            budget_after=current_budget,
            status_before=current_status,
            status_after=current_status,
            expected_gain=0.0,
        )

    def plan_retest(
        self,
        decision: OptimizationDecision,
        source_campaign_id: str = "",
        retest_budget: float = 50.0,
    ) -> MutationPlan:
        """Create a MutationPlan for a RETEST decision.

        Args:
            decision: OptimizationDecision with RETEST action.
            source_campaign_id: Campaign to duplicate from.
            retest_budget: Budget for the new test campaign.

        Returns:
            MutationPlan with DUPLICATE mutation.
        """
        return MutationPlan(
            campaign_id=decision.campaign_id,
            decision_id=decision.decision_id,
            mutation_type="DUPLICATE",
            action=ActionType.RETEST.value,
            source_campaign_id=source_campaign_id or decision.campaign_id,
            budget_before=0.0,
            budget_after=retest_budget,
            budget_delta=retest_budget,
            expected_gain=0.0,
        )