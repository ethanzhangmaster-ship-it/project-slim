"""Ranking Agent 权重配置

所有权重可配置，默认按 PRD 定义。
未来可通过配置文件或数据库动态调整。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RankingConfig:
    """评分权重配置"""

    # 10维评分权重（总和应为1.0）
    weights: dict[str, float] = field(default_factory=lambda: {
        "winning_similarity": 0.20,
        "facebook_hook": 0.20,
        "visual_readability": 0.15,
        "novelty": 0.10,
        "creative_fatigue": 0.05,
        "brand_consistency": 0.10,
        "ai_generation_risk": 0.05,
        "gameplay_consistency": 0.10,
        "facebook_policy_risk": 0.05,
    })

    # 淘汰阈值
    discard_threshold: float = 60.0  # Overall < 60 自动淘汰

    # TOP N 推荐数量
    top_n: int = 20

    # 各维度最低分阈值（低于此分该维度有风险）
    min_dimension_scores: dict[str, float] = field(default_factory=lambda: {
        "winning_similarity": 50.0,
        "facebook_hook": 55.0,
        "visual_readability": 60.0,
        "novelty": 30.0,
        "creative_fatigue": 40.0,
        "brand_consistency": 70.0,
        "ai_generation_risk": 50.0,
        "gameplay_consistency": 60.0,
        "facebook_policy_risk": 70.0,
    })

    # Facebook 最佳实践约束
    fb_constraints: dict[str, Any] = field(default_factory=lambda: {
        "min_subject_coverage": 0.40,  # 主体占画面最少40%
        "max_subject_coverage": 0.70,  # 主体占画面最多70%
        "preferred_aspect_ratio": "9:16",
        "min_contrast_ratio": 3.0,
        "max_text_overlay_words": 5,
        "hook_duration_sec": 3,
        "preferred_duration_sec": (15, 30),
    })

    # 相似度评分参数
    similarity_weights: dict[str, float] = field(default_factory=lambda: {
        "character_type": 0.20,
        "creature_type": 0.15,
        "environment_type": 0.15,
        "color_mood": 0.15,
        "lighting_temperature": 0.10,
        "hook_type": 0.15,
        "composition_layout": 0.10,
    })

    # Novelty 参数
    novelty_params: dict[str, float] = field(default_factory=lambda: {
        "color_change_bonus": 5.0,
        "creature_change_bonus": 15.0,
        "environment_change_bonus": 20.0,
        "pose_change_bonus": 10.0,
        "style_change_penalty": -20.0,
        "character_type_change_penalty": -30.0,
        "hook_type_change_penalty": -25.0,
    })

    # Fatigue 参数
    fatigue_params: dict[str, Any] = field(default_factory=lambda: {
        "similarity_threshold_high": 0.95,  # >95% 极容易疲劳
        "similarity_threshold_low": 0.70,   # <70% 安全
        "max_safe_color_variants": 5,       # 同Winning最多5个颜色变体
        "max_safe_creature_variants": 3,    # 同Winning最多3个生物变体
    })

    # AI Generation Risk 参数
    ai_risk_params: dict[str, float] = field(default_factory=lambda: {
        "hand_visible_penalty": -15.0,
        "text_in_image_penalty": -10.0,
        "complex_scene_penalty": -8.0,
        "multiple_creatures_penalty": -5.0,
        "simple_color_swap_bonus": 5.0,
        "simple_creature_swap_bonus": 3.0,
    })

    def validate(self) -> list[str]:
        """验证配置有效性，返回错误信息列表"""
        errors = []
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            errors.append(f"权重总和应为1.0，当前={total_weight:.3f}")
        if self.discard_threshold < 0 or self.discard_threshold > 100:
            errors.append(f"淘汰阈值应在0-100之间，当前={self.discard_threshold}")
        return errors

    @classmethod
    def from_dict(cls, d: dict) -> "RankingConfig":
        """从字典加载配置"""
        weights = d.get("weights", {})
        return cls(
            weights=weights if weights else cls().weights,
            discard_threshold=d.get("discard_threshold", 60.0),
            top_n=d.get("top_n", 20),
        )
