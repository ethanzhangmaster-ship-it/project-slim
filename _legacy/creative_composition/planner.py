"""Phase 2.1.6.2 — Composition Planner。

把「Winner DNA + 玩法模式 + 物体选择」翻译成一套广告版式规划
（CreativeComposition），再据此生成强约束生成 Prompt。

升级点（对比 2.1.6.1 的 prompt_template）：
  - 不再让 AI 自由决定构图，而是系统先决定 layout / 元素位置 / 焦点优先级
  - Prompt 明确写出 Before / Action / Reward 三段，强制 Facebook UA 广告结构
  - 角色约束 + 玩法锚点自动注入

最终 Prompt 形状见 PRD §7。
"""
from __future__ import annotations

from pathlib import Path

import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from creative_prompting.constraint_builder import build_constraints
from creative_prompting.gameplay_pattern import GameplayPattern, pattern_label
from creative_composition.models import CreativeComposition, CompositionElement
from creative_composition.layout_templates import get_layout, layout_for_pattern
from creative_composition.constraint_engine import (
    character_scale_limit,
    build_character_constraint,
    build_gameplay_anchor,
    FOCUS_WEIGHTS,
)

DEFAULT_GAME = "Merge Witches style fantasy merge game"

# PRD §7 升级后的 Prompt 主模板
TEMPLATE: str = """Create a Facebook mobile game advertising creative.

Composition:
{layout_label}

Main visual:
{gameplay_elements}

Before state:
{before}

Action:
{action}

Reward:
{after}

Character:
secondary supporting role.

The gameplay mechanic must be understood within 3 seconds.

Generate artwork only.
No text.
No logo.
No UI.
"""


class CompositionPlanner:
    """给定玩法模式与物体，产出 CreativeComposition（含最终 Prompt）。"""

    def plan(
        self,
        creative_id: str,
        pattern: GameplayPattern,
        before_object: str,
        after_object: str,
        character: str = "witch",
        game: str = DEFAULT_GAME,
        extra: str = "",
    ) -> CreativeComposition:
        layout_type = layout_for_pattern(pattern)
        lay = get_layout(layout_type)
        pt = pattern.value

        elements = self._build_elements(pattern, before_object, after_object, character)

        comp = CreativeComposition(
            creative_id=creative_id,
            format="square",
            layout_type=layout_type,
            pattern=pt,
            focus_order=list(lay["focus_order"]),
            elements=elements,
            weights=dict(FOCUS_WEIGHTS),
            constraints=character_scale_limit(pt),
            game=game,
        )
        comp.prompt = self.build_prompt(comp, before_object, after_object, character, extra)
        return comp

    @staticmethod
    def _build_elements(pattern: GameplayPattern, before_object: str, after_object: str, character: str) -> dict:
        pt = pattern.value
        if pt == "merge":
            return {
                "before_state": CompositionElement("before_state", object=before_object, position="left", scale=0.25),
                "action": CompositionElement("action", type="merge", position="center"),
                "after_state": CompositionElement("after_state", object=after_object, position="right", scale=0.35),
                "character": CompositionElement("character", object=character, role="host", position="background_side", scale=0.25),
            }
        if pt == "evolution":
            return {
                "before_state": CompositionElement("before_state", object=before_object, position="left", scale=0.25),
                "action": CompositionElement("action", type="evolution", position="center"),
                "after_state": CompositionElement("after_state", object=after_object, position="right", scale=0.35),
                "character": CompositionElement("character", object=character, role="host", position="background_side", scale=0.25),
            }
        if pt == "collection":
            return {
                "before_state": CompositionElement("before_state", object=before_object, position="left", scale=0.30),
                "action": CompositionElement("action", type="collection", position="center"),
                "after_state": CompositionElement("after_state", object=after_object, position="center_right", scale=0.40),
                "character": CompositionElement("character", object=character, role="host", position="background_side", scale=0.20),
            }
        # reward_reveal / surprise_reveal
        return {
            "before_state": CompositionElement("before_state", object=before_object, position="left", scale=0.25),
            "action": CompositionElement("action", type="reveal", position="center"),
            "after_state": CompositionElement("after_state", object=after_object, position="center_right", scale=0.40),
            "character": CompositionElement("character", object=character, role="host", position="background_side", scale=0.20),
        }

    def build_prompt(
        self,
        comp: CreativeComposition,
        before_object: str,
        after_object: str,
        character: str,
        extra: str = "",
    ) -> str:
        lay = get_layout(comp.layout_type)
        gameplay_elements = build_gameplay_anchor(comp.pattern)
        character_text = build_character_constraint(comp.pattern)

        prompt = TEMPLATE.format(
            layout_label=lay["label"],
            gameplay_elements=gameplay_elements,
            before=before_object,
            action=lay["action_phrase"],
            after=after_object,
        )
        # 角色约束 + Visual Asset Only + 硬负面（复用已验证的硬化约束块）
        prompt = prompt.rstrip() + "\n\n" + character_text + "\n\n" + build_constraints()
        if extra:
            prompt = prompt.rstrip() + "\n\n" + extra
        return prompt
