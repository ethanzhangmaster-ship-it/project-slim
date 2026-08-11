"""Visual Embedding — 视觉嵌入表示"""
from pathlib import Path
from typing import List

from ..models import RemixRecipe


class VisualEmbedding:
    """生成创意的视觉嵌入向量（简化版，基于素材特征）"""

    def embed(self, recipe: RemixRecipe) -> List[float]:
        """生成64维嵌入向量"""
        embedding = [0.0] * 64

        # 基于segments填充嵌入
        for i, seg in enumerate(recipe.segments[:8]):
            base = i * 8
            if base + 7 >= 64:
                break
            # role encoding
            role_map = {"hook": 1.0, "gameplay": 0.8, "problem": 0.6, "reward": 0.9, "cta": 0.7}
            embedding[base] = role_map.get(seg.role, 0.5)
            # duration
            embedding[base + 1] = min(seg.duration / 10, 1.0)
            # material score
            embedding[base + 2] = seg.material_score / 100
            # segment score
            embedding[base + 3] = seg.segment_score / 100
            # mutation type encoding (simple hash)
            embedding[base + 4] = hash(seg.mutation_type or "") % 100 / 100
            # start position
            embedding[base + 5] = min(seg.start / 20, 1.0)
            # v_num hash
            embedding[base + 6] = hash(seg.v_num) % 100 / 100
            # ratio encoding
            embedding[base + 7] = 1.0 if "9X16" in str(seg.filepath) else 0.5

        return embedding

    def similarity(self, emb_a: List[float], emb_b: List[float]) -> float:
        """计算余弦相似度"""
        import numpy as np
        a = np.array(emb_a)
        b = np.array(emb_b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
