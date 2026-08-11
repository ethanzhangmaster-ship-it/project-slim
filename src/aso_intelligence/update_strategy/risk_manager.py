"""
E16.6.11 — Update Risk Manager.

Enforces safety policies for store updates:
  * Cooldown: minimum 14 days between updates
  * Experiment gate: don't update while experiment is running
  * Full listing risk: requires human approval (Google Play restrictions)
  * Risk scoring per update type + market
"""

from __future__ import annotations

from typing import Optional

from src.aso_intelligence.update_strategy.models import (
    ASOUpdateSignal,
    UpdatePlan,
    UpdateType,
    RiskLevel,
)


_MIN_COOLDOWN = 14
_HIGH_RISK_TYPES = {UpdateType.FULL_LISTING}


class RiskManager:
    """Assess and mitigate update risks."""

    # ------------------------------------------------------------------ #
    def assess(self, plan: UpdatePlan, signal: ASOUpdateSignal) -> RiskLevel:
        """Determine final risk level for a plan, considering all gates."""
        # Block: cooldown not met
        if signal.days_since_update < _MIN_COOLDOWN:
            return RiskLevel.BLOCKED

        # Block: experiment running
        if signal.experiment_running:
            return RiskLevel.BLOCKED

        # High: full listing update
        if plan.update_type in _HIGH_RISK_TYPES:
            return RiskLevel.HIGH

        # Medium: recent update (within 30 days) or high competitor pressure
        if signal.days_since_update < 30:
            return RiskLevel.MEDIUM
        if signal.competitor_pressure > 0.8:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    # ------------------------------------------------------------------ #
    def check_cooldown(self, days_since_update: int) -> bool:
        """True if cooldown period has elapsed."""
        return days_since_update >= _MIN_COOLDOWN

    def cooldown_remaining(self, days_since_update: int) -> int:
        return max(0, _MIN_COOLDOWN - days_since_update)

    # ------------------------------------------------------------------ #
    def requires_human_approval(self, plan: UpdatePlan) -> bool:
        """Check if plan requires human approval.

        FULL_LISTING always requires human.
        HIGH risk requires human.
        """
        if plan.update_type in _HIGH_RISK_TYPES:
            return True
        if plan.risk_level == RiskLevel.HIGH:
            return True
        return False

    # ------------------------------------------------------------------ #
    def apply_gates(
        self,
        plan: UpdatePlan,
        signal: ASOUpdateSignal,
    ) -> UpdatePlan:
        """Apply all risk gates and return the (possibly modified) plan.

        BLOCKED plans get their type changed to HOLD and reason updated.
        """
        risk = self.assess(plan, signal)

        if risk == RiskLevel.BLOCKED:
            reasons = []
            if signal.days_since_update < _MIN_COOLDOWN:
                reasons.append(
                    f"Cooldown active ({signal.days_since_update}/"
                    f"{_MIN_COOLDOWN} days)"
                )
            if signal.experiment_running:
                reasons.append("Experiment currently running")
            plan.update_type = UpdateType.HOLD
            plan.risk_level = RiskLevel.BLOCKED
            plan.reason = "BLOCKED: " + "; ".join(reasons)
            return plan

        plan.risk_level = risk
        plan.requires_human_approval = self.requires_human_approval(plan)
        return plan


__all__ = ["RiskManager"]
