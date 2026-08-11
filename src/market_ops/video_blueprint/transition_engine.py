"""Transition Engine - 转场引擎

统一转场。
支持: Cut / Flash / Whip / Blur / Zoom / Match Cut / Shake / Fade

根据 Hook / Platform / Placement 自动推荐。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TransitionProfile:
    """转场配置"""
    variant_id: str
    transitions: list[dict[str, Any]] = field(default_factory=list)
    recommended: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "transitions": self.transitions,
            "recommended": self.recommended,
        }


class TransitionEngine:
    """转场引擎"""

    TRANSITIONS: dict[str, dict[str, str]] = {
        "cut": {"name": "Cut", "duration": "0s"},
        "flash": {"name": "Flash", "duration": "0.1s"},
        "whip": {"name": "Whip", "duration": "0.1s"},
        "blur": {"name": "Blur", "duration": "0.2s"},
        "zoom": {"name": "Zoom", "duration": "0.2s"},
        "match_cut": {"name": "Match Cut", "duration": "0.2s"},
        "shake": {"name": "Shake", "duration": "0.1s"},
        "fade": {"name": "Fade", "duration": "0.3s"},
    }

    HOOK_TRANS: dict[str, list[str]] = {
        "Collection": ["cut", "cut", "cut"],
        "Transformation": ["zoom", "flash", "cut"],
        "Boss": ["shake", "flash", "cut"],
        "Story": ["blur", "cut", "fade"],
        "Discovery": ["zoom", "flash", "cut"],
        "Surprise": ["flash", "cut", "cut"],
    }

    PLACEMENT_TRANS: dict[str, list[str]] = {
        "reels": ["cut", "whip", "flash"],
        "feed": ["cut", "blur", "fade"],
        "story": ["cut", "flash", "zoom"],
        "display": ["cut", "fade", "match_cut"],
    }

    def generate(self, dna: VideoDNA) -> TransitionProfile:
        """根据 Video DNA 生成转场配置"""
        hook_trans = self.HOOK_TRANS.get(dna.hook, self.HOOK_TRANS["Collection"])
        placement = dna.placement
        place_trans = self.PLACEMENT_TRANS.get(placement, self.PLACEMENT_TRANS["reels"])

        all_trans = list(dict.fromkeys([*hook_trans, *place_trans]))[:5]
        transitions = []
        for name in all_trans:
            info = self.TRANSITIONS.get(name, {})
            transitions.append({
                "name": info.get("name", name),
                "duration": info.get("duration", "0s"),
            })

        return TransitionProfile(
            variant_id=dna.variant_id,
            transitions=transitions,
            recommended=[t["name"] for t in transitions],
        )
