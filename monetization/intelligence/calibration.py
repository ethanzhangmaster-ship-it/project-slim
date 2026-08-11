"""
E13.4.3 — Module 4: Simulator Calibration
==========================================

The E13.2.9 Simulator is a transparent linear-elasticity heuristic. It will be
systematically optimistic or pessimistic until it has learned from reality.
This module *closes that loop*: it watches every closed-loop DecisionRecord,
compares the Simulator's prediction against the measured ActualOutcome, and
learns a multiplicative `correction` factor per (strategy, parameter) bucket.

    correction(key) = sum(actual) / sum(predicted)      # clipped to [0.3, 2.0]
    calibrated_delta = predicted_delta * correction

If the Simulator over-predicts revenue by 25% (actual = 0.75 * predicted),
the factor converges to ~0.75 and `apply()` pulls future predictions back
toward reality. With no data the factor is 1.0 (no change).

Lean + safe:
  * Reads only the Decision Memory (E13.4.1) — never calls MAX / any API.
  * Pure-Python; correction factors can be persisted to a JSON file and
    reloaded so the Simulator improves across runs.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from monetization.learning.decision_store import DecisionStore
from monetization.intelligence.models import CalibrationFactor


def param_key(mutation: dict) -> str:
    """A coarse parameter bucket for a strategy mutation (for grouping)."""
    m = mutation or {}
    at = m.get("action_type") or ""
    params = m.get("params", {}) or {}
    if at == "review_bidding" and m.get("increase_bid_floor"):
        mag = params.get("bid_floor_pct")
    elif at in ("change_waterfall", "review_bidding", "adjust_ad_frequency"):
        mag = params.get("magnitude_pct")
    else:
        mag = None
    if mag is None:
        return at or "unknown"
    return f"{at}:{round(float(mag))}"


class SimulatorCalibrator:
    """Learns per-(strategy, parameter) correction factors from memory."""

    def __init__(self):
        # key -> [sum_pred, sum_actual, n, strategy_type, action_type, parameter]
        self._stats: Dict[str, list] = defaultdict(lambda: [0.0, 0.0, 0, "", "", ""])

    # ------------------------------------------------------------------ #
    def record(self, strategy_type: str, action_type: str, parameter: str,
               predicted_delta: float, actual_delta: float) -> None:
        key = f"{strategy_type}|{parameter}"
        s = self._stats[key]
        s[0] += predicted_delta
        s[1] += actual_delta
        s[2] += 1
        s[3] = strategy_type
        s[4] = action_type
        s[5] = parameter

    def learn_from_store(self, store: DecisionStore) -> "SimulatorCalibrator":
        """Harvest every closed-loop record's prediction-vs-actual contrast."""
        for r in store.closed():
            pred = r.prediction_revenue_delta
            actual = r.actual.revenue_delta_pct if r.actual else 0.0
            if pred == 0.0 and actual == 0.0:
                continue
            st = r.strategy_type
            at = (r.strategy_mutation or {}).get("action_type") or ""
            pkey = param_key(r.strategy_mutation)
            self.record(st, at, pkey, pred, actual)
        return self

    # ------------------------------------------------------------------ #
    @staticmethod
    def _clip(c: float) -> float:
        return max(0.3, min(2.0, c))

    def factor(self, strategy_type: str, parameter: str) -> float:
        key = f"{strategy_type}|{parameter}"
        s = self._stats.get(key)
        if not s or s[2] == 0 or s[0] == 0:
            return 1.0
        return self._clip(s[1] / s[0])

    def apply(self, strategy_type: str, parameter: str,
              predicted_delta: float) -> float:
        """Return a calibrated revenue delta (predicted * correction)."""
        return predicted_delta * self.factor(strategy_type, parameter)

    # ------------------------------------------------------------------ #
    def factors(self) -> List[CalibrationFactor]:
        out = []
        for key, s in self._stats.items():
            st, at, pkey = s[3], s[4], s[5]
            corr = (self._clip(s[1] / s[0]) if (s[0] != 0 and s[2]) else 1.0)
            out.append(CalibrationFactor(
                key=key, strategy_type=st, action_type=at, parameter=pkey,
                correction=round(corr, 4), samples=s[2],
                sum_predicted=round(s[0], 3), sum_actual=round(s[1], 3),
            ))
        return out

    def to_dict(self) -> dict:
        return {"factors": [f.to_dict() for f in self.factors()]}

    @classmethod
    def from_dict(cls, d: dict) -> "SimulatorCalibrator":
        """Rehydrate a calibrator from a saved factor table (cross-run learning)."""
        cal = cls()
        for f in (d or {}).get("factors", []):
            key = f["key"]
            cal._stats[key] = [
                f.get("sum_predicted", 0.0), f.get("sum_actual", 0.0),
                f.get("samples", 0), f.get("strategy_type", ""),
                f.get("action_type", ""), f.get("parameter", ""),
            ]
        return cal
