"""Winning Structure Generator — 从 Policy Set 生成最优视频结构。

输入: Policy Set (P1-P5)
输出: 完整的视频结构方案，包含:
  - Hook (0-1s): 视觉规则 + 运动规则 + 构图规则
  - Comprehension (1-3s): 解释逻辑 + 视觉过渡
  - Engagement (3-6s): 互动/玩法/叙事转移
  - Reward (6s+): 奖励事件
  - Frame Blueprint: 逐帧制作指令

不使用 archetype/pattern/abstract labels。
"""
from __future__ import annotations
from typing import Dict, List, Optional


def generate_winning_structure(policy_set: List[Dict]) -> Dict:
    """基于 Policy Set 生成最优视频结构方案。

    Args:
        policy_set: get_policy_set() 的输出

    Returns:
        {
            "winning_structure": {
                "hook_0_1s": "...",
                "0_3s_motion_pattern": "...",
                "3_6s_narrative": "...",
                "reward_event": "...",
                "first_frame_spec": {...},
            },
            "frame_blueprint": [
                {"time": "0-1s", "instruction": "..."},
                ...
            ],
            "production_rules": ["..."],
        }
    """
    # ── Extract thresholds from policies ──
    p_subject = _find_policy(policy_set, "subject_presence_score")
    p_contrast = _find_policy(policy_set, "first_frame_contrast")
    p_motion = _find_policy(policy_set, "motion_change_0_3s")
    p_reward = _find_policy(policy_set, "reward_visual_surge")
    p_text = _find_policy(policy_set, "text_density_0_3s")

    # ── Build winning structure ──
    structure = {
        "hook_0_1s": (
            "High-contrast subject revealed in center 40% of frame. "
            "Single focal point, no text, no UI. "
            "Contrast >= 0.15. Subject fills >= 30% of frame area."
        ),
        "hook_visual": (
            "Center-framed character/subject with spotlight effect. "
            "Background darkened (vignette 30%). "
            "Subject edge sharp. High saturation on subject."
        ),
        "first_frame_spec": {
            "contrast_min": 0.15,
            "subject_presence_min": 0.15,
            "text_density_max": 0.04,
            "framing": "subject centered, 30%+ frame fill",
            "lighting": "spotlight on subject, background dark",
        },
        "0_3s_motion_pattern": (
            "Between 0.8s and 3.0s: at least one structural visual change. "
            "Change types: subject movement, scene cut, UI reveal, or zoom-in. "
            "Camera-only movement does not count. "
            "motion_change_0_3s must exceed 0.10."
        ),
        "3_6s_engagement": (
            "After the hook transition, show the core value proposition: "
            "gameplay loop, app feature, or interaction demo. "
            "Minimize text overlay. Let visuals communicate. "
            "Keep UI density low (text_density < 0.06)."
        ),
        "reward_event": (
            "After 6 seconds: introduce a new visual state that is "
            "measurably brighter and more saturated than the middle section. "
            "reward_visual_surge must exceed 0.05. "
            "Types: victory screen, level up animation, collection reveal, "
            "progress completion, premium item showcase."
        ),
    }

    # ── Frame blueprint (逐帧制作指令) ──
    blueprint = [
        {
            "time": "0-0.8s",
            "category": "hook",
            "instruction": "高对比度主体在画面中心出现。背景压暗 30%。无文字、无 UI。主体占画面至少 30%。",
            "ae_instruction": "放置角色/主体在画面中心, 使用径向渐变 spotlight 效果。背景添加 vignette 遮罩(60%透明度)。主体使用锐化滤镜。",
            "policy_ref": "P1+P2",
            "verification": "subject_presence_score >= 0.15, first_frame_contrast >= 0.15",
        },
        {
            "time": "0.8-3s",
            "category": "motion",
            "instruction": "画面结构变化: 主体移动、场景切换、或 UI 元素出现。至少 1 次可测量的结构变化。",
            "ae_instruction": "添加关键帧动画: 主体从中心移动/缩放。或 scene cut 到第二个画面。或 UI 元素从底部弹出。不允许仅 camera pan。",
            "policy_ref": "P3+P5",
            "verification": "motion_change_0_3s >= 0.10, text_density_0_3s <= 0.06",
        },
        {
            "time": "3-6s",
            "category": "engagement",
            "instruction": "展示核心价值: 玩法循环、App 功能、或交互演示。UI 密度低(文字覆盖 < 6%)。",
            "ae_instruction": "展示游戏玩法或 App 核心功能。使用图标替代文字说明。保持视觉清晰简洁。",
            "policy_ref": "P5",
            "verification": "text_density_0_3s <= 0.06",
        },
        {
            "time": "6-9s",
            "category": "reward",
            "instruction": "视觉奖励事件: 新的视觉状态(更亮、更饱和)。亮度+饱和度提升 measurable。",
            "ae_instruction": "安排奖励动画: 胜利画面/升级/收集展示。增加亮度 30%, 饱和度 20%, 粒子效果。",
            "policy_ref": "P4",
            "verification": "reward_visual_surge >= 0.05",
        },
        {
            "time": "9s-end",
            "category": "cta",
            "instruction": "CTA + 社交证明。保持与 reward 状态一致的视觉质量。",
            "ae_instruction": "CTA 按钮脉冲动画。社交证明(评分/用户数)文字从底部滑入。按钮使用高对比色。",
            "policy_ref": "P4",
            "verification": "保持 reward_visual_surge >= 0.05",
        },
    ]

    # ── Production rules ──
    production_rules = [
        p_subject["rule"] if p_subject else "",
        p_contrast["rule"] if p_contrast else "",
        p_motion["rule"] if p_motion else "",
        p_reward["rule"] if p_reward else "",
        p_text["rule"] if p_text else "",
        "NO logo/branding in first 3 seconds",
        "NO slow fade-in; first frame must be immediate",
        "Total duration: 15-40s recommended",
        "Aspect ratio: 9:16 (vertical) required",
    ]
    production_rules = [r for r in production_rules if r]

    # ── Anti-patterns (from all policies) ──
    all_anti = []
    for p in policy_set:
        all_anti.extend(p.get("anti_pattern", []))
    all_anti = list(set(all_anti))

    return {
        "winning_structure": structure,
        "frame_blueprint": blueprint,
        "production_rules": production_rules,
        "anti_patterns": all_anti,
    }


def _find_policy(policy_set: List[Dict], causal_var: str) -> Optional[Dict]:
    for p in policy_set:
        if p.get("causal_variable") == causal_var:
            return p
    return None
