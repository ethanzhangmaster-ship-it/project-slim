"""
E13.4.2 — Module 4: Experiment Analyzer
========================================

Turns a list of ExperimentResults into human- and machine-readable insight:

  * per-variant comparison (what each arm did on the success metric)
  * the winner + lift vs baseline
  * the experiment-level learning signal (calibration bias + recommendation)
  * a full Experiment Report (the E13.4.2 acceptance artifact), optionally
    joined with the E13.4.1 store so you can see experiments flowing into the
    strategy-prior memory.

No AI, no DB. Pure aggregation over already-simulated results.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from monetization.experiments.models import ExperimentResult


def compare_variants(result: ExperimentResult) -> List[dict]:
    """One row per variant: name, strategy, deltas, and success-metric value."""
    rows = []
    for vid, vm in result.per_variant.items():
        d = vm.get("deltas", {})
        proj = vm.get("projected", {})
        is_base = vm.get("is_baseline", False)
        rows.append({
            "variant_id": vid,
            "name": vm.get("name"),
            "strategy_type": vm.get("lever") or ("baseline" if is_base else "treatment"),
            "is_baseline": is_base,
            "revenue_delta_pct": d.get("revenue_delta_pct"),
            "ecpm_delta_pct": d.get("ecpm_delta_pct"),
            "fill_delta_pct": d.get("fill_delta_pct"),
            "retention_delta_pct": d.get("retention_delta_pct"),
            "success_metric_value": proj.get(
                "revenue" if result.success_metric == "revenue" else
                "arpdau" if result.success_metric in ("arpdau", "ad_arpdau") else
                "ecpm" if result.success_metric == "ecpm" else
                "retention_pct"),
            "confidence": vm.get("confidence"),
        })
    # sort: baseline first, then by success-metric value desc
    rows.sort(key=lambda r: (not r["is_baseline"],
                             -(r["success_metric_value"] or 0)))
    return rows


def analyze(result: ExperimentResult) -> dict:
    """Condensed analysis of one experiment."""
    comp = compare_variants(result)
    return {
        "experiment_id": result.experiment_id,
        "name": result.name,
        "success_metric": result.success_metric,
        "target_segment": result.target_segment,
        "winner": {
            "variant": result.winner_name,
            "strategy_type": result.winner_strategy_type,
            "value": result.winner_metric_value,
        },
        "baseline_value": result.baseline_metric_value,
        "lift_pct": result.lift_pct,
        "conclusion": result.conclusion,
        "learning_signal": result.learning_signal,
        "comparison": comp,
    }


def generate_experiment_report(results: List[ExperimentResult],
                                store=None) -> dict:
    """Full Experiment Report (E13.4.2 acceptance artifact)."""
    analyses = [analyze(r) for r in results]

    # aggregate learning signals across experiments
    biases = [a["learning_signal"]["measured_vs_predicted_bias"]
              for a in analyses if "measured_vs_predicted_bias" in a["learning_signal"]]
    winners = [(a["winner"]["strategy_type"], a["lift_pct"]) for a in analyses]

    report = {
        "module": "E13.4.2 Monetization Experiment Engine",
        "experiment_count": len(results),
        "experiments": analyses,
        "aggregate": {
            "mean_measured_vs_predicted_bias": round(sum(biases) / len(biases), 3) if biases else 0.0,
            "winners": [{"strategy_type": w, "lift_pct": round(l, 3)} for w, l in winners],
        },
    }

    if store is not None:
        # show experiments feeding the E13.4.1 memory
        try:
            from monetization.learning.feedback_engine import FeedbackEngine
            fe = FeedbackEngine(store)
            rep = fe.generate_report()
            report["memory_feed"] = {
                "records_total": rep["records_total"],
                "closed_loop_samples": rep["closed_loop_samples"],
                "strategy_performance": rep["strategy_performance"],
            }
        except Exception as ex:  # pragma: no cover - defensive
            report["memory_feed"] = {"error": str(ex)}

    return report
