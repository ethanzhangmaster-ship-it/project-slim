"""Phase 2.1.6.2 — Facebook 常用广告版式模板（4 种）。

每种 layout 定义：
  - label          : 人类可读名
  - template_letter: PRD 中的 A/B/C/D
  - structure      : 版式文字描述
  - constraints    : 该版式的硬性构图约束
  - focus_order    : 默认焦点优先级
  - action_phrase  :喂给生成 Prompt 的「动作」描述
  - pattern        : 对应的 GameplayPattern

映射：pattern -> layout（同一玩法用哪种版式）。
"""
from __future__ import annotations

from typing import Dict, List

from creative_prompting.gameplay_pattern import GameplayPattern

LAYOUTS: Dict[str, Dict] = {
    "merge_before_after": {
        "label": "Merge Before / After",
        "template_letter": "A",
        "structure": (
            "Before (two identical items) on the left  ->  "
            "Action (merge) in the center  ->  "
            "After (higher-level reward) on the right. "
            "Character as a small host at the side."
        ),
        "constraints": {
            "gameplay_area_min": 0.50,
            "character_max": 0.30,
            "reward_largest": True,
        },
        "focus_order": ["gameplay_action", "reward", "progression", "character", "background"],
        "action_phrase": "Two identical items combine via a merge action into a higher-level reward.",
        "pattern": GameplayPattern.MERGE,
    },
    "evolution_upgrade": {
        "label": "Evolution Upgrade",
        "template_letter": "B",
        "structure": (
            "Low-level character on the left  ->  "
            "Transition (arrow / glow) in the center  ->  "
            "High-level character on the right. "
            "The character transformation IS the gameplay."
        ),
        "constraints": {
            "needs_low_state": True,
            "needs_transition": True,
            "needs_high_state": True,
        },
        "focus_order": ["progression", "reward", "gameplay_action", "character", "background"],
        "action_phrase": "A low-level character transforms and levels up into a powerful higher-level character.",
        "pattern": GameplayPattern.EVOLUTION,
    },
    "collection_reward": {
        "label": "Collection Reward",
        "template_letter": "C",
        "structure": (
            "Multiple collectible items gathered at the bottom-left  ->  "
            "Rare collection reward revealed at the center-right. "
            "Hint of a hoard / many items."
        ),
        "constraints": {
            "needs_multiple_items": True,
            "needs_rare_reward": True,
        },
        "focus_order": ["gameplay_action", "reward", "progression", "character", "background"],
        "action_phrase": "Multiple collectible items gather together into one rare glowing reward.",
        "pattern": GameplayPattern.COLLECTION,
    },
    "surprise_reveal": {
        "label": "Surprise Reveal",
        "template_letter": "D",
        "structure": (
            "Unknown / mystery object on the left  ->  "
            "Reveal moment in the center  ->  "
            "Rare reward with emotional reaction on the right."
        ),
        "constraints": {
            "needs_reveal": True,
            "needs_rare_reward": True,
        },
        "focus_order": ["reward", "gameplay_action", "progression", "character", "background"],
        "action_phrase": "A hidden reward is revealed with an excited reaction, a big reveal moment.",
        "pattern": GameplayPattern.REWARD_REVEAL,
    },
}

# pattern -> layout_type
PATTERN_TO_LAYOUT: Dict[GameplayPattern, str] = {v["pattern"]: k for k, v in LAYOUTS.items()}


def get_layout(layout_type: str) -> Dict:
    return LAYOUTS[layout_type]


def layout_for_pattern(pattern: GameplayPattern) -> str:
    return PATTERN_TO_LAYOUT[pattern]


def all_layouts() -> List[str]:
    return list(LAYOUTS.keys())
