"""Feature Builder — 构建创意特征向量"""
from typing import Dict

from ..models import RemixRecipe, CreativeFeature, RemixSegment


class FeatureBuilder:
    """从 Recipe 构建机器学习特征"""

    def build(self, recipe: RemixRecipe) -> CreativeFeature:
        """构建创意特征"""
        feature = CreativeFeature(creative_id=recipe.recipe_id)

        # Hook 评分
        hook_segs = [s for s in recipe.segments if s.role == "hook"]
        if hook_segs:
            feature.hook_score = sum(s.material_score for s in hook_segs) / len(hook_segs)

        # DNA Match（平均素材分）
        if recipe.segments:
            feature.dna_match = sum(s.material_score for s in recipe.segments) / len(recipe.segments)

        # Gameplay 评分
        gameplay_segs = [s for s in recipe.segments if s.role == "gameplay"]
        if gameplay_segs:
            feature.gameplay_score = sum(s.segment_score for s in gameplay_segs) / len(gameplay_segs)

        # 基础特征
        feature.duration = recipe.total_duration
        feature.scene_count = len(recipe.segments)
        feature.mutation_type = recipe.variant_type

        # Text density（估算，有文字滚动则密度高）
        text_segs = [s for s in recipe.segments if "文字" in str(s.filepath)]
        feature.text_density = len(text_segs) / max(len(recipe.segments), 1)

        return feature

    def to_dict(self, feature: CreativeFeature) -> Dict:
        """转换为字典（用于模型输入）"""
        return {
            "hook_score": feature.hook_score,
            "dna_match": feature.dna_match,
            "gameplay_score": feature.gameplay_score,
            "duration": feature.duration,
            "scene_count": feature.scene_count,
            "text_density": feature.text_density,
            "mutation_type": self._encode_mutation(feature.mutation_type),
        }

    @staticmethod
    def _encode_mutation(mutation: str) -> int:
        """编码 mutation 类型为数值"""
        mapping = {
            "hook_dragon": 1, "hook_witch": 2, "hook_rescue": 3,
            "gameplay_speed": 4, "gameplay_combo": 5, "gameplay_upgrade": 6,
            "reward_transform": 7, "reward_cta": 8, "reward_character": 9,
        }
        return mapping.get(mutation, 0)
