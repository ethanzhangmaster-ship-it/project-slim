"""FrameSimilarityComputer — CLIP embedding 帧相似度计算。

支持三级降级策略：
  1. CLIP embedding (cosine similarity) — 需 torch + clip/transformers
  2. pHash 感知哈希 (hamming distance) — 内置实现，仅需 PIL + numpy
  3. 返回 0.0 — 图像加载失败时

v1.3 性能优化：
  - 预加载模型 (preload=True)
  - 批量计算 (compute_batch)
  - GPU 加速 (自动检测 CUDA)
  - Embedding 缓存 (基于图片内容)

视频首帧提取使用 ffmpeg (subprocess)，不可用时回退到 0.0。

Usage::

    # 预加载模式 (生产环境)
    computer = FrameSimilarityComputer(preload=True)
    score, method, cached = computer.compute(
        thumbnail_source="http://example.com/thumb.jpg",
        eagle_path="/path/to/video.mp4",
    )

    # 批量计算
    results = computer.compute_batch([
        ("http://thumb1.jpg", "/path/to/video1.mp4"),
        ("http://thumb2.jpg", "/path/to/video2.mp4"),
    ])
"""

from __future__ import annotations

import hashlib
import io
import logging
import subprocess
from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# 评分门禁阈值
COSINE_HIGH = 0.95      # cosine ≥ 0.95 → 1.0
COSINE_MEDIUM = 0.85    # cosine ≥ 0.85 → 0.85
COSINE_LOW = 0.70       # cosine ≥ 0.70 → 0.70
# cosine < 0.70 → 0.0

# LRU 缓存上限
DEFAULT_CACHE_SIZE = 1000
DEFAULT_EMBEDDING_CACHE_SIZE = 500

# pHash 图像尺寸 (8x8 DCT → 64 bit hash)
PHASH_SIZE = 8


class FrameSimilarityComputer:
    """帧相似度计算器 — CLIP 优先，pHash 降级。

    三级降级策略：
      1. CLIP: cosine similarity（需 torch + clip/transformers）
      2. pHash: 1 - hamming_distance / 64（内置实现）
      3. 0.0: 图像加载失败

    v1.3 性能优化：
      - preload=True 时 __init__ 立即加载 CLIP 模型
      - compute_batch() 批量计算多对图片
      - 自动检测 CUDA，模型 .to(device) + .eval()
      - embedding 缓存基于图片内容 (MD5)

    Args:
        cache_size: 结果 LRU 缓存上限 (默认 1000)
        embedding_cache_size: embedding LRU 缓存上限 (默认 500)
        enable_clip: 是否尝试使用 CLIP (默认 True，不可用时自动降级)
        preload: 是否在 __init__ 时预加载 CLIP 模型 (默认 False)
        ffmpeg_path: ffmpeg 可执行文件路径 (默认从 PATH 查找)
    """

    def __init__(
        self,
        cache_size: int = DEFAULT_CACHE_SIZE,
        embedding_cache_size: int = DEFAULT_EMBEDDING_CACHE_SIZE,
        enable_clip: bool = True,
        preload: bool = False,
        ffmpeg_path: str = "",
    ) -> None:
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._cache_size = cache_size
        self._embedding_cache: OrderedDict[str, Any] = OrderedDict()
        self._embedding_cache_size = embedding_cache_size
        self._ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self._clip_available: bool | None = None if enable_clip else False
        self._clip_model: Any = None
        self._clip_preprocess: Any = None
        self._clip_device: str = "cpu"
        self._clip_backend: str = ""

        # 预加载模型
        if preload and enable_clip:
            self._is_clip_available()

    # ── Public API ───────────────────────────────────────

    def compute(
        self,
        thumbnail_source: str,
        eagle_path: str,
    ) -> tuple[float, str, bool]:
        """计算帧相似度。

        Args:
            thumbnail_source: Facebook 缩略图 URL 或本地路径
            eagle_path: Eagle 视频文件路径

        Returns:
            (score, method, cached)
            - score: 0.0-1.0 归一化评分
            - method: "clip" | "phash" | "none"
            - cached: 是否命中缓存
        """
        if not thumbnail_source or not eagle_path:
            return 0.0, "none", False

        cache_key = self._cache_key(thumbnail_source, eagle_path)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached["score"], cached["method"], True

        # 加载图像
        thumb_img = self._load_image(thumbnail_source)
        if thumb_img is None:
            self._set_cached(cache_key, 0.0, "none")
            return 0.0, "none", False

        eagle_img = self._load_video_frame(eagle_path)
        if eagle_img is None:
            eagle_img = self._load_image(eagle_path)
        if eagle_img is None:
            self._set_cached(cache_key, 0.0, "none")
            return 0.0, "none", False

        # 尝试 CLIP
        if self._is_clip_available():
            score = self._compute_clip_similarity(thumb_img, eagle_img)
            if score is not None:
                normalized = self._normalize_clip_score(score)
                self._set_cached(cache_key, normalized, "clip")
                return normalized, "clip", False

        # 降级到 pHash
        score = self._compute_phash_similarity(thumb_img, eagle_img)
        self._set_cached(cache_key, score, "phash")
        return score, "phash", False

    def compute_batch(
        self,
        pairs: list[tuple[str, str]],
    ) -> list[tuple[float, str, bool]]:
        """批量计算帧相似度。

        v1.3 新增：批量加载图片，统一编码，提升吞吐量。

        Args:
            pairs: [(thumbnail_source, eagle_path), ...]

        Returns:
            [(score, method, cached), ...] 与输入顺序一致
        """
        if not pairs:
            return []

        results: list[tuple[float, str, bool]] = []
        pending: list[tuple[int, Image.Image, Image.Image]] = []

        # 第一轮：检查缓存 + 加载图片
        for idx, (thumb_src, eagle_path) in enumerate(pairs):
            if not thumb_src or not eagle_path:
                results.append((0.0, "none", False))
                continue

            cache_key = self._cache_key(thumb_src, eagle_path)
            cached = self._get_cached(cache_key)
            if cached is not None:
                results.append((cached["score"], cached["method"], True))
                continue

            thumb_img = self._load_image(thumb_src)
            if thumb_img is None:
                self._set_cached(cache_key, 0.0, "none")
                results.append((0.0, "none", False))
                continue

            eagle_img = self._load_video_frame(eagle_path)
            if eagle_img is None:
                eagle_img = self._load_image(eagle_path)
            if eagle_img is None:
                self._set_cached(cache_key, 0.0, "none")
                results.append((0.0, "none", False))
                continue

            # 占位，待批量计算
            results.append((0.0, "pending", False))
            pending.append((idx, thumb_img, eagle_img))

        # 第二轮：批量 CLIP 编码
        if pending and self._is_clip_available():
            clip_scores = self._compute_clip_batch(pending)
            for (idx, _thumb, _eagle), (score, method) in zip(pending, clip_scores):
                thumb_src, eagle_path = pairs[idx]
                cache_key = self._cache_key(thumb_src, eagle_path)
                if score is not None:
                    normalized = self._normalize_clip_score(score)
                    self._set_cached(cache_key, normalized, "clip")
                    results[idx] = (normalized, "clip", False)
                else:
                    # CLIP 失败，标记为待 pHash 计算
                    results[idx] = (0.0, "phash_pending", False)

        # 第三轮：pHash 降级处理（CLIP 失败或不可用的项）
        phash_items: list[tuple[int, Image.Image, Image.Image]] = []
        for idx, thumb, eagle in pending:
            if results[idx][1] in ("phash_pending", "pending"):
                phash_items.append((idx, thumb, eagle))

        for idx, thumb_img, eagle_img in phash_items:
            thumb_src, eagle_path = pairs[idx]
            cache_key = self._cache_key(thumb_src, eagle_path)
            score = self._compute_phash_similarity(thumb_img, eagle_img)
            self._set_cached(cache_key, score, "phash")
            results[idx] = (score, "phash", False)

        return results

    def warmup(self) -> bool:
        """预热模型 — 用 dummy 输入执行一次推理。

        Returns:
            True 如果预热成功，False 如果 CLIP 不可用
        """
        if not self._is_clip_available():
            return False

        try:
            # 创建 dummy 图片
            dummy = Image.new("RGB", (224, 224), color=(128, 128, 128))
            _ = self._compute_clip_similarity(dummy, dummy)
            logger.info("CLIP warmup completed")
            return True
        except Exception as exc:
            logger.warning("CLIP warmup failed: %s", exc)
            return False

    def is_clip_available(self) -> bool:
        """检查 CLIP 是否可用。"""
        return self._is_clip_available()

    @property
    def device(self) -> str:
        """当前推理设备 (cpu/cuda)。"""
        return self._clip_device

    @property
    def backend(self) -> str:
        """CLIP 后端名称 (openai/transformers/空)。"""
        return self._clip_backend

    def clear_cache(self) -> None:
        """清空结果缓存。"""
        self._cache.clear()

    def clear_embedding_cache(self) -> None:
        """清空 embedding 缓存。"""
        self._embedding_cache.clear()

    @property
    def cache_size(self) -> int:
        """当前结果缓存条目数。"""
        return len(self._cache)

    @property
    def embedding_cache_size(self) -> int:
        """当前 embedding 缓存条目数。"""
        return len(self._embedding_cache)

    # ── CLIP 相关 ──────────────────────────────────────────

    def _is_clip_available(self) -> bool:
        """检查 CLIP 库是否可用（结果缓存）。"""
        if self._clip_available is None:
            self._clip_available = self._try_init_clip()
            if self._clip_available:
                logger.info(
                    "CLIP model loaded (backend=%s, device=%s)",
                    self._clip_backend, self._clip_device,
                )
            else:
                logger.info("CLIP not available, will use pHash fallback")
        return self._clip_available

    def _try_init_clip(self) -> bool:
        """尝试加载 CLIP 模型。"""
        try:
            import torch  # type: ignore[import]

            self._clip_device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            self._clip_device = "cpu"

        try:
            # 尝试 openai-clip
            import clip  # type: ignore[import]

            self._clip_model, self._clip_preprocess = clip.load(
                "ViT-B/32", device=self._clip_device
            )
            self._clip_backend = "openai"
            return True
        except ImportError:
            pass

        try:
            # 尝试 transformers
            from transformers import (  # type: ignore[import]
                CLIPModel,
                CLIPProcessor,
            )

            self._clip_model = CLIPModel.from_pretrained(
                "openai/clip-vit-base-patch32"
            ).to(self._clip_device)
            self._clip_model.eval()
            self._clip_preprocess = CLIPProcessor.from_pretrained(
                "openai/clip-vit-base-patch32"
            )
            self._clip_backend = "transformers"
            return True
        except ImportError:
            pass

        return False

    def _compute_clip_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image,
    ) -> float | None:
        """使用 CLIP 计算 cosine similarity（带 embedding 缓存）。"""
        try:
            if self._clip_backend == "openai":
                return self._compute_clip_openai(img1, img2)
            elif self._clip_backend == "transformers":
                return self._compute_clip_transformers(img1, img2)
        except Exception as exc:
            logger.warning("CLIP computation failed: %s", exc)
        return None

    def _compute_clip_openai(self, img1: Image.Image, img2: Image.Image) -> float | None:
        """openai-clip 计算 cosine similarity。"""
        import torch  # type: ignore[import]

        device = self._clip_device
        feat1 = self._get_or_compute_embedding_openai(img1)
        feat2 = self._get_or_compute_embedding_openai(img2)

        if feat1 is None or feat2 is None:
            return None

        cos = torch.nn.functional.cosine_similarity(feat1, feat2).item()
        return cos

    def _compute_clip_transformers(
        self,
        img1: Image.Image,
        img2: Image.Image,
    ) -> float | None:
        """transformers CLIP 计算 cosine similarity（带 embedding 缓存）。"""
        import torch  # type: ignore[import]

        feat1 = self._get_or_compute_embedding_transformers(img1)
        feat2 = self._get_or_compute_embedding_transformers(img2)

        if feat1 is None or feat2 is None:
            return None

        cos = torch.nn.functional.cosine_similarity(feat1, feat2).item()
        return cos

    def _compute_clip_batch(
        self,
        items: list[tuple[int, Image.Image, Image.Image]],
    ) -> list[tuple[float | None, str]]:
        """批量 CLIP 计算。

        Returns:
            [(cosine_score, method), ...] method="clip" 或 None 表示失败
        """
        if not items:
            return []

        if self._clip_backend == "transformers":
            return self._compute_clip_batch_transformers(items)
        elif self._clip_backend == "openai":
            return self._compute_clip_batch_openai(items)
        else:
            return [(None, "none") for _ in items]

    def _compute_clip_batch_transformers(
        self,
        items: list[tuple[int, Image.Image, Image.Image]],
    ) -> list[tuple[float | None, str]]:
        """transformers 后端批量计算。"""
        import torch  # type: ignore[import]

        # 收集所有需要编码的图片（去重）
        all_images: list[Image.Image] = []
        image_keys: list[str] = []
        pair_indices: list[tuple[int, int, int]] = []  # (item_idx, feat1_pos, feat2_pos)

        img_pos_map: dict[str, int] = {}

        for item_idx, (_idx, img1, img2) in enumerate(items):
            key1 = self._image_content_key(img1)
            key2 = self._image_content_key(img2)

            if key1 not in img_pos_map:
                img_pos_map[key1] = len(all_images)
                all_images.append(img1)
                image_keys.append(key1)

            if key2 not in img_pos_map:
                img_pos_map[key2] = len(all_images)
                all_images.append(img2)
                image_keys.append(key2)

            pair_indices.append((item_idx, img_pos_map[key1], img_pos_map[key2]))

        # 批量编码（仅编码未缓存的）
        features: list[Any] = [None] * len(all_images)
        to_encode: list[tuple[int, Image.Image]] = []

        for pos, (key, img) in enumerate(zip(image_keys, all_images)):
            cached_feat = self._get_embedding_cached(key)
            if cached_feat is not None:
                features[pos] = cached_feat
            else:
                to_encode.append((pos, img))

        # 批量 forward
        if to_encode:
            try:
                images = [img for _, img in to_encode]
                inputs = self._clip_preprocess(images=images, return_tensors="pt")
                pixel_values = inputs["pixel_values"].to(self._clip_device)

                with torch.no_grad():
                    batch_features = self._clip_model.get_image_features(
                        pixel_values=pixel_values
                    )

                for (pos, _img), feat in zip(to_encode, batch_features):
                    feat_cpu = feat.unsqueeze(0).cpu()
                    features[pos] = feat_cpu
                    key = image_keys[pos]
                    self._set_embedding_cached(key, feat_cpu)
            except Exception as exc:
                logger.warning("Batch CLIP encoding failed: %s", exc)
                return [(None, "none") for _ in items]

        # 计算 cosine similarity
        results: list[tuple[float | None, str]] = []
        for _item_idx, pos1, pos2 in pair_indices:
            feat1 = features[pos1]
            feat2 = features[pos2]
            if feat1 is None or feat2 is None:
                results.append((None, "none"))
            else:
                try:
                    cos = torch.nn.functional.cosine_similarity(feat1, feat2).item()
                    results.append((cos, "clip"))
                except Exception as exc:
                    logger.warning("Cosine similarity failed: %s", exc)
                    results.append((None, "none"))

        return results

    def _compute_clip_batch_openai(
        self,
        items: list[tuple[int, Image.Image, Image.Image]],
    ) -> list[tuple[float | None, str]]:
        """openai-clip 后端批量计算。"""
        import torch  # type: ignore[import]

        # 收集去重图片
        all_images: list[Image.Image] = []
        image_keys: list[str] = []
        pair_indices: list[tuple[int, int, int]] = []
        img_pos_map: dict[str, int] = {}

        for item_idx, (_idx, img1, img2) in enumerate(items):
            key1 = self._image_content_key(img1)
            key2 = self._image_content_key(img2)

            if key1 not in img_pos_map:
                img_pos_map[key1] = len(all_images)
                all_images.append(img1)
                image_keys.append(key1)
            if key2 not in img_pos_map:
                img_pos_map[key2] = len(all_images)
                all_images.append(img2)
                image_keys.append(key2)

            pair_indices.append((item_idx, img_pos_map[key1], img_pos_map[key2]))

        # 批量编码
        features: list[Any] = [None] * len(all_images)
        to_encode: list[tuple[int, Image.Image]] = []

        for pos, (key, img) in enumerate(zip(image_keys, all_images)):
            cached_feat = self._get_embedding_cached(key)
            if cached_feat is not None:
                features[pos] = cached_feat
            else:
                to_encode.append((pos, img))

        if to_encode:
            try:
                tensors = [self._clip_preprocess(img) for _, img in to_encode]
                batch = torch.stack(tensors).to(self._clip_device)

                with torch.no_grad():
                    batch_features = self._clip_model.encode_image(batch)

                for (pos, _img), feat in zip(to_encode, batch_features):
                    feat_cpu = feat.unsqueeze(0).cpu()
                    features[pos] = feat_cpu
                    key = image_keys[pos]
                    self._set_embedding_cached(key, feat_cpu)
            except Exception as exc:
                logger.warning("Batch CLIP encoding failed: %s", exc)
                return [(None, "none") for _ in items]

        results: list[tuple[float | None, str]] = []
        for _item_idx, pos1, pos2 in pair_indices:
            feat1 = features[pos1]
            feat2 = features[pos2]
            if feat1 is None or feat2 is None:
                results.append((None, "none"))
            else:
                try:
                    cos = torch.nn.functional.cosine_similarity(feat1, feat2).item()
                    results.append((cos, "clip"))
                except Exception:
                    results.append((None, "none"))

        return results

    def _get_or_compute_embedding_transformers(
        self, img: Image.Image
    ) -> Any | None:
        """获取或计算 embedding (transformers 后端，带缓存)。"""
        import torch  # type: ignore[import]

        key = self._image_content_key(img)
        cached = self._get_embedding_cached(key)
        if cached is not None:
            return cached

        try:
            inputs = self._clip_preprocess(images=img, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(self._clip_device)

            with torch.no_grad():
                feat = self._clip_model.get_image_features(pixel_values=pixel_values)

            feat_cpu = feat.cpu()
            self._set_embedding_cached(key, feat_cpu)
            return feat_cpu
        except Exception as exc:
            logger.warning("CLIP embedding failed: %s", exc)
            return None

    def _get_or_compute_embedding_openai(
        self, img: Image.Image
    ) -> Any | None:
        """获取或计算 embedding (openai-clip 后端，带缓存)。"""
        import torch  # type: ignore[import]

        key = self._image_content_key(img)
        cached = self._get_embedding_cached(key)
        if cached is not None:
            return cached

        try:
            img_t = self._clip_preprocess(img).unsqueeze(0).to(self._clip_device)

            with torch.no_grad():
                feat = self._clip_model.encode_image(img_t)

            feat_cpu = feat.cpu()
            self._set_embedding_cached(key, feat_cpu)
            return feat_cpu
        except Exception as exc:
            logger.warning("CLIP embedding failed: %s", exc)
            return None

    @staticmethod
    def _normalize_clip_score(cosine: float) -> float:
        """归一化 CLIP cosine similarity 为 0.0-1.0 评分。"""
        if cosine >= COSINE_HIGH:
            return 1.0
        elif cosine >= COSINE_MEDIUM:
            return 0.85
        elif cosine >= COSINE_LOW:
            return 0.70
        else:
            return 0.0

    # ── pHash 相关 ─────────────────────────────────────────

    def _compute_phash_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image,
    ) -> float:
        """使用 pHash 计算相似度 (1 - hamming/64)。"""
        hash1 = self._phash(img1)
        hash2 = self._phash(img2)
        hamming = bin(hash1 ^ hash2).count("1")
        similarity = 1.0 - hamming / (PHASH_SIZE * PHASH_SIZE)

        if similarity >= 0.95:
            return 1.0
        elif similarity >= 0.85:
            return 0.85
        elif similarity >= 0.70:
            return 0.70
        else:
            return 0.0

    @staticmethod
    def _phash(img: Image.Image) -> int:
        """计算 pHash 感知哈希 (内置实现，不依赖 imagehash 库)。"""
        gray = img.convert("L").resize(
            (32, 32), Image.Resampling.LANCZOS
        )
        pixels = np.array(gray, dtype=np.float64)
        dct = _dct2(pixels)
        dct_low = dct[:PHASH_SIZE, :PHASH_SIZE]
        dct_flat = dct_low.flatten()
        mean = np.mean(dct_flat[1:])

        bits = 0
        for i, val in enumerate(dct_flat):
            if i == 0:
                continue
            bits = (bits << 1) | (1 if val > mean else 0)

        return bits

    # ── 图像加载 ───────────────────────────────────────────

    def _load_image(self, source: str) -> Image.Image | None:
        """加载图像 — 支持 URL 和本地路径。"""
        if not source:
            return None
        try:
            if self._is_url(source):
                return self._load_from_url(source)
            else:
                return self._load_from_file(source)
        except Exception as exc:
            logger.warning("Failed to load image from %s: %s", source, exc)
            return None

    @staticmethod
    def _is_url(s: str) -> bool:
        """判断字符串是否为 URL。"""
        try:
            result = urlparse(s)
            return result.scheme in ("http", "https")
        except Exception:
            return False

    @staticmethod
    def _load_from_file(path: str) -> Image.Image | None:
        """从本地文件加载图像。"""
        if not Path(path).exists():
            logger.warning("Image file not found: %s", path)
            return None
        try:
            return Image.open(path)
        except Exception as exc:
            logger.warning("Failed to open image %s: %s", path, exc)
            return None

    @staticmethod
    def _load_from_url(url: str) -> Image.Image | None:
        """从 URL 下载图像。"""
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read()
            return Image.open(io.BytesIO(data))
        except Exception as exc:
            logger.warning("Failed to download image from %s: %s", url, exc)
            return None

    def _load_video_frame(self, video_path: str) -> Image.Image | None:
        """使用 ffmpeg 提取视频首帧。"""
        if not Path(video_path).exists():
            logger.warning("Video file not found: %s", video_path)
            return None

        if not self._ffmpeg_path:
            logger.warning("ffmpeg not available, cannot extract video frame")
            return None

        try:
            cmd = [
                self._ffmpeg_path,
                "-i", video_path,
                "-vframes", "1",
                "-f", "image2pipe",
                "-vcodec", "png",
                "-",
            ]
            result = subprocess.run(
                cmd, capture_output=True, timeout=15,
            )
            if result.returncode != 0 or not result.stdout:
                return None
            return Image.open(io.BytesIO(result.stdout))
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timeout for %s", video_path)
        except subprocess.SubprocessError as exc:
            logger.warning("ffmpeg failed for %s: %s", video_path, exc)
        except Exception as exc:
            logger.warning("Unexpected error extracting frame from %s: %s", video_path, exc)
        return None

    # ── 缓存管理 ───────────────────────────────────────────

    def _cache_key(self, thumbnail_source: str, eagle_path: str) -> str:
        """生成结果缓存键。"""
        return hashlib.md5(
            f"{thumbnail_source}|{eagle_path}".encode("utf-8")
        ).hexdigest()

    def _get_cached(self, key: str) -> dict[str, Any] | None:
        """从结果缓存获取。"""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _set_cached(self, key: str, score: float, method: str) -> None:
        """写入结果缓存。"""
        self._cache[key] = {"score": score, "method": method}
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    # ── Embedding 缓存 ────────────────────────────────────

    @staticmethod
    def _image_content_key(img: Image.Image) -> str:
        """基于图片内容生成缓存键 (MD5 of raw bytes)。"""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return hashlib.md5(buf.getvalue()).hexdigest()

    def _get_embedding_cached(self, key: str) -> Any | None:
        """从 embedding 缓存获取。"""
        if key in self._embedding_cache:
            self._embedding_cache.move_to_end(key)
            return self._embedding_cache[key]
        return None

    def _set_embedding_cached(self, key: str, embedding: Any) -> None:
        """写入 embedding 缓存。"""
        self._embedding_cache[key] = embedding
        self._embedding_cache.move_to_end(key)
        while len(self._embedding_cache) > self._embedding_cache_size:
            self._embedding_cache.popitem(last=False)

    # ── 工具方法 ───────────────────────────────────────────

    @staticmethod
    def _find_ffmpeg() -> str:
        """从 PATH 查找 ffmpeg。"""
        import shutil
        return shutil.which("ffmpeg") or ""

    def __repr__(self) -> str:
        clip_status = "clip" if self._is_clip_available() else "phash"
        return (
            f"FrameSimilarityComputer(method={clip_status}, "
            f"device={self._clip_device}, cache={len(self._cache)}, "
            f"emb_cache={len(self._embedding_cache)})"
        )


# ── DCT 辅助函数 (内置实现，不依赖 scipy) ──────────────────


def _dct1d(x: np.ndarray) -> np.ndarray:
    """1D DCT-II 变换。"""
    N = len(x)
    n = np.arange(N)
    k = np.arange(N).reshape(-1, 1)
    M = np.cos(np.pi * (2 * n + 1) * k / (2 * N))
    return M @ x


def _dct2(matrix: np.ndarray) -> np.ndarray:
    """2D DCT-II 变换 (先对行，再对列)。"""
    rows_dct = np.apply_along_axis(_dct1d, 1, matrix)
    cols_dct = np.apply_along_axis(_dct1d, 0, rows_dct)
    return cols_dct


__all__ = ["FrameSimilarityComputer"]
