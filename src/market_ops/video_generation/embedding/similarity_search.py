"""Similarity Search"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import math


@dataclass
class SearchResult:
    embedding_id: str = ""
    video_path: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SimilaritySearch:
    """相似度搜索 - 在嵌入空间中查找相似视频"""

    def __init__(self):
        self._index: Dict[str, List[float]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def add(self, embedding_id: str, embedding: List[float], metadata: Dict[str, Any] = None):
        self._index[embedding_id] = embedding
        if metadata:
            self._metadata[embedding_id] = metadata

    def remove(self, embedding_id: str):
        if embedding_id in self._index:
            del self._index[embedding_id]
        if embedding_id in self._metadata:
            del self._metadata[embedding_id]

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        results = []
        for embedding_id, embedding in self._index.items():
            score = self._cosine_similarity(query_embedding, embedding)
            metadata = self._metadata.get(embedding_id, {})
            results.append(SearchResult(
                embedding_id=embedding_id,
                video_path=metadata.get("video_path", ""),
                score=round(score, 4),
                metadata=metadata,
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def find_winner_candidates(self, query_embedding: List[float], min_score: float = 0.7) -> List[SearchResult]:
        results = self.search(query_embedding, top_k=10)
        return [r for r in results if r.score >= min_score]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "index_size": len(self._index),
        }
