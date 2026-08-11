"""Storyboard Engine - 视频分镜引擎

根据 Video DNA + Story Pattern 生成真正的视频分镜。

每个 Scene:
Scene ID / Start / End / Description / Camera / Lighting / Motion / Subtitle / Voice / Transition
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoryboardScene:
    """分镜场景"""
    scene_id: str
    scene_index: int
    name: str
    start_time: float
    end_time: float
    duration: float
    description: str
    camera: str
    lighting: str
    motion: str
    subtitle: str = ""
    voice: str = ""
    transition: str = ""
    fx: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_index": self.scene_index,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "description": self.description,
            "camera": self.camera,
            "lighting": self.lighting,
            "motion": self.motion,
            "subtitle": self.subtitle,
            "voice": self.voice,
            "transition": self.transition,
            "fx": self.fx,
        }


@dataclass
class Storyboard:
    """视频分镜"""
    storyboard_id: str
    variant_id: str
    total_duration: float
    scenes: list[StoryboardScene] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "storyboard_id": self.storyboard_id,
            "variant_id": self.variant_id,
            "total_duration": self.total_duration,
            "scenes": [s.to_dict() for s in self.scenes],
        }


class StoryboardEngine:
    """视频分镜引擎"""

    # DNA Camera Style → 运镜
    CAMERA_MAP: dict[str, str] = {
        "Zoom": "Zoom In",
        "Tracking": "Tracking",
        "Orbit": "Orbit",
        "Follow": "Follow",
        "Pan": "Pan",
        "Static": "Static",
    }

    # DNA Lighting Style → 灯光
    LIGHTING_MAP: dict[str, str] = {
        "Golden": "Golden hour, warm rim light",
        "Cool": "Cool blue, moonlight",
        "Dramatic": "Dramatic side light, strong contrast",
        "Soft": "Soft diffused, gentle shadows",
        "Flash": "Bright flash, high contrast",
    }

    # DNA Transition Style → 转场
    TRANSITION_MAP: dict[str, str] = {
        "Cut": "Cut",
        "Flash": "Flash",
        "Whip": "Whip",
        "Blur": "Blur",
        "Shake": "Shake",
    }

    def generate(self, dna: VideoDNA, blueprint: VideoBlueprint, story_pattern: StoryPattern) -> Storyboard:
        """根据 Video DNA + Story Pattern 生成分镜"""
        scenes = []
        camera = self.CAMERA_MAP.get(dna.camera_style, "Zoom In")
        lighting = self.LIGHTING_MAP.get(dna.lighting_style, "Golden hour")
        transition = self.TRANSITION_MAP.get(dna.transition_style, "Cut")

        for i, seg in enumerate(blueprint.segments):
            # 根据段落名称选择不同的运镜和灯光变化
            seg_camera = self._get_segment_camera(seg["name"], camera)
            seg_lighting = self._get_segment_lighting(seg["name"], lighting)
            seg_motion = self._get_segment_motion(seg["name"])
            seg_fx = self._get_segment_fx(seg["name"])

            scenes.append(StoryboardScene(
                scene_id=f"scene_{dna.variant_id}_{i+1:02d}",
                scene_index=i + 1,
                name=seg["name"],
                start_time=seg["start"],
                end_time=seg["end"],
                duration=seg["duration"],
                description=seg["description"],
                camera=seg_camera,
                lighting=seg_lighting,
                motion=seg_motion,
                subtitle=self._get_subtitle(seg["name"], dna),
                voice="None",
                transition=transition if i > 0 else "None",
                fx=seg_fx,
            ))

        return Storyboard(
            storyboard_id=f"storyboard_{dna.variant_id}",
            variant_id=dna.variant_id,
            total_duration=blueprint.video_length,
            scenes=scenes,
        )

    def _get_segment_camera(self, seg_name: str, base_camera: str) -> str:
        overrides = {
            "Hook": "Zoom In",
            "Opening": "Zoom In",
            "Boss": "Orbit",
            "CTA": "Static",
            "Victory": "Orbit",
            "Reward": "Push In",
        }
        return overrides.get(seg_name, base_camera)

    def _get_segment_lighting(self, seg_name: str, base_lighting: str) -> str:
        overrides = {
            "Hook": "Golden hour, warm rim light",
            "Boss": "Dramatic red, strong shadows",
            "Reward": "Golden glow, volumetric light",
            "CTA": "Clean studio, even lighting",
            "Victory": "Bright celebration light",
        }
        return overrides.get(seg_name, base_lighting)

    def _get_segment_motion(self, seg_name: str) -> str:
        motions = {
            "Hook": "Fast entrance, dynamic reveal",
            "Search": "Exploring, scanning",
            "Collect": "Tap, swipe, merge",
            "Merge": "Swipe gesture, item combine",
            "Boss": "Combat movement, dodge",
            "Fail": "Freeze, shake",
            "Retry": "Power up, upgrade",
            "Victory": "Celebrate, arms up",
            "Reward": "Coins burst, chest open",
            "CTA": "Button pulse, finger tap",
        }
        return motions.get(seg_name, "Natural movement")

    def _get_segment_fx(self, seg_name: str) -> list[str]:
        fx_map = {
            "Hook": ["glow", "sparkle"],
            "Boss": ["shake", "lightning"],
            "Victory": ["confetti", "glow"],
            "Reward": ["coin_burst", "golden_glow"],
            "CTA": ["button_glow", "shimmer"],
            "Fail": ["red_flash", "shake"],
        }
        return fx_map.get(seg_name, [])

    def _get_subtitle(self, seg_name: str, dna: VideoDNA) -> str:
        subs = {
            "Hook": "Look!",
            "Search": "Find it!",
            "Collect": "Collect!",
            "Merge": "Merge!",
            "Boss": "Boss!",
            "Fail": "Try again!",
            "Retry": "Power up!",
            "Victory": "Victory!",
            "Reward": "Claim!",
            "CTA": "Play Now!",
        }
        return subs.get(seg_name, "Action!")
