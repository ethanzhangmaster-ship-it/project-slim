"""
E16.6.13 — Approval Gateway.

Three-tier execution permission system.
  Level 1 (AUTO) — low risk: analysis, reports, keyword research → auto-execute
  Level 2 (HUMAN_CONFIRM) — medium: screenshot, icon, description → AI prepares, human approves
  Level 3 (HUMAN_DECIDE) — high: title, global update → human decides
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.operator.models import (
    ASOOperationPlan,
    ApprovalLevel,
    RiskCategory,
)


# Auto-approved action types (Level 1)
_AUTO_ACTIONS = {
    "ADD_KEYWORD", "KEYWORD_REFRESH", "OPTIMIZE_LISTING",
    "GENERATE_REPORT", "ANALYZE_KEYWORDS", "ANALYZE_COMPETITOR",
}

# High-risk actions requiring human decision (Level 3)
_HUMAN_DECIDE_ACTIONS = {
    "UPDATE_TITLE", "FULL_LISTING_UPDATE", "URGENT_REVIEW",
}


class ApprovalGateway:
    """Three-tier approval decision."""

    # ------------------------------------------------------------------ #
    def determine_level(
        self, plan: ASOOperationPlan
    ) -> ApprovalLevel:
        """Determine approval level based on plan attributes."""
        action = plan.action_type.upper()

        # High risk category → Level 3
        if plan.risk_category == RiskCategory.HIGH:
            return ApprovalLevel.HUMAN_DECIDE

        # Known high-risk actions → Level 3
        if action in _HUMAN_DECIDE_ACTIONS:
            return ApprovalLevel.HUMAN_DECIDE

        # Known auto-approved actions → Level 1
        if action in _AUTO_ACTIONS:
            return ApprovalLevel.AUTO

        # Default → Level 2 (medium risk)
        return ApprovalLevel.HUMAN_CONFIRM

    # ------------------------------------------------------------------ #
    def can_auto_execute(self, plan: ASOOperationPlan) -> bool:
        """Check if plan can be fully automated."""
        return self.determine_level(plan) == ApprovalLevel.AUTO

    # ------------------------------------------------------------------ #
    def needs_human_approval(self, plan: ASOOperationPlan) -> bool:
        return self.determine_level(plan) in (
            ApprovalLevel.HUMAN_CONFIRM, ApprovalLevel.HUMAN_DECIDE
        )

    # ------------------------------------------------------------------ #
    def needs_human_decision(self, plan: ASOOperationPlan) -> bool:
        return self.determine_level(plan) == ApprovalLevel.HUMAN_DECIDE

    # ------------------------------------------------------------------ #
    def apply(self, plan: ASOOperationPlan) -> ASOOperationPlan:
        """Apply approval policy to a plan."""
        level = self.determine_level(plan)
        plan.approval_level = level
        return plan


__all__ = ["ApprovalGateway"]
