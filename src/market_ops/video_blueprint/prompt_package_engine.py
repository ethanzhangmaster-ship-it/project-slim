"""Prompt Package Engine - Prompt 包引擎

每个 Scene 输出完整 Prompt。
包括:
Scene Prompt
Camera Prompt
Motion Prompt
Lighting Prompt
Style Prompt
Negative Prompt

方便人工复制或 AI 调用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptPackage:
    """Prompt 包"""
    scene_id: str
    scene_name: str
    image_prompt: str = ""
    video_prompt: str = ""
    motion_prompt: str = ""
    character_prompt: str = ""
    lighting_prompt: str = ""
    negative_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "image_prompt": self.image_prompt,
            "video_prompt": self.video_prompt,
            "motion_prompt": self.motion_prompt,
            "character_prompt": self.character_prompt,
            "lighting_prompt": self.lighting_prompt,
            "negative_prompt": self.negative_prompt,
        }


@dataclass
class PromptPackageCollection:
    """Prompt 包集合"""
    package_id: str
    variant_id: str
    packages: list[PromptPackage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "variant_id": self.variant_id,
            "packages": [p.to_dict() for p in self.packages],
        }


class PromptPackageEngine:
    """Prompt 包引擎"""

    # 风格模板
    STYLE_TEMPLATES: dict[str, str] = {
        "Vibrant": "vibrant colors, high saturation, playful atmosphere",
        "Warm": "warm tones, golden hour, cozy feeling",
        "Cool": "cool tones, blue accents, mysterious atmosphere",
        "Dark": "dark mood, dramatic shadows, intense lighting",
    }

    # 灯光模板
    LIGHTING_TEMPLATES: dict[str, str] = {
        "Golden": "golden hour lighting, warm rim light, soft fill",
        "Cool": "cool blue lighting, moonlight effect, subtle highlights",
        "Dramatic": "dramatic side lighting, strong contrast, deep shadows",
        "Soft": "soft diffused lighting, gentle shadows, even exposure",
        "Flash": "bright flash lighting, high contrast, vivid colors",
    }

    # 负面提示词
    DEFAULT_NEGATIVE: str = (
        "low quality, blurry, distorted, watermark, text overlay, "
        "deformed hands, extra fingers, bad anatomy, noisy, grainy"
    )

    def generate(self, dna: VideoDNA, storyboard: Storyboard) -> PromptPackageCollection:
        """根据 Video DNA 和 Storyboard 生成 Prompt 包"""
        packages = []
        style = self.STYLE_TEMPLATES.get(dna.color_style, self.STYLE_TEMPLATES["Vibrant"])
        lighting = self.LIGHTING_TEMPLATES.get(dna.lighting_style, self.LIGHTING_TEMPLATES["Golden"])

        dna_data = dna.metadata.get("dna_data", {}) if dna.metadata else {}
        character_type = dna_data.get("character", {}).get("type", "character")

        for scene in storyboard.scenes:
            image_prompt = self._build_image_prompt(scene, dna)
            video_prompt = f"Camera: {scene.camera}, dynamic composition, cinematic framing"
            motion_prompt = f"Motion: {scene.motion}, fluid movement, smooth transitions"
            character_prompt = f"Character: {character_type}, {style}, mobile game aesthetic"
            lighting_prompt = f"Lighting: {lighting}"

            packages.append(PromptPackage(
                scene_id=scene.scene_id,
                scene_name=scene.name,
                image_prompt=image_prompt,
                video_prompt=video_prompt,
                motion_prompt=motion_prompt,
                character_prompt=character_prompt,
                lighting_prompt=lighting_prompt,
                negative_prompt=self.DEFAULT_NEGATIVE,
            ))

        return PromptPackageCollection(
            package_id=f"prompts_{dna.variant_id}",
            variant_id=dna.variant_id,
            packages=packages,
        )

    def _build_image_prompt(self, scene: StoryboardScene, dna: VideoDNA) -> str:
        """构建图像 Prompt"""
        return (
            f"{scene.description}. {scene.motion}. "
            f"Mobile game advertisement scene. "
            f"High quality, cinematic, engaging. "
            f"{dna.hook} style, {dna.emotion} mood."
        )
