"""
E13.4.3 — Module 1: Feature Builder
====================================

Turns an `Opportunity` (E13.3.1 shape: dict with `type`, `segment`, `metrics`)
into a `StrategyFeature` for a given candidate `strategy_type`.

The feature merges four signal sources into one vector:

  * context      — segment + current eCPM / fill / retention metrics
  * Bayesian prior (from E13.4.1 Decision Memory, via StrategyPriorEngine)
  * experiment evidence (causal lift / retention impact, via E13.4.2)
  * rule prior   (E13.3.2 static EXPECTED_IMPACT / RULE_CONFIDENCE)

No simulation happens here — the ranker adds the simulator component later.

Example feature produced:
    {
      country: "US", platform: "android", issue_type: "ecpm_drop",
      current_ecpm: 12.5, current_fill: 0.92,
      history_success_rate: {"bid_floor_adjust": 0.72, "waterfall_change": 0.61},
      prior_mean: 0.72, ...
    }
"""
from __future__ import annotations

from typing import Dict, Optional

from monetization.experiments.models import DEFAULT_BASELINE
from monetization.strategy.strategy_rules import EXPECTED_IMPACT, RULE_CONFIDENCE

from monetization.intelligence.models import StrategyFeature


def build_feature(opportunity: dict, strategy_type: str,
                  prior_engine=None,
                  experiment_evidence: Optional[Dict[str, dict]] = None,
                  current_metrics: Optional[dict] = None) -> StrategyFeature:
    """Build a StrategyFeature for (opportunity, strategy_type)."""
    opp = opportunity or {}
    seg = opp.get("segment", {}) or {}
    opp_type = opp.get("type", "") or opp.get("opportunity_type", "")
    metrics = current_metrics or opp.get("metrics", {}) or {}

    ecpm = float(metrics.get("ecpm", DEFAULT_BASELINE["ecpm"]))
    fill = float(metrics.get("fill_rate", DEFAULT_BASELINE["fill_rate"]))
    ret = float(metrics.get("d1_retention_pct", DEFAULT_BASELINE["d1_retention_pct"]))

    # ---- Bayesian prior (history) ----
    if prior_engine is not None:
        p = prior_engine.prior(strategy_type)
        prior_alpha, prior_beta = p["alpha"], p["beta"]
        prior_mean, prior_samples = p["mean"], p["samples"]
        history_map = prior_engine.prior_map()
    else:
        prior_alpha = prior_beta = 1.0
        prior_mean = 0.5
        prior_samples = 0
        history_map = {}

    # ---- experiment evidence (causal) ----
    exp = (experiment_evidence or {}).get(strategy_type)
    exp_lift = exp.get("mean_lift") if exp else None
    exp_ret = exp.get("mean_retention") if exp else None
    exp_n = exp.get("samples", 0) if exp else 0

    # ---- static rule prior ----
    rule = EXPECTED_IMPACT.get(strategy_type, {})
    rule_effect = rule.get("expected_effect", "")
    rule_conf = float(RULE_CONFIDENCE.get(strategy_type, 0.6))

    return StrategyFeature(
        opportunity_id=opp.get("id", ""),
        opportunity_type=opp_type,
        segment=seg,
        strategy_type=strategy_type,
        issue_type=opp_type,
        current_ecpm=round(ecpm, 3),
        current_fill=round(fill, 4),
        current_retention=round(ret, 3),
        prior_alpha=prior_alpha,
        prior_beta=prior_beta,
        prior_mean=prior_mean,
        prior_samples=prior_samples,
        history_success_rate=history_map,
        exp_observed_lift=exp_lift,
        exp_retention_impact=exp_ret,
        exp_samples=exp_n,
        rule_expected_effect=rule_effect,
        rule_confidence=rule_conf,
    )
