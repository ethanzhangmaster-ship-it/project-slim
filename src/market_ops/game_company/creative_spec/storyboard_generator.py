from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


SCENE_TEMPLATES = {
    "0_0_8s_hook": {
        "time_range": "0-0.8s",
        "category": "hook",
        "instruction": "High contrast subject in center 40% of frame. Background darkened 30%. No text, no UI. Subject fills >= 30%.",
        "ae_instruction": "Place character/subject in center. Radial gradient spotlight. Background vignette (60% opacity). Subject sharpened.",
    },
    "0_8_3s_motion": {
        "time_range": "0.8-3s",
        "category": "motion",
        "instruction": "Visual structure change: subject movement, scene cut, or UI reveal. At least 1 measurable change.",
        "ae_instruction": "Keyframe animation: subject moves/scales from center. Or scene cut to second frame. Or UI popup from bottom.",
    },
    "3_6s_gameplay": {
        "time_range": "3-6s",
        "category": "gameplay",
        "instruction": "Show core value proposition: gameplay loop, merge mechanic, or interaction demo. Minimal text.",
        "ae_instruction": "Show game merge mechanic or collection demo. Icons instead of text. Keep visual clean.",
    },
    "6_9s_reward": {
        "time_range": "6-9s",
        "category": "reward",
        "instruction": "Visual reward event: new visual state, brighter + more saturated. Reward visual surge >= 0.05.",
        "ae_instruction": "Victory screen / level-up / collection reveal. Increase brightness 30%, saturation 20%, particle effects.",
    },
    "9s_end_cta": {
        "time_range": "9s-end",
        "category": "cta",
        "instruction": "CTA + social proof. Consistent visual quality with reward state.",
        "ae_instruction": "CTA button pulse animation. Social proof (rating/users) slides in from bottom. Button high contrast color.",
    },
}


@dataclass
class Scene:
    scene_id: str
    time_range: str
    category: str
    duration: float
    prompt: str
    camera: str = ""
    transition: str = ""
    elements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "time_range": self.time_range,
            "category": self.category,
            "duration_seconds": self.duration,
            "prompt": self.prompt,
            "camera": self.camera,
            "transition": self.transition,
            "elements": self.elements,
        }


@dataclass
class Storyboard:
    project: str
    hook_type: str
    total_duration: float
    scenes: List[Scene] = field(default_factory=list)
    total_scenes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "hook_type": self.hook_type,
            "total_duration_seconds": self.total_duration,
            "total_scenes": self.total_scenes if self.total_scenes > 0 else len(self.scenes),
            "scenes": [s.to_dict() for s in self.scenes],
        }


class StoryboardGenerator:
    def __init__(self):
        self._templates = SCENE_TEMPLATES

    def generate(self, project: str = "P04 Witch", hook_type: str = "collection", duration: int = 25) -> Storyboard:
        storyboard = Storyboard(project=project, hook_type=hook_type, total_duration=float(duration))

        hook_scene = Scene(
            scene_id="scene_1",
            time_range="0-0.8s",
            category="hook",
            duration=0.8,
            prompt=self._templates["0_0_8s_hook"]["instruction"],
            camera="Medium wide shot, spotlight on subject",
            transition="None (instant frame)",
            elements=["character/subject", "spotlight", "darkened background"],
        )
        storyboard.scenes.append(hook_scene)

        motion_scene = Scene(
            scene_id="scene_2",
            time_range="0.8-3s",
            category="motion",
            duration=2.2,
            prompt=self._templates["0_8_3s_motion"]["instruction"],
            camera="Keyframe animation: subject moves or scene cuts",
            transition="Cut or swipe",
            elements=["subject movement", "scene change", "or UI popup"],
        )
        storyboard.scenes.append(motion_scene)

        gameplay_scene = Scene(
            scene_id="scene_3",
            time_range="3-6s",
            category="gameplay",
            duration=3.0,
            prompt=self._get_gameplay_prompt(hook_type),
            camera="Gameplay overview, top-down or isometric",
            transition="Smooth transition from motion",
            elements=["gameplay loop", "merge mechanic", "collection items"],
        )
        storyboard.scenes.append(gameplay_scene)

        reward_scene = Scene(
            scene_id="scene_4",
            time_range="6-9s",
            category="reward",
            duration=3.0,
            prompt=self._get_reward_prompt(hook_type),
            camera="Close-up on reward moment, dramatic zoom",
            transition="Flash/particle burst",
            elements=["reward event", "evolution", "bright flash", "particles"],
        )
        storyboard.scenes.append(reward_scene)

        cta_scene = Scene(
            scene_id="scene_5",
            time_range="9s-end",
            category="cta",
            duration=max(1.0, duration - 9.0),
            prompt=self._templates["9s_end_cta"]["instruction"],
            camera="Static, centered on CTA with reward background",
            transition="Fade to CTA frame",
            elements=["CTA button", "social proof", "app store badges"],
        )
        storyboard.scenes.append(cta_scene)

        storyboard.total_scenes = len(storyboard.scenes)
        return storyboard

    def _get_gameplay_prompt(self, hook_type: str) -> str:
        prompts = {
            "collection": "Show merge gameplay with multiple creatures/items appearing. Collection counter fills up.",
            "reward": "Show player progressing through levels, gaining power-ups and rewards.",
            "curiosity": "Show exploration and discovery of hidden items and secret areas.",
            "comparison": "Show before/after gameplay comparison with dramatic improvement.",
            "crisis": "Show player overcoming obstacles and rescuing/saving something.",
        }
        return prompts.get(hook_type, prompts["collection"])

    def _get_reward_prompt(self, hook_type: str) -> str:
        prompts = {
            "collection": "Collection complete! All 200+ creatures revealed. Progress bar fills to 100%. Glowing effects.",
            "reward": "Epic evolution! Character transforms to ultimate form. Level up animation with stars.",
            "curiosity": "Mystery revealed! The hidden treasure/creature is finally shown. Surprise and delight.",
            "comparison": "Complete transformation! From ordinary to extraordinary. Side by side comparison.",
            "crisis": "Crisis resolved! Everything restored better than before. Happy ending with rewards.",
        }
        return prompts.get(hook_type, prompts["collection"])

    def get_stats(self) -> Dict[str, Any]:
        return {"total_scene_templates": len(self._templates)}
