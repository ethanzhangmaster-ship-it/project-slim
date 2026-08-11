"""Remix Recipe Generator — 生成剪辑方案"""
import random
from typing import List, Dict
from pathlib import Path

from ..models import RemixRecipe, RemixSegment, MaterialScore
from ..config import DNA_TEMPLATES, RATIO_CLASSES


class RecipeGenerator:
    """基于 Winner DNA + Material Ranking 生成混剪配方"""

    def __init__(self, role_scores: Dict[str, List[MaterialScore]], video_index: Dict):
        self.role_scores = role_scores
        self.video_index = video_index

    def generate(self, template_name: str = "standard_30s",
                 target_ratio: str = "9X16",
                 count: int = 20) -> List[RemixRecipe]:
        """生成 N 个混剪配方"""
        template = DNA_TEMPLATES.get(template_name, DNA_TEMPLATES["standard_30s"])
        recipes = []

        for i in range(count):
            recipe_id = f"remix_{target_ratio}_{i+1:03d}"
            recipe = self._build_recipe(recipe_id, template, target_ratio, variant=i)
            if recipe.segments:
                recipes.append(recipe)

        return recipes

    def _build_recipe(self, recipe_id: str, template: List[Dict],
                      target_ratio: str, variant: int = 0) -> RemixRecipe:
        """构建单个配方"""
        recipe = RemixRecipe(
            recipe_id=recipe_id,
            template=template[0]["role"] if template else "",
            target_ratio=target_ratio,
            total_duration=sum(t["duration"] for t in template),
            creative_family="P04_witch_merge",
            variant_type=self._variant_type(variant),
        )

        current_time = 0.0
        used_v_nums = set()

        for slot in template:
            role = slot["role"]
            target_dur = slot["duration"]

            candidates = self.role_scores.get(role, [])
            if not candidates:
                continue

            # 选择最佳候选（带 variant 偏移，确保多样性）
            idx = min(variant, len(candidates) - 1)
            # 尝试找一个没用过且本地存在的
            selected = None
            for offset in range(len(candidates)):
                check_idx = (idx + offset) % len(candidates)
                cand = candidates[check_idx]
                if cand.v_num not in used_v_nums and cand.v_num in self.video_index:
                    selected = cand
                    break

            if not selected:
                selected = candidates[0]

            used_v_nums.add(selected.v_num)

            asset = self.video_index[selected.v_num]
            seg = selected.best_segment
            if not seg:
                seg_duration = min(target_dur, asset.duration * 0.6) if asset.duration > 0 else target_dur
                seg_start = 0
            else:
                seg_duration = min(target_dur, seg.duration, asset.duration - seg.start if asset.duration > seg.start else target_dur)
                seg_start = seg.start

            segment = RemixSegment(
                role=role,
                v_num=selected.v_num,
                start=seg_start,
                duration=seg_duration,
                filepath=asset.filepath,
                source_ratio=asset.ratio,
                material_score=selected.overall,
                segment_score=seg.overall if seg else selected.overall,
            )
            recipe.segments.append(segment)
            current_time += seg_duration

        recipe.total_duration = current_time
        return recipe

    def _variant_type(self, variant: int) -> str:
        types = ["hook_dragon", "hook_witch", "hook_rescue",
                 "gameplay_speed", "gameplay_combo", "gameplay_upgrade",
                 "reward_transform", "reward_cta", "reward_character"]
        return types[variant % len(types)]
