"""
E13.4.3 — Module 3: Strategy Ranker (Fusion Scoring)
====================================================

Upgrades the E13.3.2 ranking by fusing the Simulator prediction with the
system's own operating history (Strategy Prior) and experiment evidence.

E13.3.2 score:   0.4*Sim + 0.3*Safety + 0.3*Confidence
E13.4.3 score v1: 0.4*Sim + 0.3*Safety + 0.2*Confidence + 0.1*HistoricalPrior
Evolved (reserved): 0.3*Sim + 0.3*Historical + 0.2*Experiment + 0.2*Model

Where:
  * Sim           = clamp(0.5 + calibrated_revenue_delta / 40, 0, 1)
  * Safety        = clamp(1.0 + retention_delta / 20, 0, 1)   (retention-protective)
  * Confidence    = simulator prediction confidence
  * HistoricalPrior = Bayesian Beta mean for this strategy (E13.4.1)
  * Experiment    = clamp(0.5 + observed_lift / 40, 0, 1)     (E13.4.2 evidence)

Only *ranks* — never executes. The chosen strategy still must pass the
E13.3.3 Approval Gate before anything is applied.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from simulation.strategy_simulator import simulate_strategy
from monetization.experiments.models import DEFAULT_BASELINE
from monetization.strategy.strategy_rules import candidate_specs

from monetization.intelligence.models import (
    StrategyFeature, StrategyProbability, IntelligenceResult,
)
from monetization.intelligence.feature_builder import build_feature
from monetization.intelligence.calibration import SimulatorCalibrator, param_key


# v1 fusion weights (the accepted E13.4.3 formula).
V1_WEIGHTS = {
    "simulation": 0.4, "safety": 0.3, "confidence": 0.2, "historical_prior": 0.1,
}
# Forward-compatible evolved weights (adds experiment evidence + model slot).
EVOLVED_WEIGHTS = {
    "simulation": 0.3, "historical_prior": 0.3,
    "confidence": 0.2, "experiment_evidence": 0.2,
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _target_str(segment: dict) -> str:
    return "_".join(str(segment[k]) for k in
                    ("country", "platform", "ad_format", "network") if segment.get(k))


def experiment_evidence_for(store, strategy_type) -> Optional[dict]:
    """Mean observed lift / retention impact for a strategy across memory."""
    recs = [r for r in store.all()
            if r.strategy_type == strategy_type and r.closed_loop and r.actual]
    if not recs:
        return None
    lifts = [r.actual.revenue_delta_pct for r in recs]
    rets = [r.actual.retention_delta_pct for r in recs]
    return {
        "mean_lift": round(sum(lifts) / len(lifts), 3),
        "mean_retention": round(sum(rets) / len(rets), 3),
        "samples": len(recs),
    }


class StrategyRanker:
    """Fuses simulation + history + experiment evidence into a ranked list."""

    def __init__(self, prior_engine=None,
                 calibrator: Optional[SimulatorCalibrator] = None,
                 store=None):
        self.prior = prior_engine
        self.calibrator = calibrator or SimulatorCalibrator()
        self.store = store

    # ------------------------------------------------------------------ #
    def _experiment_evidence(self) -> Dict[str, dict]:
        if self.store is None:
            return {}
        out = {}
        for st in {r.strategy_type for r in self.store.all()}:
            ev = experiment_evidence_for(self.store, st)
            if ev:
                out[st] = ev
        return out

    # ------------------------------------------------------------------ #
    def rank(self, opportunity: dict, top_n: int = 3,
             weights: Optional[dict] = None,
             baseline_metric: Optional[dict] = None) -> IntelligenceResult:
        """Rank all candidate strategies for one opportunity.

        Returns an IntelligenceResult whose `ranked` list is sorted best-first
        and whose `top` is the winning StrategyProbability.to_dict().
        """
        weights = weights or V1_WEIGHTS
        opp = opportunity or {}
        seg = opp.get("segment", {}) or {}
        opp_type = opp.get("type", "") or opp.get("opportunity_type", "")
        metrics = baseline_metric or opp.get("metrics", {}) or {}
        baseline = dict(DEFAULT_BASELINE)
        baseline.update(metrics or {})
        target = _target_str(seg)

        specs = candidate_specs(opp_type)
        exp_evidence = self._experiment_evidence()
        evolved = "experiment_evidence" in weights

        results: List[StrategyProbability] = []
        for spec in specs:
            st = spec["strategy_type"]
            mut = spec["mutation"]
            action_type = mut.get("action_type") or ""
            params = mut.get("params", {}) or {}

            # 1) context + prior feature
            feat: StrategyFeature = build_feature(
                opportunity, st, self.prior, exp_evidence, metrics)

            # 2) simulator prediction
            pred = simulate_strategy(
                action_type, params, baseline,
                target=target, decision_id=opp.get("id", "opp")).to_dict()
            pred_rev = float(pred["prediction"]["revenue_delta_pct"])
            pred_ret = float(pred["prediction"]["retention_delta_pct"])
            conf = float(pred["prediction"]["confidence"])

            # 3) calibrate the revenue delta (revenue-only correction)
            pkey = param_key(mut)
            cal_rev = self.calibrator.apply(st, pkey, pred_rev) if self.calibrator else pred_rev

            # 4) components
            sim_score = _clamp(0.5 + cal_rev / 40.0, 0.0, 1.0)
            safety = _clamp(1.0 + pred_ret / 20.0, 0.0, 1.0)
            historical = feat.prior_mean
            exp_ev = 0.0
            if feat.exp_observed_lift is not None:
                exp_ev = _clamp(0.5 + feat.exp_observed_lift / 40.0, 0.0, 1.0)

            # 5) fuse
            if evolved:
                final = (weights.get("simulation", 0.0) * sim_score
                         + weights.get("historical_prior", 0.0) * historical
                         + weights.get("confidence", 0.0) * conf
                         + weights.get("experiment_evidence", 0.0) * exp_ev)
            else:
                final = (weights.get("simulation", 0.0) * sim_score
                         + weights.get("safety", 0.0) * safety
                         + weights.get("confidence", 0.0) * conf
                         + weights.get("historical_prior", 0.0) * historical)

            results.append(StrategyProbability(
                strategy_type=st, action_type=action_type,
                simulation_score=round(sim_score, 4),
                safety_score=round(safety, 4),
                confidence=round(conf, 4),
                historical_prior=round(historical, 4),
                experiment_evidence=round(exp_ev, 4),
                final_score=round(final, 4),
                probability=round(final, 4),
                evidence={
                    "predicted_revenue_delta": round(pred_rev, 3),
                    "calibrated_revenue_delta": round(cal_rev, 3),
                    "predicted_retention_delta": round(pred_ret, 3),
                    "prior_samples": feat.prior_samples,
                    "exp_samples": feat.exp_samples,
                    "correction": round(self.calibrator.factor(st, pkey), 4)
                    if self.calibrator else 1.0,
                },
            ))

        results.sort(key=lambda r: r.final_score, reverse=True)
        for i, r in enumerate(results, 1):
            r.evidence["rank"] = i
            r.evidence = r.evidence  # keep
        top = results[:top_n]
        return IntelligenceResult(
            opportunity_id=opp.get("id", ""),
            opportunity_type=opp_type,
            target_segment=seg,
            ranked=[r.to_dict() for r in results],
            top=top[0].to_dict() if top else None,
            weights=weights,
            notes=("v1 fusion: 0.4*sim + 0.3*safety + 0.2*conf + 0.1*prior"
                   if not evolved else
                   "evolved fusion: 0.3*sim + 0.3*prior + 0.2*conf + 0.2*exp"),
        )
