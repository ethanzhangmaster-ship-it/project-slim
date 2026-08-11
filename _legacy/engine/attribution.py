"""Soft Attribution — Top-K similarity-weighted probabilistic attribution.

Each FB video is assigned to clusters via:
  P(cluster | video) = softmax(similarity_to_cluster_members)

Output:
  dict of {cluster_id: probability} summing to 1.
"""
from collections import Counter
import numpy as np


class SoftAttributor:
    """Probabilistic attribution via Top-K similarity voting."""

    def __init__(self, k: int = 20, threshold: float = 0.1):
        self.k = k
        self.threshold = threshold

    def attribute(self, similarity_matrix: np.ndarray, top_indices: np.ndarray,
                  idx_to_cluster: dict) -> list:
        """Soft assignment for all FB videos.

        Args:
            similarity_matrix: (N_fb, K) similarity scores
            top_indices: (N_fb, K) Eagle index IDs
            idx_to_cluster: {index_id: cluster_id} mapping

        Returns:
            list[dict]: each dict {cluster_id: probability, ...}
        """
        results = []
        for i in range(len(similarity_matrix)):
            sims = similarity_matrix[i]
            idxs = top_indices[i]
            weights = {}

            for j in range(len(sims)):
                if sims[j] < self.threshold:
                    continue
                idx = int(idxs[j])
                cid = idx_to_cluster.get(idx, "Noise")
                weights[cid] = weights.get(cid, 0) + float(sims[j])

            # Normalize to probabilities
            total = sum(weights.values())
            if total > 0:
                weights = {k: round(v / total, 4) for k, v in
                           sorted(weights.items(), key=lambda x: -x[1])}
            else:
                weights = {"Noise": 1.0}

            results.append(weights)

        return results

    @staticmethod
    def best_cluster(probs: dict) -> tuple:
        """Get the highest-probability cluster from soft assignment."""
        if not probs:
            return "Noise", 0.0
        best = max(probs, key=probs.get)
        return best, probs[best]

    @staticmethod
    def top_k_clusters(probs: dict, k: int = 5) -> list:
        """Get top-K clusters by probability."""
        return sorted(probs.items(), key=lambda x: -x[1])[:k]
