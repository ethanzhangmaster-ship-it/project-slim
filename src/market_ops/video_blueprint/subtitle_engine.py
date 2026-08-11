"""Subtitle Engine - 字幕引擎

每个 Scene 输出完整字幕规范。

参数:
  Caption / Voice / Popup / Reward Text / CTA Overlay
  Font / Color / Animation / Timing
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneSubtitleSpec:
    """单个 Scene 的字幕规范"""
    scene_id: str
    scene_name: str
    caption: str = "default"
    voice: str = "default_voice"
    popup: str = "default"
    reward_text: str = "default"
    cta_overlay: str = "default"
    font: str = "Montserrat"
    color: str = "#FFFFFF"
    animation: str = "fade"
    timing: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "caption": self.caption,
            "voice": self.voice,
            "popup": self.popup,
            "reward_text": self.reward_text,
            "cta_overlay": self.cta_overlay,
            "font": self.font,
            "color": self.color,
            "animation": self.animation,
            "timing": self.timing,
        }


@dataclass
class SubtitleProfile:
    """字幕配置"""
    variant_id: str
    scenes: list[SceneSubtitleSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "scenes": [s.to_dict() for s in self.scenes],
        }


class SubtitleEngine:
    """字幕引擎"""

    SCENE_SUBTITLES: dict[str, dict[str, Any]] = {
        "Hook": {"caption": "Merge Faster!", "popup": "WOW!", "voice": "female_excited"},
        "Opening": {"caption": "Discover the truth!", "popup": "default", "voice": "female_calm"},
        "Search": {"caption": "Where is it?", "popup": "default", "voice": "female_curious"},
        "Think": {"caption": "Hmm...", "popup": "default", "voice": "female_thinking"},
        "Collect": {"caption": "Collect!", "popup": "+1", "voice": "female_excited"},
        "Merge": {"caption": "Merge!", "popup": "MERGE!", "voice": "female_excited"},
        "Match": {"caption": "Match 3!", "popup": "COMBO!", "voice": "female_excited"},
        "Boss": {"caption": "Boss Battle!", "popup": "DANGER!", "voice": "female_dramatic"},
        "Attack": {"caption": "Attack!", "popup": "CRITICAL!", "voice": "female_dramatic"},
        "Special": {"caption": "Special Move!", "popup": "ULTIMATE!", "voice": "female_dramatic"},
        "Fail": {"caption": "Almost!", "popup": "TRY AGAIN", "voice": "female_sad"},
        "Retry": {"caption": "One more time!", "popup": "default", "voice": "female_determined"},
        "Victory": {"caption": "Victory!", "popup": "VICTORY!", "voice": "female_excited"},
        "Reward": {"caption": "Legendary Reward!", "popup": "LEGENDARY!", "reward_text": "Legendary Item", "voice": "female_excited"},
        "LevelUp": {"caption": "Level Up!", "popup": "LEVEL UP!", "voice": "female_excited"},
        "CTA": {"caption": "Play Now!", "popup": "default", "cta_overlay": "PLAY NOW", "voice": "female_urgent"},
    }

    def generate(self, dna: VideoDNA, blueprint: VideoBlueprint) -> SubtitleProfile:
        """根据 Video DNA 和 Blueprint 生成每个 Scene 的字幕规范"""
        scenes = []

        for seg in blueprint.segments:
            name = seg["name"]
            tpl = self.SCENE_SUBTITLES.get(name, self.SCENE_SUBTITLES["Hook"])
            start = seg["start"]
            end = seg["end"]

            spec = SceneSubtitleSpec(
                scene_id=seg.get("scene_id", f"scene_{name}"),
                scene_name=name,
                caption=tpl.get("caption", "default"),
                voice=tpl.get("voice", "default_voice"),
                popup=tpl.get("popup", "default"),
                reward_text=tpl.get("reward_text", "default"),
                cta_overlay=tpl.get("cta_overlay", "default"),
                font="Montserrat Bold" if dna.subtitle_style == "Bold" else "Montserrat",
                color="#FFD700" if name in ("Reward", "Victory") else "#FFFFFF",
                animation=self._get_animation(name),
                timing=[round(start, 1), round(end, 1)],
            )
            scenes.append(spec)

        return SubtitleProfile(
            variant_id=dna.variant_id,
            scenes=scenes,
        )

    def _get_animation(self, scene_name: str) -> str:
        mapping = {
            "Hook": "pop",
            "Reward": "pulse",
            "Victory": "pulse",
            "LevelUp": "zoom_in",
            "CTA": "slide_up",
            "Boss": "shake",
        }
        return mapping.get(scene_name, "fade")
