"""
E16.6.11 — Update Timing Engine.

Core decision: is now a good time to update the store?

Formula: Update Score = Problem Severity × Market Opportunity × Timing Confidence − Update Risk

Factors:
  * Problem Severity — how badly the store is underperforming (CVR drop, ranking drop)
  * Market Opportunity — potential gain (competitor weakness, seasonal event)
  * Timing Confidence — are signals clear enough?
  * Update Risk — cooldown, experiment running, full listing risk

Plus seasonality calendar awareness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from src.aso_intelligence.update_strategy.models import (
    ASOUpdateSignal,
    UpdateOpportunityScore,
)


_MIN_COOLDOWN_DAYS = 14
_SURGE_RISK_BOOST = 0.3


class UpdateTimingEngine:
    """Evaluate whether now is a good time to update the store."""

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        signal: ASOUpdateSignal,
    ) -> UpdateOpportunityScore:
        """Compute the update opportunity score from signals."""
        severity = self._problem_severity(signal)
        opportunity = self._market_opportunity(signal)
        confidence = self._timing_confidence(signal)
        risk = self._update_risk(signal)

        score = UpdateOpportunityScore(
            problem_severity=severity,
            market_opportunity=opportunity,
            timing_confidence=confidence,
            update_risk=risk,
        )
        score.compute()
        return score

    # ------------------------------------------------------------------ #
    def _problem_severity(self, signal: ASOUpdateSignal) -> float:
        """How severe are the current problems?"""
        severity = 0.0

        # CVR decline (most important)
        if signal.cvr_change < -0.15:
            severity += 0.5
        elif signal.cvr_change < -0.05:
            severity += 0.3
        elif signal.cvr_change < 0:
            severity += 0.1

        # Ranking drop
        if signal.ranking_change < -20:
            severity += 0.3
        elif signal.ranking_change < -5:
            severity += 0.15

        # Install decline
        if signal.organic_install_change < -0.20:
            severity += 0.2
        elif signal.organic_install_change < -0.05:
            severity += 0.1

        # Rating decline
        if signal.rating_change < -0.3:
            severity += 0.15

        return min(1.0, severity)

    # ------------------------------------------------------------------ #
    def _market_opportunity(self, signal: ASOUpdateSignal) -> float:
        """How much potential gain from updating?"""
        opportunity = 0.3  # baseline — there's always room to improve

        # High competitor pressure → need to respond → opportunity
        if signal.competitor_pressure > 0.7:
            opportunity += 0.3
        elif signal.competitor_pressure > 0.4:
            opportunity += 0.15

        # Long time since last update → freshness opportunity
        if signal.days_since_update > 90:
            opportunity += 0.2
        elif signal.days_since_update > 60:
            opportunity += 0.1

        # Positive review sentiment → good time to update
        if signal.review_sentiment > 0.7:
            opportunity += 0.1

        return min(1.0, opportunity)

    # ------------------------------------------------------------------ #
    def _timing_confidence(self, signal: ASOUpdateSignal) -> float:
        """How confident are we in the timing decision?"""
        # More data → higher confidence
        confidence = 0.5  # baseline

        # Clear negative CVR trend → high confidence something is wrong
        if signal.cvr_change < -0.15:
            confidence += 0.2
        if signal.cvr_change < -0.05:
            confidence += 0.1

        # Clear ranking signal
        if abs(signal.ranking_change) > 15:
            confidence += 0.1

        # Having competitor data increases confidence
        if signal.competitor_pressure > 0:
            confidence += 0.1

        # Recent data is more reliable
        if signal.days_since_update > 0:
            confidence += 0.05

        return min(1.0, confidence)

    # ------------------------------------------------------------------ #
    def _update_risk(self, signal: ASOUpdateSignal) -> float:
        """What's the risk of updating now?"""
        risk = 0.0

        # Cooldown
        if signal.days_since_update < _MIN_COOLDOWN_DAYS:
            risk += 0.8  # very high risk — cooldown not met
        elif signal.days_since_update < 30:
            risk += 0.2

        # Experiment running
        if signal.experiment_running:
            risk += 0.4

        # Dramatic but unstable signals → high risk (might be noise)
        if abs(signal.cvr_change) > 0.3:
            risk += 0.1

        return min(1.0, risk)

    # ------------------------------------------------------------------ #
    def get_seasonality_notes(
        self, month: Optional[int] = None
    ) -> List[str]:
        """Get seasonality notes for the current (or specified) month.

        Provides guidance on when to prepare seasonal updates.
        """
        now = datetime.now(timezone.utc)
        m = month if month is not None else now.month

        notes: List[str] = []
        if m == 1:
            notes.append("January: New Year resolution period — test 'new beginning' messaging")
        elif m == 2:
            notes.append("February: Valentine's Day prep — romantic/social themes")
        elif m == 6:
            notes.append("June: Summer vacation prep — outdoor, travel themes")
        elif m == 7:
            notes.append("July: Mid-year ASO review — consider major listing refresh")
        elif m == 8:
            notes.append("August: Halloween preparation — prepare spooky screenshots")
        elif m == 9:
            notes.append("September: Halloween listing prep — update before Oct spike")
            notes.append("Q4 planning — prepare holiday season screenshots")
        elif m == 10:
            notes.append("October: Halloween themed screenshots live — seasonal CVR boost expected")
        elif m == 11:
            notes.append("November: Black Friday / Thanksgiving — sale and bundle themes")
            notes.append("December holiday prep — update screenshots by mid-Nov")
        elif m == 12:
            notes.append("December: Holiday season — festive themes, year-end push")

        return notes

    # ------------------------------------------------------------------ #
    def cooldown_remaining(self, days_since_update: int) -> int:
        """How many more days until the cooldown expires."""
        return max(0, _MIN_COOLDOWN_DAYS - days_since_update)

    def is_cooldown_active(self, days_since_update: int) -> bool:
        return days_since_update < _MIN_COOLDOWN_DAYS


__all__ = ["UpdateTimingEngine"]
