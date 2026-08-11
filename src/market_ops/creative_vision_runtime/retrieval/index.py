"""E11.3.4 — Vision Vector Index。

基于 numpy 的余弦相似度索引。
第一版不引入 FAISS，保持零外部依赖、可测试。

存储：
  data/vision_features/index/vectors.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from .models import VisionVector, SearchResult
from .vectorizer import VisionFeatureVectorizer

logger = logging.getLogger(__name__)


class VisionVectorIndex:
    """视觉特征向量索引。

    基于 numpy 矩阵运算的高效余弦相似度检索。

    Attributes:
        vectors:    已索引的 VisionVector 列表
        _matrix:    numpy 矩阵 (n × dim)
        _ids:       索引 ID 列表
    """

    DEFAULT_INDEX_DIR = "data/vision_features/index"

    def __init__(self, index_dir: str = DEFAULT_INDEX_DIR) -> None:
        self._index_dir = Path(index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._vectors_path = self._index_dir / "vectors.json"

        self._vectors: list[VisionVector] = []
        self._matrix: np.ndarray | None = None
        self._ids: list[str] = []

        self._load()

    # ── Add ──────────────────────────────────────────────

    def add(self, vector: VisionVector) -> None:
        """添加向量到索引。"""
        # 去重：已存在则替换
        existing_idx = self._find_index(vector.feature_id)
        if existing_idx is not None:
            self._vectors[existing_idx] = vector
        else:
            self._vectors.append(vector)

        self._rebuild_matrix()

    def add_batch(self, vectors: list[VisionVector]) -> None:
        """批量添加向量。"""
        for v in vectors:
            existing_idx = self._find_index(v.feature_id)
            if existing_idx is not None:
                self._vectors[existing_idx] = v
            else:
                self._vectors.append(v)
        self._rebuild_matrix()

    # ── Search ───────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        exclude_feature_id: str | None = None,
    ) -> list[SearchResult]:
        """余弦相似度检索。

        Args:
            query_vector:       查询向量（应已 L2 归一化）
            top_k:              返回数量
            exclude_feature_id: 排除的 feature_id（用于排除自身）

        Returns:
            SearchResult 列表，按 similarity 降序
        """
        if self._matrix is None or len(self._vectors) == 0:
            return []

        query = np.array(query_vector, dtype=np.float64)
        if query.ndim == 1:
            query = query.reshape(1, -1)

        # 余弦相似度 = 归一化向量的点积
        scores = np.dot(self._matrix, query.T).flatten()

        # 排序
        indices = np.argsort(-scores)  # 降序

        results: list[SearchResult] = []
        for idx in indices:
            if exclude_feature_id and self._vectors[idx].feature_id == exclude_feature_id:
                continue

            v = self._vectors[idx]
            results.append(SearchResult(
                creative_asset_id=v.creative_asset_id,
                feature_id=v.feature_id,
                similarity=float(scores[idx]),
                hook_score=v.hook_score,
                reward_score=v.reward_score,
                is_winner=v.is_winner,
                eagle_filename=v.metadata.get("eagle_filename", ""),
                metadata=v.metadata,
            ))

            if len(results) >= top_k:
                break

        return results

    def search_by_feature_id(
        self,
        feature_id: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """通过 feature_id 搜索相似向量。"""
        v = self.get_vector(feature_id)
        if v is None:
            return []
        return self.search(v.vector, top_k=top_k, exclude_feature_id=feature_id)

    def search_by_asset_id(
        self,
        creative_asset_id: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """通过 creative_asset_id 搜索相似向量。"""
        for v in self._vectors:
            if v.creative_asset_id == creative_asset_id:
                return self.search(v.vector, top_k=top_k, exclude_feature_id=v.feature_id)
        return []

    # ── Query ────────────────────────────────────────────

    def get_vector(self, feature_id: str) -> VisionVector | None:
        idx = self._find_index(feature_id)
        if idx is None:
            return None
        return self._vectors[idx]

    def get_by_asset_id(self, creative_asset_id: str) -> VisionVector | None:
        for v in self._vectors:
            if v.creative_asset_id == creative_asset_id:
                return v
        return None

    def remove(self, feature_id: str) -> bool:
        idx = self._find_index(feature_id)
        if idx is None:
            return False
        self._vectors.pop(idx)
        self._rebuild_matrix()
        return True

    # ── Stats ────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._vectors)

    def list_all(self) -> list[VisionVector]:
        return list(self._vectors)

    # ── Persistence ──────────────────────────────────────

    def save(self) -> None:
        """持久化索引到 JSON。"""
        data = [v.to_dict() for v in self._vectors]
        self._vectors_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load(self) -> None:
        """从 JSON 加载索引。"""
        if not self._vectors_path.exists():
            return
        try:
            data = json.loads(self._vectors_path.read_text(encoding="utf-8"))
            self._vectors = [VisionVector.from_dict(d) for d in data]
            self._rebuild_matrix()
        except Exception as e:
            logger.warning(f"VisionVectorIndex: failed to load index: {e}")

    # ── Internal ────────────────────────────────────────

    def _find_index(self, feature_id: str) -> int | None:
        for i, v in enumerate(self._vectors):
            if v.feature_id == feature_id:
                return i
        return None

    def _rebuild_matrix(self) -> None:
        if not self._vectors:
            self._matrix = None
            self._ids = []
            return
        self._matrix = np.array([v.vector for v in self._vectors], dtype=np.float64)
        self._ids = [v.feature_id for v in self._vectors]

    def __repr__(self) -> str:
        return f"VisionVectorIndex(size={self.size})"