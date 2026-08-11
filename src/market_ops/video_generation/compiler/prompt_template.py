"""Prompt Template - 提示词模板系统"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PromptToken:
    type: str
    content: str
    weight: float = 1.0
    tags: List[str] = field(default_factory=list)


@dataclass
class PromptAST:
    """Prompt 抽象语法树"""
    tokens: List[PromptToken] = field(default_factory=list)
    camera_spec: Dict[str, Any] = field(default_factory=dict)
    shot_info: Dict[str, Any] = field(default_factory=dict)
    editing_spec: Dict[str, Any] = field(default_factory=dict)
    asset_spec: Dict[str, Any] = field(default_factory=dict)
    subtitle_spec: Dict[str, Any] = field(default_factory=dict)
    music_spec: Dict[str, Any] = field(default_factory=dict)


class PromptTemplate:
    """提示词模板管理器"""

    CAMERA_TEMPLATE = {
        "lens": "{lens} lens",
        "move": "{move} camera movement",
        "move_speed": "{move_speed} speed",
        "zoom": "zoom {zoom}",
        "focus": "focus on {focus}",
        "depth": "{depth} depth of field",
        "shake": "{shake} camera shake",
        "frame_rate": "{frame_rate}fps",
        "fov": "{fov} field of view",
    }

    EDITING_TEMPLATE = {
        "exposure": "exposure {exposure}",
        "contrast": "contrast {contrast}",
        "temperature": "color temperature {temperature}K",
        "saturation": "saturation {saturation}",
        "sharpness": "sharpness {sharpness}",
        "film_grain": "film grain {film_grain}",
        "bloom": "bloom {bloom}",
        "lut": "{lut} color grading",
    }

    STYLE_TEMPLATE = [
        "cinematic",
        "high quality",
        "professional",
        "cinematic lighting",
        "8k resolution",
    ]

    @classmethod
    def generate_camera_prompt(cls, camera_spec: Dict[str, Any]) -> List[str]:
        """从 Camera Spec 生成提示词"""
        prompts = []
        for key, template in cls.CAMERA_TEMPLATE.items():
            if key in camera_spec and camera_spec[key]:
                prompts.append(template.format(**camera_spec))
        return prompts

    @classmethod
    def generate_editing_prompt(cls, editing_spec: Dict[str, Any]) -> List[str]:
        """从 Editing Spec 生成提示词"""
        prompts = []
        for key, template in cls.EDITING_TEMPLATE.items():
            if key in editing_spec and editing_spec[key]:
                if isinstance(editing_spec[key], float):
                    prompts.append(template.format(**{key: f"{editing_spec[key]:.2f}"}))
                else:
                    prompts.append(template.format(**editing_spec))
        return prompts

    @classmethod
    def generate_asset_prompt(cls, asset_spec: Dict[str, Any]) -> List[str]:
        """从 Asset Spec 生成提示词"""
        prompts = []
        if asset_spec.get("character"):
            prompts.append(f"main character: {asset_spec['character']}")
        if asset_spec.get("environment"):
            prompts.append(f"environment: {asset_spec['environment']}")
        if asset_spec.get("background"):
            prompts.append(f"background: {asset_spec['background']}")
        if asset_spec.get("fx"):
            if isinstance(asset_spec["fx"], list):
                prompts.append(f"special effects: {', '.join(asset_spec['fx'])}")
            else:
                prompts.append(f"special effects: {asset_spec['fx']}")
        if asset_spec.get("particles"):
            prompts.append(f"particles: {asset_spec['particles']}")
        return prompts