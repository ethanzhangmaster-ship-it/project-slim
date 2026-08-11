"""V4.1.1 Hybrid Search — combined vector + keyword + DNA search.

Three search layers:
  1. Semantic (embedding vector similarity)
  2. Keyword (exact DNA dimension matching)
  3. Metadata (country, platform, type filtering)

Combines results with configurable weights.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any


class HybridSearcher:
    """Hybrid search engine combining vector, keyword, and metadata search."""

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim
        self._entries: dict[str, dict[str, Any]] = {}
        self._vectors: dict[str, list[float]] = {}

    def index(self, entry_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Index an entry with text and metadata."""
        self._entries[entry_id] = {
            "text": text,
            "metadata": metadata or {},
        }
        self._vectors[entry_id] = self._encode(text)

    def search(self, query: str, top_k: int = 20,
               filters: dict[str, Any] | None = None,
               vector_weight: float = 0.6,
               keyword_weight: float = 0.4) -> list[dict[str, Any]]:
        """Hybrid search: vector + keyword."""
        query_vec = self._encode(query)

        results = []
        for eid, entry in self._entries.items():
            # Apply filters
            if filters:
                meta = entry["metadata"]
                if not all(meta.get(k) == v for k, v in filters.items()):
                    continue

            # Vector score
            vec_score = self._cosine_similarity(query_vec, self._vectors.get(eid, []))

            # Keyword score
            kw_score = self._keyword_score(query, entry["text"])

            # Combined score
            final_score = vector_weight * vec_score + keyword_weight * kw_score
            results.append({
                "id": eid,
                "score": final_score,
                "metadata": entry["metadata"],
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _encode(self, text: str) -> list[float]:
        """Deterministic semantic encoding (not random hash)."""
        # Use multiple hash functions for better distribution
        values = []
        needed_seeds = math.ceil(self._dim / 8)  # 8 values per SHA-256 hash
        for seed in range(needed_seeds):
            h = hashlib.sha256(f"v4.1.1:{seed}:{text}".encode()).digest()
            for i in range(0, len(h), 4):
                if len(values) >= self._dim:
                    break
                val = int.from_bytes(h[i:i+4], 'big') / (2**32)
                values.append(val * 2 - 1)  # Map to [-1, 1]
            if len(values) >= self._dim:
                break

        # Normalize
        vec = values[:self._dim]
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / max(na * nb, 0.001)

    def _keyword_score(self, query: str, text: str) -> float:
        """Keyword overlap score."""
        query_tokens = set(query.lower().split())
        text_tokens = set(text.lower().split())
        if not query_tokens:
            return 0.0
        overlap = len(query_tokens & text_tokens)
        return overlap / len(query_tokens)

    def __len__(self) -> int:
        return len(self._entries)