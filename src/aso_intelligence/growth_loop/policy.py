"""
E16.6.5 — ASO Policy Gate.

Safety policies that protect games from excessive or harmful experiments.

Limits:
  1. Max 3 concurrent experiments per game
  2. High-risk actions (UPDATE_TITLE) → HUMAN_QUEUE
  3. Low confidence → RECORD_ONLY (no side effects)

Multi-game isolation is enforced by scoping all counters to ``game_id``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from src.aso_intelligence.growth_loop.models import (
    ASOActionPlan,
    ApprovalStatus,
)

# High-risk actions that always require human approval
_HIGH_RISK: Set[str] = {"UPDATE_TITLE"}

# Max concurrent experiments per game
_MAX_CONCURRENT = 3

# Confidence threshold below which action is RECORD_ONLY
_MIN_CONFIDENCE_AUTO = 0.3


class ASOPolicyGate:
    """Enforce safety policies on action plans before execution.

    ``active_experiments`` is a dict of ``game_id → count`` that callers
    must keep up-to-date (the gate does not query the store itself).
    """

    def __init__(self, max_concurrent: int = _MAX_CONCURRENT):
        self.max_concurrent = max_concurrent

    # ------------------------------------------------------------------ #
    def check_high_risk(self, plan: ASOActionPlan) -> bool:
        """True if the plan involves a high-risk action."""
        return plan.action.upper() in _HIGH_RISK

    def check_low_confidence(self, plan: ASOActionPlan) -> bool:
        """True if plan confidence is below the auto-approve threshold."""
        return plan.expected_confidence < _MIN_CONFIDENCE_AUTO

    def check_concurrent_limit(
        self,
        plan: ASOActionPlan,
        active_counts: Dict[str, int],
    ) -> bool:
        """True if the game already has too many concurrent experiments."""
        count = active_counts.get(plan.game_id, 0)
        return count >= self.max_concurrent

    # ------------------------------------------------------------------ #
    def apply(
        self,
        plan: ASOActionPlan,
        active_counts: Dict[str, int],
    ) -> ASOActionPlan:
        """Apply all policy gates and return the (possibly modified) plan.

        The plan's ``approval_status`` is updated based on:
        * High-risk → HUMAN_QUEUE (overrides everything)
        * Low confidence → RECORD_ONLY
        * Concurrent limit exceeded → RECORD_ONLY (defer)
        * Otherwise → keep original status
        """
        # High-risk overrides everything
        if self.check_high_risk(plan):
            plan.approval_status = ApprovalStatus.HUMAN_QUEUE
            plan.high_risk = True
            return plan

        # Low confidence → just record
        if self.check_low_confidence(plan):
            plan.approval_status = ApprovalStatus.RECORD_ONLY
            return plan

        # Concurrent limit → defer
        if self.check_concurrent_limit(plan, active_counts):
            plan.approval_status = ApprovalStatus.RECORD_ONLY
            return plan

        # All gates passed — keep original status
        return plan

    def apply_all(
        self,
        plans: List[ASOActionPlan],
        active_counts: Dict[str, int],
    ) -> List[ASOActionPlan]:
        """Apply policies to all plans in batch."""
        return [self.apply(p, active_counts) for p in plans]


__all__ = ["ASOPolicyGate"]
