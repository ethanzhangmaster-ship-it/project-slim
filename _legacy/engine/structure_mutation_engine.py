"""Structure Mutation Engine — 生成视频结构改动候选。

输入：video_features (25维帧级特征)
输出：mutation_candidates [{name, feature, direction, magnitude, description}, ...]

Mutation 类型:
  - 增大 hook 对比度/边缘密度/饱和度
  - 减少 mid 段文字密度/熵
  - 增加帧间 delta（运动感）
  - 增加 late 段亮度/饱和度

每个 mutation 包含:
  - 改哪个 feature
  - 改多少（百分比）
  - 改完后的预期 feature 值
  - 人类可读的描述
"""
from __future__ import annotations
from typing import List, Dict, Optional, Tuple
import numpy as np


# ═══════════════════════════════════════════════════════════
# Mutation Definitions
# ═══════════════════════════════════════════════════════════

MUTATION_TEMPLATES = [
    # ── Hook (0-3s) mutations ──
    {
        "name": "increase_hook_contrast",
        "feature": "hook_contrast",
        "direction": "increase",
        "magnitude": 0.20,
        "time_window": "0-1s",
        "dimension": "hook",
        "description": "Increase first-frame contrast by 20% — sharper visual, stronger attention grab",
        "ae_instruction": "调整第一帧对比度 +20%: 提高阴影深度, 增强高光亮度, 使用曲线工具增加 S-curve",
    },
    {
        "name": "increase_hook_edge_density",
        "feature": "hook_edge_density",
        "direction": "increase",
        "magnitude": 0.25,
        "time_window": "0-1s",
        "dimension": "hook",
        "description": "Increase first-frame edge density by 25% — more visual detail, higher perceived quality",
        "ae_instruction": "增加第一帧细节密度 +25%: 使用锐化滤镜, 增加纹理层, 确保角色轮廓清晰",
    },
    {
        "name": "increase_hook_saturation",
        "feature": "hook_saturation",
        "direction": "increase",
        "magnitude": 0.20,
        "time_window": "0-1s",
        "dimension": "hook",
        "description": "Increase first-frame saturation by 20% — more vibrant colors, higher emotional arousal",
        "ae_instruction": "提升第一帧饱和度 +20%: 增加颜色 vibrance, 保持肤色自然, 背景可更饱和",
    },
    {
        "name": "increase_hook_center_contrast",
        "feature": "hook_center_contrast",
        "direction": "increase",
        "magnitude": 0.30,
        "time_window": "0-1s",
        "dimension": "hook",
        "description": "Increase center-subject contrast by 30% — stronger focal point, clear visual hierarchy",
        "ae_instruction": "增强画面中心对比度 +30%: 角色/主体加 spotlight 效果, 背景压暗, 使用径向渐变遮罩",
    },
    {
        "name": "reduce_hook_text_density",
        "feature": "hook_text_density",
        "direction": "decrease",
        "magnitude": 0.30,
        "time_window": "0-1s",
        "dimension": "hook",
        "description": "Reduce first-frame text by 30% — lower cognitive load, let visual hook breathe",
        "ae_instruction": "减少第一帧文字量 30%: 删除非关键文字, 或将文字移到 1.5s 后出现, 保留纯视觉冲击",
    },

    # ── Mid (3-8s) mutations ──
    {
        "name": "reduce_mid_text_density",
        "feature": "mid_text_density",
        "direction": "decrease",
        "magnitude": 0.25,
        "time_window": "3-8s",
        "dimension": "comprehension",
        "description": "Reduce mid-video text density by 25% — cleaner UI, better gameplay comprehension",
        "ae_instruction": "减少中段文字/UI密度 25%: 移除冗余 UI 标签, 合并信息展示, 使用图标替代文字",
    },
    {
        "name": "reduce_mid_edge_density",
        "feature": "mid_edge_density",
        "direction": "decrease",
        "magnitude": 0.15,
        "time_window": "3-8s",
        "dimension": "comprehension",
        "description": "Reduce mid-video visual complexity by 15% — less clutter, clearer gameplay signal",
        "ae_instruction": "降低中段视觉复杂度 15%: 简化背景细节, 突出核心玩法元素, 使用景深模糊",
    },
    {
        "name": "increase_mid_saturation",
        "feature": "mid_saturation",
        "direction": "increase",
        "magnitude": 0.15,
        "time_window": "3-8s",
        "dimension": "comprehension",
        "description": "Increase mid-video saturation by 15% — more engaging mid-section, better retention",
        "ae_instruction": "提升中段饱和度 15%: 游戏玩法区域颜色增强, 高亮交互元素",
    },
    {
        "name": "increase_mid_center_contrast",
        "feature": "mid_center_contrast",
        "direction": "increase",
        "magnitude": 0.20,
        "time_window": "3-8s",
        "dimension": "comprehension",
        "description": "Increase mid-video center contrast — clearer gameplay focus, better understanding",
        "ae_instruction": "增强中段中心对比度 20%: 游戏核心操作区域加亮, 周边 UI 半透明化",
    },

    # ── Late (8s+) mutations ──
    {
        "name": "increase_late_brightness",
        "feature": "late_brightness",
        "direction": "increase",
        "magnitude": 0.25,
        "time_window": "8s+",
        "dimension": "reward",
        "description": "Increase late-video brightness by 25% — stronger reward signal, better conversion",
        "ae_instruction": "提升结尾画面亮度 25%: 胜利/升级/收集画面使用高光效果, 加 lens flare 或 glow",
    },
    {
        "name": "increase_late_saturation",
        "feature": "late_saturation",
        "direction": "increase",
        "magnitude": 0.20,
        "time_window": "8s+",
        "dimension": "reward",
        "description": "Increase late-video saturation by 20% — more vibrant reward, higher emotional payoff",
        "ae_instruction": "提升结尾饱和度 20%: 奖励元素颜色增强, CTA 按钮使用高对比色",
    },
    {
        "name": "increase_late_entropy",
        "feature": "late_entropy",
        "direction": "increase",
        "magnitude": 0.15,
        "time_window": "8s+",
        "dimension": "reward",
        "description": "Increase late-video visual richness by 15% — more engaging reward scene",
        "ae_instruction": "增加结尾画面视觉丰富度 15%: 添加粒子/闪烁/动画元素, 让奖励场景更丰富",
    },

    # ── Motion mutations ──
    {
        "name": "increase_motion_contrast_delta",
        "feature": "motion_contrast_delta",
        "direction": "increase",
        "magnitude": 0.30,
        "time_window": "full",
        "dimension": "motion",
        "description": "Increase contrast variation across video — more dynamic visual journey",
        "ae_instruction": "增加全程对比度变化幅度 30%: hook 用高对比, mid 过渡自然, reward 再回到高对比",
    },
    {
        "name": "increase_motion_entropy_delta",
        "feature": "motion_entropy_delta",
        "direction": "increase",
        "magnitude": 0.25,
        "time_window": "full",
        "dimension": "motion",
        "description": "Increase visual entropy variation — stronger narrative arc, better retention",
        "ae_instruction": "增加视觉变化幅度 25%: hook 简洁, mid 丰富, reward 再次简洁形成对比节奏",
    },
]


def generate_mutations(features: Dict[str, float]) -> List[Dict]:
    """Generate mutation candidates for a video based on its current features.

    Args:
        features: 25-dim feature dict (output of feature_label_builder._extract_eagle_features)

    Returns:
        list of mutation dicts with current_value, target_value, delta
    """
    candidates = []
    for tmpl in MUTATION_TEMPLATES:
        feat_name = tmpl["feature"]
        current = features.get(feat_name, 0)

        if tmpl["direction"] == "increase":
            delta = current * tmpl["magnitude"]
            target = current + delta
        else:
            delta = current * tmpl["magnitude"]
            target = max(0, current - delta)

        candidates.append({
            "name": tmpl["name"],
            "feature": feat_name,
            "direction": tmpl["direction"],
            "magnitude": tmpl["magnitude"],
            "current_value": round(current, 4),
            "target_value": round(target, 4),
            "delta": round(delta, 4) if tmpl["direction"] == "increase" else round(-delta, 4),
            "time_window": tmpl["time_window"],
            "dimension": tmpl["dimension"],
            "description": tmpl["description"],
            "ae_instruction": tmpl["ae_instruction"],
        })

    return candidates


def apply_mutation(features: Dict[str, float], mutation: Dict) -> Dict[str, float]:
    """Apply a single mutation to feature vector and return modified features."""
    mutated = dict(features)
    feat = mutation["feature"]
    if feat in mutated:
        mutated[feat] = mutation["target_value"]
    return mutated
