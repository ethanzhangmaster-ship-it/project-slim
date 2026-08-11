"""
E16.6.11 — Update Planner.

Converts signals + timing score into a concrete UpdatePlan.
Determines WHAT type of update to perform based on the dominant problem.

Rules:
  * CVR drop + screenshot weakness → SCREENSHOT update
  * Competitor icon success → ICON experiment
  * Keyword opportunity + low coverage → KEYWORD refresh
  * Multiple strong signals → FULL_LISTING (only with high confidence + low risk)
  * Weak/no signals → HOLD
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from src.aso_intelligence.update_strategy.models import (
    ASOUpdateSignal,
    UpdateOpportunityScore,
    UpdatePlan,
    UpdateType,
    RiskLevel,
)


class UpdatePlanner:
    """Plan the type and scope of store update."""

    # ------------------------------------------------------------------ #
    def plan(
        self,
        game_id: str,
        market: str,
        signal: ASOUpdateSignal,
        opportunity_score: UpdateOpportunityScore,
    ) -> UpdatePlan:
        """Generate an UpdatePlan from signals + timing score."""
        rec = opportunity_score.recommendation

        # HOLD → truly no update
        if rec == "HOLD":
            return self._hold(game_id, market, "Update risk exceeds potential benefit")

        # Determine update type (even for MONITOR, there may be a specific fix)
        update_type = self._determine_type(signal)

        # MONITOR → still plan but with lower confidence
        if rec == "MONITOR":
            if update_type == UpdateType.HOLD:
                return self._hold(
                    game_id, market, "No urgent update needed — monitoring"
                )
            # There's a specific issue even in monitoring mode
            confidence = opportunity_score.timing_confidence * 0.6

        # Full plan mode
        else:  # IMMEDIATE_UPDATE or PLAN_UPDATE
            confidence = opportunity_score.timing_confidence
        risk_level = self._risk_level(signal, update_type)

        # Expected uplift (deterministic estimates)
        cvr_uplift = self._estimate_cvr_uplift(update_type, signal)
        revenue_uplift = self._estimate_revenue_uplift(cvr_uplift, signal)

        reason = self._build_reason(update_type, signal)

        requires_human = update_type == UpdateType.FULL_LISTING

        return UpdatePlan(
            game_id=game_id,
            market=market,
            update_type=update_type,
            score=opportunity_score.score,
            confidence=confidence,
            risk_level=risk_level,
            reason=reason,
            expected_cvr_uplift=cvr_uplift,
            expected_revenue_uplift=revenue_uplift,
            requires_human_approval=requires_human,
        )

    # ------------------------------------------------------------------ #
    def _determine_type(self, signal: ASOUpdateSignal) -> UpdateType:
        """Determine update type based on dominant signal."""
        # Multiple strong signals → FULL_LISTING
        strong_signals = 0
        if signal.cvr_change < -0.15:
            strong_signals += 1
        if signal.competitor_pressure > 0.7:
            strong_signals += 1
        if signal.ranking_change < -20:
            strong_signals += 1
        if signal.days_since_update > 90:
            strong_signals += 1

        if strong_signals >= 3:
            return UpdateType.FULL_LISTING

        # Screenshot weakness (CVR drop without other specific signals)
        if signal.cvr_change < -0.05:
            return UpdateType.SCREENSHOT

        # Ranking drop + competitor pressure → Icon opportunity
        if signal.ranking_change < -10 and signal.competitor_pressure > 0.5:
            return UpdateType.ICON

        # High competitor pressure → defensive screenshot update
        if signal.competitor_pressure > 0.6:
            return UpdateType.SCREENSHOT

        # Long time since update → keyword refresh (lowest risk)
        if signal.days_since_update > 60:
            return UpdateType.KEYWORD

        return UpdateType.HOLD

    # ------------------------------------------------------------------ #
    def _risk_level(
        self, signal: ASOUpdateSignal, update_type: UpdateType
    ) -> RiskLevel:
        if update_type == UpdateType.FULL_LISTING:
            return RiskLevel.HIGH
        if signal.experiment_running:
            return RiskLevel.MEDIUM
        if signal.days_since_update < 30:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # ------------------------------------------------------------------ #
    def _estimate_cvr_uplift(
        self, update_type: UpdateType, signal: ASOUpdateSignal
    ) -> float:
        estimates = {
            UpdateType.SCREENSHOT: 0.08,
            UpdateType.ICON: 0.05,
            UpdateType.KEYWORD: 0.04,
            UpdateType.FULL_LISTING: 0.15,
            UpdateType.HOLD: 0.0,
        }
        base = estimates.get(update_type, 0.0)
        # Boost if there's clear room for improvement
        if signal.cvr_change < -0.15:
            base *= 1.5
        return round(base, 4)

    def _estimate_revenue_uplift(
        self, cvr_uplift: float, signal: ASOUpdateSignal
    ) -> float:
        return round(cvr_uplift * 0.8, 4)  # revenue uplift ≈ 80% of CVR uplift

    # ------------------------------------------------------------------ #
    def _build_reason(
        self, update_type: UpdateType, signal: ASOUpdateSignal
    ) -> str:
        reasons = {
            UpdateType.SCREENSHOT: (
                f"CVR {signal.cvr_change:+.0%} indicates listing fatigue "
                f"— screenshot refresh recommended"
            ),
            UpdateType.ICON: (
                f"Ranking {signal.ranking_change:+.0f} with competitor "
                f"pressure {signal.competitor_pressure:.0%} — icon test warranted"
            ),
            UpdateType.KEYWORD: (
                f"{signal.days_since_update} days since last update "
                f"— keyword refresh opportunity"
            ),
            UpdateType.FULL_LISTING: (
                f"Multiple strong signals (CVR {signal.cvr_change:+.0%}, "
                f"rank {signal.ranking_change:+.0f}, "
                f"competitor {signal.competitor_pressure:.0%}) "
                f"— comprehensive listing update"
            ),
            UpdateType.HOLD: "No compelling update signal detected",
        }
        return reasons.get(update_type, "Update recommended based on signal analysis")

    # ------------------------------------------------------------------ #
    def _hold(
        self, game_id: str, market: str, reason: str
    ) -> UpdatePlan:
        return UpdatePlan(
            game_id=game_id,
            market=market,
            update_type=UpdateType.HOLD,
            reason=reason,
            risk_level=RiskLevel.LOW,
        )


__all__ = ["UpdatePlanner"]
