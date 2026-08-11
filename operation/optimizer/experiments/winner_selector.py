"""
E15.2.5+ — WinnerSelector.

Turns an ImpactMeasurement + guardrail state into a KEEP / ROLLBACK
decision — the missing "was the suggestion actually worth it" verdict.

Rules (deterministic):

  guardrail == regression                → ROLLBACK  (never trade users)
  net_impact >= +KEEP_THRESHOLD_PCT      → WINNER / KEEP
  net_impact <= -ROLLBACK_THRESHOLD_PCT  → ROLLBACK
  in between                            → INCONCLUSIVE (keep, low confidence)
  not measurable / window too short      → OBSERVING (no decision yet)

Confidence: scaled by |net_impact| and after-window length, capped 0.95.
Zero MAX writes. No LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from operation.optimizer.experiments.experiment_models import (
    INCONCLUSIVE, ROLLBACK, WINNER,
)
from operation.optimizer.experiments.impact import ImpactMeasurement

OBSERVING = "OBSERVING"      # not enough after-window yet — keep watching


@dataclass
class WinnerDecision:
    exp_id: str
    verdict: str              # WINNER | ROLLBACK | INCONCLUSIVE | OBSERVING
    decision: str             # KEEP | ROLLBACK | ""
    net_impact_pct: Optional[float]
    confidence: float
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exp_id": self.exp_id, "verdict": self.verdict,
            "decision": self.decision, "net_impact_pct": self.net_impact_pct,
            "confidence": round(self.confidence, 2), "note": self.note,
        }


class WinnerSelector:
    KEEP_THRESHOLD_PCT = 2.0        # net impact >= +2% → winner
    ROLLBACK_THRESHOLD_PCT = 2.0    # net impact <= -2% → rollback
    MIN_AFTER_DAYS = 3              # want >= 3 measurable after-days to decide

    def decide(self, m: ImpactMeasurement,
               guardrail: str = "pending") -> WinnerDecision:
        if not m.measurable or m.net_impact_pct is None:
            return WinnerDecision(
                exp_id=m.exp_id, verdict=OBSERVING, decision="",
                net_impact_pct=None, confidence=0.0,
                note=m.note or "impact not measurable yet")

        if m.after_days < self.MIN_AFTER_DAYS:
            return WinnerDecision(
                exp_id=m.exp_id, verdict=OBSERVING, decision="",
                net_impact_pct=m.net_impact_pct, confidence=0.0,
                note=(f"after-window {m.after_days}d < "
                      f"{self.MIN_AFTER_DAYS}d — keep observing"))

        conf = min(0.95,
                   0.5
                   + min(abs(m.net_impact_pct) / 20.0, 0.3)   # effect size
                   + min(m.after_days / 30.0, 0.15))          # window length

        if guardrail == "regression":
            return WinnerDecision(
                exp_id=m.exp_id, verdict=ROLLBACK, decision="ROLLBACK",
                net_impact_pct=m.net_impact_pct, confidence=conf,
                note="ARPDAU guardrail regressed — revenue not worth user cost")

        if m.net_impact_pct >= self.KEEP_THRESHOLD_PCT:
            return WinnerDecision(
                exp_id=m.exp_id, verdict=WINNER, decision="KEEP",
                net_impact_pct=m.net_impact_pct, confidence=conf,
                note=(f"net {m.net_impact_pct:+.1f}%/day revenue vs account "
                      f"drift, guardrail {guardrail} — KEEP"))
        if m.net_impact_pct <= -self.ROLLBACK_THRESHOLD_PCT:
            return WinnerDecision(
                exp_id=m.exp_id, verdict=ROLLBACK, decision="ROLLBACK",
                net_impact_pct=m.net_impact_pct, confidence=conf,
                note=(f"net {m.net_impact_pct:+.1f}%/day — change destroyed "
                      f"value, ROLLBACK in MAX dashboard"))
        return WinnerDecision(
            exp_id=m.exp_id, verdict=INCONCLUSIVE, decision="KEEP",
            net_impact_pct=m.net_impact_pct, confidence=max(conf - 0.2, 0.1),
            note=(f"net {m.net_impact_pct:+.1f}%/day within noise band "
                  f"(±{self.KEEP_THRESHOLD_PCT}%) — keep, low confidence"))
