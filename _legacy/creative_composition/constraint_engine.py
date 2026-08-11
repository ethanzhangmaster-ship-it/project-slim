"""Phase 2.1.6.2 — Focus Priority Engine + Character Constraint + Gameplay Anchor。

解决 PRD 列出的两个问题：
  - 焦点优先级：禁止 character > gameplay（默认 gameplay 第一、character 末位）
  - 角色约束：解决「女巫抢主体」——merge 类角色 <=30%、不能在中心、不能遮挡玩法
  - 玩法锚点：merge 必须出现 A + 动作 + B + reward
"""
from __future__ import annotations

from typing import Dict

# 焦点优先级（PRD §4 默认顺序）
DEFAULT_FOCUS_ORDER: list[str] = [
    "gameplay_action",
    "reward",
    "progression",
    "character",
    "background",
]

# 焦点权重（合计 1.0）：Gameplay 40% / Reward 30% / Character 15% / Env 10% / Deco 5%
FOCUS_WEIGHTS: Dict[str, float] = {
    "gameplay_action": 0.40,
    "reward": 0.30,
    "character": 0.15,
    "environment": 0.10,
    "decoration": 0.05,
}


def character_scale_limit(gameplay_type: str) -> Dict:
    """角色占比限制（PRD §5）。

    merge 类严格：<=30%、不能在中心、不能遮挡玩法；
    其它模式略宽松（角色本身即玩法主体时，如 evolution）。
    """
    if gameplay_type == "merge":
        return {
            "character_size_max": 0.30,
            "character_not_center": True,
            "character_not_cover_gameplay": True,
        }
    return {
        "character_size_max": 0.45,
        "character_not_center": False,
        "character_not_cover_gameplay": False,
    }


def build_character_constraint(gameplay_type: str) -> str:
    """自动注入到生成 Prompt 的角色约束文本（PRD §5）。"""
    base = (
        "The character is a supporting host, not the main subject. "
        "Do not create a character portrait. "
        "The gameplay interaction must be the largest visual element."
    )
    if gameplay_type == "merge":
        base += (
            " The character must be small, positioned at the side or in the "
            "background, occupying no more than 30% of the frame and never "
            "covering the gameplay."
        )
    return base


def build_gameplay_anchor(gameplay_type: str) -> str:
    """玩法锚点文本（PRD §6）——保证画面里一定出现可识别的玩法动作。"""
    if gameplay_type == "merge":
        return (
            "Show a clear mobile merge gameplay moment. "
            "Two identical game objects combine into a higher-level reward. "
            "The merge interaction must be instantly understandable."
        )
    if gameplay_type == "evolution":
        return (
            "Show a clear character evolution moment. "
            "A low-level character transforms into a powerful higher-level character. "
            "The upgrade must be instantly understandable."
        )
    if gameplay_type == "collection":
        return (
            "Show a clear collection moment. "
            "Multiple collectible items gather into a rare reward. "
            "The collection must be instantly understandable."
        )
    return (
        "Show a clear reward reveal moment. "
        "A hidden reward is revealed with an emotional reaction. "
        "The reveal must be instantly understandable."
    )
