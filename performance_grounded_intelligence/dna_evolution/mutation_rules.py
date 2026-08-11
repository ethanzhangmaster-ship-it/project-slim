"""Mutation Rules — DNA 变异规则定义

定义 Winner DNA 各维度的可选值、变异策略和不可变因素权重。
"""
from typing import Dict, List, Any

# === DNA 维度定义 ===
# 每个维度包含: key (DNA 路径), nullable (是否可为空), mutable (是否可变异)
DNA_DIMENSIONS = {
    "composition": {
        "path": ["composition"],
        "sub_dims": ["gameplay_area", "reward_area", "character_area", "background_area"],
        "mutable": True,
    },
    "gameplay": {
        "path": ["gameplay"],
        "sub_dims": ["type", "elements"],
        "mutable": False,  # gameplay 是核心, 不轻易改变
    },
    "reward": {
        "path": ["reward"],
        "sub_dims": ["type", "elements"],
        "mutable": True,
    },
    "style": {
        "path": ["style"],
        "sub_dims": ["color_palette", "lighting", "camera", "render_style"],
        "mutable": True,
    },
    "hook": {
        "path": ["hook"],
        "sub_dims": [],
        "mutable": False,  # Hook 策略不可变
    },
    "layout": {
        "path": ["layout"],
        "sub_dims": [],
        "mutable": True,
    },
}

# === 变异候选值池 ===
# 每个可变维度的候选替换值
MUTATION_POOLS: Dict[str, Dict[str, List[str]]] = {
    "style": {
        "color_palette": [
            "purple_gold", "green_nature", "blue_magic", "warm_sunset",
            "dark_fantasy", "bright_colorful", "crystal_blue", "fire_red",
        ],
        "lighting": [
            "magic_glow", "natural", "dramatic", "flat", "sparkle", "dark_moody",
        ],
        "camera": [
            "top_down", "isometric", "front", "close_up", "angled_dynamic",
        ],
        "render_style": [
            "3d_cartoon", "2d_flat", "semi_realistic", "painted", "cel_shaded",
        ],
    },
    "reward": {
        "type": [
            "dragon", "castle", "magic_item", "rare_reward", "character", "mixed",
        ],
        "elements": [
            ["dragon", "gems"],
            ["castle", "coins"],
            ["chest", "gems", "crown"],
            ["magic_staff", "potion", "crystal"],
            ["dragon", "egg", "crystal"],
            ["coins", "gems", "chest"],
        ],
    },
    "composition": {
        "gameplay_ratio_range": [0.35, 0.40, 0.45, 0.50, 0.55, 0.60],
        "reward_ratio_range": [0.15, 0.20, 0.25, 0.30, 0.35],
        "reward_position": [
            "top_right", "top_left", "center_top", "center", "bottom_right",
        ],
        "character_position": [
            "bottom_left", "bottom_right", "bottom", "left", "right",
        ],
    },
    "layout": {
        "values": [
            "center_merge", "split_compare", "reward_focus", "character_center",
            "full_board", "diagonal", "top_bottom_split",
        ],
    },
    "hook": {
        "values": [
            "merge_upgrade", "reward_reveal", "character_action", "before_after",
            "level_challenge", "collection_showcase",
        ],
    },
}

# === 四种预设变异策略 ===
# 每种策略定义: 保留哪些维度 (preserve), 变异哪些维度 (mutate)
VARIANT_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "A": {
        "name": "Style Variant",
        "description": "保留 gameplay+reward, 变异 background/character/camera/lighting/color",
        "preserve": ["gameplay", "reward", "hook", "layout"],
        "mutate": ["style", "composition"],
        "strategy_label": "视觉风格探索",
        "expected_advantage": "测试不同视觉风格对 CTR 的影响",
    },
    "B": {
        "name": "Reward Variant",
        "description": "保留 composition+hook, 变异 reward type/elements",
        "preserve": ["composition", "hook", "gameplay", "layout"],
        "mutate": ["reward", "style"],
        "strategy_label": "奖励元素探索",
        "expected_advantage": "测试不同奖励展示对转化率的影响",
    },
    "C": {
        "name": "Gameplay Variant",
        "description": "保留 reward, 变异 gameplay elements/objects",
        "preserve": ["reward", "hook", "layout"],
        "mutate": ["gameplay", "style", "composition"],
        "strategy_label": "玩法呈现探索",
        "expected_advantage": "测试不同玩法展示对 IPM 的影响",
    },
    "D": {
        "name": "Layout Variant",
        "description": "保留 style+gameplay, 重排 composition ratio/layout",
        "preserve": ["style", "gameplay", "hook"],
        "mutate": ["composition", "layout", "reward"],
        "strategy_label": "构图布局探索",
        "expected_advantage": "测试不同构图比例对视觉层次的影响",
    },
}
