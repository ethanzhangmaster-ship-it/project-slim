"""Hook Engine - Hook 引擎

分析和推荐视频 Hook 策略。

重点:
- 前三秒必须出现什么
- 情绪钩子
- 视觉钩子
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HookProfile:
    """Hook 配置"""
    variant_id: str
    hook_type: str
    emotion: str
    visual_hook: str
    action_hook: str
    text_hook: str
    first_three_seconds: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "hook_type": self.hook_type,
            "emotion": self.emotion,
            "visual_hook": self.visual_hook,
            "action_hook": self.action_hook,
            "text_hook": self.text_hook,
            "first_three_seconds": self.first_three_seconds,
            "metadata": self.metadata,
        }


class HookEngine:
    """Hook 引擎"""

    HOOK_DETAILS: dict[str, dict[str, str]] = {
        "Collection": {
            "visual": "Glowing collectible items floating",
            "action": "Player reaches out to collect",
            "text": "Collect!",
            "emotion": "Excitement",
            "first_3s": "Must show collectible items and player action",
        },
        "Transformation": {
            "visual": "Character/Creature transforming",
            "action": "Dramatic transformation sequence",
            "text": "Transform!",
            "emotion": "Wonder",
            "first_3s": "Transformation must start and complete within 3s",
        },
        "Epic": {
            "visual": "Epic boss or battle scene",
            "action": "Boss appearance, dramatic pose",
            "text": "Boss!",
            "emotion": "Adrenaline",
            "first_3s": "Boss must appear within 2s",
        },
        "Story": {
            "visual": "Character in interesting setting",
            "action": "Character discovers something",
            "text": "Discover!",
            "emotion": "Curiosity",
            "first_3s": "Character and setting must be clear",
        },
        "Discovery": {
            "visual": "Hidden treasure or secret",
            "action": "Reveal of hidden item",
            "text": "Found!",
            "emotion": "Surprise",
            "first_3s": "Reveal must happen within 3s",
        },
        "Surprise": {
            "visual": "Unexpected item appears",
            "action": "Item bursts onto screen",
            "text": "Wow!",
            "emotion": "Shock",
            "first_3s": "Surprise must happen within 2s",
        },
    }

    def generate(self, blueprint: VideoBlueprint) -> HookProfile:
        """根据 Blueprint 生成 Hook 配置"""
        details = self.HOOK_DETAILS.get(blueprint.hook, self.HOOK_DETAILS["Collection"])

        return HookProfile(
            variant_id=blueprint.variant_id,
            hook_type=blueprint.hook,
            emotion=details["emotion"],
            visual_hook=details["visual"],
            action_hook=details["action"],
            text_hook=details["text"],
            first_three_seconds={
                "rule": details["first_3s"],
                "required_elements": self._get_required_elements(blueprint.hook),
                "timing": "0-3s",
            },
            metadata={
                "platform": blueprint.platform,
                "placement": blueprint.placement,
            },
        )

    def _get_required_elements(self, hook: str) -> list[str]:
        """获取前三秒必须出现的元素"""
        elements = {
            "Collection": ["Collectible Item", "Player Hand", "Glow Effect"],
            "Transformation": ["Original Form", "Transformation Effect", "New Form"],
            "Epic": ["Boss", "Dramatic Lighting", "Camera Shake"],
            "Story": ["Main Character", "Setting", "Discovery Moment"],
            "Discovery": ["Hidden Object", "Reveal Effect", "Player Reaction"],
            "Surprise": ["Surprise Item", "Burst Effect", "Reaction"],
        }
        return elements.get(hook, ["Hook Element"])
