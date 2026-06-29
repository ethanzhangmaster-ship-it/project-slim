"""Mutation Engine - 素材变异生成器 (DEPRECATED)
Use market_ops.creative_growth_loop.04_mutation instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.04_mutation")

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

from .pattern_engine import ImagePattern


class MutationType(str, Enum):
    SUBJECT_SWAP = "subject_swap"
    COLOR_SWAP = "color_swap"
    EMOTION_SWAP = "emotion_swap"
    BACKGROUND_SWAP = "background_swap"
    COSTUME_SWAP = "costume_swap"
    POSE_SWAP = "pose_swap"
    CAMERA_SWAP = "camera_swap"
    LIGHTING_SWAP = "lighting_swap"


@dataclass
class Mutation:
    mutation_type: MutationType
    original_value: str
    new_value: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation": self.mutation_type.value,
            "original": self.original_value,
            "new_value": self.new_value,
            "description": self.description,
        }


class MutationEngine:
    SUBJECT_OPTIONS = [
        ("dragon", ["owl", "cat", "panda", "fox", "rabbit", "bear", "wolf", "deer"]),
        ("witch", ["wizard", "princess", "knight", "mage", "elf", "fairy", "vampire", "ghost"]),
        ("monster", ["robot", "alien", "dinosaur", "dragon", "golem", "titan", "phoenix", "unicorn"]),
        ("hero", ["warrior", "ninja", "samurai", "pirate", "cowboy", "detective", "spy", "scientist"]),
    ]

    COLOR_OPTIONS = [
        ("pink", ["purple", "blue", "rainbow", "gold", "silver", "neon green", "cyan", "coral"]),
        ("purple", ["pink", "blue", "magenta", "lavender", "gold", "platinum", "teal", "burgundy"]),
        ("blue", ["cyan", "purple", "turquoise", "navy", "silver", "electric blue", "sky", "ocean"]),
        ("gold", ["silver", "bronze", "rose gold", "platinum", "amber", "copper", "mint", "peach"]),
    ]

    EMOTION_OPTIONS = [
        "happy", "surprised", "crying", "angry", "excited", "peaceful", "mysterious", "playful",
        "determined", "curious", "proud", "gentle", "fierce", "whimsical", "epic", "serene"
    ]

    BACKGROUND_OPTIONS = [
        "forest", "space", "castle", "classroom", "ocean", "desert", "mountain", "city",
        "cave", "garden", "volcano", "arctic", "jungle", "underwater", "clouds", "fantasy world"
    ]

    COSTUME_OPTIONS = [
        "wizard", "superhero", "princess", "pirate", "knight", "ninja", "chef", "doctor",
        "detective", "cowboy", "viking", "samurai", "angel", "devil", "robot", "magician"
    ]

    POSE_OPTIONS = [
        "running", "flying", "jumping", "standing", "sitting", "fighting", "casting spell", "dancing",
        "meditating", "waving", "pointing", "holding object", "levitating", "crouching", "laughing", "thinking"
    ]

    CAMERA_OPTIONS = [
        "close up", "top view", "fisheye", "wide shot", "low angle", "high angle", "side view", "action shot",
        "portrait", "landscape", "macro", "panoramic", "dutch angle", "tracking shot", "zoom in", "bird eye"
    ]

    LIGHTING_OPTIONS = [
        "sunset", "neon", "cinematic", "soft", "dramatic", "natural", "studio", "candlelight",
        "neon glow", "moonlight", "spotlight", "ambient", "harsh", "golden hour", "blue hour", "fluorescent"
    ]

    def __init__(self, num_mutations: int = 8):
        self.num_mutations = num_mutations

    def generate_mutations(self, pattern: ImagePattern) -> List[Mutation]:
        mutations: List[Mutation] = []
        
        mutation_methods = [
            self._subject_swap,
            self._color_swap,
            self._emotion_swap,
            self._background_swap,
            self._costume_swap,
            self._pose_swap,
            self._camera_swap,
            self._lighting_swap,
        ]
        
        random.shuffle(mutation_methods)
        
        for method in mutation_methods[:self.num_mutations]:
            mutation = method(pattern)
            if mutation:
                mutations.append(mutation)
        
        return mutations

    def _subject_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        subject = pattern.subject.lower()
        for original, options in self.SUBJECT_OPTIONS:
            if original in subject:
                new_subject = random.choice(options)
                new_full_subject = subject.replace(original, new_subject)
                return Mutation(
                    mutation_type=MutationType.SUBJECT_SWAP,
                    original_value=pattern.subject,
                    new_value=new_full_subject,
                    description=f"Replace {original} with {new_subject}"
                )
        
        base_subjects = ["character", "creature", "animal", "person"]
        for base in base_subjects:
            if base in subject:
                new_subject = random.choice(["owl", "fox", "panda", "dragon", "fairy"])
                return Mutation(
                    mutation_type=MutationType.SUBJECT_SWAP,
                    original_value=pattern.subject,
                    new_value=f"{new_subject} {base}",
                    description=f"Replace with {new_subject}"
                )
        
        return None

    def _color_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        palette = pattern.palette.lower()
        for original, options in self.COLOR_OPTIONS:
            if original in palette:
                new_color = random.choice(options)
                return Mutation(
                    mutation_type=MutationType.COLOR_SWAP,
                    original_value=pattern.palette,
                    new_value=palette.replace(original, new_color),
                    description=f"Change {original} to {new_color}"
                )
        
        if palette:
            new_color = random.choice(["purple", "gold", "cyan", "neon green", "rose gold"])
            return Mutation(
                mutation_type=MutationType.COLOR_SWAP,
                original_value=pattern.palette,
                new_value=f"{new_color}, {palette}",
                description=f"Add {new_color} palette"
            )
        
        return None

    def _emotion_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        current_emotion = pattern.emotion.lower()
        options = [e for e in self.EMOTION_OPTIONS if e != current_emotion]
        if options:
            new_emotion = random.choice(options)
            return Mutation(
                mutation_type=MutationType.EMOTION_SWAP,
                original_value=pattern.emotion,
                new_value=new_emotion,
                description=f"Change emotion from {current_emotion} to {new_emotion}"
            )
        return None

    def _background_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        current_bg = pattern.background.lower()
        options = [b for b in self.BACKGROUND_OPTIONS if b != current_bg]
        if options:
            new_bg = random.choice(options)
            return Mutation(
                mutation_type=MutationType.BACKGROUND_SWAP,
                original_value=pattern.background,
                new_value=new_bg,
                description=f"Change background from {current_bg} to {new_bg}"
            )
        return None

    def _costume_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        new_costume = random.choice(self.COSTUME_OPTIONS)
        return Mutation(
            mutation_type=MutationType.COSTUME_SWAP,
            original_value="",
            new_value=new_costume,
            description=f"Add {new_costume} costume"
        )

    def _pose_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        current_pose = pattern.character_pose.lower() if pattern.character_pose else ""
        options = [p for p in self.POSE_OPTIONS if p not in current_pose]
        if options:
            new_pose = random.choice(options)
            return Mutation(
                mutation_type=MutationType.POSE_SWAP,
                original_value=pattern.character_pose,
                new_value=new_pose,
                description=f"Change pose to {new_pose}"
            )
        return None

    def _camera_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        current_comp = pattern.composition.lower() if pattern.composition else ""
        options = [c for c in self.CAMERA_OPTIONS if c not in current_comp]
        if options:
            new_camera = random.choice(options)
            return Mutation(
                mutation_type=MutationType.CAMERA_SWAP,
                original_value=pattern.composition,
                new_value=new_camera,
                description=f"Change camera angle to {new_camera}"
            )
        return None

    def _lighting_swap(self, pattern: ImagePattern) -> Optional[Mutation]:
        current_light = pattern.lighting.lower() if pattern.lighting else ""
        options = [l for l in self.LIGHTING_OPTIONS if l not in current_light]
        if options:
            new_light = random.choice(options)
            return Mutation(
                mutation_type=MutationType.LIGHTING_SWAP,
                original_value=pattern.lighting,
                new_value=new_light,
                description=f"Change lighting to {new_light}"
            )
        return None