"""Image Embedding — OpenCLIP ViT-B/32 图片编码

对每张缩略图生成 512 维 CLIP embedding 向量,
用于后续视觉聚类和相似度计算。
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import torch
    import open_clip
    from PIL import Image
    HAS_CLIP = True
except ImportError:
    HAS_CLIP = False

from ..config import CLIP_MODEL, CLIP_PRETRAINED, OUTPUT_DIR


class ImageEmbedding:
    """CLIP 图片嵌入引擎"""

    def __init__(self):
        self.model = None
        self.preprocess = None
        self.device = None
        self._loaded = False

    def _ensure_loaded(self):
        """懒加载 CLIP 模型"""
        if self._loaded:
            return
        if not HAS_CLIP:
            raise ImportError(
                "需要安装 open_clip_torch: pip install open_clip_torch torch Pillow"
            )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            CLIP_MODEL, pretrained=CLIP_PRETRAINED
        )
        self.model = self.model.to(self.device)
        self.model.eval()
        self._loaded = True
        print(f"[ImageEmbedding] CLIP {CLIP_MODEL} loaded on {self.device}")

    def encode_image(self, image_path: Path) -> Optional[np.ndarray]:
        """编码单张图片, 返回 512 维向量"""
        self._ensure_loaded()
        try:
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                features = self.model.encode_image(image_tensor)
                features = features / features.norm(dim=-1, keepdim=True)
            return features.cpu().numpy().flatten()
        except Exception as e:
            print(f"  [ImageEmbedding] 编码失败 {image_path.name}: {e}")
            return None

    def encode_batch(self, image_paths: Dict[str, Path],
                     cache_path: Optional[Path] = None) -> Dict[str, np.ndarray]:
        """批量编码图片

        Args:
            image_paths: {ad_id: path}
            cache_path: 缓存 .npz 文件路径

        Returns:
            {ad_id: 512-dim vector}
        """
        # 尝试加载缓存
        if cache_path and cache_path.exists():
            cached = np.load(cache_path, allow_pickle=True)
            embeddings = dict(cached["embeddings"].item())
            print(f"[ImageEmbedding] 从缓存加载 {len(embeddings)} 个 embedding")
            # 找出未缓存的
            missing = {k: v for k, v in image_paths.items() if k not in embeddings}
            if not missing:
                return embeddings
            print(f"[ImageEmbedding] 需要新编码 {len(missing)} 张")
        else:
            embeddings = {}
            missing = image_paths

        self._ensure_loaded()

        total = len(missing)
        for i, (ad_id, path) in enumerate(missing.items()):
            vec = self.encode_image(path)
            if vec is not None:
                embeddings[ad_id] = vec

            if (i + 1) % 50 == 0:
                print(f"  编码进度: {i+1}/{total}")

        # 保存缓存
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache_path, embeddings=embeddings)
            print(f"[ImageEmbedding] 缓存已保存: {cache_path}")

        print(f"[ImageEmbedding] 总 embedding: {len(embeddings)}")
        return embeddings

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """计算两个 embedding 的余弦相似度"""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))
