"""Master Prompt Models - 统一模型定义"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CameraMetadata:
    lens: str = ""
    move: str = ""
    move_speed: str = ""
    zoom: str = ""
    focus: str = ""
    depth: str = ""
    shake: str = ""
    frame_rate: int = 60
    fov: str = ""


@dataclass
class EditingMetadata:
    exposure: float = 0.0
    contrast: float = 1.0
    highlight: float = 0.0
    shadow: float = 0.0
    temperature: int = 5500
    tint: int = 0
    saturation: float = 1.0
    sharpness: float = 1.0
    film_grain: float = 0.0
    bloom: float = 0.0
    chromatic: float = 0.0
    motion_blur: float = 0.0
    particles: str = ""
    lut: str = ""


@dataclass
class SubtitleMetadata:
    caption: str = ""
    voice: str = ""
    popup: str = ""
    reward_text: str = ""
    cta_overlay: str = ""
    font: str = ""
    color: str = ""
    animation: str = ""
    timing: str = ""


@dataclass
class MusicMetadata:
    genre: str = ""
    mood: str = ""
    energy: str = ""
    bpm: int = 0
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    beat_marker: List[float] = field(default_factory=list)


@dataclass
class Metadata:
    camera: CameraMetadata = field(default_factory=CameraMetadata)
    editing: EditingMetadata = field(default_factory=EditingMetadata)
    subtitle: SubtitleMetadata = field(default_factory=SubtitleMetadata)
    music: MusicMetadata = field(default_factory=MusicMetadata)


@dataclass
class ScenePrompt:
    scene_id: str = ""
    image_prompt: str = ""
    video_prompt: str = ""
    motion_prompt: str = ""
    lighting_prompt: str = ""
    character_prompt: str = ""
    negative_prompt: str = ""
    metadata: Metadata = field(default_factory=Metadata)


@dataclass
class PromptToken:
    content: str = ""
    type: str = ""
    weight: float = 1.0
    tags: List[str] = field(default_factory=list)


@dataclass
class PromptAST:
    tokens: List[PromptToken] = field(default_factory=list)
    scene_id: str = ""


@dataclass
class CompilerContext:
    camera_specs: List[Dict[str, Any]] = field(default_factory=list)
    shot_lists: List[Dict[str, Any]] = field(default_factory=list)
    asset_specs: List[Dict[str, Any]] = field(default_factory=list)
    editing_specs: List[Dict[str, Any]] = field(default_factory=list)
    subtitle_specs: List[Dict[str, Any]] = field(default_factory=list)
    music_specs: List[Dict[str, Any]] = field(default_factory=list)
    prompt_packages: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationResult:
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PromptStatistics:
    total_tokens: int = 0
    total_prompts: int = 0
    avg_length: float = 0.0
    duplicate_rate: float = 0.0
    compression_rate: float = 0.0


@dataclass
class MasterPrompt:
    variant_id: str = ""
    scenes: List[ScenePrompt] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "scenes": [asdict(scene) for scene in self.scenes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        md_lines = []
        md_lines.append(f"# Master Prompt - {self.variant_id}")
        md_lines.append("")
        for scene in self.scenes:
            md_lines.append(f"## {scene.scene_id}")
            md_lines.append("")
            md_lines.append("### Image Prompt")
            md_lines.append(f"> {scene.image_prompt}")
            md_lines.append("")
            md_lines.append("### Video Prompt")
            md_lines.append(f"> {scene.video_prompt}")
            md_lines.append("")
            md_lines.append("### Motion Prompt")
            md_lines.append(f"> {scene.motion_prompt}")
            md_lines.append("")
            md_lines.append("### Lighting Prompt")
            md_lines.append(f"> {scene.lighting_prompt}")
            md_lines.append("")
            md_lines.append("### Character Prompt")
            md_lines.append(f"> {scene.character_prompt}")
            md_lines.append("")
            md_lines.append("### Negative Prompt")
            md_lines.append(f"> {scene.negative_prompt}")
            md_lines.append("")
        return "\n".join(md_lines)

    def to_text(self) -> str:
        lines = []
        lines.append(f"Master Prompt - {self.variant_id}")
        lines.append("=" * 60)
        for scene in self.scenes:
            lines.append(f"\n{scene.scene_id}")
            lines.append("-" * 40)
            lines.append(f"Image: {scene.image_prompt}")
            lines.append(f"Video: {scene.video_prompt}")
            lines.append(f"Motion: {scene.motion_prompt}")
            lines.append(f"Lighting: {scene.lighting_prompt}")
            lines.append(f"Character: {scene.character_prompt}")
            lines.append(f"Negative: {scene.negative_prompt}")
        return "\n".join(lines)