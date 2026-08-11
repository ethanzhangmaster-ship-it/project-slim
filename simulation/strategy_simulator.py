"""
E13.2.9 — Monetization Strategy Simulator
==========================================

Sits between E13.2.8 (Intelligence: Opportunities + proposed Decisions) and
the future E13.3 Agent / Executor.

Hard constraints (per E13.2.9 scope):
  * NO MAX API call.
  * NO execution of any mutation.
  * It only answers: "If we apply this *proposed* Decision to the current
    Fact state, what is the predicted impact on revenue / eCPM / fill /
    retention, and how confident are we?"

This is the Observe -> Understand -> Predict seam. The Agent (E13.3.2) will
read these predictions to decide; the Executor (E13.3.3) is the only place a
decision is ever applied.

Model
-----
Transparent, tunable linear elasticities. Each "lever" has a per-1%-change
coefficient for ecpm / fill / retention. Compound revenue delta is computed
from eCPM * impressions (impressions track fill for bid/waterfall levers, and
track frequency for ad-frequency levers). Replace with a trained model in
E13.3.2 when real data accumulates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Elasticity model (per +1% of lever magnitude)
# --------------------------------------------------------------------------- #
# Sign encodes direction: raising a bid floor raises eCPM (+) and lowers fill (-).
PER_PCT: Dict[str, Dict[str, float]] = {
    "bid_floor_up":      {"ecpm": 0.30, "fill": -0.22, "retention": 0.0},
    "bid_floor_down":    {"ecpm": -0.26, "fill": 0.20, "retention": 0.0},
    "waterfall_promote": {"ecpm": 0.15, "fill": -0.08, "retention": 0.0},
    "waterfall_demote":  {"ecpm": -0.15, "fill": 0.08, "retention": 0.0},
    "fill_recovery":     {"ecpm": -0.05, "fill": 0.20, "retention": 0.0},
    "freq_up":           {"ecpm": -0.05, "fill": 0.0, "retention": -0.16},
    "freq_down":         {"ecpm": 0.05, "fill": 0.0, "retention": 0.16},
}

# Base confidence by lever (better-understood mechanics -> higher confidence).
BASE_CONF: Dict[str, float] = {
    "bid_floor_up": 0.85, "bid_floor_down": 0.82,
    "waterfall_promote": 0.75, "waterfall_demote": 0.72,
    "fill_recovery": 0.70, "freq_up": 0.58, "freq_down": 0.62,
}

# Default magnitude (pct) when a Decision / params do not specify one.
DEFAULT_PCT: Dict[str, float] = {
    "bid_floor_up": 20, "bid_floor_down": 20,
    "waterfall_promote": 20, "waterfall_demote": 20,
    "fill_recovery": 15, "freq_up": 10, "freq_down": 10,
}


# --------------------------------------------------------------------------- #
# Output model
# --------------------------------------------------------------------------- #
@dataclass
class StrategyPrediction:
    decision_id: str
    action_type: str
    lever: str
    target: str
    baseline_metric: dict
    prediction: dict       # revenue/ecpm/fill/impressions/retention deltas + risk + confidence
    projected_metric: dict # absolute projected values (ad-segment aware)
    assumptions: dict      # elasticities used (explainability)
    notes: str
    status: str = "simulated"   # NEVER "executed"

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Lever resolution
# --------------------------------------------------------------------------- #
def _lever_and_magnitude(action_type: str, mutation: dict) -> (str, float):
    """Map a Decision/strategy action + mutation into a (lever, magnitude_pct)."""
    m = mutation or {}
    if action_type == "change_waterfall":
        return "waterfall_promote", float(m.get("magnitude_pct", DEFAULT_PCT["waterfall_promote"]))
    if action_type == "review_bidding":
        if m.get("increase_bid_floor"):
            return "bid_floor_up", float(m.get("bid_floor_pct", DEFAULT_PCT["bid_floor_up"]))
        # default: enable backup networks -> fill recovery
        return "fill_recovery", float(m.get("magnitude_pct", DEFAULT_PCT["fill_recovery"]))
    if action_type == "adjust_ad_frequency":
        direction = m.get("direction")
        blob = str(m).lower()
        if direction == "up" or (direction is None and "increase_interval" not in blob):
            # explicit up, or unspecified (treat as raising load)
            return "freq_up", float(m.get("magnitude_pct", DEFAULT_PCT["freq_up"]))
        return "freq_down", float(m.get("magnitude_pct", DEFAULT_PCT["freq_down"]))
    # unknown -> conservative promote
    return "waterfall_promote", float(m.get("magnitude_pct", DEFAULT_PCT["waterfall_promote"]))


# --------------------------------------------------------------------------- #
# Core simulation
# --------------------------------------------------------------------------- #
def _simulate_core(lever: str, magnitude_pct: float, baseline_metric: dict,
                   target: str = "", action_type: str = "", decision_id: str = "") -> StrategyPrediction:
    e = PER_PCT[lever]
    p = magnitude_pct

    d_ecpm = round(e["ecpm"] * p, 3)
    d_fill = round(e["fill"] * p, 3)
    d_ret = round(e["retention"] * p, 3)

    # impressions delta: bid/waterfall levers -> impressions track fill;
    # ad-frequency levers -> impressions track the frequency change itself.
    if lever in ("freq_up", "freq_down"):
        d_impr = round(p if lever == "freq_up" else -p, 3)
    else:
        d_impr = d_fill

    # compound revenue delta = eCPM * impressions
    rev_delta = round(d_ecpm + d_impr + (d_ecpm * d_impr) / 100.0, 3)

    # retention risk (downside to retention from the action)
    if lever in ("freq_up", "freq_down"):
        if lever == "freq_up":
            risk = "high" if abs(d_ret) >= 3.0 else ("medium" if abs(d_ret) >= 1.5 else "low")
        else:
            risk = "low"   # reducing frequency is retention-friendly
    else:
        risk = "low"

    # confidence: base * magnitude factor * data-quality factor
    base = BASE_CONF[lever]
    mag_f = max(0.6, 1.0 - abs(p) * 0.004)
    impr = baseline_metric.get("impressions") or baseline_metric.get("dau") or 0
    data_f = 1.0 if impr >= 5000 else (0.9 if impr >= 1000 else 0.75)
    conf = round(min(0.97, max(0.30, base * mag_f * data_f)), 3)

    # projected absolute metrics (ad-segment aware)
    proj: dict = {}
    ecpm0 = baseline_metric.get("ecpm")
    fill0 = baseline_metric.get("fill_rate")
    impr0 = baseline_metric.get("impressions")
    if ecpm0 is not None:
        proj["ecpm"] = round(ecpm0 * (1 + d_ecpm / 100.0), 3)
    if fill0 is not None:
        proj["fill_rate"] = round(min(1.0, fill0 * (1 + d_fill / 100.0)), 4)
    if impr0 is not None:
        proj["impressions"] = round(impr0 * (1 + d_impr / 100.0))
    if ecpm0 is not None and impr0 is not None:
        proj["revenue"] = round(proj.get("ecpm", ecpm0) * proj.get("impressions", impr0) / 1000.0, 4)

    prediction = {
        "revenue_delta_pct": rev_delta,
        "ecpm_delta_pct": d_ecpm,
        "fill_delta_pct": d_fill,
        "impressions_delta_pct": d_impr,
        "retention_delta_pct": d_ret,
        "retention_risk": risk,
        "confidence": conf,
    }

    assumptions = {
        "model": "linear_elasticity",
        "elasticities_per_pct": e,
        "magnitude_pct": p,
        "note": "Transparent heuristic. Replace with trained model in E13.3.2.",
    }

    notes = (f"Simulated {lever} (magnitude {p:+}%): predicted revenue "
             f"{rev_delta:+.1f}%, eCPM {d_ecpm:+.1f}%, fill {d_fill:+.1f}%, "
             f"impressions {d_impr:+.1f}%, retention {d_ret:+.2f}% "
             f"({risk} risk). Confidence {conf}.")

    return StrategyPrediction(
        decision_id=decision_id, action_type=action_type, lever=lever,
        target=target, baseline_metric=baseline_metric, prediction=prediction,
        projected_metric=proj, assumptions=assumptions, notes=notes,
        status="simulated",
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def simulate_decision(decision, baseline_fact) -> StrategyPrediction:
    """Simulate a proposed Decision against a current MonetizationFact."""
    lever, mag = _lever_and_magnitude(decision.action_type, getattr(decision, "mutation", None) or {})
    return _simulate_core(
        lever, mag, baseline_fact.metric,
        target=decision.target, action_type=decision.action_type,
        decision_id=decision.decision_id,
    )


def simulate_strategy(action_type: str, params: dict, baseline_metric: dict,
                      target: str = "", decision_id: str = "") -> StrategyPrediction:
    """Standalone API: simulate a strategy without needing a full Decision object."""
    lever, mag = _lever_and_magnitude(action_type, params or {})
    return _simulate_core(lever, mag, baseline_metric, target=target,
                          action_type=action_type, decision_id=decision_id)
