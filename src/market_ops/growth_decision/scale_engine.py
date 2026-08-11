"""E9.9.5 Module 3: Scale Engine.

Converts WINNER GrowthDecisions into automated budget scaling plans.

Core principle: Scale ≠ increase budget.
Scale = increase budget + maintain efficiency.

Scale Ladder: 100 → 200 → 500 → 1000 → 2000 → 5000
ROAS Decay Guard: pause if current_roas < original_roas * 0.7
State Machine: ACTIVE → PAUSED → STOPPED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from market_ops.growth_decision.schemas import (
    GrowthDecision, ScalePlan, ScaleStatus, GrowthAction,
)

# ── Scale Ladder ───────────────────────────────────────────

SCALE_LADDER: list[float] = [100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0]
MAX_SCALE_LEVEL = len(SCALE_LADDER) - 1  # 5

# ── ROAS Decay Guard ───────────────────────────────────────

ROAS_DECAY_THRESHOLD = 0.7  # Stop if ROAS < original * 0.7


class ScaleEngine:
    """Generates automated budget scaling plans for WINNER experiments.

    Usage:
        engine = ScaleEngine()
        plans = engine.generate_scale_plans(winner_decisions)
    """

    def __init__(self) -> None:
        self._original_roas: dict[str, float] = {}  # creative_id → original ROAS

    def generate_scale_plans(
        self,
        decisions: list[GrowthDecision],
        base_budget: float = 100.0,
    ) -> list[ScalePlan]:
        """Generate ScalePlan for each SCALE decision.

        Only processes decisions with action=SCALE.
        Others are skipped (no scale plan for KILL/WATCH/RETEST).

        Args:
            decisions: GrowthDecision list from WinnerDetector
            base_budget: Starting budget for scale ladder (default $100)

        Returns:
            List of ScalePlan objects (one per SCALE decision)
        """
        plans = []

        for d in decisions:
            if d.decision != GrowthAction.SCALE.value:
                continue

            plan = self._generate_single_plan(d, base_budget)
            plans.append(plan)

        return plans

    def generate_from_winner(
        self,
        decision: GrowthDecision,
        current_budget: float | None = None,
        current_roas: float | None = None,
        original_roas: float | None = None,
    ) -> ScalePlan:
        """Generate a scale plan for a single WINNER decision.

        Args:
            decision: GrowthDecision with action=SCALE
            current_budget: Current daily budget (default: ladder level 0)
            current_roas: Current ROAS for decay check
            original_roas: Original ROAS before scaling (for decay guard)

        Returns:
            ScalePlan with next budget level
        """
        return self._generate_single_plan(
            decision,
            base_budget=current_budget or SCALE_LADDER[0],
            current_roas=current_roas,
            original_roas=original_roas,
        )

    # ── Plan Generation ────────────────────────────────────

    def _generate_single_plan(
        self,
        decision: GrowthDecision,
        base_budget: float = 100.0,
        current_roas: float | None = None,
        original_roas: float | None = None,
    ) -> ScalePlan:
        """Generate a single scale plan."""
        # Determine current level from budget
        current_level = self._find_level(base_budget)

        # Calculate next level
        next_level = min(current_level + 1, MAX_SCALE_LEVEL)
        target_budget = SCALE_LADDER[next_level]

        # Check ROAS decay guard
        status = ScaleStatus.ACTIVE.value
        if original_roas is not None and current_roas is not None:
            if not self._check_roas_decay(current_roas, original_roas):
                status = ScaleStatus.PAUSED.value

        return ScalePlan(
            creative_id=decision.creative_id,
            current_budget=base_budget,
            target_budget=target_budget,
            scale_step=next_level,
            max_scale_level=MAX_SCALE_LEVEL,
            roas_guard_threshold=ROAS_DECAY_THRESHOLD,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _find_level(self, budget: float) -> int:
        """Find the scale ladder level for a given budget.

        Returns:
            Level index (0-5), or max level if budget exceeds all steps.
        """
        for i, level_budget in enumerate(SCALE_LADDER):
            if budget < level_budget:
                return max(0, i - 1)
        return MAX_SCALE_LEVEL

    # ── ROAS Decay Guard ───────────────────────────────────

    def check_decay(
        self,
        current_roas: float,
        original_roas: float,
        plan: ScalePlan,
    ) -> ScalePlan:
        """Check ROAS decay and update plan status.

        If current_roas < original_roas * threshold:
          PAUSED — stop scaling, observe
          If already PAUSED and still decaying → STOPPED

        Args:
            current_roas: Current ROAS at this scale level
            original_roas: ROAS at original budget level
            plan: Current ScalePlan to update

        Returns:
            Updated ScalePlan
        """
        if self._check_roas_decay(current_roas, original_roas):
            # ROAS is healthy
            if plan.status == ScaleStatus.PAUSED.value:
                plan.status = ScaleStatus.ACTIVE.value
            return plan

        # ROAS decay detected
        if plan.status == ScaleStatus.PAUSED.value:
            # Already paused → escalate to STOPPED
            plan.status = ScaleStatus.STOPPED.value
        else:
            plan.status = ScaleStatus.PAUSED.value

        return plan

    def _check_roas_decay(
        self, current_roas: float, original_roas: float
    ) -> bool:
        """Check if ROAS is within acceptable range.

        Returns True if ROAS is healthy (can continue scaling).
        Returns False if ROAS decay is detected (should pause).
        """
        if original_roas <= 0:
            return False
        return current_roas >= original_roas * ROAS_DECAY_THRESHOLD

    # ── Scale State Machine ────────────────────────────────

    def advance_level(
        self, plan: ScalePlan, roas_ok: bool = True
    ) -> ScalePlan:
        """Advance to next scale level if ROAS is healthy.

        Args:
            plan: Current ScalePlan
            roas_ok: Whether ROAS is above decay threshold

        Returns:
            Updated ScalePlan
        """
        if plan.status == ScaleStatus.STOPPED.value:
            return plan

        if not roas_ok:
            return self._pause_scale(plan)

        # Advance to next level
        next_level = plan.scale_step + 1
        if next_level > plan.max_scale_level:
            plan.status = ScaleStatus.STOPPED.value
            return plan

        plan.scale_step = next_level
        plan.current_budget = plan.target_budget
        plan.target_budget = SCALE_LADDER[next_level]
        plan.status = ScaleStatus.ACTIVE.value

        return plan

    def _pause_scale(self, plan: ScalePlan) -> ScalePlan:
        """Pause scaling due to ROAS decay."""
        if plan.status == ScaleStatus.PAUSED.value:
            plan.status = ScaleStatus.STOPPED.value
        else:
            plan.status = ScaleStatus.PAUSED.value
        return plan

    def stop_scale(self, plan: ScalePlan) -> ScalePlan:
        """Force stop scaling."""
        plan.status = ScaleStatus.STOPPED.value
        return plan

    # ── Summary ────────────────────────────────────────────

    def get_scale_summary(
        self, plans: list[ScalePlan]
    ) -> dict[str, Any]:
        """Get summary of scale plans."""
        active = sum(1 for p in plans if p.status == ScaleStatus.ACTIVE.value)
        paused = sum(1 for p in plans if p.status == ScaleStatus.PAUSED.value)
        stopped = sum(1 for p in plans if p.status == ScaleStatus.STOPPED.value)

        total_budget_increase = sum(
            p.target_budget - p.current_budget for p in plans
        )

        return {
            "total_plans": len(plans),
            "by_status": {
                "ACTIVE": active,
                "PAUSED": paused,
                "STOPPED": stopped,
            },
            "avg_current_budget": round(
                sum(p.current_budget for p in plans) / max(1, len(plans)), 2
            ),
            "avg_target_budget": round(
                sum(p.target_budget for p in plans) / max(1, len(plans)), 2
            ),
            "total_budget_increase": round(total_budget_increase, 2),
            "scale_ladder": SCALE_LADDER,
            "roas_decay_threshold": ROAS_DECAY_THRESHOLD,
        }