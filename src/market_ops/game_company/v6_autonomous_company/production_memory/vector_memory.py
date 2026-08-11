from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from enum import Enum
import math


class VectorStoreType(Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@dataclass
class VectorEntry:
    vector_id: str
    text: str
    vector: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "text": self.text,
            "metadata": self.metadata,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SearchResult:
    vector_id: str
    text: str
    similarity: float
    metadata: Dict[str, Any]


class VectorMemory:
    def __init__(self, dimension: int = 384, store_type: VectorStoreType = VectorStoreType.DENSE):
        self.dimension = dimension
        self.store_type = store_type
        self._vectors: Dict[str, VectorEntry] = {}
        self._category_index: Dict[str, List[str]] = {}

    def _text_to_vector(self, text: str) -> List[float]:
        text_lower = text.lower()
        vector = [0.0] * self.dimension
        words = text_lower.split()
        for i, word in enumerate(words):
            hash_val = hash(word) % self.dimension
            vector[hash_val] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def add(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        category: str = "general",
    ) -> VectorEntry:
        vector = self._text_to_vector(text)
        vector_id = f"vec_{hash(text + str(datetime.now())) % 100000:05d}"

        entry = VectorEntry(
            vector_id=vector_id,
            text=text,
            vector=vector,
            metadata=metadata or {},
            category=category,
        )

        self._vectors[vector_id] = entry

        if category not in self._category_index:
            self._category_index[category] = []
        self._category_index[category].append(vector_id)

        return entry

    def add_batch(
        self,
        items: List[Tuple[str, Dict[str, Any], str]],
    ) -> List[VectorEntry]:
        results = []
        for text, metadata, category in items:
            result = self.add(text, metadata, category)
            results.append(result)
        return results

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str = None,
        min_similarity: float = 0.0,
    ) -> List[SearchResult]:
        query_vector = self._text_to_vector(query)
        results = []

        candidates = list(self._vectors.values())
        if category:
            cat_ids = self._category_index.get(category, [])
            candidates = [self._vectors[vid] for vid in cat_ids if vid in self._vectors]

        for entry in candidates:
            similarity = self._cosine_similarity(query_vector, entry.vector)
            if similarity >= min_similarity:
                results.append(SearchResult(
                    vector_id=entry.vector_id,
                    text=entry.text,
                    similarity=similarity,
                    metadata=entry.metadata,
                ))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def get(self, vector_id: str) -> Optional[VectorEntry]:
        return self._vectors.get(vector_id)

    def delete(self, vector_id: str) -> bool:
        entry = self._vectors.get(vector_id)
        if not entry:
            return False

        if entry.category in self._category_index:
            if vector_id in self._category_index[entry.category]:
                self._category_index[entry.category].remove(vector_id)

        del self._vectors[vector_id]
        return True

    def get_similar(self, vector_id: str, top_k: int = 5) -> List[SearchResult]:
        entry = self._vectors.get(vector_id)
        if not entry:
            return []
        return self.search(entry.text, top_k=top_k + 1)[1:]

    def get_categories(self) -> List[str]:
        return list(self._category_index.keys())

    def get_stats(self) -> Dict[str, Any]:
        category_counts = {cat: len(ids) for cat, ids in self._category_index.items()}
        return {
            "total_vectors": len(self._vectors),
            "dimension": self.dimension,
            "store_type": self.store_type.value,
            "category_counts": category_counts,
            "total_categories": len(self._category_index),
        }
