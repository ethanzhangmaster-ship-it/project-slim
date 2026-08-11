"""FrameSimilarityComputer v1.3 性能优化测试。

覆盖:
  - 预加载模型 (preload=True)
  - 批量计算 (compute_batch) — 结果与逐个 compute 一致
  - GPU/设备检测 (device 属性, CPU 环境下为 "cpu")
  - Embedding 缓存 — 相同图片内容命中缓存
  - warmup 预热
  - backend 属性
  - 批量计算 API 端点 POST /frame-similarity/batch
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.market_ops.creative_mapping_engine.frame_similarity import (
    FrameSimilarityComputer,
)


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _create_solid_image(path: Path, color: tuple = (255, 0, 0), size: tuple = (64, 64)):
    """创建纯色图片。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color)
    img.save(path)


def _create_gradient_image(path: Path, size: tuple = (64, 64)):
    """创建渐变图片。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size)
    pixels = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            pixels[x, y] = (x * 4 % 256, y * 4 % 256, 128)
    img.save(path)


# ═══════════════════════════════════════════════════════════════
# 预加载测试
# ═══════════════════════════════════════════════════════════════


class TestPreload:
    """预加载模型测试。"""

    def test_preload_false_does_not_load_clip(self):
        """preload=False → __init__ 不触发 CLIP 加载。"""
        computer = FrameSimilarityComputer(enable_clip=True, preload=False)
        # _clip_available 应为 None（未初始化）
        assert computer._clip_available is None

    def test_preload_true_triggers_clip_init(self):
        """preload=True → __init__ 立即触发 CLIP 可用性检查。"""
        with patch(
            "src.market_ops.creative_mapping_engine.frame_similarity"
            ".FrameSimilarityComputer._try_init_clip",
            return_value=False,
        ) as mock_init:
            computer = FrameSimilarityComputer(enable_clip=True, preload=True)
            mock_init.assert_called_once()
            assert computer._clip_available is False

    def test_preload_true_with_clip_disabled_no_init(self):
        """preload=True 但 enable_clip=False → 不触发加载。"""
        with patch(
            "src.market_ops.creative_mapping_engine.frame_similarity"
            ".FrameSimilarityComputer._try_init_clip"
        ) as mock_init:
            computer = FrameSimilarityComputer(enable_clip=False, preload=True)
            mock_init.assert_not_called()
            assert computer._clip_available is False

    def test_preload_sets_device(self):
        """preload=True 后 device 属性可用 (cpu 或 cuda)。"""
        computer = FrameSimilarityComputer(enable_clip=False, preload=True)
        # enable_clip=False → device 保持默认 "cpu"
        assert computer.device in ("cpu", "cuda")


# ═══════════════════════════════════════════════════════════════
# 批量计算测试
# ═══════════════════════════════════════════════════════════════


class TestComputeBatch:
    """批量计算测试。"""

    def test_empty_pairs_returns_empty(self):
        """空列表 → 空结果。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        assert computer.compute_batch([]) == []

    def test_batch_results_match_single_compute(self, tmp_path: Path):
        """批量结果与逐个 compute 一致。"""
        _create_solid_image(tmp_path / "thumb1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "thumb2.jpg", color=(0, 255, 0))
        _create_gradient_image(tmp_path / "eagle2.jpg")

        pairs = [
            (str(tmp_path / "thumb1.jpg"), str(tmp_path / "eagle1.jpg")),
            (str(tmp_path / "thumb2.jpg"), str(tmp_path / "eagle2.jpg")),
        ]

        computer = FrameSimilarityComputer(enable_clip=False)
        single_results = [computer.compute(t, e) for t, e in pairs]
        # 清空缓存后批量计算
        computer.clear_cache()
        batch_results = computer.compute_batch(pairs)

        assert len(batch_results) == len(single_results)
        for (s_score, s_method, _), (b_score, b_method, _) in zip(
            single_results, batch_results
        ):
            assert b_score == s_score
            assert b_method == s_method

    def test_batch_preserves_order(self, tmp_path: Path):
        """批量结果顺序与输入一致。"""
        _create_solid_image(tmp_path / "thumb_a.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle_a.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "thumb_b.jpg", color=(0, 0, 255))
        _create_solid_image(tmp_path / "eagle_b.jpg", color=(0, 0, 255))

        pairs = [
            (str(tmp_path / "thumb_a.jpg"), str(tmp_path / "eagle_a.jpg")),
            (str(tmp_path / "thumb_b.jpg"), str(tmp_path / "eagle_b.jpg")),
        ]

        computer = FrameSimilarityComputer(enable_clip=False)
        results = computer.compute_batch(pairs)
        assert len(results) == 2
        # 两对都是相同颜色 → 都应为 1.0
        assert results[0][0] == 1.0
        assert results[1][0] == 1.0

    def test_batch_handles_empty_strings(self):
        """批量输入包含空字符串 → 返回 (0.0, none, False)。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        results = computer.compute_batch([("", "/path"), ("/thumb", "")])
        assert results == [(0.0, "none", False), (0.0, "none", False)]

    def test_batch_handles_nonexistent_files(self, tmp_path: Path):
        """批量输入包含不存在的文件 → 返回 (0.0, none, False)。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        results = computer.compute_batch([
            (str(tmp_path / "nope1.jpg"), str(tmp_path / "nope2.jpg")),
        ])
        assert results == [(0.0, "none", False)]

    def test_batch_cache_hit(self, tmp_path: Path):
        """批量计算后再次调用相同对 → 命中缓存。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")
        pairs = [
            (str(tmp_path / "thumb.jpg"), str(tmp_path / "eagle.jpg")),
        ]

        computer = FrameSimilarityComputer(enable_clip=False)
        first = computer.compute_batch(pairs)
        assert first[0][2] is False  # 未命中缓存

        second = computer.compute_batch(pairs)
        assert second[0][2] is True  # 命中缓存
        assert second[0][0] == first[0][0]

    def test_batch_mixed_cached_and_new(self, tmp_path: Path):
        """混合输入：部分缓存命中，部分新计算。"""
        _create_solid_image(tmp_path / "thumb1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "thumb2.jpg", color=(0, 255, 0))
        _create_solid_image(tmp_path / "eagle2.jpg", color=(0, 255, 0))

        pair1 = (str(tmp_path / "thumb1.jpg"), str(tmp_path / "eagle1.jpg"))
        pair2 = (str(tmp_path / "thumb2.jpg"), str(tmp_path / "eagle2.jpg"))

        computer = FrameSimilarityComputer(enable_clip=False)
        # 先计算 pair1（缓存）
        computer.compute_batch([pair1])
        # 批量计算 pair1（缓存命中）+ pair2（新）
        results = computer.compute_batch([pair1, pair2])
        assert results[0][2] is True   # pair1 缓存命中
        assert results[1][2] is False  # pair2 新计算


# ═══════════════════════════════════════════════════════════════
# GPU / 设备检测测试
# ═══════════════════════════════════════════════════════════════


class TestDeviceDetection:
    """GPU/设备检测测试。"""

    def test_device_defaults_to_cpu(self):
        """未加载 CLIP → device 默认为 cpu。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        assert computer.device == "cpu"

    def test_backend_empty_when_clip_disabled(self):
        """enable_clip=False → backend 为空字符串。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        assert computer.backend == ""

    def test_device_after_clip_init(self):
        """CLIP 初始化后 device 为 cpu 或 cuda。"""
        computer = FrameSimilarityComputer(enable_clip=True, preload=False)
        # 触发 CLIP 可用性检查
        computer.is_clip_available()
        assert computer.device in ("cpu", "cuda")


# ═══════════════════════════════════════════════════════════════
# Embedding 缓存测试
# ═══════════════════════════════════════════════════════════════


class TestEmbeddingCache:
    """Embedding 缓存测试。"""

    def test_image_content_key_deterministic(self, tmp_path: Path):
        """相同图片内容 → 相同缓存键。"""
        _create_solid_image(tmp_path / "img1.jpg", color=(128, 128, 128))
        _create_solid_image(tmp_path / "img2.jpg", color=(128, 128, 128))

        img1 = Image.open(tmp_path / "img1.jpg")
        img2 = Image.open(tmp_path / "img2.jpg")

        key1 = FrameSimilarityComputer._image_content_key(img1)
        key2 = FrameSimilarityComputer._image_content_key(img2)
        assert key1 == key2

    def test_image_content_key_differs_for_different_content(self, tmp_path: Path):
        """不同图片内容 → 不同缓存键。"""
        _create_solid_image(tmp_path / "img1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "img2.jpg", color=(0, 255, 0))

        img1 = Image.open(tmp_path / "img1.jpg")
        img2 = Image.open(tmp_path / "img2.jpg")

        key1 = FrameSimilarityComputer._image_content_key(img1)
        key2 = FrameSimilarityComputer._image_content_key(img2)
        assert key1 != key2

    def test_embedding_cache_hit_via_mock(self, tmp_path: Path):
        """通过 mock 验证 embedding 缓存命中。"""
        _create_solid_image(tmp_path / "thumb.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle.jpg", color=(255, 0, 0))

        computer = FrameSimilarityComputer(enable_clip=False)

        # mock CLIP 可用，使用 embedding 缓存路径
        call_count = {"encode": 0}
        original_content_key = FrameSimilarityComputer._image_content_key

        def mock_compute_clip(img1, img2):
            # 模拟 embedding 计算（带缓存）
            key1 = original_content_key(img1)
            key2 = original_content_key(img2)
            cached1 = computer._get_embedding_cached(key1)
            cached2 = computer._get_embedding_cached(key2)
            if cached1 is None:
                call_count["encode"] += 1
                computer._set_embedding_cached(key1, "fake_feat_1")
            if cached2 is None:
                call_count["encode"] += 1
                computer._set_embedding_cached(key2, "fake_feat_2")
            return 0.92  # cosine

        with patch.object(computer, "_clip_available", True), \
             patch.object(
                computer,
                "_compute_clip_similarity",
                side_effect=mock_compute_clip,
             ):
            computer.compute(
                str(tmp_path / "thumb.jpg"),
                str(tmp_path / "eagle.jpg"),
            )
            first_encodes = call_count["encode"]
            # 第二次相同图片应命中 embedding 缓存
            computer.clear_cache()  # 清结果缓存，但保留 embedding 缓存
            computer.compute(
                str(tmp_path / "thumb.jpg"),
                str(tmp_path / "eagle.jpg"),
            )
            assert call_count["encode"] == first_encodes  # 无新增编码

    def test_clear_embedding_cache(self):
        """clear_embedding_cache 清空 embedding 缓存。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        computer._set_embedding_cached("key1", "feat1")
        assert computer.embedding_cache_size == 1
        computer.clear_embedding_cache()
        assert computer.embedding_cache_size == 0

    def test_embedding_cache_lru_eviction(self):
        """embedding 缓存 LRU 淘汰。"""
        computer = FrameSimilarityComputer(
            enable_clip=False, embedding_cache_size=3
        )
        for i in range(4):
            computer._set_embedding_cached(f"key{i}", f"feat{i}")
        # 超过上限 3 → 淘汰最旧
        assert computer.embedding_cache_size == 3
        assert computer._get_embedding_cached("key0") is None
        assert computer._get_embedding_cached("key3") is not None


# ═══════════════════════════════════════════════════════════════
# Warmup 预热测试
# ═══════════════════════════════════════════════════════════════


class TestWarmup:
    """warmup 预热测试。"""

    def test_warmup_returns_false_when_clip_unavailable(self):
        """CLIP 不可用 → warmup 返回 False。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        assert computer.warmup() is False

    def test_warmup_success_with_mock(self):
        """CLIP 可用 → warmup 返回 True。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        with patch.object(computer, "_clip_available", True), \
             patch.object(
                computer,
                "_compute_clip_similarity",
                return_value=0.95,
             ):
            assert computer.warmup() is True

    def test_warmup_failure_returns_false(self):
        """warmup 推理失败 → 返回 False。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        with patch.object(computer, "_clip_available", True), \
             patch.object(
                computer,
                "_compute_clip_similarity",
                side_effect=RuntimeError("inference error"),
             ):
            assert computer.warmup() is False


# ═══════════════════════════════════════════════════════════════
# 批量计算 API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestBatchFrameSimilarityAPI:
    """批量帧相似度 API 端点测试。"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path: Path):
        """临时 client。"""
        from fastapi.testclient import TestClient

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        if hasattr(app_module._get_creative_mapping_engine, "_instance"):
            monkeypatch.delattr(app_module._get_creative_mapping_engine, "_instance")

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_batch_api_success(self, client: TestClient, tmp_path: Path):
        """POST /frame-similarity/batch — 成功批量计算。"""
        _create_solid_image(tmp_path / "thumb1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "thumb2.jpg", color=(0, 255, 0))
        _create_solid_image(tmp_path / "eagle2.jpg", color=(0, 255, 0))

        response = client.post(
            "/api/creative-mapping/frame-similarity/batch",
            json={
                "pairs": [
                    {
                        "thumbnail_source": str(tmp_path / "thumb1.jpg"),
                        "eagle_path": str(tmp_path / "eagle1.jpg"),
                    },
                    {
                        "thumbnail_source": str(tmp_path / "thumb2.jpg"),
                        "eagle_path": str(tmp_path / "eagle2.jpg"),
                    },
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["results"]) == 2
        assert "score" in data["results"][0]
        assert "method" in data["results"][0]
        assert "cached" in data["results"][0]
        assert "elapsed_seconds" in data
        # 相同图片 → 1.0
        assert data["results"][0]["score"] == 1.0
        assert data["results"][1]["score"] == 1.0

    def test_batch_api_missing_pairs(self, client: TestClient):
        """POST /frame-similarity/batch — 缺少 pairs → 400。"""
        response = client.post(
            "/api/creative-mapping/frame-similarity/batch",
            json={},
        )
        assert response.status_code == 400

    def test_batch_api_empty_pairs_list(self, client: TestClient):
        """POST /frame-similarity/batch — 空 pairs 列表 → 400 (视为缺失)。"""
        response = client.post(
            "/api/creative-mapping/frame-similarity/batch",
            json={"pairs": []},
        )
        assert response.status_code == 400

    def test_batch_api_nonexistent_files(self, client: TestClient, tmp_path: Path):
        """POST /frame-similarity/batch — 不存在的文件 → score=0.0。"""
        response = client.post(
            "/api/creative-mapping/frame-similarity/batch",
            json={
                "pairs": [
                    {
                        "thumbnail_source": str(tmp_path / "nope.jpg"),
                        "eagle_path": str(tmp_path / "nope2.jpg"),
                    }
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["score"] == 0.0
        assert data["results"][0]["method"] == "none"

    def test_batch_api_elapsed_seconds_is_float(self, client: TestClient, tmp_path: Path):
        """POST /frame-similarity/batch — elapsed_seconds 为数值。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")
        response = client.post(
            "/api/creative-mapping/frame-similarity/batch",
            json={
                "pairs": [
                    {
                        "thumbnail_source": str(tmp_path / "thumb.jpg"),
                        "eagle_path": str(tmp_path / "eagle.jpg"),
                    }
                ]
            },
        )
        data = response.json()
        assert isinstance(data["elapsed_seconds"], (int, float))
        assert data["elapsed_seconds"] >= 0


# ═══════════════════════════════════════════════════════════════
# 属性与 repr 测试
# ═══════════════════════════════════════════════════════════════


class TestPropertiesAndRepr:
    """属性与 repr 测试。"""

    def test_repr_contains_method_and_device(self):
        """repr 包含 method 和 device 信息。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        repr_str = repr(computer)
        assert "FrameSimilarityComputer" in repr_str
        assert "device=" in repr_str

    def test_cache_size_property(self, tmp_path: Path):
        """cache_size 属性反映缓存条目数。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")
        computer = FrameSimilarityComputer(enable_clip=False)
        assert computer.cache_size == 0
        computer.compute(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert computer.cache_size == 1

    def test_is_clip_available_method(self):
        """is_clip_available 方法返回 bool。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        assert isinstance(computer.is_clip_available(), bool)
        assert computer.is_clip_available() is False
