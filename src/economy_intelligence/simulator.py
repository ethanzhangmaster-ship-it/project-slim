"""
E16.2 — Economy Simulator: *what happens if we change the economy?*

Mirror of the E16.1 Revenue Simulator, but for in-game economy levers.
Deterministic elasticity models per ``EconomyAction`` predict:

* churn change        (player friction / engagement)
* purchase change     (IAP demand)
* revenue change      (short-term money)
* LTV change          (long-term money = revenue + retention compounding)

The simulator can *reject* an action: spec example — "increase coin output
+20%" reduces friction (churn -8%) but kills purchase motivation
(purchases -15%) and drags long-term LTV down -> ``recommended=False``.

``experience_stats`` (from the shared JSONL experience store) calibrates
confidence exactly like E16.1: winning history raises it, losing history
lowers it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from .models import EconomyAction, PlayerEconomySnapshot

# Per-action elasticities: effect % per 1% of magnitude.
# Positive magnitude = "more of the lever" (higher price, more coins, ...).
_ELASTICITY: Dict[EconomyAction, Dict[str, float]] = {
    # more free resources -> less friction, less reason to pay
    EconomyAction.MODIFY_RESOURCE_RATE: {
        "churn": -0.40,      # +20% coins -> churn -8%
        "purchase": -0.75,   # +20% coins -> purchases -15%
    },
    # richer level rewards: milder version of resource rate
    EconomyAction.MODIFY_REWARD: {
        "churn": -0.25,
        "purchase": -0.45,
    },
    # price increase -> fewer purchases (per-1% effects; large moves should
    # use PriceStrategyAgent's constant-elasticity model)
    EconomyAction.MODIFY_PRICE: {
        "churn": 0.05,
        "purchase": -1.50,
    },
    # a new well-targeted offer adds demand with negligible friction
    EconomyAction.CREATE_OFFER: {
        "churn": 0.0,
        "purchase": 0.60,
    },
    # re-ordering the shop nudges demand slightly
    EconomyAction.MODIFY_SHOP_ORDER: {
        "churn": 0.0,
        "purchase": 0.25,
    },
    # removing a dead offer frees exposure for sellers
    EconomyAction.REMOVE_BAD_OFFER: {
        "churn": 0.0,
        "purchase": 0.15,
    },
}

# How strongly churn compounds into LTV (retention leverage).
_LTV_CHURN_WEIGHT = 1.2


@dataclass
class EconomySimulationResult:
    """Predicted outcome of one economy action at a given magnitude."""

    action: EconomyAction
    game_id: str
    magnitude_pct: float  # size of the lever move, in % (e.g. +20.0)
    churn_change_pct: float = 0.0
    purchase_change_pct: float = 0.0
    revenue_change_pct: float = 0.0
    ltv_change_pct: float = 0.0
    confidence: float = 0.0
    recommended: bool = True
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "game_id": self.game_id,
            "magnitude_pct": round(self.magnitude_pct, 2),
            "churn_change_pct": round(self.churn_change_pct, 2),
            "purchase_change_pct": round(self.purchase_change_pct, 2),
            "revenue_change_pct": round(self.revenue_change_pct, 2),
            "ltv_change_pct": round(self.ltv_change_pct, 2),
            "confidence": round(self.confidence, 4),
            "recommended": self.recommended,
            "reason": self.reason,
        }


@runtime_checkable
class EconomySimulationProvider(Protocol):
    """Seam so the agent can swap in richer simulators later."""

    def simulate(
        self,
        action: EconomyAction,
        snapshot: PlayerEconomySnapshot,
        magnitude_pct: float = 10.0,
        experience_stats: Optional[Dict[str, Any]] = None,
    ) -> EconomySimulationResult:
        ...


class EconomySimulator:
    """Deterministic elasticity-based economy simulator."""

    def simulate(
        self,
        action: EconomyAction,
        snapshot: PlayerEconomySnapshot,
        magnitude_pct: float = 10.0,
        experience_stats: Optional[Dict[str, Any]] = None,
    ) -> EconomySimulationResult:
        el = _ELASTICITY.get(action, {"churn": 0.0, "purchase": 0.0})
        churn = el["churn"] * magnitude_pct
        purchase = el["purchase"] * magnitude_pct

        # Short-term revenue moves with purchases; a price change also moves
        # unit revenue directly.
        revenue = purchase
        if action == EconomyAction.MODIFY_PRICE:
            revenue = magnitude_pct + purchase  # price effect + demand effect

        # LTV = short-term revenue + compounded retention effect
        # (lower churn helps LTV, higher churn hurts it).
        ltv = revenue - _LTV_CHURN_WEIGHT * churn

        recommended = ltv > 0.0
        if recommended:
            reason = (
                f"projected LTV {ltv:+.1f}% "
                f"(revenue {revenue:+.1f}%, churn {churn:+.1f}%) -> accept"
            )
        else:
            reason = (
                f"projected LTV {ltv:+.1f}% is negative "
                f"(revenue {revenue:+.1f}%, churn {churn:+.1f}%, purchases "
                f"{purchase:+.1f}%) -> reject execution"
            )

        confidence = self._calibrate(0.7, experience_stats)
        return EconomySimulationResult(
            action=action,
            game_id=snapshot.game_id,
            magnitude_pct=magnitude_pct,
            churn_change_pct=churn,
            purchase_change_pct=purchase,
            revenue_change_pct=revenue,
            ltv_change_pct=ltv,
            confidence=confidence,
            recommended=recommended,
            reason=reason,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _calibrate(
        base: float, experience_stats: Optional[Dict[str, Any]]
    ) -> float:
        """Same calibration idea as E16.1: history moves confidence."""
        if not experience_stats:
            return base
        n = int(experience_stats.get("n", 0))
        if n <= 0:
            return base
        success_rate = float(experience_stats.get("success_rate", 0.0))
        # up to +0.2 for a strong track record, down to -0.2 for a bad one
        adjustment = (success_rate - 0.5) * 0.4 * min(1.0, n / 5.0)
        return max(0.1, min(0.95, base + adjustment))


__all__ = [
    "EconomySimulationResult",
    "EconomySimulationProvider",
    "EconomySimulator",
]
