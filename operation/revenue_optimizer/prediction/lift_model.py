"""
E15.2.6 §5 — Revenue Lift Model.

Predicts revenue before/after a proposed change. The opportunity's
`expected_lift` already carries the conservative upside estimated by the intel
rules (zombie reallocation, hidden-winner capture gap, bid-floor recovery).
This model turns that into an absolute revenue number and applies a
sample-size dampener so tiny-impression segments cannot be over-trusted.

Deterministic, no numpy, no LLM.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from operation.revenue_optimizer.models import (
    PredictionResult, RevenueOpportunity,
)


def _ctx_get(ctx: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(ctx.get(key, default) or default)
    except (TypeError, ValueError):
        return default


class LiftModel:
    # below this many impressions on the target segment, dampen the lift
    MIN_IMP_DAMP = 200
    # floor multiplier applied at zero impressions (still some prior belief)
    DAMP_FLOOR = 0.4

    def dampen(self, opp: RevenueOpportunity) -> float:
        """Return a multiplier in [DAMP_FLOOR, 1.0] scaling the opportunity's
        raw expected_lift down when the target segment has few impressions."""
        imps = float((opp.metrics or {}).get("impressions", 0) or 0)
        if imps >= self.MIN_IMP_DAMP:
            return 1.0
        if imps <= 0:
            return self.DAMP_FLOOR
        frac = imps / self.MIN_IMP_DAMP
        return round(self.DAMP_FLOOR + (1.0 - self.DAMP_FLOOR) * frac, 4)

    def predict(self, opp: RevenueOpportunity,
                 ctx: Dict[str, Any]) -> PredictionResult:
        before = _ctx_get(ctx, "total_revenue")
        damp = self.dampen(opp)
        eff_lift = opp.expected_lift * damp
        after = before * (1.0 + eff_lift)
        note = ""
        if damp < 1.0:
            note = (f"lift dampened x{damp} (target segment impressions "
                    f"< {self.MIN_IMP_DAMP})")
        return PredictionResult(
            change=f"{opp.action} {opp.target}",
            before_revenue=before,
            after_revenue=after,
            lift_percent=round(eff_lift * 100.0, 2),
            confidence=opp.confidence,
            risk=opp.risk,
            note=note,
        )
