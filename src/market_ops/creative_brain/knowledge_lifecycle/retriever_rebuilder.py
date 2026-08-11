"""V4.3.5 Retriever Rebuilder — rebuild retriever index with updated knowledge.

After embeddings are refreshed, the retriever index must be rebuilt
to reflect the updated knowledge. This module handles incremental
index rebuilds without full reconstruction.
"""

from __future__ import annotations

from typing import Any


class RetrieverRebuilder:
    """Rebuild retriever index with updated knowledge.

    In production, this connects to the V4.1.1 Retriever module.
    Here it maintains its own index for testing and lifecycle management.
    """

    def __init__(self) -> None:
        self._index: dict[str, list[float]] = {}  # creative_id → vector
        self._index_version: str = "v1.0"
        self._rebuild_count: int = 0
        self._rebuild_history: list[dict[str, Any]] = []

    def rebuild(self, embeddings: dict[str, list[float]],
                new_version: str = "") -> dict[str, Any]:
        """Rebuild the retriever index with new embeddings.

        Args:
            embeddings: All embeddings to index.
            new_version: Version label for this index.

        Returns:
            Rebuild summary dict.
        """
        old_count = len(self._index)
        self._index = dict(embeddings)
        self._index_version = new_version or f"v{self._rebuild_count + 2}.0"
        self._rebuild_count += 1

        summary = {
            "index_version": self._index_version,
            "old_count": old_count,
            "new_count": len(self._index),
            "added": max(0, len(self._index) - old_count),
            "removed": max(0, old_count - len(self._index)),
            "rebuild_count": self._rebuild_count,
        }
        self._rebuild_history.append(summary)
        return summary

    def incremental_update(self, added: dict[str, list[float]] | None = None,
                           removed: list[str] | None = None) -> dict[str, Any]:
        """Incrementally update the index without full rebuild.

        Args:
            added: New embeddings to add.
            removed: Creative IDs to remove.

        Returns:
            Update summary dict.
        """
        added_count = 0
        removed_count = 0

        if added:
            for cid, vec in added.items():
                self._index[cid] = vec
                added_count += 1

        if removed:
            for cid in removed:
                if cid in self._index:
                    del self._index[cid]
                    removed_count += 1

        summary = {
            "index_version": self._index_version,
            "added": added_count,
            "removed": removed_count,
            "total": len(self._index),
            "rebuild_count": self._rebuild_count,
        }
        self._rebuild_history.append(summary)
        return summary

    def search(self, query_vector: list[float], top_k: int = 5
               ) -> list[dict[str, Any]]:
        """Search index for nearest neighbors (cosine similarity).

        Args:
            query_vector: Query embedding.
            top_k: Number of results.

        Returns:
            List of {creative_id, score}.
        """
        results = []
        for cid, vec in self._index.items():
            score = self._cosine_similarity(query_vector, vec)
            results.append({"creative_id": cid, "score": score})

        results.sort(key=lambda r: -r["score"])
        return results[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = (sum(x * x for x in a)) ** 0.5
        norm_b = (sum(x * x for x in b)) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @property
    def index_version(self) -> str:
        return self._index_version

    @property
    def index_size(self) -> int:
        return len(self._index)

    @property
    def rebuild_count(self) -> int:
        return self._rebuild_count

    def get_rebuild_history(self) -> list[dict[str, Any]]:
        return list(self._rebuild_history)