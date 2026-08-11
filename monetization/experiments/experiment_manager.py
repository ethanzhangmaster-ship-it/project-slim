"""
E13.4.2 — Module 3: Experiment Manager  (the orchestrator)
===========================================================

Builds monetisation experiments (A/B/n tests) from either an explicit spec or a
real E13.3.2 Strategy Candidate, runs them through the E13.2.9 Simulator as the
*traffic simulator*, and (optionally) writes each treatment arm into the
E13.4.1 Decision Memory as a closed-loop sample.

Why this layer exists
---------------------
E13.3.2 picks ONE candidate. E13.4.1 remembers what happened. E13.4.2 *creates*
comparable evidence: baseline vs several treatments on the SAME segment under
the SAME (simulated) traffic, so the system learns which magnitude/network/
frequency actually caused the better outcome — not just what happened to occur.

Pipeline (per experiment):

    build variants (baseline + treatments, swept magnitudes)
            |
            |  variant_allocator -> equal traffic split
            v
    for each variant: E13.2.9 simulate_strategy(scaled baseline)  -> VariantMetric
            |
            v
    pick winner by success_metric (higher = better)
            |
            v
    ExperimentResult (winner + lift + learning signal)
            |
            v
    [optional] record each treatment arm as a DecisionRecord (closed loop)
              into the E13.4.1 store -> future training data

Hard constraints (per E13.4.2 scope):
  * NO MAX / LevelPlay / RemoteConfig. Simulation only.
  * NO execution. This is evidence generation, not config change.
  * Lean: pure Python, no DB, no ML.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from simulation.strategy_simulator import simulate_strategy

from monetization.experiments.models import (
    DEFAULT_BASELINE, Experiment, ExperimentResult, Variant, VariantMetric,
    new_id,
)
from monetization.experiments.variant_allocator import (
    allocate, assign_impressions,
)
from monetization.learning.decision_store import DecisionStore
from monetization.learning.models import ActualOutcome, DecisionRecord
from monetization.learning.outcome_tracker import compute_learning_signal

# How much of the predicted lift "actually shows up" in a noisy A/B test, and
# the +/- random pct added. Deterministic per (experiment, variant) seed.
REALIZATION = 0.85
NOISE = 1.5


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _target_str(segment: dict) -> str:
    return "_".join(str(segment[k]) for k in ("country", "platform", "ad_format", "network")
                    if segment.get(k))


def _baseline_variant() -> Variant:
    return Variant(new_id("v"), "A_baseline", True, "baseline", "", {},
                   {"mutation_type": "none", "gene": {}},
                   description="No change (control arm).")


def create_bid_floor_experiment(segment: dict, baseline_floor_pct: float = 30,
                                magnitudes=(0, 20, 40),
                                success_metric: str = "revenue",
                                opportunity=None) -> Experiment:
    """Sweep the bid floor: baseline + N floor-raise treatments."""
    base = _baseline_variant()
    variants = [base]
    for m in magnitudes:
        if m == 0:
            continue  # baseline already covers 0%
        variants.append(Variant(
            new_id("v"), f"B_floor+{m}%", False, "bid_floor_adjust",
            "review_bidding",
            {"increase_bid_floor": True, "bid_floor_pct": m},
            {"mutation_type": "bid_floor_gene", "gene": {"bid_floor_delta": m / 100.0},
             "description": f"Raise bid floor to {baseline_floor_pct * (1 + m/100.0):.0f} (+{m}%)."},
            description=f"Raise bid floor +{m}% (to ~{baseline_floor_pct*(1+m/100.0):.0f}).",
        ))
    return _assemble("Bid Floor Sweep", segment, success_metric, variants,
                     "Raising the bid floor lifts eCPM; testing which magnitude "
                     "maximises revenue without crushing fill.", opportunity)


def create_waterfall_experiment(segment: dict,
                                networks=("mintegral", "applovin"),
                                magnitudes=(20, 25),
                                success_metric: str = "revenue",
                                opportunity=None) -> Experiment:
    """Sweep waterfall priority shifts across candidate networks."""
    base = _baseline_variant()
    variants = [base]
    for net, m in zip(networks, magnitudes):
        variants.append(Variant(
            new_id("v"), f"B_wf_{net}+{m}", False, "waterfall_change",
            "change_waterfall", {"magnitude_pct": m},
            {"mutation_type": "waterfall_gene",
             "gene": {"priority_shift": 1, "network": net},
             "description": f"Promote {net} in the waterfall (+{m}%)."},
            description=f"Promote {net} higher in the waterfall (+{m}%).",
        ))
    return _assemble("Waterfall Priority Sweep", segment, success_metric, variants,
                     "Re-prioritising the waterfall to a healthier network can "
                     "lift eCPM; testing which network shift wins.", opportunity)


def create_frequency_experiment(segment: dict, base_freq: int = 5,
                                arms=(("down", 10), ("up", 10)),
                                success_metric: str = "retention",
                                opportunity=None) -> Experiment:
    """Test ad-frequency changes against a baseline load."""
    base = _baseline_variant()
    variants = [base]
    for direction, m in arms:
        stype = "frequency_down" if direction == "down" else "frequency_adjust"
        new_freq = base_freq - 1 if direction == "down" else base_freq + 1
        variants.append(Variant(
            new_id("v"), f"B_freq{new_freq}({direction})", False, stype,
            "adjust_ad_frequency", {"direction": direction, "magnitude_pct": m},
            {"mutation_type": "frequency_gene",
             "gene": {"reward_interval_delta": 1 if direction == "down" else -1},
             "description": f"Set ad frequency to {new_freq} ({direction})."},
            description=f"Change rewarded-ad frequency to {new_freq} ({direction}).",
        ))
    return _assemble("Ad Frequency Test", segment, success_metric, variants,
                     "Ad frequency trades revenue against retention; testing "
                     "whether reducing or raising load is better.", opportunity)


def experiment_from_candidate(candidate, baseline_metric: dict,
                              success_metric: str = "revenue",
                              opportunity=None) -> Experiment:
    """Build a 2-arm (baseline + the candidate) experiment from a real
    E13.3.2 StrategyCandidate."""
    mut = candidate.mutation or {}
    seg = candidate.target_segment or {}
    opp_id = (opportunity.id if opportunity else None) or candidate.opportunity_id or ""
    opp_type = (opportunity.type if opportunity else None) or ""
    base = _baseline_variant()
    treatment = Variant(
        new_id("v"), f"B_{candidate.strategy_type}", False,
        candidate.strategy_type, mut.get("action_type", ""),
        mut.get("params", {}) or {}, mut,
        description=mut.get("description", candidate.strategy_type),
    )
    return _assemble(
        f"Exp: {candidate.strategy_type} on {_target_str(seg) or 'global'}",
        seg, success_metric, [base, treatment],
        f"Test whether {candidate.strategy_type} improves {success_metric} "
        f"for this segment (derived from a real E13.3.1 opportunity).",
        opportunity, opp_id, opp_type)


def _assemble(name, segment, success_metric, variants, hypothesis,
              opportunity=None, opp_id="", opp_type="") -> Experiment:
    exp = Experiment(
        id=new_id("exp"), name=name, hypothesis=hypothesis,
        target_segment=dict(segment or {}), success_metric=success_metric,
        opportunity_id=opp_id, opportunity_type=opp_type, status="draft",
        baseline_variant_id=variants[0].variant_id, variants=variants,
    )
    return exp


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class ExperimentManager:
    def __init__(self, facts: Optional[List] = None, store: Optional[DecisionStore] = None):
        self.facts = list(facts or [])
        self.store = store

    def set_facts(self, facts) -> None:
        self.facts = list(facts or [])

    def set_store(self, store: DecisionStore) -> None:
        self.store = store

    # ------------------------------------------------------------------ #
    def run_experiment(self, experiment: Experiment,
                       baseline_metric: Optional[dict] = None) -> ExperimentResult:
        """Simulate every arm and produce the winner + learning signal.

        Does NOT touch the store. Pure evidence generation.
        """
        if baseline_metric is None:
            baseline_metric = dict(DEFAULT_BASELINE)
        target = _target_str(experiment.target_segment)
        variants = experiment.variants
        allocate(variants, "equal")

        baseline_impr = baseline_metric.get("impressions", DEFAULT_BASELINE["impressions"])
        dau = baseline_metric.get("dau", DEFAULT_BASELINE["dau"])
        impr_per = assign_impressions(baseline_impr, variants)

        per_variant: Dict[str, VariantMetric] = {}
        baseline_value = None
        for v in variants:
            arm_baseline = dict(baseline_metric)
            arm_baseline["impressions"] = impr_per[v.variant_id]
            arm_baseline["dau"] = max(1, int(round(dau * v.allocation)))
            vm = self._simulate_variant(v, arm_baseline, target)
            per_variant[v.variant_id] = vm
            if v.is_baseline:
                baseline_value = vm.metric_value(experiment.success_metric)

        # winner = highest success-metric value (higher is better for all kinds)
        winner = max(
            variants,
            key=lambda v: per_variant[v.variant_id].metric_value(experiment.success_metric),
        )
        winner_vm = per_variant[winner.variant_id]
        winner_value = winner_vm.metric_value(experiment.success_metric)
        lift = ((winner_value - baseline_value) / baseline_value * 100.0
                if baseline_value else 0.0)

        learning = self._learning_signal(experiment, per_variant, baseline_value, winner, winner_vm)

        conclusion = (
            f"Winner: {winner.name} ({winner.strategy_type}) with "
            f"{winner_value:.3f} {experiment.success_metric} "
            f"(+{lift:.1f}% vs baseline). {learning['recommendation']}"
        )

        return ExperimentResult(
            experiment_id=experiment.id, name=experiment.name,
            opportunity_type=experiment.opportunity_type,
            target_segment=experiment.target_segment,
            success_metric=experiment.success_metric,
            baseline_metric=baseline_metric,
            per_variant={vid: vm.to_dict() for vid, vm in per_variant.items()},
            baseline_variant_id=experiment.baseline_variant_id,
            winner_variant_id=winner.variant_id,
            winner_strategy_type=winner.strategy_type,
            winner_name=winner.name,
            winner_metric_value=winner_value,
            baseline_metric_value=baseline_value,
            lift_pct=lift, conclusion=conclusion,
            learning_signal=learning, variants_count=len(variants),
            status="completed",
        )

    # ------------------------------------------------------------------ #
    def run_and_record(self, experiment: Experiment,
                       baseline_metric: Optional[dict] = None,
                       store: Optional[DecisionStore] = None) -> ExperimentResult:
        """Run the experiment AND write each treatment arm into the store as a
        closed-loop DecisionRecord (evidence -> E13.4.1 memory)."""
        store = store or self.store
        result = self.run_experiment(experiment, baseline_metric)
        if store is not None:
            self._record_arms(experiment, result, store)
        return result

    def run_pipeline_experiments(self, opportunities, facts,
                                 baseline_builder=None,
                                 success_metric: str = "revenue",
                                 store: Optional[DecisionStore] = None) -> List[ExperimentResult]:
        """For each real E13.3.1 opportunity: derive a candidate via E13.3.2,
        build a 2-arm experiment, run + record it. Returns the results."""
        from monetization.strategy.strategy_generator import StrategyEngine
        store = store or self.store
        engine = StrategyEngine(facts)
        results: List[ExperimentResult] = []
        for opp in opportunities:
            ranked = engine.process_opportunity(opp)
            if ranked.top is None:
                continue
            # build a baseline metric for this opportunity's segment
            bm = baseline_builder(opp) if baseline_builder else dict(DEFAULT_BASELINE)
            exp = experiment_from_candidate(ranked.top.candidate, bm,
                                            success_metric, opportunity=opp)
            res = self.run_and_record(exp, bm, store)
            results.append(res)
        return results

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _simulate_variant(self, v: Variant, arm_baseline: dict, target: str) -> VariantMetric:
        if v.is_baseline or not v.action_type:
            ecpm = arm_baseline.get("ecpm", 0.0)
            fill = arm_baseline.get("fill_rate", 0.0)
            impr = arm_baseline.get("impressions", 0)
            rev = ecpm * impr / 1000.0
            dau = arm_baseline.get("dau", 1) or 1
            ret = arm_baseline.get("d1_retention_pct", 0.0)
            deltas = {"revenue_delta_pct": 0.0, "ecpm_delta_pct": 0.0,
                      "fill_delta_pct": 0.0, "impressions_delta_pct": 0.0,
                      "retention_delta_pct": 0.0}
            proj = {"ecpm": ecpm, "fill_rate": fill, "impressions": impr,
                    "revenue": rev, "arpdau": rev / dau, "retention_pct": ret}
            return VariantMetric(
                v.variant_id, v.name, True, "", "none", deltas, proj,
                confidence=1.0, retention_risk="low", allocation=v.allocation,
                sample_size=max(1, int(round(arm_baseline.get("dau", 1) or 1))),
                impressions=impr,
                notes="Baseline (no change). Control arm.",
            )

        pred = simulate_strategy(v.action_type, v.params, arm_baseline,
                                 target=target, decision_id=v.variant_id)
        p = pred.prediction
        ecpm0 = arm_baseline.get("ecpm", 0.0)
        impr0 = arm_baseline.get("impressions", 0)
        dau = arm_baseline.get("dau", 1) or 1
        ret0 = arm_baseline.get("d1_retention_pct", 0.0)

        d_ecpm = p["ecpm_delta_pct"]
        d_impr = p["impressions_delta_pct"]
        d_ret = p["retention_delta_pct"]
        proj_ecpm = ecpm0 * (1 + d_ecpm / 100.0)
        proj_impr = impr0 * (1 + d_impr / 100.0)
        proj_rev = proj_ecpm * proj_impr / 1000.0
        proj_ret = ret0 * (1 + d_ret / 100.0)

        deltas = {k: p[k] for k in ("revenue_delta_pct", "ecpm_delta_pct",
                                     "fill_delta_pct", "impressions_delta_pct",
                                     "retention_delta_pct")}
        proj = {
            "ecpm": round(proj_ecpm, 3),
            "fill_rate": round(pred.projected_metric.get("fill_rate",
                                                           arm_baseline.get("fill_rate", 0.0)), 4),
            "impressions": round(proj_impr),
            "revenue": round(proj_rev, 4),
            "arpdau": round(proj_rev / dau, 4),
            "retention_pct": round(proj_ret, 3),
        }
        sample = max(1, int(round(dau)))
        return VariantMetric(
            v.variant_id, v.name, False, v.action_type, pred.lever, deltas, proj,
            confidence=p["confidence"], retention_risk=p["retention_risk"],
            allocation=v.allocation, sample_size=sample, impressions=impr0,
            notes=pred.notes,
        )

    def _measured(self, vm: VariantMetric, seed: int):
        """A/B-test-observed outcome for a variant (predicted lift under noise)."""
        rng = random.Random(seed)
        pred_rev = vm.deltas["revenue_delta_pct"]
        pred_ret = vm.deltas["retention_delta_pct"]
        meas_rev = round(pred_rev * REALIZATION + rng.uniform(-NOISE, NOISE), 3)
        meas_ret = round(pred_ret * (REALIZATION * 0.5 + 0.5) + rng.uniform(-NOISE * 0.3, NOISE * 0.3), 3)
        return meas_rev, meas_ret

    def _learning_signal(self, experiment: Experiment, per_variant: Dict[str, VariantMetric],
                         baseline_value, winner: Variant, winner_vm: VariantMetric) -> dict:
        treatments = [v for v in experiment.variants if not v.is_baseline]
        biases = []
        per_treatment = {}
        for i, v in enumerate(treatments):
            vm = per_variant[v.variant_id]
            seed = (abs(hash(experiment.id)) % 1000) * 31 + i
            meas_rev, meas_ret = self._measured(vm, seed)
            per_treatment[v.variant_id] = {
                "variant": v.name, "strategy_type": v.strategy_type,
                "predicted_revenue_delta": vm.deltas["revenue_delta_pct"],
                "measured_revenue_delta": meas_rev,
                "measured_retention_delta": meas_ret,
            }
            biases.append(meas_rev - vm.deltas["revenue_delta_pct"])

        bias = round(sum(biases) / len(biases), 3) if biases else 0.0
        interpretation = (
            "Simulator OVER-predicts revenue (actuals fall short)."
            if bias < -0.05 else
            "Simulator UNDER-predicts revenue (actuals beat forecast)."
            if bias > 0.05 else
            "Simulator well-calibrated on experiment evidence."
        )
        return {
            "winner_strategy_type": winner.strategy_type,
            "winner_variant": winner.name,
            "winner_lift_pct": round(
                (winner_vm.metric_value(experiment.success_metric) - baseline_value)
                / baseline_value * 100.0 if baseline_value else 0.0, 3),
            "measured_vs_predicted_bias": bias,
            "bias_interpretation": interpretation,
            "per_treatment": per_treatment,
            "recommendation": (
                f"Adopt '{winner.name}' ({winner.strategy_type}) for "
                f"{_target_str(experiment.target_segment) or 'this segment'}; "
                f"promote it for A/B-confirmed lift before any production rollout."
            ),
            "confidence": winner_vm.confidence,
        }

    def _record_arms(self, experiment: Experiment, result: ExperimentResult,
                     store: DecisionStore) -> None:
        target = _target_str(experiment.target_segment)
        treatments = [v for v in experiment.variants if not v.is_baseline]
        for i, v in enumerate(treatments):
            vm_dict = result.per_variant.get(v.variant_id, {})
            deltas = vm_dict.get("deltas", {})
            seed = (abs(hash(experiment.id)) % 1000) * 31 + i
            meas_rev, meas_ret = self._measured(
                VariantMetric(v.variant_id, v.name, False, vm_dict.get("action_type", ""),
                              vm_dict.get("lever", "none"), deltas,
                              vm_dict.get("projected", {}),
                              confidence=vm_dict.get("confidence", 0.0),
                              retention_risk=vm_dict.get("retention_risk", "low")),
                seed)
            rec = DecisionRecord(
                decision_id=f"exp_{experiment.id}_{v.variant_id}",
                opportunity_id=experiment.opportunity_id,
                opportunity_type=experiment.opportunity_type or "experiment",
                segment=experiment.target_segment,
                strategy_type=v.strategy_type,
                strategy_score=0.0,
                strategy_mutation=v.mutation,
                prediction={
                    "experiment_id": experiment.id, "variant": v.name,
                    "lever": vm_dict.get("lever", "none"), "target": target,
                    "prediction": deltas,
                },
                prediction_confidence=float(vm_dict.get("confidence", 0.0)),
                prediction_revenue_delta=float(deltas.get("revenue_delta_pct", 0.0)),
                prediction_retention_delta=float(deltas.get("retention_delta_pct", 0.0)),
                gate_verdict="",
                execution_status="executed",   # executed within the experiment
                execution_changes=1,
            )
            actual = ActualOutcome(
                revenue_delta_pct=meas_rev, retention_delta_pct=meas_ret,
                sample_size=int(vm_dict.get("sample_size", 0)),
                source="experiment_sim",
            )
            rec.actual = actual
            rec.learning_signal = compute_learning_signal(rec, actual)
            rec.closed_loop = True
            store.append(rec)
