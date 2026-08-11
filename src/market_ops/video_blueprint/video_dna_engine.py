"""Video DNA Engine - Video DNA 中央引擎

所有模块不得独立决策，必须引用 Video DNA。

Video DNA Schema:
- hook
- emotion
- story_pattern
- camera_style
- editing_style
- music_style
- subtitle_style
- transition_style
- color_style
- lighting_style
- cta_style
- rhythm
- platform
- placement
- audience

后续所有模块共享这一份 DNA。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoDNA:
    """Video DNA - 视频创意基因"""
    variant_id: str
    hook: str = ""                    # Collection / Merge / Boss / Puzzle 等
    emotion: str = ""                 # Curiosity / Urgency / Excitement / Wonder
    story_pattern: str = ""           # Discovery / Challenge / Journey / Surprise
    camera_style: str = ""            # Tracking / Zoom / Orbit / Static
    editing_style: str = ""           # Fast Cut / Smooth / Cinematic
    music_style: str = ""             # Epic / Upbeat / Ambient / Dramatic
    subtitle_style: str = ""          # Bold / Minimal / Animated
    transition_style: str = ""        # Cut / Flash / Whip / Blur
    color_style: str = ""             # Vibrant / Warm / Cool / Dark
    lighting_style: str = ""          # Golden / Cool / Dramatic / Soft
    cta_style: str = ""               # Button / Overlay / Character Point
    rhythm: str = ""                  # Fast / Medium / Slow / Explosive
    platform: str = ""                # facebook / tiktok / google
    placement: str = ""               # reels / feed / story / display
    audience: str = ""                # Female 35+ / Male 25-34
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "hook": self.hook,
            "emotion": self.emotion,
            "story_pattern": self.story_pattern,
            "camera_style": self.camera_style,
            "editing_style": self.editing_style,
            "music_style": self.music_style,
            "subtitle_style": self.subtitle_style,
            "transition_style": self.transition_style,
            "color_style": self.color_style,
            "lighting_style": self.lighting_style,
            "cta_style": self.cta_style,
            "rhythm": self.rhythm,
            "platform": self.platform,
            "placement": self.placement,
            "audience": self.audience,
            "metadata": self.metadata,
        }


class VideoDNAEngine:
    """Video DNA 中央引擎

    从 Decision Variant 提取 Video DNA。
    所有后续模块必须引用这一份 DNA。
    """

    # 维度变化 → Video DNA 映射
    DIM_TO_DNA: dict[str, dict[str, str]] = {
        "lighting_temperature": {
            "hook": "Transformation",
            "emotion": "Curiosity",
            "story_pattern": "Discovery",
            "camera_style": "Zoom",
            "editing_style": "Fast Cut",
            "music_style": "Epic",
            "subtitle_style": "Bold",
            "transition_style": "Flash",
            "color_style": "Warm",
            "lighting_style": "Golden",
            "cta_style": "Button",
            "rhythm": "Fast",
        },
        "color_palette": {
            "hook": "Collection",
            "emotion": "Excitement",
            "story_pattern": "Journey",
            "camera_style": "Tracking",
            "editing_style": "Fast Cut",
            "music_style": "Upbeat",
            "subtitle_style": "Animated",
            "transition_style": "Cut",
            "color_style": "Vibrant",
            "lighting_style": "Cool",
            "cta_style": "Overlay",
            "rhythm": "Medium",
        },
        "creature": {
            "hook": "Boss",
            "emotion": "Urgency",
            "story_pattern": "Challenge",
            "camera_style": "Orbit",
            "editing_style": "Cinematic",
            "music_style": "Dramatic",
            "subtitle_style": "Bold",
            "transition_style": "Shake",
            "color_style": "Dark",
            "lighting_style": "Dramatic",
            "cta_style": "Character Point",
            "rhythm": "Explosive",
        },
        "character": {
            "hook": "Story",
            "emotion": "Wonder",
            "story_pattern": "Journey",
            "camera_style": "Follow",
            "editing_style": "Smooth",
            "music_style": "Ambient",
            "subtitle_style": "Minimal",
            "transition_style": "Blur",
            "color_style": "Warm",
            "lighting_style": "Soft",
            "cta_style": "Character Point",
            "rhythm": "Medium",
        },
        "background": {
            "hook": "Discovery",
            "emotion": "Curiosity",
            "story_pattern": "Discovery",
            "camera_style": "Pan",
            "editing_style": "Smooth",
            "music_style": "Ambient",
            "subtitle_style": "Minimal",
            "transition_style": "Blur",
            "color_style": "Vibrant",
            "lighting_style": "Golden",
            "cta_style": "Button",
            "rhythm": "Medium",
        },
        "hook_type": {
            "hook": "Surprise",
            "emotion": "Excitement",
            "story_pattern": "Surprise",
            "camera_style": "Zoom",
            "editing_style": "Fast Cut",
            "music_style": "Upbeat",
            "subtitle_style": "Animated",
            "transition_style": "Flash",
            "color_style": "Vibrant",
            "lighting_style": "Flash",
            "cta_style": "Overlay",
            "rhythm": "Fast",
        },
    }

    def generate(self, variant: dict[str, Any]) -> VideoDNA:
        """从 Decision Variant 生成 Video DNA"""
        variant_id = variant.get("variant_id", "unknown")
        dim = variant.get("changed_dimension", "")
        dna_map = self.DIM_TO_DNA.get(dim, self.DIM_TO_DNA["lighting_temperature"])

        # 平台/版位处理
        platform = variant.get("platform", "facebook")
        placement_raw = variant.get("placement", "reels")
        if isinstance(placement_raw, dict):
            placement = placement_raw.get("primary", "reels")
        else:
            placement = str(placement_raw).lower()

        return VideoDNA(
            variant_id=variant_id,
            hook=dna_map["hook"],
            emotion=dna_map["emotion"],
            story_pattern=dna_map["story_pattern"],
            camera_style=dna_map["camera_style"],
            editing_style=dna_map["editing_style"],
            music_style=dna_map["music_style"],
            subtitle_style=dna_map["subtitle_style"],
            transition_style=dna_map["transition_style"],
            color_style=dna_map["color_style"],
            lighting_style=dna_map["lighting_style"],
            cta_style=dna_map["cta_style"],
            rhythm=dna_map["rhythm"],
            platform=platform.lower(),
            placement=placement.lower(),
            audience=variant.get("audience", "Female 35+"),
            metadata={
                "decision_score": variant.get("decision_score"),
                "predicted_ctr": variant.get("predicted_ctr"),
                "predicted_roas": variant.get("predicted_roas"),
                "changed_dimension": dim,
                "risk_level": variant.get("risk_level"),
                "dna_data": variant.get("dna", {}),
            },
        )
