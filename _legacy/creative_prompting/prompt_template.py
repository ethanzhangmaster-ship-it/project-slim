"""Phase 2.1.6.1 — Hardened Prompt Template（生成端）。

将「游戏玩法模式 + 约束块」组装成可直接喂给 Lovart 等图像生成模型的
强化 Prompt。核心升级：从「生成一张像 winner 的图」变为
「生成一张可投放的广告视觉资产」——强制 Visual Asset Only + 4 模式构图
+ 广告三段式结构 + 硬负面约束（灭文字/Logo/UI 幻觉）。
"""
from __future__ import annotations

from creative_prompting.constraint_builder import build_constraints
from creative_prompting.gameplay_pattern import (
    GameplayPattern,
    pattern_label,
    pattern_requirement,
)

# 主模板。{game} / {pattern} / {pattern_requirement} / {constraints} 由 build_prompt 填充。
TEMPLATE: str = """Create a premium mobile game UA creative visual.

Game: {game}

Gameplay pattern: {pattern}

The image must communicate the gameplay within 3 seconds.

Required visual:
{pattern_requirement}

Character:
A witch character as a supporting host, not a portrait. Main focus is the gameplay action and the reward.

Style:
High-end 3D mobile game advertisement, App Store quality, colorful fantasy lighting.

Composition: Square 1:1 format. Only generate artwork.

{constraints}
"""


def build_prompt(
    game: str,
    pattern: GameplayPattern,
    extra: str = "",
) -> str:
    """组装一张创意的完整强化 Prompt。

    game   : 游戏描述（如 "Merge Witches style fantasy merge game"）
    pattern: GameplayPattern 枚举
    extra  : 可选追加约束（如特定物体 / 色调要求）
    """
    prompt = TEMPLATE.format(
        game=game,
        pattern=pattern_label(pattern),
        pattern_requirement=pattern_requirement(pattern),
        constraints=build_constraints(),
    )
    if extra:
        prompt = prompt.rstrip() + "\n\n" + extra
    return prompt


# 便捷：按 3 张 v3 验证图对应的模式批量出 Prompt
DEFAULT_GAME = "Merge Witches style fantasy merge game"

V3_PROMPT_PLAN: list[tuple[str, GameplayPattern]] = [
    ("creative_001", GameplayPattern.MERGE),
    ("creative_002", GameplayPattern.EVOLUTION),
    ("creative_003", GameplayPattern.MERGE),
]


def build_v3_prompts() -> dict[str, str]:
    """返回 3 张验证图各自对应的强化 Prompt（证明 Prompt Hardening 可用）。"""
    return {
        cid: build_prompt(DEFAULT_GAME, pat) for cid, pat in V3_PROMPT_PLAN
    }
