"""EagleAssetTagger — 基于 CLIP 零样本分类的 Eagle 素材自动打标签器。

CME v1.9 扩展能力。复用 FrameSimilarityComputer 的 CLIP 加载策略
(openai-clip 优先, transformers 降级), 增加 image-text similarity 用于
零样本分类。

设计原则:
  - 复用已有 CLIP 模型加载逻辑 (与 FrameSimilarityComputer 一致)
  - 预定义标签集面向游戏广告素材 (玩法/场景/视觉风格/画面元素)
  - 纯本地推理, 无需任何外部凭证
  - 降级策略: CLIP 不可用时返回空标签列表 (不抛异常)
  - 持久化到 data/eagle_tags/{asset_id}.json

Usage::

    tagger = EagleAssetTagger(preload=True)
    tags = tagger.tag_asset("/path/to/MW_VIDEO_260721_000123.mp4")
    # tags: [AssetTag(tag="merge", category="gameplay_type", confidence=0.92), ...]

    # 批量打标签
    results = tagger.tag_batch(["/path/a.mp4", "/path/b.png"])
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import subprocess
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

# ── 常量 ───────────────────────────────────────────────────────────

# 标签置信度阈值: 低于此值的标签不返回
DEFAULT_MIN_CONFIDENCE = 0.15

# 默认返回 top-K 标签
DEFAULT_TOP_K = 5

# embedding 缓存上限
DEFAULT_EMBEDDING_CACHE_SIZE = 500

# ── 预定义标签集 (面向游戏广告素材) ──────────────────────────────

DEFAULT_TAG_VOCABULARY: dict[str, list[str]] = {
    "gameplay_type": [
        "merge game", "match-3 puzzle", "idle game", "role-playing game",
        "strategy game", "simulation game", "runner game", "card game",
    ],
    "scene": [
        "reward unlock screen", "gameplay footage", "character close-up",
        "in-app store", "loading screen", "battle scene", "tutorial screen",
        "level complete screen",
    ],
    "visual_style": [
        "cartoon style", "realistic 3d render", "anime style", "pixel art",
        "flat design", "dark fantasy", "cute kawaii style",
    ],
    "element": [
        "dragon", "hero character", "gold coins", "gems", "treasure chest",
        "sword and shield", "magic spell effect", "monster enemy",
        "castle building", "puzzle grid",
    ],
}

# ── 数据模型 ───────────────────────────────────────────────────────


@dataclass
class AssetTag:
    """单个素材标签。

    Attributes:
        tag: 标签文本
        category: 标签类别 (gameplay_type/scene/visual_style/element)
        confidence: 置信度 0.0-1.0
    """

    tag: str
    category: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "category": self.category,
            "confidence": round(self.confidence, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetTag:
        return cls(
            tag=data.get("tag", ""),
            category=data.get("category", ""),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class AssetTagResult:
    """素材打标签完整结果。

    Attributes:
        asset_path: 素材文件路径
        asset_id: 素材 ID (creative_asset_id 或文件名)
        tags: 标签列表 (按 confidence 降序)
        method: 使用的标签方法 ("clip" | "none")
        error: 错误信息 (成功时为空)
    """

    asset_path: str = ""
    asset_id: str = ""
    tags: list[AssetTag] = field(default_factory=list)
    method: str = "none"
    error: str = ""

    @property
    def is_success(self) -> bool:
        return not self.error and bool(self.tags)

    @property
    def top_tag(self) -> AssetTag | None:
        return self.tags[0] if self.tags else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_path": self.asset_path,
            "asset_id": self.asset_id,
            "tags": [t.to_dict() for t in self.tags],
            "method": self.method,
            "error": self.error,
            "tag_count": len(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetTagResult:
        return cls(
            asset_path=data.get("asset_path", ""),
            asset_id=data.get("asset_id", ""),
            tags=[AssetTag.from_dict(t) for t in data.get("tags", [])],
            method=data.get("method", "none"),
            error=data.get("error", ""),
        )


# ── EagleAssetTagger ──────────────────────────────────────────────


class EagleAssetTagger:
    """Eagle 素材自动打标签器 — 基于 CLIP 零样本分类。

    复用 FrameSimilarityComputer 的 CLIP 加载策略:
      1. 优先 openai-clip (ViT-B/32)
      2. 降级 transformers (openai/clip-vit-base-patch32)
      3. 不可用时返回空标签列表

    Args:
        preload: 是否在 __init__ 时预加载 CLIP 模型
        min_confidence: 标签置信度阈值 (低于此值不返回)
        top_k: 默认返回 top-K 标签
        tag_vocabulary: 自定义标签词表 (None 则用默认)
        ffmpeg_path: ffmpeg 可执行文件路径 (默认从 PATH 查找)
        embedding_cache_size: embedding LRU 缓存上限
    """

    def __init__(
        self,
        preload: bool = False,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        top_k: int = DEFAULT_TOP_K,
        tag_vocabulary: dict[str, list[str]] | None = None,
        ffmpeg_path: str = "",
        embedding_cache_size: int = DEFAULT_EMBEDDING_CACHE_SIZE,
    ) -> None:
        self.min_confidence = min_confidence
        self.top_k = top_k
        self.tag_vocabulary = tag_vocabulary or DEFAULT_TAG_VOCABULARY
        self._ffmpeg_path = ffmpeg_path or self._find_ffmpeg()

        # CLIP 状态
        self._clip_available: bool | None = None
        self._clip_model: Any = None
        self._clip_preprocess: Any = None
        self._clip_device: str = "cpu"
        self._clip_backend: str = ""

        # embedding 缓存 (图片内容 MD5 → embedding)
        self._embedding_cache: OrderedDict[str, Any] = OrderedDict()
        self._embedding_cache_size = embedding_cache_size

        # 文本标签 embedding 缓存 (词表 MD5 → {tag_text: embedding})
        self._text_embedding_cache: dict[str, Any] = {}

        # 线程安全 (CLIP 模型推理非线程安全)
        self._lock = threading.Lock()

        if preload:
            self._is_clip_available()

    # ── Public API ──────────────────────────────────────────

    def tag_asset(
        self,
        asset_path: str,
        top_k: int | None = None,
        min_confidence: float | None = None,
    ) -> AssetTagResult:
        """对单个素材打标签 (自动识别图片/视频)。

        Args:
            asset_path: 素材文件路径 (图片或视频)
            top_k: 返回 top-K 标签 (None 则用默认)
            min_confidence: 置信度阈值 (None 则用默认)

        Returns:
            AssetTagResult
        """
        if not asset_path:
            return AssetTagResult(error="asset_path is empty")

        path = Path(asset_path)
        if not path.exists():
            return AssetTagResult(
                asset_path=asset_path,
                asset_id=path.stem,
                error=f"file not found: {asset_path}",
            )

        asset_id = path.stem
        top_k = top_k or self.top_k
        min_confidence = min_confidence if min_confidence is not None else self.min_confidence

        # 加载图像 (视频提取首帧)
        img = self._load_image_from_asset(asset_path)
        if img is None:
            return AssetTagResult(
                asset_path=asset_path,
                asset_id=asset_id,
                error="failed to load image from asset",
            )

        # CLIP 打标签
        if not self._is_clip_available():
            return AssetTagResult(
                asset_path=asset_path,
                asset_id=asset_id,
                error="CLIP not available",
            )

        tags = self._classify_image(img, top_k, min_confidence)
        return AssetTagResult(
            asset_path=asset_path,
            asset_id=asset_id,
            tags=tags,
            method="clip",
        )

    def tag_batch(
        self,
        asset_paths: list[str],
        top_k: int | None = None,
        min_confidence: float | None = None,
    ) -> list[AssetTagResult]:
        """批量打标签。

        Args:
            asset_paths: 素材路径列表
            top_k: 返回 top-K 标签
            min_confidence: 置信度阈值

        Returns:
            [AssetTagResult, ...] 与输入顺序一致
        """
        if not asset_paths:
            return []

        results: list[AssetTagResult] = []
        for path in asset_paths:
            results.append(self.tag_asset(path, top_k, min_confidence))
        return results

    def warmup(self) -> bool:
        """预热模型 — 用 dummy 输入执行一次推理。

        Returns:
            True 如果预热成功
        """
        if not self._is_clip_available():
            return False

        try:
            dummy = Image.new("RGB", (224, 224), color=(128, 128, 128))
            with self._lock:
                _ = self._encode_image(dummy)
            # 预计算文本标签 embedding
            self._ensure_text_embeddings()
            logger.info("EagleAssetTagger warmup completed")
            return True
        except Exception as exc:
            logger.warning("EagleAssetTagger warmup failed: %s", exc)
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

    @property
    def total_tags_in_vocabulary(self) -> int:
        """标签词表总标签数。"""
        return sum(len(v) for v in self.tag_vocabulary.values())

    @property
    def categories(self) -> list[str]:
        """标签类别列表。"""
        return list(self.tag_vocabulary.keys())

    def clear_cache(self) -> None:
        """清空 embedding 缓存。"""
        self._embedding_cache.clear()
        self._text_embedding_cache.clear()

    @property
    def embedding_cache_size(self) -> int:
        """当前 embedding 缓存条目数。"""
        return len(self._embedding_cache)

    # ── CLIP 加载 (与 FrameSimilarityComputer 策略一致) ────

    def _is_clip_available(self) -> bool:
        """检查 CLIP 库是否可用 (结果缓存)。"""
        if self._clip_available is None:
            self._clip_available = self._try_init_clip()
            if self._clip_available:
                logger.info(
                    "EagleAssetTagger CLIP loaded (backend=%s, device=%s)",
                    self._clip_backend, self._clip_device,
                )
            else:
                logger.info("EagleAssetTagger CLIP not available")
        return self._clip_available

    def _try_init_clip(self) -> bool:
        """尝试加载 CLIP 模型。"""
        try:
            import torch  # type: ignore[import]

            self._clip_device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            self._clip_device = "cpu"

        # 尝试 openai-clip
        try:
            import clip  # type: ignore[import]

            self._clip_model, self._clip_preprocess = clip.load(
                "ViT-B/32", device=self._clip_device
            )
            self._clip_backend = "openai"
            return True
        except ImportError:
            pass

        # 尝试 transformers
        try:
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

    # ── 图像/视频加载 ───────────────────────────────────────

    def _load_image_from_asset(self, asset_path: str) -> Image.Image | None:
        """从素材路径加载图像 (视频提取首帧)。

        支持的图片格式: png/jpg/jpeg/gif/webp/bmp
        支持的视频格式: mp4/mov/avi/webm/mkv (提取首帧)
        """
        path = Path(asset_path)
        ext = path.suffix.lower()

        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
        video_exts = {".mp4", ".mov", ".avi", ".webm", ".mkv"}

        if ext in image_exts:
            return self._load_image(asset_path)
        elif ext in video_exts:
            return self._extract_video_frame(asset_path)
        else:
            # 未知扩展名, 尝试当图片加载
            return self._load_image(asset_path)

    def _load_image(self, source: str) -> Image.Image | None:
        """加载图片 (本地路径)。"""
        try:
            img = Image.open(source)
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img
        except Exception as exc:
            logger.warning("Failed to load image %s: %s", source, exc)
            return None

    def _extract_video_frame(self, video_path: str) -> Image.Image | None:
        """使用 ffmpeg 提取视频首帧。"""
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
                cmd,
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0 or not result.stdout:
                return None

            img = Image.open(io.BytesIO(result.stdout))
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img
        except Exception as exc:
            logger.warning("Failed to extract video frame %s: %s", video_path, exc)
            return None

    def _find_ffmpeg(self) -> str:
        """查找 ffmpeg 可执行文件。"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return "ffmpeg"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return ""

    # ── CLIP 编码 + 分类 ────────────────────────────────────

    def _encode_image(self, img: Image.Image) -> Any:
        """编码图片为 CLIP embedding (带缓存)。"""
        content_key = self._image_content_key(img)
        if content_key in self._embedding_cache:
            # LRU: 移到末尾
            self._embedding_cache.move_to_end(content_key)
            return self._embedding_cache[content_key]

        if self._clip_backend == "openai":
            feat = self._encode_image_openai(img)
        elif self._clip_backend == "transformers":
            feat = self._encode_image_transformers(img)
        else:
            return None

        if feat is not None:
            self._embedding_cache[content_key] = feat
            if len(self._embedding_cache) > self._embedding_cache_size:
                self._embedding_cache.popitem(last=False)

        return feat

    def _encode_image_openai(self, img: Image.Image) -> Any:
        """openai-clip 编码图片。"""
        import torch  # type: ignore[import]

        try:
            image_input = self._clip_preprocess(img).unsqueeze(0).to(self._clip_device)
            with torch.no_grad():
                feat = self._clip_model.encode_image(image_input)
            return feat
        except Exception as exc:
            logger.warning("openai-clip encode_image failed: %s", exc)
            return None

    def _encode_image_transformers(self, img: Image.Image) -> Any:
        """transformers CLIP 编码图片。"""
        import torch  # type: ignore[import]

        try:
            inputs = self._clip_preprocess(images=img, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(self._clip_device)
            with torch.no_grad():
                outputs = self._clip_model.get_image_features(pixel_values=pixel_values)
            return outputs
        except Exception as exc:
            logger.warning("transformers encode_image failed: %s", exc)
            return None

    def _ensure_text_embeddings(self) -> dict[str, Any]:
        """确保所有标签文本的 embedding 已计算并缓存。

        Returns:
            {tag_text: embedding} 字典
        """
        vocab_key = self._vocab_hash()
        if vocab_key in self._text_embedding_cache:
            return self._text_embedding_cache[vocab_key]

        # 计算所有标签文本的 embedding
        all_tags: list[tuple[str, str]] = []  # (category, tag_text)
        for category, tags in self.tag_vocabulary.items():
            for tag in tags:
                all_tags.append((category, tag))

        text_embeddings: dict[str, Any] = {}
        if self._clip_backend == "openai":
            text_embeddings = self._encode_texts_openai([t for _, t in all_tags])
        elif self._clip_backend == "transformers":
            text_embeddings = self._encode_texts_transformers([t for _, t in all_tags])

        self._text_embedding_cache[vocab_key] = text_embeddings
        return text_embeddings

    def _encode_texts_openai(self, texts: list[str]) -> dict[str, Any]:
        """openai-clip 批量编码文本。"""
        import torch  # type: ignore[import]
        import clip  # type: ignore[import]

        try:
            text_tokens = clip.tokenize(texts).to(self._clip_device)
            with torch.no_grad():
                text_feats = self._clip_model.encode_text(text_tokens)
            return {text: text_feats[i] for i, text in enumerate(texts)}
        except Exception as exc:
            logger.warning("openai-clip encode_text failed: %s", exc)
            return {}

    def _encode_texts_transformers(self, texts: list[str]) -> dict[str, Any]:
        """transformers CLIP 批量编码文本。"""
        import torch  # type: ignore[import]

        try:
            inputs = self._clip_preprocess(text=texts, return_tensors="pt", padding=True, truncation=True)
            input_ids = inputs["input_ids"].to(self._clip_device)
            attention_mask = inputs.get("attention_mask")
            if attention_mask is not None:
                attention_mask = attention_mask.to(self._clip_device)
            with torch.no_grad():
                outputs = self._clip_model.get_text_features(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                )
            return {text: outputs[i] for i, text in enumerate(texts)}
        except Exception as exc:
            logger.warning("transformers encode_text failed: %s", exc)
            return {}

    def _classify_image(
        self,
        img: Image.Image,
        top_k: int,
        min_confidence: float,
    ) -> list[AssetTag]:
        """使用 CLIP 对图片进行零样本分类。

        Args:
            img: PIL Image
            top_k: 返回 top-K 标签
            min_confidence: 最低置信度阈值

        Returns:
            标签列表 (按 confidence 降序)
        """
        import torch  # type: ignore[import]
        import torch.nn.functional as F  # type: ignore[import]

        with self._lock:
            # 编码图片
            img_feat = self._encode_image(img)
            if img_feat is None:
                return []

            # 确保文本 embedding 已计算
            text_embeddings = self._ensure_text_embeddings()
            if not text_embeddings:
                return []

            # 计算图片与每个标签文本的相似度
            similarities: list[tuple[str, str, float]] = []  # (category, tag, similarity)
            for category, tags in self.tag_vocabulary.items():
                for tag in tags:
                    if tag not in text_embeddings:
                        continue
                    text_feat = text_embeddings[tag]
                    sim = F.cosine_similarity(img_feat, text_feat).item()
                    similarities.append((category, tag, sim))

        # 按 similarity 降序排序
        similarities.sort(key=lambda x: x[2], reverse=True)

        # 过滤低置信度 + 截取 top-K
        result: list[AssetTag] = []
        for category, tag, sim in similarities:
            if sim < min_confidence:
                continue
            # 将 similarity 映射到 0-1 区间 (cosine similarity 范围约 -1 到 1)
            # 对于 CLIP, 通常 0.1-0.4 已经是较好的匹配
            confidence = max(0.0, min(1.0, (sim + 1.0) / 2.0))
            result.append(AssetTag(
                tag=tag,
                category=category,
                confidence=confidence,
            ))
            if len(result) >= top_k:
                break

        return result

    # ── 辅助方法 ────────────────────────────────────────────

    def _image_content_key(self, img: Image.Image) -> str:
        """基于图片内容生成 MD5 key (用于 embedding 缓存)。"""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return hashlib.md5(buf.getvalue()).hexdigest()

    def _vocab_hash(self) -> str:
        """标签词表的哈希 key (用于文本 embedding 缓存)。"""
        content = json.dumps(self.tag_vocabulary, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()


# ── 持久化存储 ─────────────────────────────────────────────────────


class EagleTagStore:
    """Eagle 素材标签持久化存储。

    存储路径: data/eagle_tags/
    文件格式: {asset_id}.json
    索引文件: data/eagle_tags/index.json

    Usage::

        store = EagleTagStore()
        store.save(result)
        loaded = store.load("MW_VIDEO_260721_000123")
        all_tags = store.load_all()
    """

    def __init__(self, data_dir: str = "") -> None:
        if data_dir:
            self._data_dir = Path(data_dir)
        else:
            # 默认: 项目根目录 / data / eagle_tags
            # eagle_tagger.py → creative_mapping_engine → market_ops → src → project_slim
            project_root = Path(__file__).resolve().parents[3]
            self._data_dir = project_root / "data" / "eagle_tags"

        self._data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def save(self, result: AssetTagResult) -> Path:
        """保存打标签结果。

        Args:
            result: 打标签结果

        Returns:
            保存的文件路径
        """
        asset_id = result.asset_id or "unknown"
        file_path = self._data_dir / f"{asset_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        return file_path

    def load(self, asset_id: str) -> AssetTagResult | None:
        """加载单个素材的标签。

        Args:
            asset_id: 素材 ID

        Returns:
            AssetTagResult 或 None (不存在时)
        """
        file_path = self._data_dir / f"{asset_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AssetTagResult.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load tag result for %s: %s", asset_id, exc)
            return None

    def load_all(self) -> list[AssetTagResult]:
        """加载所有已保存的标签结果。"""
        results: list[AssetTagResult] = []
        for file_path in sorted(self._data_dir.glob("*.json")):
            if file_path.name == "index.json":
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(AssetTagResult.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue
        return results

    def delete(self, asset_id: str) -> bool:
        """删除单个素材的标签。

        Returns:
            True 如果删除成功
        """
        file_path = self._data_dir / f"{asset_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def exists(self, asset_id: str) -> bool:
        """检查标签是否已存在。"""
        return (self._data_dir / f"{asset_id}.json").exists()

    def list_asset_ids(self) -> list[str]:
        """列出所有已打标签的素材 ID。"""
        return [
            f.stem for f in sorted(self._data_dir.glob("*.json"))
            if f.name != "index.json"
        ]

    def get_stats(self) -> dict[str, Any]:
        """获取标签存储统计信息。"""
        all_results = self.load_all()
        category_count: dict[str, int] = {}
        for r in all_results:
            for tag in r.tags:
                category_count[tag.category] = category_count.get(tag.category, 0) + 1

        return {
            "total_assets": len(all_results),
            "total_tags": sum(len(r.tags) for r in all_results),
            "avg_tags_per_asset": (
                sum(len(r.tags) for r in all_results) / len(all_results)
                if all_results else 0.0
            ),
            "category_distribution": category_count,
            "storage_dir": str(self._data_dir),
        }


# ── 单例 ──────────────────────────────────────────────────────────

_tagger_instance: EagleAssetTagger | None = None
_tagger_lock = threading.Lock()


def get_eagle_tagger(
    preload: bool = False,
    **kwargs: Any,
) -> EagleAssetTagger:
    """获取 EagleAssetTagger 单例。

    Args:
        preload: 是否预加载 CLIP 模型 (仅首次调用有效)
        **kwargs: 传给 EagleAssetTagger 的额外参数 (仅首次调用有效)

    Returns:
        EagleAssetTagger 实例
    """
    global _tagger_instance
    if _tagger_instance is None:
        with _tagger_lock:
            if _tagger_instance is None:
                _tagger_instance = EagleAssetTagger(preload=preload, **kwargs)
    return _tagger_instance


def reset_eagle_tagger() -> None:
    """重置单例 (主要用于测试)。"""
    global _tagger_instance
    with _tagger_lock:
        _tagger_instance = None


_store_instance: EagleTagStore | None = None
_store_lock = threading.Lock()


def get_eagle_tag_store(data_dir: str = "") -> EagleTagStore:
    """获取 EagleTagStore 单例。"""
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = EagleTagStore(data_dir=data_dir)
    return _store_instance


def reset_eagle_tag_store() -> None:
    """重置单例 (主要用于测试)。"""
    global _store_instance
    with _store_lock:
        _store_instance = None
