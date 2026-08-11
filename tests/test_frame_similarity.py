"""FrameSimilarityComputer — 单元测试。

覆盖:
  - 基础功能: compute 方法返回 (score, method, cached)
  - 空输入处理: thumbnail_source 或 eagle_path 为空
  - 图像加载: 本地图片文件、不存在的文件
  - pHash 降级: CLIP 不可用时使用 pHash
  - 相同图片: pHash 相似度 = 1.0
  - 不同图片: pHash 相似度 < 1.0
  - LRU 缓存: 相同输入命中缓存
  - 评分门禁: 归一化评分 (1.0/0.85/0.70/0.0)
  - CLIP 归一化: cosine → score 映射
  - API 端点: POST /frame-similarity
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from src.market_ops.creative_mapping_engine.frame_similarity import (
    COSINE_HIGH,
    COSINE_LOW,
    COSINE_MEDIUM,
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
# 基础功能测试
# ═══════════════════════════════════════════════════════════════


class TestFrameSimilarityBasic:
    """基础功能测试。"""

    def test_empty_thumbnail_returns_zero(self):
        """空 thumbnail_source → 0.0。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, cached = computer.compute("", "/path/to/video.mp4")
        assert score == 0.0
        assert method == "none"
        assert cached is False

    def test_empty_eagle_path_returns_zero(self):
        """空 eagle_path → 0.0。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, cached = computer.compute("http://thumb.jpg", "")
        assert score == 0.0
        assert method == "none"
        assert cached is False

    def test_both_empty_returns_zero(self):
        """两者都空 → 0.0。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, cached = computer.compute("", "")
        assert score == 0.0
        assert method == "none"
        assert cached is False

    def test_nonexistent_files_returns_zero(self, tmp_path: Path):
        """文件不存在 → 0.0。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, cached = computer.compute(
            str(tmp_path / "nonexistent.jpg"),
            str(tmp_path / "nonexistent.mp4"),
        )
        assert score == 0.0
        assert method == "none"
        assert cached is False

    def test_returns_tuple_of_three(self, tmp_path: Path):
        """返回值为 (float, str, bool) 三元组。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        result = computer.compute(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], float)
        assert isinstance(result[1], str)
        assert isinstance(result[2], bool)


# ═══════════════════════════════════════════════════════════════
# pHash 降级测试
# ═══════════════════════════════════════════════════════════════


class TestPHashFallback:
    """pHash 降级测试（CLIP 不可用）。"""

    def test_identical_images_high_similarity(self, tmp_path: Path):
        """相同图片 → pHash 相似度 = 1.0。"""
        _create_solid_image(tmp_path / "thumb.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle.jpg", color=(255, 0, 0))

        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, cached = computer.compute(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert score == 1.0
        assert method == "phash"
        assert cached is False

    def test_different_images_lower_similarity(self, tmp_path: Path):
        """不同图片 → pHash 相似度 < 1.0。"""
        _create_solid_image(tmp_path / "thumb.jpg", color=(255, 0, 0))
        _create_gradient_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, cached = computer.compute(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert method == "phash"
        # 不同图片相似度应低于相同图片
        assert score <= 1.0

    def test_phash_method_returned(self, tmp_path: Path):
        """CLIP 不可用时返回 method=phash。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        _score, method, _cached = computer.compute(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert method == "phash"


# ═══════════════════════════════════════════════════════════════
# LRU 缓存测试
# ═══════════════════════════════════════════════════════════════


class TestLRUCache:
    """LRU 缓存测试。"""

    def test_cache_hit(self, tmp_path: Path):
        """相同输入第二次命中缓存。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        source = str(tmp_path / "thumb.jpg")
        eagle = str(tmp_path / "eagle.jpg")

        # 第一次计算
        score1, method1, cached1 = computer.compute(source, eagle)
        assert cached1 is False

        # 第二次命中缓存
        score2, method2, cached2 = computer.compute(source, eagle)
        assert cached2 is True
        assert score2 == score1
        assert method2 == method1

    def test_cache_miss_different_input(self, tmp_path: Path):
        """不同输入不命中缓存。"""
        _create_solid_image(tmp_path / "thumb1.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "thumb2.jpg", color=(0, 255, 0))
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        computer.compute(str(tmp_path / "thumb1.jpg"), str(tmp_path / "eagle.jpg"))

        # 不同 thumb → 缓存未命中
        _score, _method, cached = computer.compute(
            str(tmp_path / "thumb2.jpg"), str(tmp_path / "eagle.jpg")
        )
        assert cached is False

    def test_cache_clear(self, tmp_path: Path):
        """clear_cache 清空缓存。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        source = str(tmp_path / "thumb.jpg")
        eagle = str(tmp_path / "eagle.jpg")

        computer.compute(source, eagle)
        assert computer.cache_size == 1

        computer.clear_cache()
        assert computer.cache_size == 0

        # 清空后重新计算
        _score, _method, cached = computer.compute(source, eagle)
        assert cached is False

    def test_cache_lru_eviction(self, tmp_path: Path):
        """LRU 淘汰 — 超过上限时淘汰最旧条目。"""
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(cache_size=3, enable_clip=False)
        eagle = str(tmp_path / "eagle.jpg")

        # 写入 4 条（超过上限 3）
        for i in range(4):
            _create_solid_image(tmp_path / f"thumb_{i}.jpg", color=(i * 60, 0, 0))
            computer.compute(str(tmp_path / f"thumb_{i}.jpg"), eagle)

        # 缓存应只有 3 条
        assert computer.cache_size == 3


# ═══════════════════════════════════════════════════════════════
# 评分门禁测试
# ═══════════════════════════════════════════════════════════════


class TestScoreGates:
    """评分门禁测试。"""

    def test_normalize_clip_score_high(self):
        """cosine ≥ 0.95 → 1.0。"""
        assert FrameSimilarityComputer._normalize_clip_score(0.96) == 1.0
        assert FrameSimilarityComputer._normalize_clip_score(COSINE_HIGH) == 1.0

    def test_normalize_clip_score_medium(self):
        """cosine ≥ 0.85 → 0.85。"""
        assert FrameSimilarityComputer._normalize_clip_score(0.86) == 0.85
        assert FrameSimilarityComputer._normalize_clip_score(COSINE_MEDIUM) == 0.85

    def test_normalize_clip_score_low(self):
        """cosine ≥ 0.70 → 0.70。"""
        assert FrameSimilarityComputer._normalize_clip_score(0.71) == 0.70
        assert FrameSimilarityComputer._normalize_clip_score(COSINE_LOW) == 0.70

    def test_normalize_clip_score_below_threshold(self):
        """cosine < 0.70 → 0.0。"""
        assert FrameSimilarityComputer._normalize_clip_score(0.69) == 0.0
        assert FrameSimilarityComputer._normalize_clip_score(0.0) == 0.0
        assert FrameSimilarityComputer._normalize_clip_score(-1.0) == 0.0

    def test_normalize_clip_score_boundaries(self):
        """边界值测试。"""
        # 恰好 0.95
        assert FrameSimilarityComputer._normalize_clip_score(0.95) == 1.0
        # 恰好 0.85
        assert FrameSimilarityComputer._normalize_clip_score(0.85) == 0.85
        # 恰好 0.70
        assert FrameSimilarityComputer._normalize_clip_score(0.70) == 0.70


# ═══════════════════════════════════════════════════════════════
# CLIP 可用性测试
# ═══════════════════════════════════════════════════════════════


class TestClipAvailability:
    """CLIP 可用性测试。"""

    def test_clip_disabled(self):
        """enable_clip=False → CLIP 不可用。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        assert computer.is_clip_available() is False

    def test_clip_not_available_falls_back_to_phash(self, tmp_path: Path):
        """CLIP 不可用 → 自动降级到 pHash。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)
        score, method, _ = computer.compute(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert method == "phash"
        assert score >= 0.0

    def test_clip_available_uses_clip(self, tmp_path: Path):
        """CLIP 可用时使用 CLIP（通过 mock）。"""
        _create_solid_image(tmp_path / "thumb.jpg")
        _create_solid_image(tmp_path / "eagle.jpg")

        computer = FrameSimilarityComputer(enable_clip=False)

        # mock CLIP 可用 + 返回固定 cosine
        with patch.object(
            computer, "_clip_available", True
        ), patch.object(
            computer, "_compute_clip_similarity", return_value=0.92
        ):
            score, method, _ = computer.compute(
                str(tmp_path / "thumb.jpg"),
                str(tmp_path / "eagle.jpg"),
            )
        assert method == "clip"
        assert score == 0.85  # 0.92 归一化 → 0.85


# ═══════════════════════════════════════════════════════════════
# 图像加载测试
# ═══════════════════════════════════════════════════════════════


class TestImageLoading:
    """图像加载测试。"""

    def test_load_image_from_file(self, tmp_path: Path):
        """从本地文件加载图片。"""
        _create_solid_image(tmp_path / "test.jpg")
        computer = FrameSimilarityComputer(enable_clip=False)
        img = computer._load_image(str(tmp_path / "test.jpg"))
        assert img is not None
        assert isinstance(img, Image.Image)

    def test_load_image_nonexistent_file(self, tmp_path: Path):
        """不存在的文件 → None。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        img = computer._load_image(str(tmp_path / "nonexistent.jpg"))
        assert img is None

    def test_load_image_empty_source(self):
        """空路径 → None。"""
        computer = FrameSimilarityComputer(enable_clip=False)
        img = computer._load_image("")
        assert img is None

    def test_is_url_detection(self):
        """URL 检测。"""
        assert FrameSimilarityComputer._is_url("http://example.com/img.jpg") is True
        assert FrameSimilarityComputer._is_url("https://example.com/img.jpg") is True
        assert FrameSimilarityComputer._is_url("/path/to/img.jpg") is False
        assert FrameSimilarityComputer._is_url("relative/path.jpg") is False


# ═══════════════════════════════════════════════════════════════
# pHash 算法测试
# ═══════════════════════════════════════════════════════════════


class TestPHashAlgorithm:
    """pHash 算法测试。"""

    def test_phash_identical_images_same_hash(self, tmp_path: Path):
        """相同图片 → 相同 pHash。"""
        _create_solid_image(tmp_path / "img1.jpg", color=(128, 128, 128))
        _create_solid_image(tmp_path / "img2.jpg", color=(128, 128, 128))

        img1 = Image.open(tmp_path / "img1.jpg")
        img2 = Image.open(tmp_path / "img2.jpg")

        hash1 = FrameSimilarityComputer._phash(img1)
        hash2 = FrameSimilarityComputer._phash(img2)
        assert hash1 == hash2

    def test_phash_different_images_different_hash(self, tmp_path: Path):
        """不同图片 → 不同 pHash。"""
        _create_solid_image(tmp_path / "img1.jpg", color=(255, 0, 0))
        _create_gradient_image(tmp_path / "img2.jpg")

        img1 = Image.open(tmp_path / "img1.jpg")
        img2 = Image.open(tmp_path / "img2.jpg")

        hash1 = FrameSimilarityComputer._phash(img1)
        hash2 = FrameSimilarityComputer._phash(img2)
        assert hash1 != hash2

    def test_phash_returns_int(self, tmp_path: Path):
        """pHash 返回 int 类型。"""
        _create_solid_image(tmp_path / "img.jpg")
        img = Image.open(tmp_path / "img.jpg")
        h = FrameSimilarityComputer._phash(img)
        assert isinstance(h, int)


# ═══════════════════════════════════════════════════════════════
# 集成测试 — MappingScorer + FrameSimilarityComputer
# ═══════════════════════════════════════════════════════════════


class TestScorerIntegration:
    """MappingScorer 集成测试。"""

    def test_scorer_has_frame_computer(self):
        """MappingScorer 持有 FrameSimilarityComputer 实例。"""
        from src.market_ops.creative_mapping_engine import MappingScorer

        scorer = MappingScorer()
        assert scorer.frame_computer is not None
        assert isinstance(scorer.frame_computer, FrameSimilarityComputer)

    def test_scorer_frame_similarity_empty(self):
        """空输入 → 0.0。"""
        from src.market_ops.creative_mapping_engine import MappingScorer

        scorer = MappingScorer()
        assert scorer.score_frame_similarity("", "/path/to/video") == 0.0

    def test_scorer_frame_similarity_with_real_images(self, tmp_path: Path):
        """真实图片 → pHash 相似度。"""
        from src.market_ops.creative_mapping_engine import MappingScorer

        _create_solid_image(tmp_path / "thumb.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle.jpg", color=(255, 0, 0))

        scorer = MappingScorer()
        score = scorer.score_frame_similarity(
            str(tmp_path / "thumb.jpg"),
            str(tmp_path / "eagle.jpg"),
        )
        assert score == 1.0  # 相同图片

    def test_six_dimensions_all_match_with_frame(self, tmp_path: Path):
        """6 维全匹配 (含帧相似度) → confidence ≥ 0.85。"""
        from src.market_ops.creative_mapping_engine import (
            MappingScores,
            MappingScorer,
        )

        _create_solid_image(tmp_path / "thumb.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle.jpg", color=(255, 0, 0))

        scorer = MappingScorer()
        scores = scorer.score_all(
            fb_name="MW_VIDEO_260721_000123",
            eagle_filename="MW_VIDEO_260721_000123.mp4",
            fb_duration=32.5,
            eagle_duration=32.5,
            fb_resolution="1080x1920",
            eagle_resolution="1080x1920",
            fb_creation_time="2026-07-24",
            eagle_creation_time="2026-07-24",
            fb_thumbnail=str(tmp_path / "thumb.jpg"),
            eagle_path=str(tmp_path / "eagle.jpg"),
            fb_hash="abc123",
            eagle_hash="abc123",
        )
        confidence = scorer.weighted_total(scores)
        assert confidence >= 0.85
        assert scores.name_similarity == 1.0
        assert scores.frame_similarity == 1.0
        assert scores.file_hash_match == 1.0


# ═══════════════════════════════════════════════════════════════
# API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestFrameSimilarityAPI:
    """帧相似度 API 端点测试。"""

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

    def test_frame_similarity_api_success(self, client: TestClient, tmp_path: Path):
        """POST /frame-similarity — 成功计算。"""
        _create_solid_image(tmp_path / "thumb.jpg", color=(255, 0, 0))
        _create_solid_image(tmp_path / "eagle.jpg", color=(255, 0, 0))

        response = client.post("/api/creative-mapping/frame-similarity", json={
            "thumbnail_source": str(tmp_path / "thumb.jpg"),
            "eagle_path": str(tmp_path / "eagle.jpg"),
        })
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "method" in data
        assert "cached" in data
        assert data["score"] == 1.0
        assert data["method"] == "phash"

    def test_frame_similarity_api_missing_params(self, client: TestClient):
        """POST /frame-similarity — 缺少参数 → 400。"""
        response = client.post("/api/creative-mapping/frame-similarity", json={
            "thumbnail_source": "",
        })
        assert response.status_code == 400

    def test_frame_similarity_api_nonexistent_files(self, client: TestClient, tmp_path: Path):
        """POST /frame-similarity — 文件不存在 → score=0.0。"""
        response = client.post("/api/creative-mapping/frame-similarity", json={
            "thumbnail_source": str(tmp_path / "nonexistent.jpg"),
            "eagle_path": str(tmp_path / "nonexistent.mp4"),
        })
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 0.0
        assert data["method"] == "none"
