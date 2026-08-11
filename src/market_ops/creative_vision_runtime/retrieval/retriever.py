"""E11.3.4 — Vision Retrieval Engine。

VisionFeatureStore → VectorIndex → Similarity Search → Winner Pattern Analysis。

Usage:
    engine = VisionRetrievalEngine(feature_store, index_dir="data/vision_features/index")
    engine.build_index()

    results = engine.retrieve(feature_id="vfr_xxx", top_k=10)
    pattern = engine.retrieve_winner_patterns(feature_id="vfr_xxx")
"""

from __future__ import annotations

import logging
from typing import Any

from ..feature_store.models import VisionFeatureRecord
from ..feature_store.store import VisionFeatureStore
from .models import VisionVector, SearchResult, WinnerPattern
from .vectorizer import VisionFeatureVectorizer
from .index import VisionVectorIndex

logger = logging.getLogger(__name__)


class VisionRetrievalEngine:
    """视觉检索引擎。

    Attributes:
        store:     VisionFeatureStore（数据源）
        vectorizer: 特征向量化器
        index:     VisionVectorIndex（相似度检索）
    """

    def __init__(
        self,
        feature_store: VisionFeatureStore,
        index_dir: str = "data/vision_features/index",
    ) -> None:
        self._store = feature_store
        self._vectorizer = VisionFeatureVectorizer()
        self._index = VisionVectorIndex(index_dir=index_dir)

    # ── Build Index ──────────────────────────────────────

    def build_index(self, force: bool = False) -> int:
        """从 FeatureStore 构建向量索引。

        Args:
            force: 是否强制重建

        Returns:
            索引的向量数量
        """
        if self._index.size > 0 and not force:
            logger.info(
                f"VisionRetrievalEngine: index already has {self._index.size} vectors, "
                f"use force=True to rebuild"
            )
            return self._index.size

        records = self._store.list_all()
        if not records:
            logger.warning("VisionRetrievalEngine: no records in feature store")
            return 0

        vectors = self._vectorizer.encode_batch(records)
        self._index.add_batch(vectors)
        self._index.save()

        logger.info(
            f"VisionRetrievalEngine: built index with {len(vectors)} vectors"
        )
        return len(vectors)

    # ── Retrieve ─────────────────────────────────────────

    def retrieve(
        self,
        feature_id: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """通过 feature_id 检索相似素材。

        Args:
            feature_id: 特征记录 ID
            top_k:      返回数量

        Returns:
            SearchResult 列表，按 similarity 降序
        """
        return self._index.search_by_feature_id(feature_id, top_k=top_k)

    def find_similar_asset(
        self,
        creative_asset_id: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """通过 creative_asset_id 检索相似素材。

        Args:
            creative_asset_id: 素材 ID
            top_k:             返回数量

        Returns:
            SearchResult 列表
        """
        return self._index.search_by_asset_id(creative_asset_id, top_k=top_k)

    def retrieve_by_record(
        self,
        record: VisionFeatureRecord,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """通过 VisionFeatureRecord 检索相似素材。

        适用于刚创建但尚未入库的素材。
        """
        vector = self._vectorizer.encode(record)
        return self._index.search(vector.vector, top_k=top_k)

    # ── Winner Pattern Analysis ──────────────────────────

    def retrieve_winner_patterns(
        self,
        feature_id: str,
        top_k: int = 10,
    ) -> WinnerPattern | None:
        """分析 Winner 模式。

        对于给定的素材，找到 top_k 个相似素材，分析其中 WINNER 的视觉规律。

        Args:
            feature_id: 特征记录 ID
            top_k:      检索数量

        Returns:
            WinnerPattern 或 None
        """
        query_vector = self._index.get_vector(feature_id)
        if query_vector is None:
            # 尝试从 store 加载并编码
            record = self._store_repo_load_record(feature_id)
            if record is None:
                return None
            query_vector = self._vectorizer.encode(record)
            self._index.add(query_vector)

        results = self._index.search(
            query_vector.vector,
            top_k=top_k,
            exclude_feature_id=feature_id,
        )

        if not results:
            return None

        # 收集所有相似素材的 feature_id
        similar_feature_ids = [r.feature_id for r in results]

        # 从 store 加载完整记录
        similar_records = self._load_records_by_feature_ids(similar_feature_ids)

        winners = [r for r in similar_records if r.is_winner]
        total = len(similar_records)

        pattern = WinnerPattern(
            query_asset_id=query_vector.creative_asset_id,
            total_similar=total,
            winner_count=len(winners),
            winner_ratio=len(winners) / total if total > 0 else 0.0,
        )

        if winners:
            pattern.avg_hook_score = sum(w.hook_score for w in winners) / len(winners)
            pattern.avg_reward_score = sum(w.reward_score for w in winners) / len(winners)
            pattern.avg_brightness = sum(w.avg_brightness for w in winners) / len(winners)
            pattern.avg_contrast = sum(w.avg_contrast for w in winners) / len(winners)
            pattern.avg_edge_density = sum(w.avg_edge_density for w in winners) / len(winners)
            pattern.avg_saturation = sum(w.avg_saturation for w in winners) / len(winners)
            pattern.avg_color_entropy = sum(w.avg_color_entropy for w in winners) / len(winners)

        # 生成推荐
        pattern.recommendations = self._generate_recommendations(pattern, query_vector)

        # 附加 top_similar
        pattern.top_similar = [r.to_dict() for r in results[:5]]

        return pattern

    def find_similar_winner_patterns(
        self,
        creative_asset_id: str,
        top_k: int = 10,
    ) -> WinnerPattern | None:
        """通过 creative_asset_id 分析 Winner 模式。"""
        v = self._index.get_by_asset_id(creative_asset_id)
        if v is None:
            return None
        return self.retrieve_winner_patterns(v.feature_id, top_k=top_k)

    # ── Index Management ─────────────────────────────────

    def add_to_index(self, record: VisionFeatureRecord) -> None:
        """将单个记录添加到索引。"""
        vector = self._vectorizer.encode(record)
        self._index.add(vector)
        self._index.save()

    def remove_from_index(self, feature_id: str) -> bool:
        result = self._index.remove(feature_id)
        if result:
            self._index.save()
        return result

    @property
    def index_size(self) -> int:
        return self._index.size

    # ── Internal ────────────────────────────────────────

    def _store_repo_load_record(self, feature_id: str) -> VisionFeatureRecord | None:
        """从 store 的 repository 加载记录。"""
        return self._store._repo.load_record(feature_id)  # noqa: SLF001

    def _load_records_by_feature_ids(
        self, feature_ids: list[str]
    ) -> list[VisionFeatureRecord]:
        """批量加载记录。"""
        records: list[VisionFeatureRecord] = []
        for fid in feature_ids:
            record = self._store._repo.load_record(fid)  # noqa: SLF001
            if record is not None:
                records.append(record)
        return records

    @staticmethod
    def _generate_recommendations(
        pattern: WinnerPattern,
        query_vector: VisionVector,
    ) -> list[str]:
        """生成模式推荐。"""
        recs: list[str] = []

        if pattern.winner_ratio >= 0.8:
            recs.append(f"High winner ratio ({pattern.winner_ratio:.0%}): similar visual pattern is effective")
        elif pattern.winner_ratio >= 0.5:
            recs.append(f"Moderate winner ratio ({pattern.winner_ratio:.0%}): visual pattern shows potential")
        else:
            recs.append(f"Low winner ratio ({pattern.winner_ratio:.0%}): consider visual variation")

        if pattern.avg_hook_score >= 0.7:
            recs.append("High hook score in winners: strong opening visual is key")
        if pattern.avg_contrast >= 0.5:
            recs.append("High contrast in winners: bold visual design recommended")
        if pattern.avg_brightness >= 0.6:
            recs.append("Bright backgrounds in winners: light/clean visuals preferred")
        if pattern.avg_edge_density >= 0.4:
            recs.append("High edge density in winners: detailed/complex visuals work well")
        if pattern.avg_saturation >= 0.5:
            recs.append("High saturation in winners: vibrant colors are effective")

        return recs

    def __repr__(self) -> str:
        return (
            f"VisionRetrievalEngine(index_size={self._index.size})"
        )