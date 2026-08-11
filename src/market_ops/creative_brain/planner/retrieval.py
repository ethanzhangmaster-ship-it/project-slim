"""V4.1 Retriever — retrieves relevant memory for planning."""

from __future__ import annotations

from typing import Any

from ..memory.memory_center import MemoryCenter
from ..embedding.embedding_service import EmbeddingService
from ..vector_store.search_engine import SearchEngine


class Retriever:
    """Retrieves relevant creative memory, DNA, and prompts."""

    def __init__(self, memory: MemoryCenter, embedder: EmbeddingService,
                 searcher: SearchEngine) -> None:
        self._memory = memory
        self._embedder = embedder
        self._searcher = searcher

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve top-K relevant items from memory."""
        results = []

        # Search creative memory
        creatives = self._memory.creatives.search()
        results.extend([
            {"type": "creative", "id": c.creative_id, "metadata": c.to_dict()}
            for c in creatives[:top_k]
        ])

        # Search DNA memory
        dna_records = self._memory.dna.search()
        results.extend([
            {"type": "dna", "id": d.dna_id, "metadata": d.to_dict()}
            for d in dna_records[:top_k]
        ])

        # Search prompt memory
        prompts = self._memory.prompts.search()
        results.extend([
            {"type": "prompt", "id": p.prompt_id, "metadata": p.to_dict()}
            for p in prompts[:top_k]
        ])

        return results[:top_k]