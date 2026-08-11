"""Embedding Features — 64维嵌入特征"""
from typing import List

from ..models import RemixRecipe
from ..analyzer.visual_embedding import VisualEmbedding


class EmbeddingFeatures:
    """生成64维特征向量"""

    def __init__(self):
        self.visual_embed = VisualEmbedding()

    def extract(self, recipe: RemixRecipe) -> List[float]:
        """提取64维特征"""
        features = []

        # 1. 视觉嵌入 (32维)
        visual_emb = self.visual_embed.embed(recipe)
        features.extend(visual_emb[:32])

        # 2. 结构特征 (16维)
        roles = [s.role for s in recipe.segments]
        role_counts = {r: roles.count(r) for r in ["hook", "gameplay", "problem", "reward", "cta"]}
        features.extend([
            role_counts.get("hook", 0) / 3,
            role_counts.get("gameplay", 0) / 3,
            role_counts.get("problem", 0) / 3,
            role_counts.get("reward", 0) / 3,
            role_counts.get("cta", 0) / 3,
            len(recipe.segments) / 10,
            recipe.total_duration / 60,
            sum(s.material_score for s in recipe.segments) / 500,
            sum(s.segment_score for s in recipe.segments) / 500,
            len(set(s.v_num for s in recipe.segments)) / len(recipe.segments) if recipe.segments else 0,
            1.0 if recipe.variant_type else 0,
            hash(recipe.creative_family) % 100 / 100,
            0, 0, 0, 0,  # padding
        ])

        # 3. 变异特征 (16维)
        mutations = [s.mutation_type for s in recipe.segments if s.mutation_type]
        mut_counts = {}
        for m in mutations:
            mut_counts[m] = mut_counts.get(m, 0) + 1

        top_mutations = sorted(mut_counts.items(), key=lambda x: -x[1])[:8]
        for mut, count in top_mutations:
            features.extend([hash(mut) % 100 / 100, count / len(recipe.segments) if recipe.segments else 0])

        # padding to 64
        while len(features) < 64:
            features.append(0.0)

        return features[:64]
