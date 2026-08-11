"""
E16.6.5 — ASO Priority Engine / Scheduler.

Converts ranked opportunities into concrete action plans.

Formula: ``Priority = Impact × Confidence × Revenue_Potential × Urgency / Cost``

The engine also:
* Tags high-risk actions (``UPDATE_TITLE`` → manual approval required)
* Generates execution steps for each action type
* Limits to Top-K actions per cycle
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.growth_loop.models import (
    ASOActionPlan,
    ASOOpportunity,
    ApprovalStatus,
)


# High-risk actions that always require human approval
_HIGH_RISK_ACTIONS: Dict[str, str] = {
    "UPDATE_TITLE": "Changing the store title can hurt discoverability — manual review required",
}


_STEPS_BY_ACTION: Dict[str, List[str]] = {
    "UPDATE_SCREENSHOT": [
        "Analyze current screenshot weaknesses (hook, clarity, value)",
        "Generate 3 candidate variants via Creative Engine",
        "Review visual scores for each candidate",
        "Select best candidate for experiment",
        "Upload candidate to store listing (manual if needed)",
    ],
    "UPDATE_ICON": [
        "Analyze current icon performance (focus, emotion, readability)",
        "Generate 2–3 icon variants via Creative Engine",
        "Review visual scores for each variant",
        "Select best candidate",
        "Update icon in store (manual if needed)",
    ],
    "UPDATE_TITLE": [
        "Review title keyword strategy",
        "Draft 2 alternative titles (A/B test ready)",
        "Manual review and approval",
        "Update title in store (requires human)",
    ],
    "ADD_KEYWORD": [
        "Identify high-potential keywords from competitor analysis",
        "Check keyword difficulty and relevance",
        "Add keyword to store listing (manual if needed)",
    ],
    "REMOVE_KEYWORD": [
        "Identify underperforming keywords",
        "Verify keyword traffic data",
        "Remove keyword from store listing (manual if needed)",
    ],
    "UPDATE_DESCRIPTION": [
        "Review current description performance",
        "Draft improved description with keyword optimization",
        "Update description in store (manual if needed)",
    ],
    "CREATE_EXPERIMENT": [
        "Define experiment parameters (duration, variants)",
        "Set up A/B test in store console",
        "Monitor initial data collection",
    ],
}

_DEFAULT_STEPS = ["Analyze current state", "Generate variant", "Apply change (manual if needed)"]


class ASOPriorityEngine:
    """Convert opportunities → ranked action plans.

    Produces ``ASOActionPlan`` entries that feed into the Policy Gate and
    Experiment Manager.
    """

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    # ------------------------------------------------------------------ #
    def _is_high_risk(self, action: str) -> bool:
        return action.upper() in _HIGH_RISK_ACTIONS

    def _risk_reason(self, action: str) -> str:
        return _HIGH_RISK_ACTIONS.get(action.upper(), "")

    def _steps_for(self, action: str) -> List[str]:
        key = action.upper()
        return _STEPS_BY_ACTION.get(key, _DEFAULT_STEPS)

    def _determine_approval(self, opportunity: ASOOpportunity) -> ApprovalStatus:
        """Set approval status based on risk and confidence."""
        action = (opportunity.suggested_action or "").upper()

        # High-risk → always HUMAN_QUEUE
        if action in _HIGH_RISK_ACTIONS:
            return ApprovalStatus.HUMAN_QUEUE

        # Low confidence → RECORD_ONLY (no experiment, just log)
        if opportunity.confidence < 0.3:
            return ApprovalStatus.RECORD_ONLY

        # Default → AUTO_APPROVED
        return ApprovalStatus.AUTO_APPROVED

    # ------------------------------------------------------------------ #
    def rank(self, opportunities: List[ASOOpportunity]) -> List[ASOOpportunity]:
        """Sort opportunities by ``priority_score`` descending."""
        return sorted(
            opportunities, key=lambda o: o.priority_score, reverse=True
        )

    def plan(
        self,
        opportunities: List[ASOOpportunity],
        top_k: Optional[int] = None,
    ) -> List[ASOActionPlan]:
        """Convert top opportunities into action plans.

        Each plan includes steps, risk flag, and approval status.
        Only plans with ``priority_score > 0`` are emitted.
        """
        ranked = self.rank(opportunities)
        k = top_k if top_k is not None else self.top_k
        plans: List[ASOActionPlan] = []

        for i, opp in enumerate(ranked):
            if i >= k:
                break
            if opp.priority_score <= 0:
                continue

            action = (opp.suggested_action or opp.title).upper()
            risk_reason = self._risk_reason(action)
            approval = self._determine_approval(opp)

            plan = ASOActionPlan(
                plan_id=f"plan_{opp.opportunity_id}_{i}",
                game_id=opp.game_id,
                opportunity_id=opp.opportunity_id,
                action=opp.suggested_action,
                title=opp.title,
                steps=self._steps_for(action),
                high_risk=risk_reason != "",
                approval_status=approval,
                expected_impact=opp.impact,
                expected_confidence=opp.confidence,
            )
            plans.append(plan)

        return plans


__all__ = ["ASOPriorityEngine"]
