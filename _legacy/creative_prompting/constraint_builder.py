"""Phase 2.1.6.1 — Constraint Builder（正向资产约束 + 广告结构约束 + 负面约束）。

把三类约束拼成一段稳定的「约束块」，供 prompt_template 注入：
  1. Visual Asset Only 正向约束（只出美术，文字/UI 后期加）
  2. 广告三段式结构约束（Top safe / Main gameplay / Reward reveal）
  3. Hard Negative（文字/Logo/UI 幻觉防护，来自 negative_prompt）
"""
from __future__ import annotations

from creative_prompting.negative_prompt import build_negative

# 正向：Visual Asset Only
ASSET_CONSTRAINT: str = (
    "Create a clean mobile game advertising visual asset. "
    "Focus only on the gameplay scene and visual composition. "
    "The final image will be edited later with professional advertising text and UI. "
    "Generate only the artwork. "
    "All elements must be organic game-world objects or characters, "
    "not interface shapes, frames, or banners."
)

# 广告结构三段式约束（防止生成海报 / 立绘 / 风景 / 伪 UI 框）
AD_STRUCTURE: str = (
    "Composition structure (top to bottom):\n"
    "  - Top safe area: completely empty, no text, no banner, no shape, no frame, no rounded rectangle.\n"
    "  - Main gameplay area: the core merge / evolution / collection / reward action.\n"
    "  - Reward reveal area: the upgraded reward shown clearly at the bottom, "
    "no frame, no border, no panel, no rounded rectangle around it.\n"
    "Square 1:1 format.\n"
    "No UI-like shapes anywhere in the image."
)


def build_constraints() -> str:
    """返回正向约束 + 结构约束 + 负面约束的组合块。"""
    return "\n\n".join([ASSET_CONSTRAINT, AD_STRUCTURE, build_negative()])
