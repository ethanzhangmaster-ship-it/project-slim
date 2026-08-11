"""Variant Generator — 从父创意生成多个变体"""
from typing import List
from copy import deepcopy

from ..models import RemixRecipe, RemixSegment
from ..generator.mutation_engine import MutationEngine


class VariantGenerator:
    """生成 Creative Family Tree"""

    def __init__(self):
        self.mutation = MutationEngine()

    def generate_variants(self, parent: RemixRecipe, count: int = 100) -> List[RemixRecipe]:
        """基于父创意生成 N 个变体"""
        variants = []

        for i in range(count):
            variant = self._mutate_recipe(parent, i)
            variants.append(variant)

        return variants

    def _mutate_recipe(self, parent: RemixRecipe, variant_idx: int) -> RemixRecipe:
        """对单个配方进行变异"""
        config = self.mutation.generate_variant_config(variant_idx)

        recipe = RemixRecipe(
            recipe_id=f"{parent.recipe_id}_v{variant_idx+1:03d}",
            template=parent.template,
            target_ratio=parent.target_ratio,
            total_duration=parent.total_duration,
            creative_family=parent.creative_family,
            variant_type=f"{config['hook_variant']}_{config['gameplay_variant']}_{config['ending_variant']}",
            parent_id=parent.recipe_id,
            generation=parent.generation + 1,
        )

        # 复制并变异 segments
        for seg in parent.segments:
            new_seg = deepcopy(seg)
            # 根据 segment role 应用对应的 mutation
            if seg.role == "hook":
                new_seg.mutation_type = config["hook_variant"]
            elif seg.role == "gameplay":
                new_seg.mutation_type = config["gameplay_variant"]
            elif seg.role in ["reward", "cta"]:
                new_seg.mutation_type = config["ending_variant"]

            # 应用速度乘数调整时长
            if config["speed_multiplier"] != 1.0:
                new_seg.duration = round(new_seg.duration * config["speed_multiplier"], 2)

            recipe.segments.append(new_seg)

        # 重新计算总时长
        recipe.total_duration = sum(s.duration for s in recipe.segments)

        return recipe
