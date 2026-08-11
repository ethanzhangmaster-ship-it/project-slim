"""V4.1 FAISS-compatible store interface.

Provides a FAISS-like API on top of the pure Python VectorDatabase.
"""

from .vector_database import VectorDatabase, VectorEntry

__all__ = ["VectorDatabase", "VectorEntry"]


class FAISSStore:
    """FAISS-compatible vector store wrapper."""

    def __init__(self, dim: int = 768) -> None:
        self._db = VectorDatabase(dim=dim)

    def add(self, entry_id: str, vector: list[float], metadata: dict | None = None) -> None:
        self._db.add(entry_id, vector, metadata)

    def search(self, query: list[float], k: int = 10, metric: str = "cosine") -> list[VectorEntry]:
        if metric == "l2":
            return self._db.search_l2(query, top_k=k)
        return self._db.search_cosine(query, top_k=k)

    def __len__(self) -> int:
        return len(self._db)