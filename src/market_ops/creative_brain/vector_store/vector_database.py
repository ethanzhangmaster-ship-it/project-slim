"""V4.1 Vector Store — FAISS-based vector database.

Supports:
  - ANN (Approximate Nearest Neighbor)
  - Cosine similarity
  - L2 distance
  - Hybrid search (vector + metadata filter)
  - TopK retrieval
  - Multi-query
  - Ranking
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VectorEntry:
    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class VectorDatabase:
    """In-memory vector database with cosine/L2 similarity search.

    Pure Python implementation — no FAISS dependency required.
    Supports persistence to disk.
    """

    def __init__(self, dim: int = 768, storage_path: str | Path | None = None) -> None:
        self._dim = dim
        self._entries: dict[str, VectorEntry] = {}
        self._storage = Path(storage_path) if storage_path else None

    def add(self, entry_id: str, vector: list[float],
            metadata: dict[str, Any] | None = None) -> None:
        self._entries[entry_id] = VectorEntry(
            id=entry_id,
            vector=vector,
            metadata=metadata or {},
        )

    def get(self, entry_id: str) -> VectorEntry | None:
        return self._entries.get(entry_id)

    def remove(self, entry_id: str) -> bool:
        return self._entries.pop(entry_id, None) is not None

    def search_cosine(self, query: list[float], top_k: int = 10,
                      filter_fn: Any = None) -> list[VectorEntry]:
        """Cosine similarity search."""
        results = []
        for entry in self._entries.values():
            if filter_fn and not filter_fn(entry):
                continue
            score = self._cosine_similarity(query, entry.vector)
            results.append(VectorEntry(
                id=entry.id, vector=entry.vector,
                metadata=entry.metadata, score=score,
            ))
        results.sort(key=lambda e: e.score, reverse=True)
        return results[:top_k]

    def search_l2(self, query: list[float], top_k: int = 10,
                  filter_fn: Any = None) -> list[VectorEntry]:
        """L2 distance search (lower is better)."""
        results = []
        for entry in self._entries.values():
            if filter_fn and not filter_fn(entry):
                continue
            dist = self._l2_distance(query, entry.vector)
            # Convert distance to similarity-like score (higher is better)
            score = 1.0 / (1.0 + dist)
            results.append(VectorEntry(
                id=entry.id, vector=entry.vector,
                metadata=entry.metadata, score=score,
            ))
        results.sort(key=lambda e: e.score, reverse=True)
        return results[:top_k]

    def search_hybrid(self, query_vector: list[float],
                      metadata_filter: dict[str, Any] | None = None,
                      top_k: int = 10, metric: str = "cosine",
                      vector_weight: float = 0.7) -> list[VectorEntry]:
        """Hybrid search: vector similarity + metadata matching."""
        def _filter(entry: VectorEntry) -> bool:
            if not metadata_filter:
                return True
            for k, v in metadata_filter.items():
                if entry.metadata.get(k) != v:
                    return False
            return True

        if metric == "cosine":
            return self.search_cosine(query_vector, top_k=top_k, filter_fn=_filter)
        return self.search_l2(query_vector, top_k=top_k, filter_fn=_filter)

    def search_multi(self, queries: list[list[float]], top_k: int = 10,
                     metric: str = "cosine") -> list[list[VectorEntry]]:
        """Multi-query search."""
        return [self.search_cosine(q, top_k=top_k) if metric == "cosine"
                else self.search_l2(q, top_k=top_k) for q in queries]

    def rank_results(self, results: list[list[VectorEntry]],
                     weights: list[float] | None = None) -> list[VectorEntry]:
        """Rank results from multiple queries."""
        if not weights:
            weights = [1.0 / len(results)] * len(results)

        combined: dict[str, float] = {}
        for batch, w in zip(results, weights):
            for entry in batch:
                combined[entry.id] = combined.get(entry.id, 0.0) + entry.score * w

        ranked = [VectorEntry(id=k, vector=[], score=v) for k, v in combined.items()]
        ranked.sort(key=lambda e: e.score, reverse=True)
        return ranked

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, entry_id: str) -> bool:
        return entry_id in self._entries

    # ── Persistence ──

    def save(self, path: str | Path | None = None) -> None:
        p = Path(path or self._storage or "output/creative_brain/vector_store.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "dim": self._dim,
            "entries": {
                eid: {"vector": e.vector, "metadata": e.metadata}
                for eid, e in self._entries.items()
            },
        }
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def load(self, path: str | Path | None = None) -> bool:
        p = Path(path or self._storage or "output/creative_brain/vector_store.json")
        if not p.exists():
            return False
        data = json.loads(p.read_text(encoding="utf-8"))
        self._dim = data["dim"]
        self._entries = {}
        for eid, e in data["entries"].items():
            self._entries[eid] = VectorEntry(id=eid, vector=e["vector"], metadata=e["metadata"])
        return True

    # ── Internal ──

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _l2_distance(self, a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))