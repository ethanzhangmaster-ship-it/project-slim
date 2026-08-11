"""Mutation Engine — 创意变异引擎"""
import random
from typing import List

from ..config import MUTATION_CONFIG


class MutationEngine:
    """生成 Hook / Gameplay / Ending 的多维度变异"""

    def __init__(self):
        self.hook_pool = MUTATION_CONFIG["hook_variants"]
        self.gameplay_pool = MUTATION_CONFIG["gameplay_variants"]
        self.ending_pool = MUTATION_CONFIG["ending_variants"]

    def mutate_hook(self, base: str = "", variant_idx: int = 0) -> str:
        """Hook 变异"""
        if base and base in self.hook_pool:
            idx = self.hook_pool.index(base)
            return self.hook_pool[(idx + variant_idx) % len(self.hook_pool)]
        return self.hook_pool[variant_idx % len(self.hook_pool)]

    def mutate_gameplay(self, base: str = "", variant_idx: int = 0) -> str:
        """Gameplay 变异"""
        if base and base in self.gameplay_pool:
            idx = self.gameplay_pool.index(base)
            return self.gameplay_pool[(idx + variant_idx) % len(self.gameplay_pool)]
        return self.gameplay_pool[variant_idx % len(self.gameplay_pool)]

    def mutate_ending(self, base: str = "", variant_idx: int = 0) -> str:
        """Ending 变异"""
        if base and base in self.ending_pool:
            idx = self.ending_pool.index(base)
            return self.ending_pool[(idx + variant_idx) % len(self.ending_pool)]
        return self.ending_pool[variant_idx % len(self.ending_pool)]

    def generate_variant_config(self, variant_idx: int = 0) -> dict:
        """生成一组完整的变异配置"""
        return {
            "hook_variant": self.mutate_hook(variant_idx=variant_idx),
            "gameplay_variant": self.mutate_gameplay(variant_idx=variant_idx),
            "ending_variant": self.mutate_ending(variant_idx=variant_idx),
            "speed_multiplier": random.choice([0.9, 1.0, 1.1, 1.2]),
            "transition_style": random.choice(["fade", "dissolve", "cut"]),
        }
