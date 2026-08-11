"""Phase 2.1.6.1 — Gameplay Pattern Schema。

定义可投放广告视觉资产的 4 种核心玩法构图模式。
每种模式给出：
  - label     : 机器可读标识
  - requirement : 喂给 Prompt 的「构图硬性要求」文本
  - example    : 人类可读示例（用于校验/说明）

这 4 类覆盖了真实 Merge Witches winner 的主要胜出结构，
解决了旧流程「只认 Merge Board → Level/Collection/Reward 类型被误判」的问题。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List


class GameplayPattern(str, Enum):
    MERGE = "merge"
    EVOLUTION = "evolution"
    COLLECTION = "collection"
    REWARD_REVEAL = "reward_reveal"


# 每种模式的构图要求 + 示例。requirement 直接拼进生成 Prompt。
_PATTERNS: Dict[GameplayPattern, Dict[str, str]] = {
    GameplayPattern.MERGE: {
        "label": "MERGE",
        "requirement": (
            "Two identical plain items shown side by side, with a plus sign or arrow "
            "between them, combining into one higher-level reward. "
            "The items must be clean and unmarked: no runes, glyphs, writing, "
            "or text-like patterns on the objects. "
            "e.g. plain Dragon egg + plain Dragon egg -> Baby dragon."
        ),
        "example": "Dragon egg + Dragon egg -> Baby dragon",
    },
    GameplayPattern.EVOLUTION: {
        "label": "EVOLUTION",
        "requirement": (
            "A low-level character on one side transforming and leveling up into a "
            "powerful higher-level character on the other side, with an arrow showing "
            "the upgrade. e.g. Level 1 Witch -> MAX Witch Queen."
        ),
        "example": "Level 1 Witch -> MAX Witch Queen",
    },
    GameplayPattern.COLLECTION: {
        "label": "COLLECTION",
        "requirement": (
            "Multiple collectible items gathered together forming a collection or "
            "treasure hoard, hinting at a rare reward unlocked by collecting. "
            "e.g. many small items -> one rare glowing reward."
        ),
        "example": "Many small items -> one rare glowing reward",
    },
    GameplayPattern.REWARD_REVEAL: {
        "label": "REWARD_REVEAL",
        "requirement": (
            "A hidden reward being revealed with an excited emotional reaction, "
            "a big reveal moment of a legendary prize. "
            "e.g. chest opening -> legendary character emerges with awe."
        ),
        "example": "Chest opening -> legendary character revealed with awe",
    },
}


def get_pattern(p: GameplayPattern) -> Dict[str, str]:
    return _PATTERNS[p]


def all_patterns() -> List[GameplayPattern]:
    return list(_PATTERNS.keys())


def pattern_requirement(p: GameplayPattern) -> str:
    return _PATTERNS[p]["requirement"]


def pattern_label(p: GameplayPattern) -> str:
    return _PATTERNS[p]["label"]
