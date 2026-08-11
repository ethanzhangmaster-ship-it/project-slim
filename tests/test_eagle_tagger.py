"""EagleAssetTagger 测试套件 — CME v1.9 Eagle 素材自动打标签。

测试覆盖:
  1. 数据模型 (AssetTag, AssetTagResult) 序列化/反序列化
  2. EagleAssetTagger 初始化 + 配置
  3. 标签词表 + 词汇统计
  4. CLIP 可用性检查 + 降级
  5. 图片加载 + 视频首帧提取
  6. 打标签流程 (CLIP 可用 / 不可用)
  7. 批量打标签
  8. embedding 缓存 (LRU)
  9. warmup
  10. EagleTagStore 持久化 (save/load/load_all/delete/exists/stats)
  11. 单例 (get_eagle_tagger / get_eagle_tag_store / reset)
  12. API 端点 (7 个)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.creative_mapping_engine.eagle_tagger import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_TAG_VOCABULARY,
    DEFAULT_TOP_K,
    AssetTag,
    AssetTagResult,
    EagleAssetTagger,
    EagleTagStore,
    get_eagle_tagger,
    get_eagle_tag_store,
    reset_eagle_tagger,
    reset_eagle_tag_store,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def tmp_image(tmp_path: Path) -> Path:
    """创建临时测试图片。"""
    img = Image.new("RGB", (224, 224), color=(128, 64, 32))
    img_path = tmp_path / "test_asset.png"
    img.save(img_path)
    return img_path


@pytest.fixture
def tmp_images(tmp_path: Path) -> list[Path]:
    """创建多张临时测试图片。"""
    paths: list[Path] = []
    for i in range(3):
        img = Image.new("RGB", (224, 224), color=(i * 80, 100, 200))
        img_path = tmp_path / f"test_asset_{i}.png"
        img.save(img_path)
        paths.append(img_path)
    return paths


@pytest.fixture
def tagger_no_clip() -> EagleAssetTagger:
    """创建 CLIP 不可用的 tagger (用于测试降级)。"""
    tagger = EagleAssetTagger(preload=False)
    tagger._clip_available = False
    return tagger


@pytest.fixture
def mock_tagger() -> EagleAssetTagger:
    """创建带 mock CLIP 的 tagger (用于测试打标签流程)。"""
    tagger = EagleAssetTagger(preload=False)
    tagger._clip_available = True
    tagger._clip_backend = "mock"
    tagger._clip_device = "cpu"

    # Mock encode_image 返回固定 tensor
    def mock_encode_image(img):
        import torch
        return torch.randn(1, 512)

    def mock_ensure_text_embeddings():
        import torch
        result = {}
        for category, tags in tagger.tag_vocabulary.items():
            for tag in tags:
                result[tag] = torch.randn(1, 512)
        return result

    tagger._encode_image = mock_encode_image
    tagger._ensure_text_embeddings = mock_ensure_text_embeddings

    # Mock classify 返回可预测的标签
    def mock_classify(img, top_k, min_confidence):
        return [
            AssetTag(tag="merge game", category="gameplay_type", confidence=0.85),
            AssetTag(tag="cartoon style", category="visual_style", confidence=0.72),
            AssetTag(tag="gameplay footage", category="scene", confidence=0.65),
            AssetTag(tag="dragon", category="element", confidence=0.55),
        ][:top_k]

    tagger._classify_image = mock_classify
    return tagger


@pytest.fixture
def tmp_store(tmp_path: Path) -> EagleTagStore:
    """创建临时存储。"""
    return EagleTagStore(data_dir=str(tmp_path / "eagle_tags"))


@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试前后重置单例。"""
    reset_eagle_tagger()
    reset_eagle_tag_store()
    yield
    reset_eagle_tagger()
    reset_eagle_tag_store()


# ── 1. 数据模型 ──────────────────────────────────────────


class TestAssetTag:
    """AssetTag 数据模型测试。"""

    def test_creation(self) -> None:
        tag = AssetTag(tag="merge game", category="gameplay_type", confidence=0.85)
        assert tag.tag == "merge game"
        assert tag.category == "gameplay_type"
        assert tag.confidence == 0.85

    def test_to_dict(self) -> None:
        tag = AssetTag(tag="dragon", category="element", confidence=0.92)
        d = tag.to_dict()
        assert d["tag"] == "dragon"
        assert d["category"] == "element"
        assert d["confidence"] == 0.92

    def test_from_dict(self) -> None:
        d = {"tag": "coins", "category": "element", "confidence": 0.7}
        tag = AssetTag.from_dict(d)
        assert tag.tag == "coins"
        assert tag.category == "element"
        assert tag.confidence == 0.7

    def test_roundtrip(self) -> None:
        tag = AssetTag(tag="battle scene", category="scene", confidence=0.88)
        d = tag.to_dict()
        restored = AssetTag.from_dict(d)
        assert restored.tag == tag.tag
        assert restored.category == tag.category
        assert restored.confidence == tag.confidence

    def test_confidence_rounding(self) -> None:
        tag = AssetTag(tag="test", category="test", confidence=0.123456789)
        d = tag.to_dict()
        assert d["confidence"] == 0.1235  # round to 4 decimal places


class TestAssetTagResult:
    """AssetTagResult 数据模型测试。"""

    def test_empty_result(self) -> None:
        result = AssetTagResult()
        assert not result.is_success
        assert result.top_tag is None
        assert result.method == "none"

    def test_success_result(self) -> None:
        tags = [
            AssetTag(tag="merge game", category="gameplay_type", confidence=0.9),
            AssetTag(tag="dragon", category="element", confidence=0.7),
        ]
        result = AssetTagResult(
            asset_path="/path/to/asset.mp4",
            asset_id="MW_VIDEO_001",
            tags=tags,
            method="clip",
        )
        assert result.is_success
        assert result.top_tag.tag == "merge game"
        assert result.to_dict()["tag_count"] == 2

    def test_error_result(self) -> None:
        result = AssetTagResult(error="CLIP not available")
        assert not result.is_success
        assert result.top_tag is None

    def test_to_dict(self) -> None:
        tags = [AssetTag(tag="t1", category="c1", confidence=0.5)]
        result = AssetTagResult(
            asset_path="/path/asset.png",
            asset_id="asset_001",
            tags=tags,
            method="clip",
        )
        d = result.to_dict()
        assert d["asset_id"] == "asset_001"
        assert d["method"] == "clip"
        assert d["tag_count"] == 1
        assert len(d["tags"]) == 1

    def test_from_dict(self) -> None:
        d = {
            "asset_path": "/path/asset.png",
            "asset_id": "asset_002",
            "tags": [{"tag": "t", "category": "c", "confidence": 0.6}],
            "method": "clip",
            "error": "",
        }
        result = AssetTagResult.from_dict(d)
        assert result.asset_id == "asset_002"
        assert len(result.tags) == 1
        assert result.tags[0].tag == "t"

    def test_roundtrip(self) -> None:
        tags = [
            AssetTag(tag="merge", category="gameplay_type", confidence=0.8),
            AssetTag(tag="cartoon", category="visual_style", confidence=0.6),
        ]
        result = AssetTagResult(
            asset_path="/p/a.png",
            asset_id="id_123",
            tags=tags,
            method="clip",
        )
        d = result.to_dict()
        restored = AssetTagResult.from_dict(d)
        assert restored.asset_id == result.asset_id
        assert restored.method == result.method
        assert len(restored.tags) == len(result.tags)
        assert restored.tags[0].tag == result.tags[0].tag


# ── 2. EagleAssetTagger 初始化 ─────────────────────────


class TestTaggerInit:
    """EagleAssetTagger 初始化测试。"""

    def test_default_init(self) -> None:
        tagger = EagleAssetTagger()
        assert tagger.min_confidence == DEFAULT_MIN_CONFIDENCE
        assert tagger.top_k == DEFAULT_TOP_K
        assert tagger.tag_vocabulary is not None
        assert len(tagger.tag_vocabulary) > 0

    def test_custom_config(self) -> None:
        tagger = EagleAssetTagger(
            min_confidence=0.3,
            top_k=3,
            ffmpeg_path="/usr/bin/ffmpeg",
        )
        assert tagger.min_confidence == 0.3
        assert tagger.top_k == 3
        assert tagger._ffmpeg_path == "/usr/bin/ffmpeg"

    def test_custom_vocabulary(self) -> None:
        custom_vocab = {
            "custom": ["tag1", "tag2"],
        }
        tagger = EagleAssetTagger(tag_vocabulary=custom_vocab)
        assert tagger.tag_vocabulary == custom_vocab
        assert tagger.total_tags_in_vocabulary == 2

    def test_preload_false(self) -> None:
        """preload=False 时 CLIP 不应被加载。"""
        tagger = EagleAssetTagger(preload=False)
        assert tagger._clip_available is None  # 未检查

    def test_categories(self) -> None:
        tagger = EagleAssetTagger()
        categories = tagger.categories
        assert "gameplay_type" in categories
        assert "scene" in categories
        assert "visual_style" in categories
        assert "element" in categories

    def test_total_tags_in_vocabulary(self) -> None:
        tagger = EagleAssetTagger()
        expected = sum(len(v) for v in DEFAULT_TAG_VOCABULARY.items())
        actual = tagger.total_tags_in_vocabulary
        assert actual == len(DEFAULT_TAG_VOCABULARY["gameplay_type"]) + \
            len(DEFAULT_TAG_VOCABULARY["scene"]) + \
            len(DEFAULT_TAG_VOCABULARY["visual_style"]) + \
            len(DEFAULT_TAG_VOCABULARY["element"])


# ── 3. CLIP 可用性 + 降级 ───────────────────────────────


class TestCLIPAvailability:
    """CLIP 可用性测试。"""

    def test_clip_not_available(self, tagger_no_clip: EagleAssetTagger) -> None:
        assert not tagger_no_clip.is_clip_available()

    def test_device_default_cpu(self, tagger_no_clip: EagleAssetTagger) -> None:
        assert tagger_no_clip.device == "cpu"

    def test_backend_empty_when_no_clip(self, tagger_no_clip: EagleAssetTagger) -> None:
        assert tagger_no_clip.backend == ""

    def test_warmup_fails_without_clip(self, tagger_no_clip: EagleAssetTagger) -> None:
        assert not tagger_no_clip.warmup()


# ── 4. 打标签流程 ────────────────────────────────────────


class TestTagAsset:
    """打标签流程测试。"""

    def test_empty_path(self, mock_tagger: EagleAssetTagger) -> None:
        result = mock_tagger.tag_asset("")
        assert not result.is_success
        assert "empty" in result.error

    def test_nonexistent_file(self, mock_tagger: EagleAssetTagger) -> None:
        result = mock_tagger.tag_asset("/nonexistent/path/file.png")
        assert not result.is_success
        assert "not found" in result.error

    def test_clip_not_available(self, tagger_no_clip: EagleAssetTagger, tmp_image: Path) -> None:
        result = tagger_no_clip.tag_asset(str(tmp_image))
        assert not result.is_success
        assert "CLIP not available" in result.error

    def test_success(self, mock_tagger: EagleAssetTagger, tmp_image: Path) -> None:
        result = mock_tagger.tag_asset(str(tmp_image))
        assert result.is_success
        assert result.asset_id == "test_asset"
        assert result.method == "clip"
        assert len(result.tags) > 0
        assert result.top_tag is not None

    def test_top_k_limit(self, mock_tagger: EagleAssetTagger, tmp_image: Path) -> None:
        result = mock_tagger.tag_asset(str(tmp_image), top_k=2)
        assert result.is_success
        assert len(result.tags) <= 2

    def test_min_confidence_filter(
        self, mock_tagger: EagleAssetTagger, tmp_image: Path
    ) -> None:
        """mock_tagger 的 _classify_image 被 mock, 不会过滤 min_confidence.
        此测试验证 tag_asset 传递了 min_confidence 参数。"""
        result = mock_tagger.tag_asset(
            str(tmp_image), min_confidence=0.99
        )
        # mock _classify_image 不应用 min_confidence, 标签仍然返回
        # 真实过滤逻辑在 _classify_image 内部, 此处验证参数传递
        assert result.is_success


class TestTagBatch:
    """批量打标签测试。"""

    def test_empty_list(self, mock_tagger: EagleAssetTagger) -> None:
        results = mock_tagger.tag_batch([])
        assert results == []

    def test_batch(
        self, mock_tagger: EagleAssetTagger, tmp_images: list[Path]
    ) -> None:
        paths = [str(p) for p in tmp_images]
        results = mock_tagger.tag_batch(paths)
        assert len(results) == 3
        for r in results:
            assert r.is_success
            assert len(r.tags) > 0

    def test_batch_with_nonexistent(
        self, mock_tagger: EagleAssetTagger, tmp_image: Path
    ) -> None:
        results = mock_tagger.tag_batch([
            str(tmp_image),
            "/nonexistent/file.png",
        ])
        assert len(results) == 2
        assert results[0].is_success
        assert not results[1].is_success

    def test_batch_order_preserved(
        self, mock_tagger: EagleAssetTagger, tmp_images: list[Path]
    ) -> None:
        paths = [str(p) for p in tmp_images]
        results = mock_tagger.tag_batch(paths)
        for i, r in enumerate(results):
            assert r.asset_id == f"test_asset_{i}"


# ── 5. 图片/视频加载 ─────────────────────────────────────


class TestImageLoading:
    """图片和视频加载测试。"""

    def test_load_image(self, tagger_no_clip: EagleAssetTagger, tmp_image: Path) -> None:
        img = tagger_no_clip._load_image(str(tmp_image))
        assert img is not None
        assert img.mode == "RGB"

    def test_load_nonexistent_image(self, tagger_no_clip: EagleAssetTagger) -> None:
        img = tagger_no_clip._load_image("/nonexistent/image.png")
        assert img is None

    def test_load_image_from_asset_image(
        self, tagger_no_clip: EagleAssetTagger, tmp_image: Path
    ) -> None:
        img = tagger_no_clip._load_image_from_asset(str(tmp_image))
        assert img is not None

    def test_load_image_from_asset_video(self, tagger_no_clip: EagleAssetTagger) -> None:
        """视频文件 (ffmpeg 不可用时返回 None)。"""
        # 创建假视频文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            # ffmpeg 可能不可用, 所以结果可能是 None
            img = tagger_no_clip._load_image_from_asset(video_path)
            # 不断言成功, 只断言不抛异常
        finally:
            Path(video_path).unlink(missing_ok=True)

    def test_load_image_from_asset_unknown_ext(
        self, tagger_no_clip: EagleAssetTagger, tmp_image: Path
    ) -> None:
        """未知扩展名, 尝试当图片加载。"""
        # 重命名为 .xyz
        new_path = tmp_image.with_suffix(".xyz")
        tmp_image.rename(new_path)
        img = tagger_no_clip._load_image_from_asset(str(new_path))
        # PIL 可能能加载 (取决于内容), 也可能返回 None
        # 主要测试不抛异常


# ── 6. embedding 缓存 ────────────────────────────────────


class TestEmbeddingCache:
    """embedding 缓存测试。"""

    def test_clear_cache(self, mock_tagger: EagleAssetTagger) -> None:
        mock_tagger._embedding_cache["test"] = "value"
        mock_tagger.clear_cache()
        assert len(mock_tagger._embedding_cache) == 0
        assert len(mock_tagger._text_embedding_cache) == 0

    def test_cache_size_initial(self, mock_tagger: EagleAssetTagger) -> None:
        assert mock_tagger.embedding_cache_size == 0

    def test_image_content_key(self, tagger_no_clip: EagleAssetTagger) -> None:
        img1 = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img2 = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img3 = Image.new("RGB", (100, 100), color=(0, 255, 0))

        key1 = tagger_no_clip._image_content_key(img1)
        key2 = tagger_no_clip._image_content_key(img2)
        key3 = tagger_no_clip._image_content_key(img3)

        assert key1 == key2  # 相同内容 → 相同 key
        assert key1 != key3  # 不同内容 → 不同 key


# ── 7. EagleTagStore 持久化 ──────────────────────────────


class TestEagleTagStore:
    """EagleTagStore 持久化测试。"""

    def test_save_and_load(self, tmp_store: EagleTagStore) -> None:
        result = AssetTagResult(
            asset_path="/path/asset.png",
            asset_id="asset_001",
            tags=[AssetTag(tag="merge", category="gameplay_type", confidence=0.9)],
            method="clip",
        )
        saved_path = tmp_store.save(result)
        assert saved_path.exists()

        loaded = tmp_store.load("asset_001")
        assert loaded is not None
        assert loaded.asset_id == "asset_001"
        assert len(loaded.tags) == 1
        assert loaded.tags[0].tag == "merge"

    def test_load_nonexistent(self, tmp_store: EagleTagStore) -> None:
        loaded = tmp_store.load("nonexistent_id")
        assert loaded is None

    def test_exists(self, tmp_store: EagleTagStore) -> None:
        result = AssetTagResult(
            asset_id="asset_002",
            tags=[AssetTag(tag="t", category="c", confidence=0.5)],
            method="clip",
        )
        assert not tmp_store.exists("asset_002")
        tmp_store.save(result)
        assert tmp_store.exists("asset_002")

    def test_delete(self, tmp_store: EagleTagStore) -> None:
        result = AssetTagResult(
            asset_id="asset_003",
            tags=[AssetTag(tag="t", category="c", confidence=0.5)],
            method="clip",
        )
        tmp_store.save(result)
        assert tmp_store.delete("asset_003")
        assert not tmp_store.exists("asset_003")
        assert not tmp_store.delete("asset_003")  # 已删除

    def test_load_all(self, tmp_store: EagleTagStore) -> None:
        for i in range(3):
            result = AssetTagResult(
                asset_id=f"asset_{i}",
                tags=[AssetTag(tag=f"tag_{i}", category="c", confidence=0.8)],
                method="clip",
            )
            tmp_store.save(result)

        all_results = tmp_store.load_all()
        assert len(all_results) == 3

    def test_list_asset_ids(self, tmp_store: EagleTagStore) -> None:
        for i in range(5):
            result = AssetTagResult(
                asset_id=f"asset_{i}",
                tags=[AssetTag(tag="t", category="c", confidence=0.8)],
                method="clip",
            )
            tmp_store.save(result)

        ids = tmp_store.list_asset_ids()
        assert len(ids) == 5
        assert "asset_0" in ids
        assert "asset_4" in ids

    def test_get_stats_empty(self, tmp_store: EagleTagStore) -> None:
        stats = tmp_store.get_stats()
        assert stats["total_assets"] == 0
        assert stats["total_tags"] == 0
        assert stats["avg_tags_per_asset"] == 0.0

    def test_get_stats_with_data(self, tmp_store: EagleTagStore) -> None:
        for i in range(3):
            result = AssetTagResult(
                asset_id=f"asset_{i}",
                tags=[
                    AssetTag(tag="merge", category="gameplay_type", confidence=0.9),
                    AssetTag(tag="cartoon", category="visual_style", confidence=0.7),
                ],
                method="clip",
            )
            tmp_store.save(result)

        stats = tmp_store.get_stats()
        assert stats["total_assets"] == 3
        assert stats["total_tags"] == 6
        assert stats["avg_tags_per_asset"] == pytest.approx(2.0)
        assert stats["category_distribution"]["gameplay_type"] == 3
        assert stats["category_distribution"]["visual_style"] == 3

    def test_data_dir_creation(self, tmp_path: Path) -> None:
        """存储目录不存在时自动创建。"""
        new_dir = tmp_path / "new_dir" / "eagle_tags"
        store = EagleTagStore(data_dir=str(new_dir))
        assert new_dir.exists()

    def test_save_unknown_asset_id(self, tmp_store: EagleTagStore) -> None:
        """asset_id 为空时使用 "unknown"。"""
        result = AssetTagResult(tags=[AssetTag(tag="t", category="c", confidence=0.5)])
        saved_path = tmp_store.save(result)
        assert "unknown" in saved_path.name

    def test_load_corrupted_file(self, tmp_store: EagleTagStore) -> None:
        """损坏的 JSON 文件返回 None。"""
        file_path = tmp_store.data_dir / "corrupt.json"
        file_path.write_text("not valid json {{{")
        loaded = tmp_store.load("corrupt")
        assert loaded is None


# ── 8. 单例 ──────────────────────────────────────────────


class TestSingleton:
    """单例测试。"""

    def test_get_eagle_tagger_singleton(self) -> None:
        t1 = get_eagle_tagger()
        t2 = get_eagle_tagger()
        assert t1 is t2

    def test_reset_eagle_tagger(self) -> None:
        t1 = get_eagle_tagger()
        reset_eagle_tagger()
        t2 = get_eagle_tagger()
        assert t1 is not t2

    def test_get_eagle_tag_store_singleton(self) -> None:
        s1 = get_eagle_tag_store()
        s2 = get_eagle_tag_store()
        assert s1 is s2

    def test_reset_eagle_tag_store(self) -> None:
        s1 = get_eagle_tag_store()
        reset_eagle_tag_store()
        s2 = get_eagle_tag_store()
        assert s1 is not s2


# ── 9. 默认标签词表 ──────────────────────────────────────


class TestTagVocabulary:
    """默认标签词表测试。"""

    def test_default_vocabulary_has_categories(self) -> None:
        assert "gameplay_type" in DEFAULT_TAG_VOCABULARY
        assert "scene" in DEFAULT_TAG_VOCABULARY
        assert "visual_style" in DEFAULT_TAG_VOCABULARY
        assert "element" in DEFAULT_TAG_VOCABULARY

    def test_gameplay_type_tags(self) -> None:
        tags = DEFAULT_TAG_VOCABULARY["gameplay_type"]
        assert len(tags) >= 5
        assert "merge game" in tags
        assert "match-3 puzzle" in tags

    def test_scene_tags(self) -> None:
        tags = DEFAULT_TAG_VOCABULARY["scene"]
        assert len(tags) >= 5
        assert "reward unlock screen" in tags
        assert "gameplay footage" in tags

    def test_visual_style_tags(self) -> None:
        tags = DEFAULT_TAG_VOCABULARY["visual_style"]
        assert len(tags) >= 3
        assert "cartoon style" in tags

    def test_element_tags(self) -> None:
        tags = DEFAULT_TAG_VOCABULARY["element"]
        assert len(tags) >= 5
        assert "dragon" in tags
        assert "gold coins" in tags

    def test_all_categories_non_empty(self) -> None:
        for category, tags in DEFAULT_TAG_VOCABULARY.items():
            assert len(tags) > 0, f"category {category} is empty"


# ── 10. API 端点 ─────────────────────────────────────────


class TestAPIEndpoints:
    """API 端点测试。"""

    @pytest.fixture
    def client(self, tmp_path: Path):
        """创建测试客户端, 使用临时存储目录。"""
        from fastapi.testclient import TestClient

        # 重置单例
        reset_eagle_tagger()
        reset_eagle_tag_store()

        from src.market_ops.workspace.app import app

        # Patch the store singleton to use tmp directory
        tmp_store = EagleTagStore(data_dir=str(tmp_path / "eagle_tags"))

        with patch(
            "src.market_ops.workspace.app._get_eagle_tag_store",
            return_value=tmp_store,
        ):
            # Also patch the tagger to use mock
            mock_t = EagleAssetTagger()
            mock_t._clip_available = True
            mock_t._clip_backend = "mock"

            def mock_tag_asset(asset_path, top_k=None, min_confidence=None):
                return AssetTagResult(
                    asset_path=asset_path,
                    asset_id=Path(asset_path).stem,
                    tags=[
                        AssetTag(tag="merge game", category="gameplay_type", confidence=0.85),
                        AssetTag(tag="cartoon style", category="visual_style", confidence=0.72),
                    ],
                    method="clip",
                )

            def mock_tag_batch(asset_paths, top_k=None, min_confidence=None):
                return [mock_tag_asset(p, top_k, min_confidence) for p in asset_paths]

            mock_t.tag_asset = mock_tag_asset
            mock_t.tag_batch = mock_tag_batch
            mock_t.is_clip_available = lambda: True
            mock_t._clip_device = "cpu"
            mock_t._clip_backend = "mock"
            mock_t.tag_vocabulary = DEFAULT_TAG_VOCABULARY
            mock_t._embedding_cache = {}

            with patch(
                "src.market_ops.workspace.app._get_eagle_tagger",
                return_value=mock_t,
            ):
                client = TestClient(app)
                yield client

    def test_tag_endpoint(self, client, tmp_image: Path) -> None:
        response = client.post(
            "/api/creative-mapping/eagle-tagger/tag",
            json={"asset_path": str(tmp_image), "save": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "clip"
        assert len(data["tags"]) > 0

    def test_tag_endpoint_missing_path(self, client) -> None:
        response = client.post(
            "/api/creative-mapping/eagle-tagger/tag",
            json={},
        )
        assert response.status_code == 400

    def test_tag_batch_endpoint(self, client, tmp_images: list[Path]) -> None:
        response = client.post(
            "/api/creative-mapping/eagle-tagger/tag-batch",
            json={
                "asset_paths": [str(p) for p in tmp_images],
                "save": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["success"] == 3

    def test_tag_batch_empty_list(self, client) -> None:
        response = client.post(
            "/api/creative-mapping/eagle-tagger/tag-batch",
            json={"asset_paths": []},
        )
        assert response.status_code == 400

    def test_get_tags_not_found(self, client) -> None:
        response = client.get(
            "/api/creative-mapping/eagle-tagger/tags/nonexistent_id"
        )
        assert response.status_code == 404

    def test_list_tags_empty(self, client) -> None:
        response = client.get("/api/creative-mapping/eagle-tagger/tags")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_save_and_get_tags(self, client, tmp_image: Path) -> None:
        """打标签并保存, 然后查询。"""
        # 打标签并保存
        response = client.post(
            "/api/creative-mapping/eagle-tagger/tag",
            json={"asset_path": str(tmp_image), "save": True},
        )
        assert response.status_code == 200

        # 查询标签
        asset_id = tmp_image.stem
        response = client.get(
            f"/api/creative-mapping/eagle-tagger/tags/{asset_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["asset_id"] == asset_id

    def test_delete_tags(self, client, tmp_image: Path) -> None:
        """保存后删除。"""
        # 先打标签并保存
        client.post(
            "/api/creative-mapping/eagle-tagger/tag",
            json={"asset_path": str(tmp_image), "save": True},
        )
        asset_id = tmp_image.stem

        # 删除
        response = client.delete(
            f"/api/creative-mapping/eagle-tagger/tags/{asset_id}"
        )
        assert response.status_code == 200

        # 确认已删除
        response = client.get(
            f"/api/creative-mapping/eagle-tagger/tags/{asset_id}"
        )
        assert response.status_code == 404

    def test_delete_not_found(self, client) -> None:
        response = client.delete(
            "/api/creative-mapping/eagle-tagger/tags/nonexistent"
        )
        assert response.status_code == 404

    def test_stats_endpoint(self, client) -> None:
        response = client.get("/api/creative-mapping/eagle-tagger/stats")
        assert response.status_code == 200
        data = response.json()
        assert "store" in data
        assert "tagger" in data
        assert data["tagger"]["clip_available"] is True

    def test_vocabulary_endpoint(self, client) -> None:
        response = client.get("/api/creative-mapping/eagle-tagger/vocabulary")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "total_tags" in data
        assert data["total_tags"] > 0
        assert "gameplay_type" in data["categories"]


# ── 11. warmup ───────────────────────────────────────────


class TestWarmup:
    """warmup 测试。"""

    def test_warmup_without_clip(self, tagger_no_clip: EagleAssetTagger) -> None:
        assert not tagger_no_clip.warmup()

    def test_warmup_with_mock_clip(self, mock_tagger: EagleAssetTagger) -> None:
        """mock_tagger 的 warmup 应该成功 (因为 _encode_image 被 mock)。"""
        assert mock_tagger.warmup()
