"""V4.1.1 Recall — evaluation metrics for retrieval quality.

Measures:
  - Recall@K (how many relevant items are found in top K)
  - Precision@K (how many of top K are relevant)
  - MRR (Mean Reciprocal Rank — where is the first relevant item?)
  - NDCG@K (Normalized Discounted Cumulative Gain)
  - Hit Rate (does at least one relevant item appear?)
"""

from __future__ import annotations

import math
from typing import Any


class RecallTracker:
    """Tracks and computes retrieval evaluation metrics."""

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []

    def record(self, query: str, retrieved_ids: list[str],
               relevant_ids: list[str], relevance_scores: dict[str, float] | None = None) -> None:
        """Record a single retrieval evaluation."""
        self._history.append({
            "query": query,
            "retrieved": retrieved_ids,
            "relevant": relevant_ids,
            "relevance": relevance_scores or {},
        })

    def recall_at_k(self, k: int = 10) -> float:
        """Compute average Recall@K across all recorded queries."""
        if not self._history:
            return 0.0
        total = 0.0
        for h in self._history:
            retrieved = set(h["retrieved"][:k])
            relevant = set(h["relevant"])
            if relevant:
                total += len(retrieved & relevant) / len(relevant)
        return total / len(self._history)

    def precision_at_k(self, k: int = 10) -> float:
        """Compute average Precision@K."""
        if not self._history:
            return 0.0
        total = 0.0
        for h in self._history:
            retrieved = set(h["retrieved"][:k])
            relevant = set(h["relevant"])
            if retrieved:
                total += len(retrieved & relevant) / len(retrieved)
        return total / len(self._history)

    def mrr(self) -> float:
        """Compute Mean Reciprocal Rank."""
        if not self._history:
            return 0.0
        total = 0.0
        for h in self._history:
            relevant = set(h["relevant"])
            for rank, rid in enumerate(h["retrieved"]):
                if rid in relevant:
                    total += 1.0 / (rank + 1)
                    break
        return total / len(self._history)

    def ndcg_at_k(self, k: int = 20) -> float:
        """Compute NDCG@K."""
        if not self._history:
            return 0.0
        total = 0.0
        for h in self._history:
            relevance = h.get("relevance", {})
            if not relevance:
                continue

            # DCG
            dcg = 0.0
            for rank, rid in enumerate(h["retrieved"][:k]):
                rel = relevance.get(rid, 0)
                if rel > 0:
                    dcg += rel / math.log2(rank + 2)

            # IDCG
            ideal_rels = sorted(relevance.values(), reverse=True)[:k]
            idcg = 0.0
            for i, rel in enumerate(ideal_rels):
                if rel > 0:
                    idcg += rel / math.log2(i + 2)

            total += dcg / max(idcg, 0.001)

        return total / max(len(self._history), 1)

    def hit_rate(self, k: int = 10) -> float:
        """Compute hit rate (at least one relevant in top K)."""
        if not self._history:
            return 0.0
        total = 0.0
        for h in self._history:
            retrieved = set(h["retrieved"][:k])
            relevant = set(h["relevant"])
            if retrieved & relevant:
                total += 1.0
        return total / len(self._history)

    def summary(self) -> dict[str, float]:
        """Return a summary of all metrics."""
        return {
            "recall@5": self.recall_at_k(5),
            "recall@10": self.recall_at_k(10),
            "recall@20": self.recall_at_k(20),
            "precision@10": self.precision_at_k(10),
            "mrr": self.mrr(),
            "ndcg@20": self.ndcg_at_k(20),
            "hit_rate@10": self.hit_rate(10),
            "total_queries": len(self._history),
        }