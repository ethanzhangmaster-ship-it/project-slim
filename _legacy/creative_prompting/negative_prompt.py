"""Phase 2.1.6.1 — Hard Negative Constraint（文字 / Logo / UI 幻觉防护）。

这是「Visual Asset Only」策略的核心：生成模型只出美术，所有文字 / Logo /
UI / CTA 后续由专业广告后期叠加。严格禁止模型自己画任何文字或界面元素，
从源头消灭 Fake Text / Fake Logo / Fake Button / Fake UI 类投放违规。
"""
from __future__ import annotations

# 绝对禁止生成的元素（投放违规雷区）
HARD_NEGATIVE: str = (
    "DO NOT generate any of the following: "
    "text, logo, brand name, button, CTA, fake UI, watermark, "
    "numbers, letters, words, sentences, runes, glyphs, magical symbols, "
    "inscriptions, writing, alphabet, characters, text-like patterns, "
    "frames, borders, outlines, rounded rectangles, panels, cards, "
    "empty banners, UI-like shapes, or any marks that resemble letters or "
    "words on objects, characters, items, eggs, rewards, or backgrounds."
)

# 禁止的「非广告」画风（避免生成电影海报 / 立绘 / 壁纸 / 概念图）
REJECT_STYLES: str = (
    "Do NOT produce a movie poster, book cover, character portrait, "
    "wallpaper, or concept art. This is a UA gameplay advertisement asset, "
    "not illustration art."
)

# 组合后的完整负面约束块
FULL_NEGATIVE: str = HARD_NEGATIVE + "\n\n" + REJECT_STYLES


def build_negative() -> str:
    """返回可直接拼进 Prompt 的完整负面约束文本。"""
    return FULL_NEGATIVE
