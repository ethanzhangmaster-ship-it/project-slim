"""
E15.2.6 §8 — Safety Gate (pre-execution guardrails).

Every proposed change must pass before a ChangePackage is emitted for apply:

  * Revenue Protection   : expected revenue loss > 5%  -> REJECT
  * Retention Protection : predicted retention drop > 3% -> REJECT
  * Confidence           : confidence < 0.8            -> APPROVAL (human)
  * Frequency            : ad-frequency levers are stricter (none wired yet;
                           flagged for Agent 2 / Unity SDK).

Tiers:
  AUTO     — safe, confident, auto-eligible for the apply checklist
  APPROVAL — allowed but a human must confirm (low confidence / borderline)
  REJECT   — would breach a hard protection rule
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from operation.revenue_optimizer.models import (
    PredictionResult, RevenueOpportunity,
)

REVENUE_LOSS_LIMIT_PCT = -5.0
RETENTION_DROP_LIMIT_PCT = -3.0
CONFIDENCE_MIN = 0.8


class ApprovalGate:
    REVENUE_LOSS_LIMIT_PCT = -5.0
    RETENTION_DROP_LIMIT_PCT = -3.0
    CONFIDENCE_MIN = 0.8

    def check(self, opp: RevenueOpportunity,
              prediction: Optional[PredictionResult] = None,
              retention_delta_pct: Optional[float] = None
              ) -> Dict[str, Any]:
        reasons: List[str] = []

        # Revenue Protection
        if prediction is not None and prediction.lift_percent <= REVENUE_LOSS_LIMIT_PCT:
            reasons.append(
                f"expected revenue loss {prediction.lift_percent:.1f}% "
                f"exceeds {REVENUE_LOSS_LIMIT_PCT}% limit")
            return {"tier": "REJECT", "reasons": reasons}

        # Retention Protection
        if (retention_delta_pct is not None
                and retention_delta_pct <= RETENTION_DROP_LIMIT_PCT):
            reasons.append(
                f"predicted retention drop {retention_delta_pct:.1f}% "
                f"exceeds {RETENTION_DROP_LIMIT_PCT}% limit")
            return {"tier": "REJECT", "reasons": reasons}

        # Confidence
        conf = (prediction.confidence if prediction is not None
                else opp.confidence)
        if conf < CONFIDENCE_MIN:
            reasons.append(
                f"confidence {conf:.2f} < {CONFIDENCE_MIN} requires human approval")
            return {"tier": "APPROVAL", "reasons": reasons}

        # Frequency strictness note (no in-game frequency lever wired yet)
        if opp.action in ("diversify",):
            reasons.append("risk-hedge action — still allowed, monitor guardrail")
            return {"tier": "APPROVAL", "reasons": reasons}

        reasons.append("passed all guardrails")
        return {"tier": "AUTO", "reasons": reasons}
