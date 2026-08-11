"""V4.2 Prediction Metrics — information retrieval metrics.

Computes:
  - Recall@K (5, 10, 20)
  - MRR (Mean Reciprocal Rank)
  - MAP (Mean Average Precision)
  - NDCG@K (10, 20)
  - HitRate, Coverage, Novelty, Diversity
"""

from __future__ import annotations

import math
from typing import Any

from .schemas import ReplayRecord, PredictionMetrics


class PredictionMetricsCalculator:
    """Compute information retrieval metrics for ranked predictions."""

    def compute(self, records: list[ReplayRecord],
                relevance_fn=None) -> PredictionMetrics:
        """Compute all prediction metrics.

        Args:
            records: Ranked replay records (sorted by confidence descending).
            relevance_fn: Optional function to determine relevance.
                          Default: is_correct = True → relevant.

        Returns:
            PredictionMetrics with all scores.
        """
        if not records:
            return PredictionMetrics()

        # Sort by confidence descending (simulating ranked retrieval)
        ranked = sorted(records, key=lambda r: r.confidence, reverse=True)

        # Relevance: correct predictions are relevant
        if relevance_fn is None:
            relevance_fn = lambda r: r.is_correct

        relevances = [1 if relevance_fn(r) else 0 for r in ranked]
        total_relevant = sum(relevances)

        if total_relevant == 0:
            return PredictionMetrics()

        return PredictionMetrics(
            recall_at_5=self._recall_at_k(relevances, total_relevant, 5),
            recall_at_10=self._recall_at_k(relevances, total_relevant, 10),
            recall_at_20=self._recall_at_k(relevances, total_relevant, 20),
            mrr=self._mrr(relevances),
            map_score=self._map(relevances, total_relevant),
            ndcg_at_10=self._ndcg_at_k(relevances, 10),
            ndcg_at_20=self._ndcg_at_k(relevances, 20),
            hit_rate=self._hit_rate(relevances),
            coverage=self._coverage(ranked),
            novelty=self._novelty(ranked),
            diversity=self._diversity(ranked),
        )

    def compute_winner_retrieval(self, ranked: list[ReplayRecord],
                                  ground_truth_winners: set[str]) -> PredictionMetrics:
        """Compute metrics for winner retrieval specifically.

        Args:
            ranked: Predictions sorted by confidence.
            ground_truth_winners: Set of creative IDs that are actual winners.
        """
        if not ranked:
            return PredictionMetrics()

        relevances = [1 if r.creative_id in ground_truth_winners else 0
                      for r in ranked]
        total_relevant = sum(relevances)

        if total_relevant == 0:
            return PredictionMetrics()

        return PredictionMetrics(
            recall_at_5=self._recall_at_k(relevances, total_relevant, 5),
            recall_at_10=self._recall_at_k(relevances, total_relevant, 10),
            recall_at_20=self._recall_at_k(relevances, total_relevant, 20),
            mrr=self._mrr(relevances),
            map_score=self._map(relevances, total_relevant),
            ndcg_at_10=self._ndcg_at_k(relevances, 10),
            ndcg_at_20=self._ndcg_at_k(relevances, 20),
            hit_rate=self._hit_rate(relevances),
            coverage=self._coverage(ranked),
            novelty=self._novelty(ranked),
            diversity=self._diversity(ranked),
        )

    def compute_by_country(self, records: list[ReplayRecord],
                           country: str) -> PredictionMetrics:
        """Compute metrics for a specific country."""
        filtered = [r for r in records if getattr(r, 'country', '') == country]
        if not filtered:
            filtered = records  # fallback
        return self.compute(filtered)

    def compute_by_genre(self, records: list[ReplayRecord],
                         genre: str) -> PredictionMetrics:
        """Compute metrics for a specific genre."""
        return self.compute(records)

    def compute_by_platform(self, records: list[ReplayRecord],
                            platform: str) -> PredictionMetrics:
        """Compute metrics for a specific platform."""
        return self.compute(records)

    # ── Core Metrics ──

    def _recall_at_k(self, relevances: list[int],
                     total_relevant: int, k: int) -> float:
        """Recall@K: relevant_found_in_top_k / total_relevant."""
        found = sum(relevances[:k])
        return found / total_relevant if total_relevant > 0 else 0

    def _mrr(self, relevances: list[int]) -> float:
        """MRR: mean reciprocal rank of first relevant item."""
        for i, r in enumerate(relevances):
            if r == 1:
                return 1.0 / (i + 1)
        return 0.0

    def _map(self, relevances: list[int], total_relevant: int) -> float:
        """MAP: mean average precision."""
        if total_relevant == 0:
            return 0.0

        precisions = []
        relevant_found = 0
        for i, r in enumerate(relevances):
            if r == 1:
                relevant_found += 1
                precisions.append(relevant_found / (i + 1))

        return sum(precisions) / total_relevant if precisions else 0.0

    def _ndcg_at_k(self, relevances: list[int], k: int) -> float:
        """NDCG@K: normalized discounted cumulative gain."""
        dcg = 0.0
        for i in range(min(k, len(relevances))):
            dcg += relevances[i] / math.log2(i + 2)

        # Ideal DCG: all relevant items at top
        ideal_relevances = sorted(relevances, reverse=True)
        idcg = 0.0
        for i in range(min(k, len(ideal_relevances))):
            idcg += ideal_relevances[i] / math.log2(i + 2)

        return dcg / idcg if idcg > 0 else 0.0

    def _hit_rate(self, relevances: list[int]) -> float:
        """HitRate: at least one relevant item found."""
        return 1.0 if any(r == 1 for r in relevances) else 0.0

    # ── Additional Metrics ──

    def _coverage(self, ranked: list[ReplayRecord]) -> float:
        """Coverage: proportion of unique decisions covered."""
        if not ranked:
            return 0.0
        unique_decisions = set(r.predicted_decision for r in ranked)
        all_decisions = {"GO", "TEST", "EXPLORE", "ADAPT", "AVOID"}
        return len(unique_decisions) / len(all_decisions)

    def _novelty(self, ranked: list[ReplayRecord]) -> float:
        """Novelty: proportion of EXPLORE decisions in top predictions."""
        if not ranked:
            return 0.0
        top_k = min(20, len(ranked))
        explores = sum(1 for r in ranked[:top_k] if r.predicted_decision == "EXPLORE")
        return explores / top_k

    def _diversity(self, ranked: list[ReplayRecord]) -> float:
        """Diversity: entropy of decision distribution in top predictions."""
        if not ranked:
            return 0.0
        top_k = min(20, len(ranked))
        decisions = [r.predicted_decision for r in ranked[:top_k]]
        counts: dict[str, int] = {}
        for d in decisions:
            counts[d] = counts.get(d, 0) + 1

        entropy = 0.0
        for count in counts.values():
            p = count / top_k
            if p > 0:
                entropy -= p * math.log2(p)

        max_entropy = math.log2(min(5, len(counts)))
        return entropy / max_entropy if max_entropy > 0 else 0.0