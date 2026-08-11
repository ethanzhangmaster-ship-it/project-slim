"""V4.1.1 Creative Retriever — the core retrieval engine of Creative Brain.

Not a keyword search. Not a hash lookup. A real semantic retrieval system:

  1. Encode query into embedding vector
  2. Search across Creative / DNA / Prompt / Performance indexes
  3. Rerank with cross-attention scoring
  4. Hybrid search: vector + metadata + DNA dimensions
  5. Return ranked results with recall metrics

Usage:
    retriever = CreativeRetriever()
    retriever.index_creative("c001", creative_data, dna_data)
    results = retriever.retrieve("dragon merge game ad", top_k=20)
    # results[0] = {"creative_id": "c042", "score": 0.92, "dna": {...}}
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .hybrid_search import HybridSearcher
from .reranker import Reranker
from .recall import RecallTracker


@dataclass
class RetrievalResult:
    """A single retrieval result with full context."""
    creative_id: str = ""
    score: float = 0.0
    dna: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    relevance_labels: list[str] = field(default_factory=list)
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "score": round(self.score, 4),
            "dna": self.dna,
            "performance": self.performance,
            "prompt": self.prompt[:200] if self.prompt else "",
            "relevance_labels": self.relevance_labels,
            "rank": self.rank,
        }


class CreativeRetriever:
    """The core retrieval engine for Creative Brain.

    Retrieves creatives by:
      - Semantic similarity (embedding)
      - DNA dimension matching (character, reward, hook, etc.)
      - Performance filtering (ROAS, CTR, IPM thresholds)
      - Metadata filtering (country, platform, type)

    The retriever is the foundation of all Planner decisions.
    """

    def __init__(self, dim: int = 768) -> None:
        self._hybrid = HybridSearcher(dim=dim)
        self._reranker = Reranker()
        self._recall = RecallTracker()
        self._creative_store: dict[str, dict[str, Any]] = {}
        self._dna_store: dict[str, dict[str, Any]] = {}

    # ── Indexing ──

    def index_creative(self, creative_id: str, creative_data: dict[str, Any],
                       dna_data: dict[str, Any] | None = None,
                       performance: dict[str, Any] | None = None,
                       prompt: str = "") -> None:
        """Index a creative into the retriever."""
        self._creative_store[creative_id] = {
            "data": creative_data,
            "performance": performance or {},
            "prompt": prompt,
        }
        if dna_data:
            self._dna_store[creative_id] = dna_data

        # Build text for embedding
        text = self._build_index_text(creative_data, dna_data, prompt)
        self._hybrid.index(creative_id, text, {
            "creative_type": creative_data.get("creative_type", "image"),
            "country": creative_data.get("country", ""),
            "platform": creative_data.get("platform", "facebook"),
            "dna": dna_data or {},
            "performance": performance or {},
        })

    def index_batch(self, items: list[dict[str, Any]]) -> int:
        """Index multiple creatives at once."""
        count = 0
        for item in items:
            self.index_creative(
                creative_id=item.get("creative_id", ""),
                creative_data=item.get("data", {}),
                dna_data=item.get("dna"),
                performance=item.get("performance"),
                prompt=item.get("prompt", ""),
            )
            count += 1
        return count

    # ── Retrieval ──

    def retrieve(self, query: str, top_k: int = 20,
                 filters: dict[str, Any] | None = None,
                 min_roas: float = 0.0,
                 creative_type: str = "",
                 country: str = "") -> list[RetrievalResult]:
        """Retrieve top-K creatives for a query.

        Args:
            query: Natural language query (e.g., "dragon merge game for US")
            top_k: Number of results
            filters: Additional metadata filters
            min_roas: Minimum ROAS D7 threshold
            creative_type: Filter by "image" or "video"
            country: Filter by country code
        """
        # 1. Hybrid search (vector + keyword + DNA)
        candidates = self._hybrid.search(query, top_k=top_k * 3, filters=filters)

        # 2. Apply performance filters
        filtered = []
        for c in candidates:
            perf = c.get("metadata", {}).get("performance", {})
            ct = c.get("metadata", {}).get("creative_type", "")
            co = c.get("metadata", {}).get("country", "")

            if min_roas > 0 and perf.get("roas_d7", 0) < min_roas:
                continue
            if creative_type and ct != creative_type:
                continue
            if country and co != country:
                continue
            filtered.append(c)

        # 3. Rerank with cross-attention scoring
        reranked = self._reranker.rerank(query, filtered, top_k=top_k)

        # 4. Build results
        results = []
        for rank, item in enumerate(reranked):
            cid = item["id"]
            creative = self._creative_store.get(cid, {})
            dna = self._dna_store.get(cid, {})
            results.append(RetrievalResult(
                creative_id=cid,
                score=item["score"],
                dna=dna,
                performance=creative.get("performance", {}),
                prompt=creative.get("prompt", ""),
                rank=rank + 1,
            ))

        return results

    def retrieve_by_dna(self, dna_query: dict[str, Any], top_k: int = 20) -> list[RetrievalResult]:
        """Retrieve by DNA dimensions (character, reward, hook, etc.)."""
        query_text = " ".join(
            f"{k}:{v}" for k, v in dna_query.items() if v
        )
        return self.retrieve(query_text, top_k=top_k)

    def retrieve_winners(self, query: str, top_k: int = 20,
                         min_roas: float = 0.5) -> list[RetrievalResult]:
        """Retrieve only winning creatives."""
        return self.retrieve(query, top_k=top_k, min_roas=min_roas)

    def retrieve_similar(self, creative_id: str, top_k: int = 20) -> list[RetrievalResult]:
        """Find creatives similar to a given creative."""
        dna = self._dna_store.get(creative_id, {})
        if not dna:
            return []
        return self.retrieve_by_dna(dna, top_k=top_k)

    # ── Recall Evaluation ──

    def evaluate_recall(self, queries: list[dict[str, Any]],
                        top_k_values: list[int] | None = None) -> dict[str, float]:
        """Evaluate recall@K for a set of queries with known relevant items.

        Each query dict: {"query": str, "relevant_ids": [str, ...]}
        """
        if top_k_values is None:
            top_k_values = [5, 10, 20, 50]

        metrics = {}
        for k in top_k_values:
            recall_sum = 0.0
            for q in queries:
                results = self.retrieve(q["query"], top_k=k)
                retrieved_ids = {r.creative_id for r in results}
                relevant = set(q.get("relevant_ids", []))
                if relevant:
                    recall_sum += len(retrieved_ids & relevant) / len(relevant)
            metrics[f"recall@{k}"] = recall_sum / max(len(queries), 1)

        return metrics

    def evaluate_mrr(self, queries: list[dict[str, Any]]) -> float:
        """Evaluate Mean Reciprocal Rank."""
        mrr_sum = 0.0
        for q in queries:
            results = self.retrieve(q["query"], top_k=50)
            relevant = set(q.get("relevant_ids", []))
            for rank, r in enumerate(results):
                if r.creative_id in relevant:
                    mrr_sum += 1.0 / (rank + 1)
                    break
        return mrr_sum / max(len(queries), 1)

    def evaluate_ndcg(self, queries: list[dict[str, Any]], k: int = 20) -> float:
        """Evaluate NDCG@K."""
        ndcg_sum = 0.0
        for q in queries:
            results = self.retrieve(q["query"], top_k=k)
            relevance = q.get("relevance", {})  # {creative_id: score}

            dcg = 0.0
            for rank, r in enumerate(results):
                rel = relevance.get(r.creative_id, 0)
                if rel > 0:
                    dcg += rel / math.log2(rank + 2)

            # Ideal DCG
            ideal_rels = sorted(relevance.values(), reverse=True)[:k]
            idcg = 0.0
            for i, rel in enumerate(ideal_rels):
                if rel > 0:
                    idcg += rel / math.log2(i + 2)

            ndcg_sum += dcg / max(idcg, 0.001)

        return ndcg_sum / max(len(queries), 1)

    # ── Stats ──

    @property
    def index_size(self) -> int:
        return len(self._creative_store)

    def _build_index_text(self, creative_data: dict[str, Any],
                          dna_data: dict[str, Any] | None,
                          prompt: str) -> str:
        """Build a text representation for embedding."""
        parts = []
        if dna_data:
            for dim in ["character", "reward", "hook", "gameplay", "style",
                         "camera", "lighting", "palette", "emotion", "brand"]:
                v = dna_data.get(dim, "")
                if v:
                    parts.append(f"{dim}: {v}")
        if prompt:
            parts.append(prompt)
        if creative_data.get("country"):
            parts.append(f"country: {creative_data['country']}")
        return " | ".join(parts) if parts else str(creative_data)