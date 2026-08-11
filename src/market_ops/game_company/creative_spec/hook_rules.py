from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


HOOK_LIBRARY = {
    "collection": {
        "name": "Collection Hook",
        "hook_type": "collection",
        "priority": 1,
        "weight": 0.621,
        "description": "Show many collectible items/creatures to trigger collection desire",
        "opening_prompt": "Open with a character surrounded by many collectible magical creatures/items. Show variety and abundance.",
        "first_frame": "Center hero with array of creatures/items visible. High saturation, warm palette.",
        "camera": "Medium wide shot showing abundance. Slow zoom in on character.",
        "duration": {"min": 15, "max": 45, "recommended": 25},
        "transition": "Swipe or fade to merge gameplay",
        "reward_type": "Collection completion reveal (200+ creatures, progress bar filling)",
        "cta_style": "Bottom banner: 'Collect them all!' or '200+ Creatures to Collect'",
        "anti_patterns": [
            "Do NOT show only one item",
            "Do NOT use dark/desaturated palette",
        ],
    },
    "reward": {
        "name": "Reward Hook",
        "hook_type": "reward",
        "priority": 2,
        "weight": 0.096,
        "description": "Show powerful reward/evolution moment to trigger anticipation",
        "opening_prompt": "Start with a dramatic reward moment: character evolution, egg hatching, or treasure reveal. Use bright flash effects.",
        "first_frame": "Before state (weaker form) transitioning to after state (powerful form). Split screen works well.",
        "camera": "Close-up on the transformation. Quick zoom out after reveal.",
        "duration": {"min": 15, "max": 40, "recommended": 25},
        "transition": "Flash/particle burst to gameplay",
        "reward_type": "Character evolution, level-up, treasure hoard reveal, egg hatching",
        "cta_style": "Bottom banner: 'Your epic journey awaits!' or 'Evolve them all!'",
        "anti_patterns": [
            "Do NOT show reward without context",
            "Do NOT make reward feel small or insignificant",
        ],
    },
    "curiosity": {
        "name": "Curiosity Hook",
        "hook_type": "curiosity",
        "priority": 3,
        "weight": 0.164,
        "description": "Use mystery/question to trigger curiosity gap",
        "opening_prompt": "Open with a mystery: hidden object, question mark, or 'what happened?' scenario. Partial reveal only.",
        "first_frame": "Tight shot on mysterious element (covered object, shadow, question box). Darker and focused.",
        "camera": "Extreme close-up. Slow pull back to reveal context.",
        "duration": {"min": 20, "max": 50, "recommended": 30},
        "transition": "Fast zoom out to full scene. Text overlay: 'Only 1% Can Find This'",
        "reward_type": "Mystery reveal followed by abundance of rewards",
        "cta_style": "Bottom banner: 'Discover the secret!' or 'Only 1% Can Reach This'",
        "anti_patterns": [
            "Do NOT reveal everything in the first frame",
            "Do NOT use this as primary hook (lower ROAS in data)",
        ],
    },
    "comparison": {
        "name": "Comparison Hook",
        "hook_type": "comparison",
        "priority": 4,
        "weight": 0.052,
        "description": "Before/after comparison to show dramatic improvement",
        "opening_prompt": "Split screen or swipe comparison showing before (ordinary/poor) and after (magnificent/rich).",
        "first_frame": "Split screen: left=before, right=after. Or swipe reveal.",
        "camera": "Static split frame or horizontal pan across comparison.",
        "duration": {"min": 15, "max": 35, "recommended": 22},
        "transition": "Swipe transition revealing full after state",
        "reward_type": "Complete transformation reveal",
        "cta_style": "Bottom banner: 'From... to... Start your journey!'",
        "anti_patterns": [
            "Do NOT make before look too good",
            "Do NOT use subtle differences",
        ],
    },
    "crisis": {
        "name": "Crisis Hook",
        "hook_type": "crisis",
        "priority": 5,
        "weight": 0.034,
        "description": "Create urgency with limited-time or danger scenario",
        "opening_prompt": "Show urgent situation: countdown, broken castle, or creature in danger. Create immediate tension.",
        "first_frame": "Dramatic wide shot of crisis situation. Slightly darker, higher contrast.",
        "camera": "Dynamic, handheld-style movement. Quick cuts.",
        "duration": {"min": 20, "max": 45, "recommended": 30},
        "transition": "Fast cut to 'you can fix this' gameplay",
        "reward_type": "Crisis resolved, restoration, saving something precious",
        "cta_style": "Bottom banner: 'Save them now!' or 'Limited time - Act now!'",
        "anti_patterns": [
            "Do NOT artificially create fake urgency",
            "Do NOT use crisis without clear resolution path",
        ],
    },
}


@dataclass
class HookSpec:
    hook_type: str
    name: str = ""
    weight: float = 0.0
    opening_prompt: str = ""
    first_frame: str = ""
    camera: str = ""
    duration: Dict[str, int] = field(default_factory=lambda: {"min": 15, "max": 45, "recommended": 25})
    transition: str = ""
    reward_type: str = ""
    cta_style: str = ""
    anti_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_type": self.hook_type,
            "name": self.name,
            "weight": self.weight,
            "opening_prompt": self.opening_prompt,
            "first_frame": self.first_frame,
            "camera": self.camera,
            "duration": self.duration,
            "transition": self.transition,
            "reward_type": self.reward_type,
            "cta_style": self.cta_style,
            "anti_patterns": self.anti_patterns,
        }


class HookLibrary:
    def __init__(self):
        self._hooks = {}
        for htype, data in HOOK_LIBRARY.items():
            self._hooks[htype] = HookSpec(
                hook_type=data["hook_type"],
                name=data["name"],
                weight=data["weight"],
                opening_prompt=data["opening_prompt"],
                first_frame=data["first_frame"],
                camera=data["camera"],
                duration=data["duration"],
                transition=data["transition"],
                reward_type=data["reward_type"],
                cta_style=data["cta_style"],
                anti_patterns=data["anti_patterns"],
            )

    def get_hook(self, hook_type: str) -> Optional[HookSpec]:
        return self._hooks.get(hook_type)

    def get_all_hooks(self) -> List[HookSpec]:
        return list(self._hooks.values())

    def get_priority(self) -> List[HookSpec]:
        return sorted(self._hooks.values(), key=lambda h: -h.weight)

    def get_recommended_hook(self) -> HookSpec:
        return self.get_priority()[0]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_hooks": len(self._hooks),
            "top_hook": self.get_recommended_hook().hook_type,
            "weights": {h.hook_type: h.weight for h in self._hooks.values()},
        }
