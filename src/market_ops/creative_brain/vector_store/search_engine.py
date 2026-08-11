"""V4.1 Search Engine — unified search interface for Creative Brain.

Combines vector search with metadata filtering for:
  - Similar creative search
  - Similar prompt search
  - Similar DNA search
  - Similar gameplay search
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .vector_database import VectorDatabase, VectorEntry


@dataclass
class SearchResult:
    id: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    creative_type: str = ""
    source: str = ""


class SearchEngine:
    """Unified search engine for Creative Brain.

    Usage:
        engine = SearchEngine()
        engine.index_creative("c001", vector, {"type": "image"})
        results = engine.search_similar(query_vector, top_k=10)
    """

    def __init__(self, dim: int = 768) -> None:
        self._db = VectorDatabase(dim=dim)
        self._index_name: dict[str, str] = {}  # entry_id -> index_type

    def index_creative(self, creative_id: str, vector: list[float],
                       metadata: dict[str, Any] | None = None) -> None:
        meta = metadata or {}
        meta["_index_type"] = "creative"
        self._db.add(creative_id, vector, meta)
        self._index_name[creative_id] = "creative"

    def index_prompt(self, prompt_id: str, vector: list[float],
                     metadata: dict[str, Any] | None = None) -> None:
        meta = metadata or {}
        meta["_index_type"] = "prompt"
        self._db.add(prompt_id, vector, meta)
        self._index_name[prompt_id] = "prompt"

    def index_dna(self, dna_id: str, vector: list[float],
                  metadata: dict[str, Any] | None = None) -> None:
        meta = metadata or {}
        meta["_index_type"] = "dna"
        self._db.add(dna_id, vector, meta)
        self._index_name[dna_id] = "dna"

    def search_similar(self, query_vector: list[float], top_k: int = 10,
                       index_type: str = "", metric: str = "cosine",
                       metadata_filter: dict[str, Any] | None = None) -> list[SearchResult]:
        """Search for similar entries."""
        def _filter(entry: VectorEntry) -> bool:
            if index_type and entry.metadata.get("_index_type") != index_type:
                return False
            if metadata_filter:
                for k, v in metadata_filter.items():
                    if entry.metadata.get(k) != v:
                        return False
            return True

        if metric == "l2":
            entries = self._db.search_l2(query_vector, top_k=top_k, filter_fn=_filter)
        else:
            entries = self._db.search_cosine(query_vector, top_k=top_k, filter_fn=_filter)

        return [
            SearchResult(
                id=e.id, score=e.score, metadata=e.metadata,
                creative_type=e.metadata.get("creative_type", ""),
                source=e.metadata.get("_index_type", ""),
            )
            for e in entries
        ]

    def search_similar_creative(self, query_vector: list[float],
                                top_k: int = 10) -> list[SearchResult]:
        return self.search_similar(query_vector, top_k=top_k, index_type="creative")

    def search_similar_prompt(self, query_vector: list[float],
                              top_k: int = 10) -> list[SearchResult]:
        return self.search_similar(query_vector, top_k=top_k, index_type="prompt")

    def search_similar_dna(self, query_vector: list[float],
                           top_k: int = 10) -> list[SearchResult]:
        return self.search_similar(query_vector, top_k=top_k, index_type="dna")

    def search_multi_query(self, query_vectors: list[list[float]],
                           top_k: int = 10) -> list[list[SearchResult]]:
        return [self.search_similar(qv, top_k=top_k) for qv in query_vectors]

    def rank_results(self, result_batches: list[list[SearchResult]],
                     weights: list[float] | None = None) -> list[SearchResult]:
        if not weights:
            weights = [1.0 / len(result_batches)] * len(result_batches)

        combined: dict[str, float] = {}
        meta_store: dict[str, dict] = {}
        for batch, w in zip(result_batches, weights):
            for r in batch:
                combined[r.id] = combined.get(r.id, 0.0) + r.score * w
                meta_store[r.id] = r.metadata

        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return [
            SearchResult(id=k, score=v, metadata=meta_store.get(k, {}))
            for k, v in ranked
        ]

    def __len__(self) -> int:
        return len(self._db)