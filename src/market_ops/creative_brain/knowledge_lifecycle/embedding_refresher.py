"""V4.3.5 Embedding Refresher — incremental embedding updates.

When new winners enter, auto-update:
  Embedding → Index → Retriever

No full re-encode needed. Supports incremental add/update/remove.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from .schemas import EmbeddingUpdate


class EmbeddingRefresher:
    """Incremental embedding update manager.

    Uses a simple hash-based embedding for deterministic similarity.
    In production, this would connect to a real embedding model (e.g., CLIP).
    """

    def __init__(self, vector_dim: int = 64) -> None:
        self._vector_dim = vector_dim
        self._embeddings: dict[str, list[float]] = {}  # creative_id → vector
        self._update_history: list[EmbeddingUpdate] = []

    def add(self, creative_id: str, dna: dict[str, Any]) -> EmbeddingUpdate:
        """Add a new embedding for a creative.

        Returns the EmbeddingUpdate record.
        """
        vector = self._encode_dna(dna)
        self._embeddings[creative_id] = vector

        update = EmbeddingUpdate(
            creative_id=creative_id,
            dna=dna,
            embedding_vector=vector,
            action="add",
            timestamp=datetime.now().isoformat(),
        )
        self._update_history.append(update)
        return update

    def update(self, creative_id: str, dna: dict[str, Any]) -> EmbeddingUpdate:
        """Update an existing embedding."""
        vector = self._encode_dna(dna)
        action = "update" if creative_id in self._embeddings else "add"
        self._embeddings[creative_id] = vector

        update = EmbeddingUpdate(
            creative_id=creative_id,
            dna=dna,
            embedding_vector=vector,
            action=action,
            timestamp=datetime.now().isoformat(),
        )
        self._update_history.append(update)
        return update

    def remove(self, creative_id: str) -> EmbeddingUpdate | None:
        """Remove an embedding."""
        if creative_id not in self._embeddings:
            return None

        vector = self._embeddings.pop(creative_id)
        update = EmbeddingUpdate(
            creative_id=creative_id,
            embedding_vector=vector,
            action="remove",
            timestamp=datetime.now().isoformat(),
        )
        self._update_history.append(update)
        return update

    def refresh_batch(self, creatives: list[dict[str, Any]]) -> list[EmbeddingUpdate]:
        """Add/update embeddings for a batch of creatives.

        Args:
            creatives: List of {creative_id, dna}.

        Returns:
            List of EmbeddingUpdate applied.
        """
        updates = []
        for c in creatives:
            update = self.update(c["creative_id"], c.get("dna", {}))
            updates.append(update)
        return updates

    def _encode_dna(self, dna: dict[str, Any]) -> list[float]:
        """Encode DNA into a deterministic embedding vector.

        Uses hashing for reproducibility. In production, use a real model.
        """
        dna_str = str(sorted(dna.items()))
        hash_bytes = hashlib.sha256(dna_str.encode()).digest()

        vector = []
        for i in range(self._vector_dim):
            # Use hash bytes cyclically to generate float values
            byte_val = hash_bytes[i % len(hash_bytes)]
            # Normalize to [-1, 1]
            normalized = (byte_val / 127.5) - 1.0
            vector.append(round(normalized, 6))

        return vector

    def get_embedding(self, creative_id: str) -> list[float] | None:
        """Get embedding vector for a creative."""
        return self._embeddings.get(creative_id)

    def get_all_embeddings(self) -> dict[str, list[float]]:
        """Get all embeddings."""
        return dict(self._embeddings)

    @property
    def embedding_count(self) -> int:
        return len(self._embeddings)

    @property
    def vector_dim(self) -> int:
        return self._vector_dim

    def get_update_history(self) -> list[EmbeddingUpdate]:
        return list(self._update_history)