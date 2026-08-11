"""
E13.4.3 — Module 5 (optional): Lightweight Model
=================================================

The first "model" in the Intelligence Layer. Per E13.4.3 the v1 should NOT use
LLM / RL / XGBoost — it should be a small, transparent, trainable estimator.

This is a **bucketed Laplace success-rate estimator**: it learns P(strategy
wins) directly from the E13.4.1 Decision Memory, using progressively specific
buckets:

    (strategy, issue, country, platform)   <- most specific
    (strategy, issue)                       <- fallback
    (strategy)                              <- fallback
    global                                  <- ultimate fallback

Each bucket is smoothed with a Beta(alpha, beta) prior so rare buckets do not
produce over-confident estimates. Pure-Python, zero external dependencies.

It is intentionally simple and explainable — a real LogisticRegression /
XGBoost / LightGBM can replace it later behind the same `predict()` interface.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from monetization.learning.decision_store import DecisionStore


class LightweightModel:
    """Trainable P(strategy wins) estimator over the decision memory."""

    def __init__(self, alpha: float = 1.0, beta: float = 1.0):
        self.alpha = alpha
        self.beta = beta
        self._global = [0, 0]                              # [wins, losses]
        self._by_strategy = defaultdict(lambda: [0, 0])
        self._by_strat_issue = defaultdict(lambda: [0, 0])
        self._by_seg = defaultdict(lambda: [0, 0])         # (st, issue, c, p)

    # ------------------------------------------------------------------ #
    def train(self, store: DecisionStore) -> "LightweightModel":
        for r in store.closed():
            st = r.strategy_type
            ok = bool(r.learning_signal and r.learning_signal.success)
            w, l = (1, 0) if ok else (0, 1)
            self._global[0] += w
            self._global[1] += l
            self._by_strategy[st][0] += w
            self._by_strategy[st][1] += l
            ki = (st, r.opportunity_type)
            self._by_strat_issue[ki][0] += w
            self._by_strat_issue[ki][1] += l
            ks = (st, r.opportunity_type,
                  r.segment.get("country"), r.segment.get("platform"))
            self._by_seg[ks][0] += w
            self._by_seg[ks][1] += l
        return self

    # ------------------------------------------------------------------ #
    @staticmethod
    def _rate(counts, a, b) -> float:
        w, l = counts
        return (w + a) / (w + l + a + b)

    def predict(self, opportunity_type: str, strategy_type: str,
                segment: dict) -> float:
        ks = (strategy_type, opportunity_type,
              segment.get("country"), segment.get("platform"))
        if ks in self._by_seg and sum(self._by_seg[ks]) > 4:
            return self._rate(self._by_seg[ks], self.alpha, self.beta)
        ki = (strategy_type, opportunity_type)
        if ki in self._by_strat_issue and sum(self._by_strat_issue[ki]) > 4:
            return self._rate(self._by_strat_issue[ki], self.alpha, self.beta)
        if strategy_type in self._by_strategy and sum(self._by_strategy[strategy_type]) > 4:
            return self._rate(self._by_strategy[strategy_type], self.alpha, self.beta)
        return self._rate(self._global, self.alpha, self.beta)

    def predict_all(self, opportunity_type: str, segment: dict,
                    strategy_types: List[str]) -> Dict[str, float]:
        return {st: round(self.predict(opportunity_type, st, segment), 4)
                for st in strategy_types}
