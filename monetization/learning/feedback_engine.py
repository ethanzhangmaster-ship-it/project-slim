"""
E13.4.1 — Module 4: Feedback Engine
====================================

Turns the accumulated DecisionRecords into **strategy priors** — the first
statistical asset the future E13.4.3 AI Strategy Ranking will fuse with rules
and simulation. No ML library; just aggregations over closed-loop samples.

Outputs:
  * per-strategy success rate, avg predicted vs actual revenue, avg error/bias
  * per-segment performance (optional)
  * overall prediction-error statistics (calibration of the E13.2.9 simulator)
  * a `strategy_prior` in [0,1] = smoothed success rate, ready to fuse later
  * a full `Strategy Performance Report` (the E13.4.1 acceptance artifact)

The prior is deliberately conservative: with few samples it is pulled toward
0.5 (uncertainty), so the system does not over-trust a single lucky run.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from monetization.learning.decision_store import DecisionStore
from monetization.learning.models import DecisionRecord


# Laplace smoothing strength for the success-rate prior.
PRIOR_STRENGTH = 2.0


def _success_rate(successes: int, total: int) -> float:
    """Laplace-smoothed success rate in [0,1] (uncertain when few samples)."""
    if total == 0:
        return 0.5
    return round((successes + PRIOR_STRENGTH * 0.5) / (total + PRIOR_STRENGTH), 4)


class FeedbackEngine:
    """Aggregates stored decisions into strategy priors + performance report."""

    def __init__(self, store: DecisionStore):
        self.store = store

    # ------------------------------------------------------------------ #
    def strategy_performance(self, strategy_type: str) -> dict:
        recs = self.store.by_strategy(strategy_type)
        return self._aggregate(recs, strategy_type)

    def segment_performance(self, segment: dict) -> dict:
        recs = self.store.by_segment(segment)
        label = "_".join(f"{k}={v}" for k, v in segment.items())
        return self._aggregate(recs, label)

    def overall(self) -> dict:
        return self._aggregate(self.store.all(), "ALL")

    # ------------------------------------------------------------------ #
    def _aggregate(self, recs: List[DecisionRecord], label: str) -> dict:
        total = len(recs)
        executed = [r for r in recs if r.execution_status == "executed"]
        closed = [r for r in recs if r.closed_loop and r.actual is not None]
        successes = sum(1 for r in closed if r.learning_signal and r.learning_signal.success)

        pred_rev = [r.prediction_revenue_delta for r in closed]
        act_rev = [r.actual.revenue_delta_pct for r in closed if r.actual]
        errs = [r.learning_signal.prediction_error_revenue for r in closed if r.learning_signal]
        biases = errs  # single-sample bias == error

        def _mean(xs):
            return round(sum(xs) / len(xs), 3) if xs else 0.0

        return {
            "label": label,
            "total_decisions": total,
            "executed": len(executed),
            "closed_loop": len(closed),
            "successes": successes,
            "success_rate": _success_rate(successes, len(closed)),
            "avg_predicted_revenue_delta": _mean(pred_rev),
            "avg_actual_revenue_delta": _mean(act_rev),
            "avg_abs_prediction_error": _mean([abs(e) for e in errs]),
            "avg_bias": _mean(biases),     # >0 => simulator systematically under-predicts
        }

    # ------------------------------------------------------------------ #
    def prediction_error_stats(self) -> dict:
        closed = self.store.closed()
        errs = [r.learning_signal.prediction_error_revenue for r in closed if r.learning_signal]
        ret_errs = [r.learning_signal.prediction_error_retention for r in closed if r.learning_signal]
        def _mean(xs):
            return round(sum(xs) / len(xs), 3) if xs else 0.0
        def _mae(xs):
            return round(sum(abs(x) for x in xs) / len(xs), 3) if xs else 0.0
        return {
            "closed_samples": len(closed),
            "revenue_mae": _mae(errs),
            "revenue_mean_bias": _mean(errs),
            "retention_mae": _mae(ret_errs),
            "retention_mean_bias": _mean(ret_errs),
            "interpretation": _interpret_bias(_mean(errs)),
        }

    # ------------------------------------------------------------------ #
    def strategy_prior(self, strategy_type: str) -> float:
        """Smoothed success-rate prior in [0,1] for E13.4.3 fusion."""
        return self.strategy_performance(strategy_type)["success_rate"]

    def priors(self) -> Dict[str, float]:
        """All known strategy types -> prior weights."""
        out = {}
        for st in sorted({r.strategy_type for r in self.store.all()}):
            out[st] = self.strategy_prior(st)
        return out

    # ------------------------------------------------------------------ #
    def generate_report(self) -> dict:
        """Full Strategy Performance Report (E13.4.1 acceptance artifact)."""
        all_types = sorted({r.strategy_type for r in self.store.all()})
        per_strategy = {st: self.strategy_performance(st) for st in all_types}
        # rank strategies by prior (desc) for the "Strategy Prior" table
        ranked = sorted(
            per_strategy.items(),
            key=lambda kv: (kv[1]["success_rate"], kv[1]["avg_actual_revenue_delta"]),
            reverse=True,
        )
        return {
            "module": "E13.4.1 Decision Memory Layer",
            "records_total": self.store.count(),
            "closed_loop_samples": len(self.store.closed()),
            "strategy_performance": per_strategy,
            "strategy_prior_ranked": [
                {"strategy_type": st, **perf} for st, perf in ranked
            ],
            "prediction_error_stats": self.prediction_error_stats(),
            "priors": self.priors(),
        }


def _interpret_bias(mean_bias: float) -> str:
    if mean_bias is None or mean_bias == 0.0:
        return "Well-calibrated (no systematic revenue bias)."
    if mean_bias > 0:
        return ("Simulator systematically UNDER-predicts revenue "
                "(actuals beat forecasts).")
    return ("Simulator systematically OVER-predicts revenue "
            "(actuals fall short of forecasts).")
