"""Variant Generator"""
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class VariantConfig:
    hook_types: List[str] = field(default_factory=lambda: ["close_up", "fast_zoom", "product_reveal", "action"])
    camera_moves: List[str] = field(default_factory=lambda: ["pan_right", "tilt_up", "zoom_in", "tracking"])
    lighting_options: List[str] = field(default_factory=lambda: ["bright", "dramatic", "soft", "cinematic"])
    cta_types: List[str] = field(default_factory=lambda: ["buy_now", "learn_more", "download", "subscribe"])
    endings: List[str] = field(default_factory=lambda: ["fade_out", "freeze_frame", "text_overlay", "loop"])


class VariantGenerator:
    """变体生成器 - 为 A/B 测试生成不同变体"""

    def __init__(self, config: VariantConfig = None):
        self.config = config or VariantConfig()

    def generate_variants(self, base_blueprint: Dict[str, Any], count: int = 3) -> List[Dict[str, Any]]:
        variants = []
        for i in range(count):
            variant = self._create_variant(base_blueprint, i + 1)
            variants.append(variant)
        return variants

    def _create_variant(self, base_blueprint: Dict[str, Any], variant_num: int) -> Dict[str, Any]:
        variant = base_blueprint.copy()

        idx = variant_num - 1
        variant["variant_id"] = f"{base_blueprint.get('id', 'V001')}-{chr(65 + idx)}"

        variant["hook_type"] = self.config.hook_types[idx % len(self.config.hook_types)]
        variant["camera_move"] = self.config.camera_moves[idx % len(self.config.camera_moves)]
        variant["lighting"] = self.config.lighting_options[idx % len(self.config.lighting_options)]
        variant["cta"] = self.config.cta_types[idx % len(self.config.cta_types)]
        variant["ending"] = self.config.endings[idx % len(self.config.endings)]

        variant["prompt_dna"] = f"{variant['hook_type']} + {variant['camera_move']} + {variant['lighting']}"

        return variant

    def generate_grid(self, base_blueprint: Dict[str, Any]) -> List[Dict[str, Any]]:
        variants = []
        idx = 0
        for hook in self.config.hook_types[:2]:
            for camera in self.config.camera_moves[:2]:
                variant = base_blueprint.copy()
                variant["variant_id"] = f"{base_blueprint.get('id', 'V001')}-G{idx + 1}"
                variant["hook_type"] = hook
                variant["camera_move"] = camera
                variant["prompt_dna"] = f"{hook} + {camera}"
                variants.append(variant)
                idx += 1
        return variants
