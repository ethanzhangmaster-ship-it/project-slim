"""Winner Similarity — CLIP 余弦相似度检查

计算生成图与 Top Winner 的视觉相似度。
通过阈值: similarity > 0.75
"""
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import WINNER_SIMILARITY_THRESHOLD


class WinnerSimilarityChecker:
    """Winner 相似度检查器"""

    def __init__(self, threshold: float = WINNER_SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            from ..asset_resolver.image_embedding import ImageEmbedding
            self._embedder = ImageEmbedding()
        return self._embedder

    def check(self, generated_path: Path,
              winner_paths: List[Path]) -> Dict[str, float]:
        """检查生成图与 winners 的相似度

        Args:
            generated_path: 生成图路径
            winner_paths: winner 图片路径列表

        Returns:
            {"max_similarity": float, "avg_similarity": float, "passed": bool}
        """
        embedder = self._get_embedder()

        gen_emb = embedder.encode_image(generated_path)
        if gen_emb is None:
            return {"max_similarity": 0, "avg_similarity": 0, "passed": False}

        similarities = []
        for wp in winner_paths:
            win_emb = embedder.encode_image(wp)
            if win_emb is not None:
                sim = embedder.cosine_similarity(gen_emb, win_emb)
                similarities.append(sim)

        if not similarities:
            return {"max_similarity": 0, "avg_similarity": 0, "passed": False}

        max_sim = max(similarities)
        avg_sim = sum(similarities) / len(similarities)

        return {
            "max_similarity": round(max_sim, 4),
            "avg_similarity": round(avg_sim, 4),
            "passed": max_sim >= self.threshold,
            "threshold": self.threshold,
            "n_winners_compared": len(similarities),
        }

    def check_batch(self, generated_paths: List[Path],
                    winner_paths: List[Path]) -> List[dict]:
        """批量检查"""
        results = []
        for gp in generated_paths:
            result = self.check(gp, winner_paths)
            result["image"] = str(gp.name)
            results.append(result)
        return results
