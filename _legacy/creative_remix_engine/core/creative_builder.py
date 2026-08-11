"""Creative Builder — 创意构建器"""
from ..models import RemixRecipe


class CreativeBuilder:
    """基于配方构建完整创意"""

    def build(self, recipe: RemixRecipe) -> dict:
        """构建创意描述"""
        return {
            "id": recipe.recipe_id,
            "family": recipe.creative_family,
            "variant": recipe.variant_type,
            "duration": recipe.total_duration,
            "segments": len(recipe.segments),
            "hook_v_num": next((s.v_num for s in recipe.segments if s.role == "hook"), ""),
            "gameplay_v_num": next((s.v_num for s in recipe.segments if s.role == "gameplay"), ""),
            "reward_v_num": next((s.v_num for s in recipe.segments if s.role == "reward"), ""),
        }
