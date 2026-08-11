"""
E13.4.3 — Module 2: Strategy Prior Engine (Bayesian Beta Prior)
==============================================================

Computes a *prior* success-rate per strategy from the system's own operating
history, so the ranker can fuse "what has worked before" with "what the
simulator predicts now".

Two evidence sources (per E13.4.3 design):
  1. E13.4.1 Decision Memory  — closed-loop records (success / fail).
  2. E13.4.2 Experiment Result — each experiment arm is one causal win/lose
     sample for its `strategy_type`.

Bayesian Beta prior:
    alpha = wins   + 1     (pseudo-count for a flat Beta(1,1) prior)
    beta  = losses + 1
    mean  = alpha / (alpha + beta)

So 20 wins / 5 losses -> alpha=21, beta=6 -> mean = 21/27 = 0.777...  (the
PRD's illustrative 0.78). With zero data the mean is 0.5 (uncertain -> the
system does not over-trust a single lucky run).

No ML library; pure aggregation over DecisionRecords / ExperimentResults.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from monetization.learning.decision_store import DecisionStore
from monetization.experiments.models import ExperimentResult


class StrategyPriorEngine:
    """Aggregates strategy outcomes into Beta(alpha, beta) priors."""

    def __init__(self):
        self._wins: Dict[str, int] = defaultdict(int)
        self._losses: Dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------ #
    def add_outcome(self, strategy_type: str, success: bool) -> None:
        if success:
            self._wins[strategy_type] += 1
        else:
            self._losses[strategy_type] += 1

    def learn_from_store(self, store: DecisionStore) -> "StrategyPriorEngine":
        """Ingest closed-loop DecisionRecords (the E13.4.1 memory)."""
        for r in store.closed():
            st = r.strategy_type
            if not st:
                continue
            ok = bool(r.learning_signal and r.learning_signal.success)
            self.add_outcome(st, ok)
        return self

    def learn_from_experiments(self, results: List[ExperimentResult]) -> "StrategyPriorEngine":
        """Ingest A/B/n experiment arms (the E13.4.2 causal evidence).

        Each arm becomes one sample: the winning arm is a `success` for its
        strategy_type; every non-winning treatment arm is a `fail`.
        """
        for res in results:
            variants = res.per_variant or {}
            for vid, vm in variants.items():
                st = vm.get("strategy_type") or ""
                if not st:
                    continue
                is_winner = (vid == res.winner_variant_id)
                self.add_outcome(st, is_winner)
        return self

    # ------------------------------------------------------------------ #
    def alpha_beta(self, strategy_type: str):
        w = self._wins.get(strategy_type, 0)
        l = self._losses.get(strategy_type, 0)
        return w + 1, l + 1          # flat Beta(1,1) prior

    def prior(self, strategy_type: str) -> dict:
        a, b = self.alpha_beta(strategy_type)
        return {
            "strategy_type": strategy_type,
            "alpha": a,
            "beta": b,
            "mean": round(a / (a + b), 4),
            "samples": a + b - 2,    # minus the 2 pseudo-counts
            "wins": self._wins.get(strategy_type, 0),
            "losses": self._losses.get(strategy_type, 0),
        }

    def prior_map(self) -> Dict[str, float]:
        """strategy_type -> prior mean (for the feature builder's history map)."""
        out = {}
        for st in set(list(self._wins) + list(self._losses)):
            out[st] = self.prior(st)["mean"]
        return out

    def all_priors(self) -> List[dict]:
        return [self.prior(st)
                for st in sorted(set(list(self._wins) + list(self._losses)))]
