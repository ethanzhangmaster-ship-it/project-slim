"""Hook Mutator - V15素材增长闭环

收敛约束 v2: 所有变异器支持 signal_guided_choice().
当传入 guide 参数时, 变异方向由 Bandit 信号引导, 而非纯随机.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


# ============================================================================
# Signal-Guided Choice Helper
# ============================================================================

def _signal_guided_choice(
    options: list[str],
    guide: dict[str, Any] | None,
    mutation_rate: float = 0.5,
) -> str:
    """基于 Bandit 信号的定向选择。

    当 guide 为 None 或 mutation_rate 触发随机探索时, 回退到 random.choice().
    否则:
    - 优先选择 guide["target"] (如果它在 options 中)
    - 排除 guide["avoid"] 中的值
    - 在剩余选项中随机选择

    Args:
        options: 候选值列表
        guide: {"target": str|None, "avoid": list[str], "rate": float}
        mutation_rate: 当前变异率 (用于决定探索 vs 利用)

    Returns:
        选中的值
    """
    if guide is None:
        return random.choice(options)

    # 按 mutation_rate 决定是探索还是利用
    if random.random() < mutation_rate:
        # 探索: 随机, 但避开 avoid 值
        target = guide.get("target")
        avoid = set(guide.get("avoid", []) or [])

        eligible = [o for o in options if o not in avoid]
        if not eligible:
            eligible = options  # 全部被 avoid, 退回全量

        # 优先 target 附近的: 如果 target 在 eligible 中, 加权选择
        if target and target in eligible and len(eligible) > 1:
            # 70% 概率选 target, 30% 选其他 eligible
            return target if random.random() < 0.7 else random.choice([o for o in eligible if o != target])

        return random.choice(eligible)
    else:
        # 利用: 优先选 target
        target = guide.get("target")
        if target and target in options:
            return target
        return random.choice(options)


# ============================================================================
# Mutators
# ============================================================================


@dataclass
class HookMutation:
    hook_type: str
    hook_text: str
    weight: float = 0.4
    guided: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_type": self.hook_type,
            "hook_text": self.hook_text,
            "weight": self.weight,
            "guided": self.guided,
        }


class HookMutator:
    HOOK_WEIGHT = 0.40

    HOOK_TEMPLATES = {
        "secret": [
            "Secret Dragon Inside",
            "Only 1% Know This Secret",
            "Hidden Treasure Revealed",
            "Secret Level Discovered",
            "The Secret to Winning",
            "Unlock Secret Character",
            "Secret Evolution Path",
            "What's The Secret?",
        ],
        "challenge": [
            "Can You Reach Lv100?",
            "Only 1% Can Beat This",
            "Challenge Accepted?",
            "Impossible Level?",
            "Can You Survive?",
            "Beat This Challenge",
            "Pro Challenge Mode",
            "Ultimate Challenge",
        ],
        "wrong_choice": [
            "Don't Merge Them!",
            "Wrong Choice!",
            "Don't Click This",
            "Stop! Wrong Way",
            "Don't Do This",
            "Warning: Wrong Move",
            "Think Before You Click",
            "This Choice Will Fail",
        ],
        "before_after": [
            "Broken Farm → Castle",
            "Lv1 → Lv100",
            "Before vs After",
            "From Zero to Hero",
            "Evolution in 3 Steps",
            "Small → Legendary",
            "Transform Your Game",
            "Level Up Fast",
        ],
        "reward": [
            "Get Golden Dragon",
            "Claim Your Reward",
            "Free Treasure Inside",
            "Unlock Legendary",
            "Reward Waiting",
            "Collect Your Prize",
            "Exclusive Reward",
            "Bonus Unlocked",
        ],
        "curiosity": [
            "What Happens Next?",
            "Why Is Everyone Stuck?",
            "What's Inside?",
            "Guess The Result",
            "Find Out Now",
            "Discover The Truth",
            "Mystery Revealed",
            "The Answer Is...",
        ],
        "urgency": [
            "Last Chance!",
            "Limited Time Only",
            "Act Now!",
            "Time Running Out",
            "Don't Miss This",
            "Hurry! Ends Soon",
            "Final Warning",
            "Only Today",
        ],
        "level": [
            "Wait For Lv100",
            "Level 100 Evolution",
            "Max Level Reached",
            "Ultimate Level",
            "Level Up Fast",
            "Reach Max Level",
            "Level 100 Secret",
            "Final Level Boss",
        ],
    }

    def __init__(self):
        pass

    def generate_mutations(
        self, count: int = 10,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[HookMutation]:
        """生成Hook变体 (支持信号引导)"""
        mutations = []

        hook_types = list(self.HOOK_TEMPLATES.keys())
        guided = guide is not None

        for i in range(count):
            hook_type = _signal_guided_choice(hook_types, guide, mutation_rate)
            templates = self.HOOK_TEMPLATES[hook_type]
            hook_text = _signal_guided_choice(templates, guide, mutation_rate)

            mutation = HookMutation(
                hook_type=hook_type,
                hook_text=hook_text,
                weight=self.HOOK_WEIGHT,
                guided=guided,
            )
            mutations.append(mutation)

        return mutations

    def generate_from_winner(
        self, winner_hook: str, count: int = 10,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[HookMutation]:
        """从赢家Hook生成变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        if winner_hook in self.HOOK_TEMPLATES:
            templates = self.HOOK_TEMPLATES[winner_hook]
            selected = random.sample(templates, min(count, len(templates)))

            for hook_text in selected:
                mutation = HookMutation(
                    hook_type=winner_hook,
                    hook_text=hook_text,
                    weight=self.HOOK_WEIGHT,
                    guided=guided,
                )
                mutations.append(mutation)

        other_types = [t for t in self.HOOK_TEMPLATES.keys() if t != winner_hook]
        remaining = count - len(mutations)

        for i in range(remaining):
            hook_type = _signal_guided_choice(other_types, guide, mutation_rate)
            hook_text = _signal_guided_choice(self.HOOK_TEMPLATES[hook_type], guide, mutation_rate)

            mutation = HookMutation(
                hook_type=hook_type,
                hook_text=hook_text,
                weight=self.HOOK_WEIGHT * 0.5,
                guided=guided,
            )
            mutations.append(mutation)

        return mutations


class RewardMutator:
    REWARD_WEIGHT = 0.20

    REWARD_TYPES = [
        "Dragon", "Golden Dragon", "Phoenix", "Treasure",
        "Castle", "Diamond Tree", "Unicorn", "Magic Item",
        "Legendary Creature", "Rare Egg", "Golden Egg",
        "Crystal Dragon", "Rainbow Phoenix", "Secret Pet",
    ]

    def generate_mutations(
        self, count: int = 5,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """生成Reward变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        for i in range(count):
            reward = _signal_guided_choice(self.REWARD_TYPES, guide, mutation_rate)
            mutations.append({
                "reward_type": "reward",
                "reward_value": reward,
                "weight": self.REWARD_WEIGHT,
                "guided": guided,
            })

        return mutations


class EmotionMutator:
    EMOTION_WEIGHT = 0.15

    EMOTION_TYPES = [
        "surprise", "panic", "happy", "wow", "cry",
        "angry", "excited", "curious", "proud", "mysterious",
        "shocked", "amazed", "thrilled", "nervous", "confident",
    ]

    def generate_mutations(
        self, count: int = 5,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """生成Emotion变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        for i in range(count):
            emotion = _signal_guided_choice(self.EMOTION_TYPES, guide, mutation_rate)
            mutations.append({
                "emotion_type": "emotion",
                "emotion_value": emotion,
                "weight": self.EMOTION_WEIGHT,
                "guided": guided,
            })

        return mutations


class ProgressMutator:
    PROGRESS_WEIGHT = 0.10

    PROGRESS_TYPES = [
        "Lv10", "Lv50", "Lv100", "Ultimate", "Secret",
        "Final", "Evolution", "Max", "Legendary", "Complete",
        "Level 1", "Level 50", "Level 100", "Max Level",
    ]

    def generate_mutations(
        self, count: int = 5,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """生成Progress变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        for i in range(count):
            progress = _signal_guided_choice(self.PROGRESS_TYPES, guide, mutation_rate)
            mutations.append({
                "progress_type": "progress",
                "progress_value": progress,
                "weight": self.PROGRESS_WEIGHT,
                "guided": guided,
            })

        return mutations


class OverlayMutator:
    OVERLAY_WEIGHT = 0.10

    OVERLAY_TYPES = [
        "Arrow", "Circle", "Glow", "Text", "+999",
        "NEW", "SECRET", "LEVEL100", "Question Mark",
        "Exclamation", "Star", "Badge", "Banner",
    ]

    def generate_mutations(
        self, count: int = 5,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """生成Overlay变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        for i in range(count):
            overlay = _signal_guided_choice(self.OVERLAY_TYPES, guide, mutation_rate)
            mutations.append({
                "overlay_type": "overlay",
                "overlay_value": overlay,
                "weight": self.OVERLAY_WEIGHT,
                "guided": guided,
            })

        return mutations


class SubjectMutator:
    SUBJECT_WEIGHT = 0.05

    SUBJECT_TYPES = [
        "Dragon", "Phoenix", "Unicorn", "Wolf",
        "Cat", "Fox", "Bear", "Rabbit",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """生成Subject变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        for i in range(count):
            subject = _signal_guided_choice(self.SUBJECT_TYPES, guide, mutation_rate)
            mutations.append({
                "subject_type": "subject",
                "subject_value": subject,
                "weight": self.SUBJECT_WEIGHT,
                "guided": guided,
            })

        return mutations


class CompositionMutator:
    COMPOSITION_WEIGHT = 0.05

    COMPOSITION_TYPES = [
        "Split Screen", "Before After", "Vertical Stack",
        "Horizontal Split", "Center Focus", "Side Comparison",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """生成Composition变体 (支持信号引导)"""
        mutations = []
        guided = guide is not None

        for i in range(count):
            composition = _signal_guided_choice(self.COMPOSITION_TYPES, guide, mutation_rate)
            mutations.append({
                "composition_type": "composition",
                "composition_value": composition,
                "weight": self.COMPOSITION_WEIGHT,
                "guided": guided,
            })

        return mutations


class CostumeMutator:
    """服装变异器 (Port from old creative_loop mutation_engine)"""
    COSTUME_WEIGHT = 0.03

    COSTUME_OPTIONS = [
        "wizard", "superhero", "princess", "pirate", "knight", "ninja", "chef", "doctor",
        "detective", "cowboy", "viking", "samurai", "angel", "devil", "robot", "magician",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        mutations = []
        guided = guide is not None
        for i in range(count):
            costume = _signal_guided_choice(self.COSTUME_OPTIONS, guide, mutation_rate)
            mutations.append({
                "costume_type": "costume",
                "costume_value": costume,
                "weight": self.COSTUME_WEIGHT,
                "guided": guided,
            })
        return mutations


class PoseMutator:
    """姿势变异器 (Port from old creative_loop mutation_engine)"""
    POSE_WEIGHT = 0.03

    POSE_OPTIONS = [
        "running", "flying", "jumping", "standing", "sitting", "fighting",
        "casting spell", "dancing", "meditating", "waving", "pointing",
        "holding object", "levitating", "crouching", "laughing", "thinking",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        mutations = []
        guided = guide is not None
        for i in range(count):
            pose = _signal_guided_choice(self.POSE_OPTIONS, guide, mutation_rate)
            mutations.append({
                "pose_type": "pose",
                "pose_value": pose,
                "weight": self.POSE_WEIGHT,
                "guided": guided,
            })
        return mutations


class CameraMutator:
    """镜头变异器 (Port from old creative_loop mutation_engine)"""
    CAMERA_WEIGHT = 0.03

    CAMERA_OPTIONS = [
        "close up", "top view", "fisheye", "wide shot", "low angle", "high angle",
        "side view", "action shot", "portrait", "landscape", "macro", "panoramic",
        "dutch angle", "tracking shot", "zoom in", "bird eye",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        mutations = []
        guided = guide is not None
        for i in range(count):
            camera = _signal_guided_choice(self.CAMERA_OPTIONS, guide, mutation_rate)
            mutations.append({
                "camera_type": "camera",
                "camera_value": camera,
                "weight": self.CAMERA_WEIGHT,
                "guided": guided,
            })
        return mutations


class LightingMutator:
    """光照变异器 (Port from old creative_loop mutation_engine)"""
    LIGHTING_WEIGHT = 0.03

    LIGHTING_OPTIONS = [
        "sunset", "neon", "cinematic", "soft", "dramatic", "natural", "studio",
        "candlelight", "neon glow", "moonlight", "spotlight", "ambient", "harsh",
        "golden hour", "blue hour", "fluorescent",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        mutations = []
        guided = guide is not None
        for i in range(count):
            lighting = _signal_guided_choice(self.LIGHTING_OPTIONS, guide, mutation_rate)
            mutations.append({
                "lighting_type": "lighting",
                "lighting_value": lighting,
                "weight": self.LIGHTING_WEIGHT,
                "guided": guided,
            })
        return mutations


class ColorMutator:
    """颜色变异器 (Port from old creative_loop mutation_engine)"""
    COLOR_WEIGHT = 0.03

    COLOR_OPTIONS = [
        "purple", "blue", "rainbow", "gold", "silver", "neon green", "cyan", "coral",
        "pink", "magenta", "lavender", "platinum", "teal", "burgundy", "turquoise",
        "navy", "electric blue", "sky", "ocean",
    ]

    def generate_mutations(
        self, count: int = 3,
        guide: dict[str, Any] | None = None,
        mutation_rate: float = 0.5,
    ) -> List[Dict[str, Any]]:
        mutations = []
        guided = guide is not None
        for i in range(count):
            color = _signal_guided_choice(self.COLOR_OPTIONS, guide, mutation_rate)
            mutations.append({
                "color_type": "color",
                "color_value": color,
                "weight": self.COLOR_WEIGHT,
                "guided": guided,
            })
        return mutations