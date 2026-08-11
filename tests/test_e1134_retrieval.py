"""E11.3.4 — Vision Retrieval Engine 测试。

测试范围：
  - VisionVector: 数据模型 + 序列化
  - SearchResult: 检索结果
  - WinnerPattern: Winner 模式分析
  - VisionFeatureVectorizer: 向量化 + 归一化 + 余弦相似度
  - VisionVectorIndex: 添加/搜索/持久化
  - VisionRetrievalEngine: 构建索引/检索/Winner 模式分析
  - Integration: FeatureStore → Engine → retrieve → winner patterns
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from market_ops.creative_vision_runtime.feature_store.models import (
    VisionFeatureRecord,
)
from market_ops.creative_vision_runtime.feature_store.store import (
    VisionFeatureStore,
)
from market_ops.creative_vision_runtime.retrieval.models import (
    VisionVector,
    SearchResult,
    WinnerPattern,
)
from market_ops.creative_vision_runtime.retrieval.vectorizer import (
    VisionFeatureVectorizer,
    VECTOR_DIM,
)
from market_ops.creative_vision_runtime.retrieval.index import (
    VisionVectorIndex,
)
from market_ops.creative_vision_runtime.retrieval.retriever import (
    VisionRetrievalEngine,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _make_record(
    asset_id: str = "MW_VID_001",
    hook: float = 0.82,
    comp: float = 0.65,
    reward: float = 0.71,
    brightness: float = 0.61,
    contrast: float = 0.45,
    edge: float = 0.33,
    saturation: float = 0.55,
    entropy: float = 6.2,
    is_winner: bool = False,
    lifecycle: str = "TESTING",
) -> VisionFeatureRecord:
    return VisionFeatureRecord(
        creative_asset_id=asset_id,
        video_path=f"Y:/Eagle/{asset_id}.mp4",
        eagle_filename=f"{asset_id}.mp4",
        frame_count=6,
        duration_seconds=30.0,
        resolution=(1920, 1080),
        hook_score=hook,
        comprehension_score=comp,
        reward_score=reward,
        avg_brightness=brightness,
        avg_contrast=contrast,
        avg_edge_density=edge,
        avg_saturation=saturation,
        avg_color_entropy=entropy,
        metric={"roas": 3.0} if is_winner else {"roas": 0.8},
        lifecycle_status=lifecycle,
        is_winner=is_winner,
    )


def _make_store(tmp_path: Path) -> VisionFeatureStore:
    return VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))


# ════════════════════════════════════════════════════════════════════
# VisionVector
# ════════════════════════════════════════════════════════════════════

class TestVisionVector:
    """VisionVector 数据模型测试。"""

    def test_create(self):
        v = VisionVector(
            feature_id="vfr_001",
            creative_asset_id="MW_VID_001",
            vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            hook_score=0.82,
            reward_score=0.71,
            is_winner=True,
        )
        assert v.feature_id == "vfr_001"
        assert v.dimension == 8
        assert v.is_winner is True

    def test_to_dict(self):
        v = VisionVector(
            feature_id="vfr_001",
            creative_asset_id="MW_VID_001",
            vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            hook_score=0.82,
            is_winner=True,
            metadata={"roas": 3.0},
        )
        d = v.to_dict()
        assert d["feature_id"] == "vfr_001"
        assert d["vector"] == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        assert d["metadata"]["roas"] == 3.0

    def test_from_dict(self):
        data = {
            "feature_id": "vfr_001",
            "creative_asset_id": "MW_VID_001",
            "vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            "hook_score": 0.82,
            "reward_score": 0.71,
            "is_winner": False,
        }
        v = VisionVector.from_dict(data)
        assert v.feature_id == "vfr_001"
        assert v.dimension == 8
        assert v.is_winner is False

    def test_repr(self):
        v = VisionVector(
            feature_id="vfr_001",
            creative_asset_id="MW_VID_001",
            vector=[0.1] * 8,
            is_winner=True,
        )
        r = repr(v)
        assert "MW_VID_001" in r
        assert "winner=True" in r


# ════════════════════════════════════════════════════════════════════
# SearchResult
# ════════════════════════════════════════════════════════════════════

class TestSearchResult:
    """SearchResult 数据模型测试。"""

    def test_create(self):
        sr = SearchResult(
            creative_asset_id="MW_VID_001",
            feature_id="vfr_001",
            similarity=0.93,
            hook_score=0.82,
            is_winner=True,
        )
        assert sr.similarity == 0.93
        assert sr.is_winner is True

    def test_to_dict(self):
        sr = SearchResult(
            creative_asset_id="MW_VID_001",
            feature_id="vfr_001",
            similarity=0.93,
            hook_score=0.82,
            reward_score=0.71,
            is_winner=True,
            eagle_filename="test.mp4",
        )
        d = sr.to_dict()
        assert d["similarity"] == 0.93
        assert d["eagle_filename"] == "test.mp4"

    def test_repr(self):
        sr = SearchResult(
            creative_asset_id="MW_VID_001",
            feature_id="vfr_001",
            similarity=0.93,
        )
        r = repr(sr)
        assert "0.930" in r


# ════════════════════════════════════════════════════════════════════
# WinnerPattern
# ════════════════════════════════════════════════════════════════════

class TestWinnerPattern:
    """WinnerPattern 数据模型测试。"""

    def test_create_empty(self):
        wp = WinnerPattern(query_asset_id="MW_VID_001")
        assert wp.query_asset_id == "MW_VID_001"
        assert wp.winner_ratio == 0.0
        assert wp.recommendations == []

    def test_create_full(self):
        wp = WinnerPattern(
            query_asset_id="MW_VID_001",
            total_similar=10,
            winner_count=8,
            winner_ratio=0.8,
            avg_hook_score=0.75,
            avg_reward_score=0.70,
            avg_brightness=0.65,
            avg_contrast=0.50,
            avg_edge_density=0.40,
            avg_saturation=0.55,
            avg_color_entropy=6.0,
            recommendations=["High contrast in winners"],
            top_similar=[{"creative_asset_id": "MW_VID_002", "similarity": 0.93}],
        )
        assert wp.winner_ratio == 0.8
        assert len(wp.recommendations) == 1
        assert len(wp.top_similar) == 1

    def test_to_dict(self):
        wp = WinnerPattern(
            query_asset_id="MW_VID_001",
            total_similar=5,
            winner_count=3,
            winner_ratio=0.6,
            avg_hook_score=0.75,
            recommendations=["test"],
        )
        d = wp.to_dict()
        assert d["winner_ratio"] == 0.6
        assert d["recommendations"] == ["test"]

    def test_repr(self):
        wp = WinnerPattern(
            query_asset_id="MW_VID_001",
            total_similar=10,
            winner_count=8,
            winner_ratio=0.8,
        )
        r = repr(wp)
        assert "80.0%" in r


# ════════════════════════════════════════════════════════════════════
# VisionFeatureVectorizer
# ════════════════════════════════════════════════════════════════════

class TestVisionFeatureVectorizer:
    """VisionFeatureVectorizer 向量化测试。"""

    @pytest.fixture
    def vectorizer(self):
        return VisionFeatureVectorizer()

    def test_dimension(self, vectorizer):
        assert vectorizer.dimension == 8

    def test_encode(self, vectorizer):
        record = _make_record("MW_VID_001", hook=0.82, comp=0.65, reward=0.71,
                              brightness=0.61, contrast=0.45, edge=0.33,
                              saturation=0.55, entropy=6.2)
        v = vectorizer.encode(record)
        assert v.feature_id == record.feature_id
        assert v.creative_asset_id == "MW_VID_001"
        assert len(v.vector) == 8
        assert v.hook_score == 0.82

    def test_encode_normalized(self, vectorizer):
        record = _make_record("MW_VID_001")
        v = vectorizer.encode(record)
        # L2 norm should be 1.0 (unit vector)
        norm = math.sqrt(sum(x * x for x in v.vector))
        assert norm == pytest.approx(1.0, abs=0.001)

    def test_encode_winner(self, vectorizer):
        record = _make_record("MW_WINNER", is_winner=True, lifecycle="WINNER")
        v = vectorizer.encode(record)
        assert v.is_winner is True
        assert v.metadata["lifecycle_status"] == "WINNER"

    def test_encode_batch(self, vectorizer):
        records = [
            _make_record("MW_VID_001"),
            _make_record("MW_VID_002", hook=0.5),
            _make_record("MW_VID_003", hook=0.9),
        ]
        vectors = vectorizer.encode_batch(records)
        assert len(vectors) == 3
        assert vectors[0].creative_asset_id == "MW_VID_001"

    def test_cosine_similarity_identical(self, vectorizer):
        record = _make_record("MW_VID_001")
        v = vectorizer.encode(record)
        sim = VisionFeatureVectorizer.cosine_similarity(v.vector, v.vector)
        assert sim == pytest.approx(1.0, abs=0.001)

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        sim = VisionFeatureVectorizer.cosine_similarity(a, b)
        assert sim == pytest.approx(0.0, abs=0.001)

    def test_cosine_similarity_dimension_mismatch(self):
        with pytest.raises(ValueError, match="dimension mismatch"):
            VisionFeatureVectorizer.cosine_similarity([1.0], [1.0, 2.0])

    def test_repr(self, vectorizer):
        assert "dim=8" in repr(vectorizer)


# ════════════════════════════════════════════════════════════════════
# VisionVectorIndex
# ════════════════════════════════════════════════════════════════════

class TestVisionVectorIndex:
    """VisionVectorIndex 索引测试。"""

    @pytest.fixture
    def vectorizer(self):
        return VisionFeatureVectorizer()

    @pytest.fixture
    def index(self, tmp_path):
        return VisionVectorIndex(index_dir=str(tmp_path / "index"))

    def _make_vector(self, vectorizer, asset_id: str, **kwargs) -> VisionVector:
        record = _make_record(asset_id, **kwargs)
        return vectorizer.encode(record)

    def test_add(self, index, vectorizer):
        v = self._make_vector(vectorizer, "MW_VID_001")
        index.add(v)
        assert index.size == 1

    def test_add_duplicate(self, index, vectorizer):
        # 使用相同 feature_id 模拟重复添加
        record = _make_record("MW_VID_001", hook=0.82)
        v1 = vectorizer.encode(record)
        record2 = _make_record("MW_VID_001", hook=0.90)
        v2 = VisionVector(
            feature_id=v1.feature_id,  # 相同 feature_id
            creative_asset_id="MW_VID_001",
            vector=vectorizer.encode(record2).vector,
            hook_score=0.90,
        )
        index.add(v1)
        index.add(v2)  # same feature_id → replace
        assert index.size == 1
        loaded = index.get_vector(v1.feature_id)
        assert loaded is not None
        assert loaded.creative_asset_id == "MW_VID_001"

    def test_add_batch(self, index, vectorizer):
        vectors = [
            self._make_vector(vectorizer, "MW_VID_001"),
            self._make_vector(vectorizer, "MW_VID_002"),
            self._make_vector(vectorizer, "MW_VID_003"),
        ]
        index.add_batch(vectors)
        assert index.size == 3

    def test_search(self, index, vectorizer):
        v1 = self._make_vector(vectorizer, "MW_VID_001", hook=0.9, comp=0.8, reward=0.85)
        v2 = self._make_vector(vectorizer, "MW_VID_002", hook=0.5, comp=0.4, reward=0.45)
        v3 = self._make_vector(vectorizer, "MW_VID_003", hook=0.88, comp=0.78, reward=0.83)
        index.add_batch([v1, v2, v3])

        # Search with v1's vector
        results = index.search(v1.vector, top_k=2)
        assert len(results) == 2
        # v1 itself is the most similar (cosine=1.0)
        assert results[0].creative_asset_id == "MW_VID_001"
        assert results[0].similarity == pytest.approx(1.0, abs=0.001)
        # v3 should be more similar to v1 than v2
        assert results[1].creative_asset_id == "MW_VID_003"

    def test_search_exclude_self(self, index, vectorizer):
        v1 = self._make_vector(vectorizer, "MW_VID_001", hook=0.9)
        v2 = self._make_vector(vectorizer, "MW_VID_002", hook=0.5)
        index.add_batch([v1, v2])

        results = index.search(v1.vector, top_k=2, exclude_feature_id=v1.feature_id)
        assert len(results) == 1
        assert results[0].creative_asset_id == "MW_VID_002"

    def test_search_by_feature_id(self, index, vectorizer):
        v1 = self._make_vector(vectorizer, "MW_VID_001", hook=0.9)
        v2 = self._make_vector(vectorizer, "MW_VID_002", hook=0.5)
        v3 = self._make_vector(vectorizer, "MW_VID_003", hook=0.88)
        index.add_batch([v1, v2, v3])

        results = index.search_by_feature_id(v1.feature_id, top_k=2)
        assert len(results) == 2
        assert results[0].creative_asset_id != "MW_VID_001"  # excluded self

    def test_search_by_asset_id(self, index, vectorizer):
        v1 = self._make_vector(vectorizer, "MW_VID_001", hook=0.9)
        v2 = self._make_vector(vectorizer, "MW_VID_002", hook=0.5)
        index.add_batch([v1, v2])

        results = index.search_by_asset_id("MW_VID_001", top_k=2)
        assert len(results) == 1
        assert results[0].creative_asset_id == "MW_VID_002"

    def test_search_empty(self, index):
        results = index.search([0.1] * 8, top_k=5)
        assert results == []

    def test_get_vector(self, index, vectorizer):
        v = self._make_vector(vectorizer, "MW_VID_001")
        index.add(v)
        found = index.get_vector(v.feature_id)
        assert found is not None
        assert found.creative_asset_id == "MW_VID_001"

    def test_get_vector_not_found(self, index):
        assert index.get_vector("nonexistent") is None

    def test_get_by_asset_id(self, index, vectorizer):
        v = self._make_vector(vectorizer, "MW_VID_001")
        index.add(v)
        found = index.get_by_asset_id("MW_VID_001")
        assert found is not None
        assert found.feature_id == v.feature_id

    def test_remove(self, index, vectorizer):
        v = self._make_vector(vectorizer, "MW_VID_001")
        index.add(v)
        assert index.size == 1
        result = index.remove(v.feature_id)
        assert result is True
        assert index.size == 0

    def test_remove_nonexistent(self, index):
        assert index.remove("nonexistent") is False

    def test_save_and_load(self, tmp_path, vectorizer):
        index_dir = str(tmp_path / "index")
        idx1 = VisionVectorIndex(index_dir=index_dir)
        v = self._make_vector(vectorizer, "MW_VID_001")
        idx1.add(v)
        idx1.save()

        # 新实例加载
        idx2 = VisionVectorIndex(index_dir=index_dir)
        assert idx2.size == 1
        found = idx2.get_vector(v.feature_id)
        assert found is not None
        assert found.creative_asset_id == "MW_VID_001"

    def test_search_result_metadata(self, index, vectorizer):
        v = self._make_vector(vectorizer, "MW_VID_001", is_winner=True)
        index.add(v)

        results = index.search(v.vector, top_k=1)
        assert len(results) == 1
        assert results[0].is_winner is True
        assert results[0].hook_score == 0.82

    def test_repr(self, index, vectorizer):
        assert "size=0" in repr(index)
        index.add(self._make_vector(vectorizer, "MW_VID_001"))
        assert "size=1" in repr(index)


# ════════════════════════════════════════════════════════════════════
# VisionRetrievalEngine
# ════════════════════════════════════════════════════════════════════

class TestVisionRetrievalEngine:
    """VisionRetrievalEngine 检索引擎测试。"""

    @pytest.fixture
    def engine(self, tmp_path):
        store = _make_store(tmp_path)
        return VisionRetrievalEngine(
            feature_store=store,
            index_dir=str(tmp_path / "index"),
        )

    def _populate_store(self, engine, store):
        """添加多个素材到 store 并构建索引。"""
        records = [
            _make_record("MW_VID_001", hook=0.9, comp=0.85, reward=0.88, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_VID_002", hook=0.5, comp=0.45, reward=0.48, is_winner=False),
            _make_record("MW_VID_003", hook=0.87, comp=0.82, reward=0.85, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_VID_004", hook=0.3, comp=0.35, reward=0.32, is_winner=False),
            _make_record("MW_VID_005", hook=0.85, comp=0.80, reward=0.83, is_winner=True, lifecycle="WINNER"),
        ]
        for r in records:
            store._repo.save_record(r)
        return engine.build_index()  # uses engine._store

    def test_build_index(self, engine):
        store = engine._store
        store._repo.save_record(_make_record("MW_VID_001"))
        store._repo.save_record(_make_record("MW_VID_002"))
        count = engine.build_index()
        assert count == 2
        assert engine.index_size == 2

    def test_build_index_empty(self, engine):
        count = engine.build_index()
        assert count == 0

    def test_build_index_no_force(self, engine):
        store = engine._store
        store._repo.save_record(_make_record("MW_VID_001"))
        engine.build_index()
        # 第二次 build 不加 force 应该跳过
        count = engine.build_index(force=False)
        assert count == 1

    def test_retrieve(self, engine):
        store = engine._store
        self._populate_store(engine, store)

        # 获取 MW_VID_001 的 feature_id
        record = store._repo.find_by_asset_id("MW_VID_001")
        assert record is not None

        results = engine.retrieve(record.feature_id, top_k=3)
        assert len(results) == 3
        # 最相似的不应该是自己
        for r in results:
            assert r.creative_asset_id != "MW_VID_001"

    def test_find_similar_asset(self, engine):
        store = engine._store
        self._populate_store(engine, store)

        results = engine.find_similar_asset("MW_VID_001", top_k=3)
        assert len(results) == 3
        # 高 hook 素材应该排在前面
        assert results[0].hook_score > 0.8

    def test_retrieve_by_record(self, engine):
        store = engine._store
        self._populate_store(engine, store)

        new_record = _make_record("MW_NEW", hook=0.91, comp=0.86, reward=0.89)
        results = engine.retrieve_by_record(new_record, top_k=3)
        assert len(results) == 3
        # 最相似的应该是高 hook 的素材
        assert results[0].hook_score > 0.8

    def test_retrieve_winner_patterns(self, engine):
        store = engine._store
        self._populate_store(engine, store)

        record = store._repo.find_by_asset_id("MW_VID_001")
        assert record is not None

        pattern = engine.retrieve_winner_patterns(record.feature_id, top_k=4)
        assert pattern is not None
        assert pattern.query_asset_id == "MW_VID_001"
        assert pattern.total_similar > 0
        assert pattern.winner_ratio > 0
        assert len(pattern.top_similar) > 0
        assert len(pattern.recommendations) > 0

    def test_retrieve_winner_patterns_high_ratio(self, engine):
        store = engine._store
        # All similar are winners
        records = [
            _make_record("MW_WIN_001", hook=0.9, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN_002", hook=0.88, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN_003", hook=0.87, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_LOSER", hook=0.3, is_winner=False),
        ]
        for r in records:
            store._repo.save_record(r)
        engine.build_index()

        record = store._repo.find_by_asset_id("MW_WIN_001")
        pattern = engine.retrieve_winner_patterns(record.feature_id, top_k=3)
        assert pattern is not None
        assert pattern.winner_count >= 2
        assert pattern.winner_ratio >= 0.66

    def test_find_similar_winner_patterns(self, engine):
        store = engine._store
        self._populate_store(engine, store)

        pattern = engine.find_similar_winner_patterns("MW_VID_001", top_k=4)
        assert pattern is not None
        assert pattern.winner_ratio > 0

    def test_add_to_index(self, engine):
        record = _make_record("MW_VID_001")
        engine.add_to_index(record)
        assert engine.index_size == 1

    def test_remove_from_index(self, engine):
        record = _make_record("MW_VID_001")
        engine.add_to_index(record)
        assert engine.index_size == 1
        result = engine.remove_from_index(record.feature_id)
        assert result is True
        assert engine.index_size == 0

    def test_remove_nonexistent(self, engine):
        assert engine.remove_from_index("nonexistent") is False

    def test_retrieve_winner_patterns_hook_analysis(self, engine):
        store = engine._store
        self._populate_store(engine, store)

        record = store._repo.find_by_asset_id("MW_VID_001")
        pattern = engine.retrieve_winner_patterns(record.feature_id, top_k=4)
        assert pattern is not None
        # Winners should have high hook score
        assert pattern.avg_hook_score > 0.7

    def test_repr(self, engine):
        r = repr(engine)
        assert "VisionRetrievalEngine" in r


# ════════════════════════════════════════════════════════════════════
# Integration: FeatureStore → RetrievalEngine → Winner Patterns
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试：FeatureStore → RetrievalEngine → Winner Patterns。"""

    def test_full_workflow(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))
        engine = VisionRetrievalEngine(
            feature_store=store,
            index_dir=str(tmp_path / "index"),
        )

        # 1. 保存素材到 FeatureStore
        records = [
            _make_record("MW_WITCH_001", hook=0.9, comp=0.85, reward=0.88, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WITCH_002", hook=0.87, comp=0.83, reward=0.86, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WITCH_003", hook=0.85, comp=0.80, reward=0.84, is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WITCH_004", hook=0.5, comp=0.48, reward=0.5, is_winner=False),
            _make_record("MW_WITCH_005", hook=0.3, comp=0.35, reward=0.32, is_winner=False),
        ]
        for r in records:
            store._repo.save_record(r)

        # 2. 构建索引
        count = engine.build_index()
        assert count == 5

        # 3. 检索相似素材
        results = engine.find_similar_asset("MW_WITCH_001", top_k=3)
        assert len(results) == 3
        assert results[0].similarity > 0.9

        # 4. Winner 模式分析
        pattern = engine.find_similar_winner_patterns("MW_WITCH_001", top_k=4)
        assert pattern is not None
        assert pattern.winner_count >= 2
        assert pattern.winner_ratio >= 0.5
        assert pattern.avg_hook_score > 0.7
        assert len(pattern.recommendations) > 0

    def test_similarity_ranking(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))
        engine = VisionRetrievalEngine(
            feature_store=store,
            index_dir=str(tmp_path / "index"),
        )

        # 创建一组素材：一个非常相似，一个中等，一个不相似
        records = [
            _make_record("MW_BASE", hook=0.9, comp=0.85, reward=0.88, brightness=0.7, contrast=0.5),
            _make_record("MW_VERY_SIMILAR", hook=0.89, comp=0.84, reward=0.87, brightness=0.69, contrast=0.49),
            _make_record("MW_MEDIUM", hook=0.7, comp=0.65, reward=0.68, brightness=0.5, contrast=0.4),
            _make_record("MW_DIFFERENT", hook=0.2, comp=0.25, reward=0.22, brightness=0.3, contrast=0.2),
        ]
        for r in records:
            store._repo.save_record(r)
        engine.build_index()

        results = engine.find_similar_asset("MW_BASE", top_k=3)
        assert len(results) == 3
        # 相似度应该递减
        assert results[0].similarity > results[1].similarity
        assert results[1].similarity > results[2].similarity
        # 最相似的应该是 MW_VERY_SIMILAR
        assert results[0].creative_asset_id == "MW_VERY_SIMILAR"

    def test_winner_loser_separation(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))
        engine = VisionRetrievalEngine(
            feature_store=store,
            index_dir=str(tmp_path / "index"),
        )

        # 高 hook + 高亮 + 高对比度 winner
        # 低 hook + 低亮 + 低对比度 loser（所有 8 维都不同）
        records = [
            _make_record("MW_WIN", hook=0.9, comp=0.85, reward=0.88,
                         brightness=0.7, contrast=0.6, edge=0.5, saturation=0.7, entropy=7.0,
                         is_winner=True, lifecycle="WINNER"),
            _make_record("MW_WIN2", hook=0.88, comp=0.83, reward=0.86,
                         brightness=0.68, contrast=0.58, edge=0.48, saturation=0.68, entropy=6.8,
                         is_winner=True, lifecycle="WINNER"),
            _make_record("MW_LOSE", hook=0.3, comp=0.35, reward=0.32,
                         brightness=0.25, contrast=0.2, edge=0.15, saturation=0.3, entropy=4.0,
                         is_winner=False),
            _make_record("MW_LOSE2", hook=0.28, comp=0.33, reward=0.30,
                         brightness=0.23, contrast=0.18, edge=0.13, saturation=0.28, entropy=3.8,
                         is_winner=False),
        ]
        for r in records:
            store._repo.save_record(r)
        engine.build_index()

        # 查询 winner
        pattern_winner = engine.find_similar_winner_patterns("MW_WIN", top_k=3)
        assert pattern_winner is not None
        assert pattern_winner.winner_count >= 1
        assert pattern_winner.avg_hook_score > 0.8

        # 查询 loser - 确认 loser 也能正常检索
        pattern_loser = engine.find_similar_winner_patterns("MW_LOSE", top_k=3)
        assert pattern_loser is not None
        assert pattern_loser.total_similar > 0

    def test_serialization_roundtrip(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))
        engine = VisionRetrievalEngine(
            feature_store=store,
            index_dir=str(tmp_path / "index"),
        )

        store._repo.save_record(_make_record("MW_VID_001", is_winner=True))
        engine.build_index()

        # 检索结果序列化
        results = engine.find_similar_asset("MW_VID_001", top_k=1)
        if results:
            d = results[0].to_dict()
            assert "similarity" in d
            assert "creative_asset_id" in d

        # WinnerPattern 序列化
        record = store._repo.find_by_asset_id("MW_VID_001")
        pattern = engine.retrieve_winner_patterns(record.feature_id, top_k=1)
        if pattern:
            d = pattern.to_dict()
            assert "winner_ratio" in d
            assert "recommendations" in d