"""
E16.1.1 — Revenue Simulator (the "what-if" in the loop)

Given a ``GrowthAction`` and the current ``RevenueSnapshot``, predicts the
*outcome* of executing that action: expected spend %, expected revenue %,
expected ROAS, and a prediction confidence.

The default model is a **deterministic, diminishing-returns elasticity** model
(UA budget change -> smaller revenue change). It is intentionally simple,
auditable, and calibration-friendly: historical ``RevenueExperience`` stats
tighten / align the prediction confidence. The ``SimulationProvider`` protocol
is the seam where the real E12 Prediction Layer / E13 Simulation Provider can
be plugged in without touching the agent.

Example
-------
    increase Meta Facebook budget 20%
        Spend          : +20%
        Expected Rev   : +15%   (elasticity 0.75)
        Expected ROAS  : 1.32
        Confidence     : 0.74
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from .models import RevenueAction, RevenueSnapshot


@dataclass
class SimulationResult:
    action: str
    magnitude_pct: float
    expected_spend_pct: float
    expected_revenue_pct: float
    expected_roas: float
    confidence: float
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "magnitude_pct": round(self.magnitude_pct, 4),
            "expected_spend_pct": round(self.expected_spend_pct, 4),
            "expected_revenue_pct": round(self.expected_revenue_pct, 4),
            "expected_roas": round(self.expected_roas, 4),
            "confidence": round(self.confidence, 4),
            "note": self.note,
        }


@runtime_checkable
class SimulationProvider(Protocol):
    """Seam for the real E12 Prediction Layer / E13 Simulation Provider."""

    def simulate(
        self,
        action: Any,
        current: RevenueSnapshot,
        *,
        magnitude_pct: Optional[float] = None,
        experience_stats: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        ...


class RevenueSimulator:
    """Deterministic elasticity-based revenue simulator (default provider)."""

    # revenue responds at 0.75x the UA spend change (diminishing returns)
    UA_REVENUE_ELASTICITY = 0.75
    DEFAULT_BUDGET_STEP = 10.0  # % if no magnitude supplied

    def __init__(self, base_confidence: float = 0.74):
        self.base_confidence = base_confidence

    # ------------------------------------------------------------------ #
    def simulate(
        self,
        action: Any,
        current: RevenueSnapshot,
        *,
        magnitude_pct: Optional[float] = None,
        experience_stats: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        action_value = (
            action.action.value if hasattr(action, "action") else str(action)
        )
        mag = self._magnitude(action, action_value, magnitude_pct)
        spend = current.spend or 0.0
        revenue = current.revenue_total or 0.0
        roas = current.roas or (revenue / spend if spend > 0 else 0.0)

        if action_value in (
            RevenueAction.INCREASE_UA_BUDGET.value,
            RevenueAction.DECREASE_UA_BUDGET.value,
        ):
            expected_spend_pct = mag
            expected_revenue_pct = self.UA_REVENUE_ELASTICITY * mag
            new_spend = spend * (1 + mag / 100.0)
            new_revenue = revenue * (1 + expected_revenue_pct / 100.0)
            expected_roas = (new_revenue / new_spend) if new_spend > 0 else roas
            note = "UA budget elasticity (diminishing returns)"
        elif action_value == RevenueAction.MODIFY_PRICE.value:
            expected_spend_pct = 0.0
            expected_revenue_pct = 0.5 * mag  # ARPU up, conversion down
            new_revenue = revenue * (1 + expected_revenue_pct / 100.0)
            expected_roas = (new_revenue / spend) if spend > 0 else roas
            note = "price elasticity (ARPU up, conversion down)"
        elif action_value == RevenueAction.CREATE_OFFER.value:
            offer_lift = mag or 8.0
            expected_spend_pct = 0.0
            expected_revenue_pct = offer_lift
            new_revenue = revenue * (1 + offer_lift / 100.0)
            expected_roas = (new_revenue / spend) if spend > 0 else roas
            note = "new-offer incremental revenue"
        else:
            # ROLLBACK_VERSION / INVESTIGATE_RETENTION / SCALE_FEATURE:
            # qualitative only -- no quantitative lever modeled
            expected_spend_pct = 0.0
            expected_revenue_pct = 0.0
            expected_roas = roas
            note = "no quantitative lever modeled (qualitative only)"

        confidence = self._calibrate(experience_stats)
        return SimulationResult(
            action=action_value,
            magnitude_pct=mag,
            expected_spend_pct=expected_spend_pct,
            expected_revenue_pct=expected_revenue_pct,
            expected_roas=expected_roas,
            confidence=confidence,
            note=note,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _magnitude(
        action: Any, action_value: str, magnitude_pct: Optional[float]
    ) -> float:
        if magnitude_pct is not None:
            return float(magnitude_pct)
        ev = getattr(action, "evidence", None) or {}
        if isinstance(ev, dict) and ev.get("budget_change_pct") is not None:
            return float(ev["budget_change_pct"])
        if action_value == RevenueAction.INCREASE_UA_BUDGET.value:
            return RevenueSimulator.DEFAULT_BUDGET_STEP
        if action_value == RevenueAction.DECREASE_UA_BUDGET.value:
            return -RevenueSimulator.DEFAULT_BUDGET_STEP
        return 0.0

    def _calibrate(self, experience_stats: Optional[Dict[str, Any]]) -> float:
        base = self.base_confidence
        if not experience_stats:
            return round(base, 4)
        n = int(experience_stats.get("n", 0))
        avg_reward = float(experience_stats.get("avg_reward", 0.0))
        boost = min(0.2, 0.04 * n)
        align = 0.03 if (n > 0 and avg_reward > 0) else (-0.05 if n > 0 else 0.0)
        conf = base + boost + align
        return round(min(1.0, max(0.0, conf)), 4)


__all__ = [
    "SimulationResult",
    "SimulationProvider",
    "RevenueSimulator",
]
