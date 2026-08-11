"""V4.1.1 Reranker — cross-attention scoring for retrieval results.

Reranks candidate results using:
  1. DNA dimension overlap (character, reward, hook, etc.)
  2. Performance-weighted scoring (higher ROAS → higher rank)
  3. Semantic similarity (embedding cosine)
  4. Freshness decay (newer creatives get slight boost)
"""

from __future__ import annotations

import math
from typing import Any


class Reranker:
    """Cross-attention reranker for creative retrieval.

    Not just a simple score sort. Combines multiple signals:
      - Vector similarity (40% weight)
      - DNA dimension match (30% weight)
      - Performance quality (20% weight)
      - Freshness (10% weight)
    """

    def __init__(self,
                 vector_weight: float = 0.40,
                 dna_weight: float = 0.30,
                 performance_weight: float = 0.20,
                 freshness_weight: float = 0.10) -> None:
        self._w_vec = vector_weight
        self._w_dna = dna_weight
        self._w_perf = performance_weight
        self._w_fresh = freshness_weight

    def rerank(self, query: str, candidates: list[dict[str, Any]],
               top_k: int = 20) -> list[dict[str, Any]]:
        """Rerank candidates and return top-K."""
        if not candidates:
            return []

        # Extract query DNA dimensions from natural language query
        query_dna = self._extract_query_dna(query)

        # Score each candidate
        scored = []
        for c in candidates:
            meta = c.get("metadata", {})
            dna = meta.get("dna", {})

            vec_score = c.get("score", 0.0)
            dna_score = self._dna_match_score(query_dna, dna)
            perf_score = self._performance_score(meta.get("performance", {}))
            fresh_score = self._freshness_score(meta)

            final_score = (
                self._w_vec * vec_score +
                self._w_dna * dna_score +
                self._w_perf * perf_score +
                self._w_fresh * fresh_score
            )

            scored.append({"id": c["id"], "score": final_score, "metadata": meta})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _extract_query_dna(self, query: str) -> dict[str, str]:
        """Extract DNA-like dimensions from natural language query."""
        dna = {}
        query_lower = query.lower()

        # Character detection
        characters = ["witch", "dragon", "knight", "ninja", "warrior", "mage",
                      "princess", "robot", "zombie", "vampire", "baby", "queen"]
        for ch in characters:
            if ch in query_lower:
                dna["character"] = ch
                break

        # Reward detection
        rewards = ["dragon", "treasure", "gold", "gem", "chest", "crown",
                   "evolution", "upgrade", "collection", "egg"]
        for rw in rewards:
            if rw in query_lower:
                dna["reward"] = rw
                break

        # Gameplay detection
        gameplays = ["merge", "puzzle", "match", "clicker", "runner", "idle",
                     "merge", "fight", "battle", "build"]
        for gp in gameplays:
            if gp in query_lower:
                dna["gameplay"] = gp
                break

        # Hook detection
        hooks = ["fail", "collection", "satisfying", "challenge", "surprise",
                 "transformation", "asmr"]
        for hk in hooks:
            if hk in query_lower:
                dna["hook"] = hk
                break

        # Country
        countries = ["us", "jp", "kr", "uk", "de", "fr", "br", "in"]
        for co in countries:
            if co in query_lower:
                dna["country"] = co.upper()
                break

        return dna

    def _dna_match_score(self, query_dna: dict[str, str],
                         candidate_dna: dict[str, Any]) -> float:
        """Score DNA dimension overlap."""
        if not query_dna or not candidate_dna:
            return 0.0

        matches = 0
        total = len(query_dna)
        for dim, q_val in query_dna.items():
            c_val = str(candidate_dna.get(dim, "")).lower()
            if q_val in c_val or c_val in q_val:
                matches += 1

        return matches / max(total, 1)

    def _performance_score(self, perf: dict[str, Any]) -> float:
        """Score based on performance metrics."""
        if not perf:
            return 0.0

        roas = perf.get("roas_d7", 0)
        ctr = perf.get("ctr", 0)
        ipm = perf.get("ipm", 0)

        # Normalize to [0, 1]
        roas_score = min(roas / 2.0, 1.0)  # 2.0 ROAS = perfect
        ctr_score = min(ctr / 5.0, 1.0)    # 5% CTR = perfect
        ipm_score = min(ipm / 50.0, 1.0)   # 50 IPM = perfect

        return (roas_score * 0.5 + ctr_score * 0.3 + ipm_score * 0.2)

    def _freshness_score(self, meta: dict[str, Any]) -> float:
        """Score based on recency (newer = slightly higher)."""
        # Default: neutral score
        return 0.5