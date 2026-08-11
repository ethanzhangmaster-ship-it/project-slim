"""Phase 2.1.6.2 — Creative Composition 数据结构。

CreativeComposition 描述「系统替 AI 决定的广告版式规划」：
  - 用哪种 Facebook 常用 layout
  - 画面里有什么元素、各自位置 / 占比
  - 焦点优先级（谁最大、谁其次）
  - 约束（角色不能抢主体、必须出现 merge 锚点等）

这是「广告构图决策」与「AI 渲染」之间的契约：AI 只负责按此版式出图。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class CompositionElement:
    """版式中的一个元素（before / action / after / character / environment）。"""

    kind: str                                   # before_state / action / after_state / character / environment
    object: str = ""                            # 物体描述（如 "dragon egg"）
    position: str = ""                          # left / center / right / background_side / center_right
    scale: float = 0.0                          # 相对占比 0-1
    role: str = ""                              # host / subject
    type: str = ""                              # merge / evolution / collection / reveal

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CreativeComposition:
    """单张创意的完整版式规划。"""

    creative_id: str
    format: str = "square"                       # square / portrait / landscape
    layout_type: str = ""                        # merge_before_after / evolution_upgrade / ...
    pattern: str = ""                            # merge / evolution / collection / reward_reveal
    focus_order: list = field(default_factory=list)        # 焦点优先级列表
    elements: dict = field(default_factory=dict)           # kind -> CompositionElement(dict)
    weights: dict = field(default_factory=dict)           # 焦点权重（focus priority engine）
    constraints: dict = field(default_factory=dict)       # character_scale_limit 等
    game: str = ""
    prompt: str = ""                                       # 由 planner 生成的最终 Prompt

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # elements 内可能是 CompositionElement 或 dict，统一成 dict
        out = {}
        for k, v in self.elements.items():
            out[k] = v.to_dict() if isinstance(v, CompositionElement) else v
        d["elements"] = out
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CreativeComposition":
        elems = {}
        for k, v in d.get("elements", {}).items():
            if isinstance(v, dict):
                elems[k] = CompositionElement(**v)
            else:
                elems[k] = v
        known = {kk: vv for kk, vv in d.items() if kk != "elements"}
        return cls(elements=elems, **known)
