"""Pattern Lock — 锁定 Character Reveal 赢家结构。

唯一目标：将 Character Reveal (ROAS 1.01) 的结构参数完全锁定，
变体只能改视觉风格，不能改结构逻辑。

锁定维度：
  hook_type:  shock reveal (不可变)
  narrative:  identity reinforcement loop (不可变)
  visual:     character dominant 60%+ (不可变)
  duration:   31s ±5s (微调范围)
  trigger:    identity reinforcement (不可变)
  anti:       character static >2s, slow intro (不可变)

用法：
  from engine.pattern_lock import LOCKED_CARD, validate_variant
  errors = validate_variant(my_card)  # 返回违反的结构规则
"""
from __future__ import annotations
from typing import Any

# ═══════════════════════════════════════════════════════════
# 锁定结构 (IMMUTABLE)
# ═══════════════════════════════════════════════════════════

LOCKED_CARD = {
    "cluster_id": "C09",
    "archetype": "Character Reveal",
    "winning_direction": (
        "Create a 31s character-centric video that opens with a striking "
        "character using a 'shock reveal' hook, triggering identity reinforcement."
    ),
    "hook_direction": {
        "hook_type": "shock reveal",
        "alt_hook_type": "curiosity gap",
        "duration": "0-3 seconds",
        "execution": (
            "Introduce a visually striking character in frame 1. "
            "Let the character make eye contact or perform a surprising action within 1 second."
        ),
    },
    "narrative_structure": {
        "narrative_type": "story-driven",
        "flow": "Hero introduction → Challenge → Power-up → Victory glimpse",
    },
    "visual_language": {
        "motion_intensity": "medium-slow",
        "cut_frequency": "3-5 cuts per 15s",
        "ui_overlay_density": "low",
        "framing": "9:16, character centered, 60%+ frame fill",
        "notes": "Use rack focus or slow zoom. Background blurred. Character in sharp focus.",
    },
    "cognitive_trigger": {
        "primary": "identity reinforcement",
        "secondary": "curiosity gap",
        "mechanism": "Viewer projects self onto the character. 'I want to be that hero.'",
    },
    "anti_patterns": [
        "Do NOT use generic stock character art",
        "Do NOT keep character static for more than 2 seconds",
        "Do NOT show character smaller than 40% of frame",
    ],
    "expected_performance": {
        "ctr_uplift_estimate": "+40-60% above baseline",
        "cvr_uplift_estimate": "+20-35%",
        "confidence": "high",
    },
    "constraints": {
        "duration_range": "26-36s",
        "hook_first_frame_required": True,
        "character_min_frame_pct": 60,
        "max_static_time_seconds": 2,
        "no_logo_intro": True,
        "no_slow_fade_in": True,
        "ui_feedback_immediate": True,
    },
}


# ═══════════════════════════════════════════════════════════
# 变体规则 — 只允许修改视觉风格
# ═══════════════════════════════════════════════════════════

VARIANTS = {
    "v1_dark_fantasy": {
        "style": "dark fantasy",
        "ai_prompt_suffix": (
            "dark fantasy art style, grim atmosphere, deep shadows, "
            "moody lighting, magical particles, epic scale, 9:16"
        ),
        "color_palette": "dark purple, black, gold accent",
        "mood": "epic, mysterious, powerful",
    },
    "v2_anime": {
        "style": "anime",
        "ai_prompt_suffix": (
            "anime art style, cel-shaded, vibrant colors, expressive eyes, "
            "dynamic action lines, Japanese animation aesthetic, 9:16"
        ),
        "color_palette": "bright blue, pink, white",
        "mood": "energetic, emotional, inspiring",
    },
    "v3_sci_fi": {
        "style": "sci-fi UI heavy",
        "ai_prompt_suffix": (
            "sci-fi futuristic style, holographic UI overlays, neon lighting, "
            "cyberpunk aesthetic, HUD elements, tech interface, 9:16"
        ),
        "color_palette": "cyan, magenta, dark grey",
        "mood": "futuristic, high-tech, fast-paced",
    },
    "v4_hyper_realistic": {
        "style": "hyper-realistic",
        "ai_prompt_suffix": (
            "hyper-realistic 3D render style, photorealistic textures, "
            "real-time rendering, Unreal Engine 5 quality, detailed skin, "
            "natural lighting, 9:16"
        ),
        "color_palette": "natural, warm tones, soft shadows",
        "mood": "immersive, believable, premium",
    },
    "v5_minimalist": {
        "style": "minimalist UI focus",
        "ai_prompt_suffix": (
            "minimalist flat design style, clean UI, pastel colors, "
            "simple shapes, elegant typography, white space focus, 9:16"
        ),
        "color_palette": "white, pastel blue, soft coral",
        "mood": "clean, modern, accessible",
    },
}


# ═══════════════════════════════════════════════════════════
# 验证函数
# ═══════════════════════════════════════════════════════════

VALIDATION_RULES = {
    "hook_type": {
        "expected": "shock reveal",
        "severity": "critical",
        "message": "Hook type must be 'shock reveal'. Cannot change hook logic.",
    },
    "cognitive_trigger_primary": {
        "expected": "identity reinforcement",
        "severity": "critical",
        "message": "Primary trigger must be 'identity reinforcement'.",
    },
    "character_min_frame_pct": {
        "expected": 60,
        "severity": "warning",
        "message": "Character must occupy ≥60% of frame.",
    },
    "no_logo_intro": {
        "expected": True,
        "severity": "critical",
        "message": "No logo intro allowed.",
    },
}


def validate_variant(card: dict) -> list[dict]:
    """Validate a Direction Card against locked structure.

    Returns:
        list of violations: [{field, severity, message}, ...]
    """
    violations = []

    hook = card.get("hook_direction", {})
    if hook.get("hook_type") != "shock reveal":
        violations.append({
            "field": "hook_type",
            "severity": "critical",
            "message": "Hook type must be 'shock reveal'. Cannot change hook logic.",
        })

    trigger = card.get("cognitive_trigger", {})
    if trigger.get("primary") != "identity reinforcement":
        violations.append({
            "field": "cognitive_trigger_primary",
            "severity": "critical",
            "message": "Primary trigger must be 'identity reinforcement'.",
        })

    visual = card.get("visual_language", {})
    framing = visual.get("framing", "")
    if "60%" not in framing and "60" not in framing:
        violations.append({
            "field": "character_min_frame_pct",
            "severity": "warning",
            "message": "Character must occupy ≥60% of frame.",
        })

    anti = card.get("anti_patterns", [])
    anti_text = " ".join(anti).lower()
    if "logo" in anti_text:
        violations.append({
            "field": "no_logo_intro",
            "severity": "critical",
            "message": "No logo intro allowed.",
        })

    return violations


def generate_locked_card(variant_key: str = "v1_dark_fantasy") -> dict:
    """Generate Character Reveal Direction Card with variant visual style.

    Structure is fully locked. Only visual style references change.
    """
    variant = VARIANTS.get(variant_key, VARIANTS["v1_dark_fantasy"])

    card = {
        "cluster_id": "C09",
        "archetype": "Character Reveal",
        "variant": variant_key,
        "variant_style": variant["style"],
        "winning_direction": LOCKED_CARD["winning_direction"],
        "hook_direction": dict(LOCKED_CARD["hook_direction"]),
        "narrative_structure": dict(LOCKED_CARD["narrative_structure"]),
        "visual_language": dict(LOCKED_CARD["visual_language"]),
        "cognitive_trigger": dict(LOCKED_CARD["cognitive_trigger"]),
        "anti_patterns": list(LOCKED_CARD["anti_patterns"]),
        "expected_performance": dict(LOCKED_CARD["expected_performance"]),
        "constraints": dict(LOCKED_CARD["constraints"]),
        "variant_styling": {
            "style": variant["style"],
            "color_palette": variant["color_palette"],
            "mood": variant["mood"],
            "ai_prompt_suffix": variant["ai_prompt_suffix"],
        },
    }

    return card


def list_variants() -> list[dict]:
    """List available variants with metadata."""
    return [
        {"key": k, "style": v["style"], "mood": v["mood"]}
        for k, v in VARIANTS.items()
    ]
