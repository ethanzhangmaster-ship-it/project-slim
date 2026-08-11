"""E11.3.4 — Vision Feature Vectorizer。

VisionFeatureRecord → 8 维 float vector。

向量维度：
  [hook_score, comprehension_score, reward_score,
   avg_brightness, avg_contrast, avg_edge_density,
   avg_saturation, avg_color_entropy]

所有值已天然在 [0,1] 或相近范围，无需额外归一化。
"""

from __future__ import annotations

import math
from typing import Any

from ..feature_store.models import VisionFeatureRecord
from .models import VisionVector

# 8 维特征向量
VECTOR_DIM = 8


class VisionFeatureVectorizer:
    """VisionFeatureRecord → float vector 编码器。

    第一版使用 8 个手工视觉特征，无需 CLIP/ResNet。
    后续可扩展为学习型 embedding。
    """

    FEATURE_KEYS = [
        "hook_score",
        "comprehension_score",
        "reward_score",
        "avg_brightness",
        "avg_contrast",
        "avg_edge_density",
        "avg_saturation",
        "avg_color_entropy",
    ]

    @property
    def dimension(self) -> int:
        return VECTOR_DIM

    def encode(self, record: VisionFeatureRecord) -> VisionVector:
        """将 VisionFeatureRecord 编码为 VisionVector。

        Args:
            record: 视觉特征记录

        Returns:
            VisionVector with 8-dim vector
        """
        vector = [
            record.hook_score,
            record.comprehension_score,
            record.reward_score,
            record.avg_brightness,
            record.avg_contrast,
            record.avg_edge_density,
            record.avg_saturation,
            record.avg_color_entropy,
        ]

        # L2 normalize
        vector = self._normalize(vector)

        return VisionVector(
            feature_id=record.feature_id,
            creative_asset_id=record.creative_asset_id,
            vector=vector,
            hook_score=record.hook_score,
            reward_score=record.reward_score,
            is_winner=record.is_winner,
            metadata={
                "eagle_filename": record.eagle_filename,
                "lifecycle_status": record.lifecycle_status,
                "metric": record.metric,
            },
        )

    def encode_batch(
        self, records: list[VisionFeatureRecord]
    ) -> list[VisionVector]:
        """批量编码。"""
        return [self.encode(r) for r in records]

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        """L2 归一化。"""
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算两个向量之间的余弦相似度。

        Args:
            a: 向量 A（应已 L2 归一化）
            b: 向量 B（应已 L2 归一化）

        Returns:
            余弦相似度 (0-1)
        """
        if len(a) != len(b):
            raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
        return sum(ai * bi for ai, bi in zip(a, b))

    def __repr__(self) -> str:
        return f"VisionFeatureVectorizer(dim={VECTOR_DIM})"