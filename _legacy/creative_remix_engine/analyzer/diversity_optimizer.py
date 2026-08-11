"""Diversity Optimizer V2 — 三级去重引擎"""
from typing import List, Dict, Tuple
from collections import defaultdict

from ..models import RemixRecipe, CreativePrediction


class DiversityOptimizer:
    """三级去重：Exact Duplicate > Similar Family > Different Creative"""

    def __init__(self):
        self.exact_threshold = 0.995
        self.similar_threshold = 0.99

    def deduplicate(self, recipes: List[RemixRecipe],
                    predictions: List[CreativePrediction]) -> List[Tuple[RemixRecipe, CreativePrediction]]:
        """
        三级去重：
        1. Exact Duplicate (>0.98): 删除
        2. Similar Family (0.90-0.98): 保留最高Prediction
        3. Different Creative (<0.90): 全部保留
        """
        scored = sorted(zip(recipes, predictions), key=lambda x: -x[1].overall_score)

        exact_duplicates = 0
        similar_skipped = 0
        kept = []
        kept_signatures = []

        for recipe, pred in scored:
            sig = self._signature(recipe)
            sim = self._max_similarity(sig, kept_signatures)

            if sim >= self.exact_threshold:
                # Level 1: Exact Duplicate -> 删除
                exact_duplicates += 1
                continue
            elif sim >= self.similar_threshold:
                # Level 2: Similar Family -> 只保留更高分的
                similar_skipped += 1
                continue
            else:
                # Level 3: Different Creative -> 保留
                kept.append((recipe, pred))
                kept_signatures.append(sig)

        print(f"  去重统计: Exact={exact_duplicates}, Similar跳过={similar_skipped}, 保留={len(kept)}")
        return kept

    def _signature(self, recipe: RemixRecipe) -> Dict:
        """生成创意签名"""
        return {
            "v_nums": tuple(sorted(set(s.v_num for s in recipe.segments))),
            "roles": tuple(s.role for s in recipe.segments),
            "duration": round(recipe.total_duration),
            "variant": recipe.variant_type,
            "mutation_types": tuple(sorted(set(s.mutation_type for s in recipe.segments if s.mutation_type))),
        }

    def _max_similarity(self, sig: Dict, kept_sigs: List[Dict]) -> float:
        """计算与已保留签名的最大相似度"""
        if not kept_sigs:
            return 0.0
        return max(self._similarity(sig, k) for k in kept_sigs)

    def _similarity(self, sig_a: Dict, sig_b: Dict) -> float:
        """计算两个签名的相似度"""
        set_a = set(sig_a["v_nums"])
        set_b = set(sig_b["v_nums"])
        overlap = len(set_a & set_b) / max(len(set_a), len(set_b), 1)

        roles_match = sum(1 for a, b in zip(sig_a["roles"], sig_b["roles"]) if a == b)
        role_sim = roles_match / max(len(sig_a["roles"]), len(sig_b["roles"]), 1)

        dur_sim = 1.0 if abs(sig_a["duration"] - sig_b["duration"]) <= 5 else 0.5

        mut_a = set(sig_a.get("mutation_types", ()))
        mut_b = set(sig_b.get("mutation_types", ()))
        mut_sim = len(mut_a & mut_b) / max(len(mut_a), len(mut_b), 1) if mut_a or mut_b else 1.0

        return overlap * 0.40 + role_sim * 0.25 + dur_sim * 0.15 + mut_sim * 0.20
