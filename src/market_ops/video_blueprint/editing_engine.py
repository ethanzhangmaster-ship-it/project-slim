"""Editing Engine - 剪辑规范引擎

每个 Scene 输出完整后期调色与特效参数。

参数:
  Exposure / Contrast / Highlight / Shadow / Temperature / Tint
  Saturation / Sharpness / Film Grain / Bloom / Chromatic / Particles
  LUT / Motion Blur
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneEditingSpec:
    """单个 Scene 的剪辑规范"""
    scene_id: str
    scene_name: str
    exposure: float = 0.0
    contrast: float = 1.0
    highlight: float = -10.0
    shadow: float = 10.0
    temperature: float = 5500.0
    tint: float = 0.0
    saturation: float = 1.0
    sharpness: float = 0.5
    film_grain: float = 0.0
    bloom: float = 0.0
    chromatic: float = 0.0
    particles: str = "none"
    lut: str = "default"
    motion_blur: float = 0.4

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "exposure": self.exposure,
            "contrast": self.contrast,
            "highlight": self.highlight,
            "shadow": self.shadow,
            "temperature": self.temperature,
            "tint": self.tint,
            "saturation": self.saturation,
            "sharpness": self.sharpness,
            "film_grain": self.film_grain,
            "bloom": self.bloom,
            "chromatic": self.chromatic,
            "particles": self.particles,
            "lut": self.lut,
            "motion_blur": self.motion_blur,
        }


@dataclass
class EditingGuide:
    """剪辑规范"""
    variant_id: str
    scenes: list[SceneEditingSpec] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "scenes": [s.to_dict() for s in self.scenes],
            "notes": self.notes,
        }


class EditingEngine:
    """剪辑规范引擎"""

    LUT_PRESETS: dict[str, str] = {
        "Vibrant": "lut_vibrant_02",
        "Warm": "lut_warm_01",
        "Cool": "lut_cool_01",
        "Dark": "lut_cinematic_01",
    }

    def generate(self, dna: VideoDNA, storyboard: Storyboard) -> EditingGuide:
        """根据 Video DNA 和 Storyboard 生成每个 Scene 的剪辑规范"""
        lut = self.LUT_PRESETS.get(dna.color_style, "lut_vibrant_02")
        scenes = []

        for scene in storyboard.scenes:
            spec = self._build_scene_spec(scene, dna, lut)
            scenes.append(spec)

        return EditingGuide(
            variant_id=dna.variant_id,
            scenes=scenes,
            notes="All values are suggestions. Adjust based on final footage quality.",
        )

    def _build_scene_spec(self, scene: StoryboardScene, dna: VideoDNA, lut: str) -> SceneEditingSpec:
        """构建单个 Scene 的剪辑参数"""
        base = {
            "exposure": 0.0,
            "contrast": 1.2,
            "highlight": -15.0,
            "shadow": 12.0,
            "temperature": 6500.0,
            "tint": 0.0,
            "saturation": 1.1,
            "sharpness": 0.5,
            "film_grain": 0.0,
            "bloom": 0.0,
            "chromatic": 0.0,
            "particles": "none",
            "motion_blur": 0.4,
        }

        # 根据场景调整
        if scene.name in ("Hook", "Opening"):
            base["exposure"] = 0.3
            base["contrast"] = 1.3
            base["highlight"] = -10.0
            base["sharpness"] = 0.8
            base["motion_blur"] = 0.5
        elif scene.name in ("Reward", "Victory", "LevelUp"):
            base["exposure"] = 0.2
            base["saturation"] = 1.3
            base["bloom"] = 0.5
            base["particles"] = "gold_sparkle"
            base["film_grain"] = 0.05
            base["motion_blur"] = 0.3
        elif scene.name == "Boss":
            base["contrast"] = 1.4
            base["shadow"] = -5.0
            base["temperature"] = 5500.0
            base["film_grain"] = 0.12
            base["motion_blur"] = 0.6
        elif scene.name == "CTA":
            base["exposure"] = 0.1
            base["contrast"] = 1.2
            base["sharpness"] = 0.7
            base["bloom"] = 0.3
            base["motion_blur"] = 0.2

        # 根据 DNA 颜色风格调整
        if dna.color_style == "Vibrant":
            base["saturation"] = 1.2
            base["contrast"] = 1.15
        elif dna.color_style == "Warm":
            base["temperature"] = 7000.0
            base["tint"] = 5.0
            base["saturation"] = 1.1
        elif dna.color_style == "Cool":
            base["temperature"] = 4500.0
            base["tint"] = -5.0
            base["saturation"] = 0.95
        elif dna.color_style == "Dark":
            base["exposure"] = -0.2
            base["shadow"] = -10.0
            base["contrast"] = 1.3
            base["film_grain"] = 0.12

        return SceneEditingSpec(
            scene_id=scene.scene_id,
            scene_name=scene.name,
            exposure=round(base["exposure"], 2),
            contrast=round(base["contrast"], 2),
            highlight=round(base["highlight"], 1),
            shadow=round(base["shadow"], 1),
            temperature=round(base["temperature"], 0),
            tint=round(base["tint"], 1),
            saturation=round(base["saturation"], 2),
            sharpness=round(base["sharpness"], 2),
            film_grain=round(base["film_grain"], 2),
            bloom=round(base["bloom"], 2),
            chromatic=round(base["chromatic"], 2),
            particles=base["particles"],
            lut=lut,
            motion_blur=round(base["motion_blur"], 2),
        )
