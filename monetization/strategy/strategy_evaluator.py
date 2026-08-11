"""
E13.3.2 — Module 3: Strategy Evaluator
=======================================

Bridges a StrategyCandidate to the E13.2.9 Simulator and produces a score.

Pipeline per candidate:

    StrategyCandidate
          |
          |  read candidate.mutation[action_type, params]
          v
    E13.2.9 simulate_strategy(baseline_metric)
          |
          v
    StrategyPrediction   (status always 'simulated')
          |
          v
    score = revenue_gain*0.4 + retention_safety*0.3 + confidence*0.3

Hard constraints:
  * NO MAX API. NO RemoteConfig write. NO execution.
  * Reuses the E13.2.9 simulator as-is; does not redefine its model.
  * `no_action` candidates are scored against a neutral do-nothing baseline.

Scoring formula (normalises each component to [0,1]):
  revenue_gain      = clamp(0.5 + revenue_delta_pct / 40, 0, 1)
                       (0% delta -> 0.5 neutral; +8% -> 0.7; -2% -> 0.45)
  retention_safety  = clamp(1.0 + retention_delta_pct / 20, 0, 1)
                       (0% -> 1.0 safe; -2% -> 0.9; +1.6% -> 1.0 capped)
  confidence        = prediction confidence
  score             = revenue_gain*0.4 + retention_safety*0.3 + confidence*0.3

This reproduces the PRD's qualitative example (a balanced +high-confidence
strategy beats a higher-revenue-but-retention-harming one) without hard-coding
its illustrative 0.82/0.86 literals.
"""
from __future__ import annotations

from typing import List, Optional

from simulation.strategy_simulator import simulate_strategy

from monetization.strategy.models import CANDIDATE, SIMULATED, ScoredCandidate, StrategyCandidate

# Confidence assigned to a do-nothing baseline when an anomaly is active.
# Low enough that a genuinely-better active strategy can beat it, high enough
# that no_action stays a legitimate fallback.
NO_ACTION_CONFIDENCE = 0.60


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _target_str(segment: dict) -> str:
    return "_".join(str(segment[k]) for k in ("country", "platform", "ad_format", "network")
                    if segment.get(k))


def _neutral_prediction(candidate: StrategyCandidate) -> dict:
    """Synthetic 'do nothing' prediction for no_action / unmapped candidates."""
    return {
        "decision_id": candidate.id,
        "action_type": candidate.mutation.get("action_type") or "no_action",
        "lever": "none",
        "target": _target_str(candidate.target_segment),
        "baseline_metric": {},
        "prediction": {
            "revenue_delta_pct": 0.0,
            "ecpm_delta_pct": 0.0,
            "fill_delta_pct": 0.0,
            "impressions_delta_pct": 0.0,
            "retention_delta_pct": 0.0,
            "retention_risk": "low",
            "confidence": NO_ACTION_CONFIDENCE,
        },
        "projected_metric": {},
        "assumptions": {"model": "no_action", "note": "No mutation simulated; do-nothing baseline."},
        "notes": "No mutation applied (no_action).",
        "status": "simulated",
    }


def evaluate_candidate(candidate: StrategyCandidate,
                       baseline_fact=None) -> ScoredCandidate:
    """Run the candidate through the E13.2.9 Simulator and compute its score.

    Returns a ScoredCandidate (status always 'simulated').
    """
    mut = candidate.mutation or {}
    action_type = mut.get("action_type")
    params = mut.get("params", {}) or {}

    has_action = bool(action_type) and action_type != "no_action"
    if has_action:
        baseline_metric = baseline_fact.metric if baseline_fact else {}
        target = _target_str(candidate.target_segment)
        pred = simulate_strategy(action_type, params, baseline_metric,
                                 target=target, decision_id=candidate.id).to_dict()
        rev = pred["prediction"]["revenue_delta_pct"]
        ret = pred["prediction"]["retention_delta_pct"]
        conf = pred["prediction"]["confidence"]
    else:
        pred = _neutral_prediction(candidate)
        rev = 0.0
        ret = 0.0
        conf = NO_ACTION_CONFIDENCE

    revenue_component = _clamp(0.5 + rev / 40.0, 0.0, 1.0)
    retention_component = _clamp(1.0 + ret / 20.0, 0.0, 1.0)
    confidence_component = _clamp(conf, 0.0, 1.0)
    score = (revenue_component * 0.4
             + retention_component * 0.3
             + confidence_component * 0.3)

    return ScoredCandidate(
        candidate=candidate,
        prediction=pred,
        revenue_component=revenue_component,
        retention_component=retention_component,
        confidence_component=confidence_component,
        score=score,
        status=SIMULATED,
    )


def _baseline_for_opportunity(opportunity, facts: List) -> Optional[object]:
    """Find the latest fact that matches the opportunity's segment."""
    seg = opportunity.segment or {}
    country = seg.get("country")
    platform = seg.get("platform")
    ad_format = seg.get("ad_format")
    network = seg.get("network")

    if opportunity.type == "ad_frequency_issue":
        matches = [f for f in facts
                   if f.segment_type == "user"
                   and f.country == country and f.platform == platform
                   and f.metric.get("ads_per_dau") is not None]
    else:
        matches = [f for f in facts
                   if f.segment_type == "ad"
                   and f.country == country and f.platform == platform
                   and (ad_format is None or f.ad_format == ad_format)
                   and (network is None or f.network == network)]
    if not matches:
        return None
    return max(matches, key=lambda f: f.date)
