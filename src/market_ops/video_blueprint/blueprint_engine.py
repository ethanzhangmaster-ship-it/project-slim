"""Blueprint Engine - Video Blueprint 核心引擎

输入: Decision Variant + Video DNA
输出: Video Blueprint

Blueprint 包含:
Duration / Opening / Gameplay / Reward / CTA
Emotion / Hook / Audience / Platform / Placement / Story Pattern
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoBlueprint:
    """视频蓝图"""
    variant_id: str
    video_length: float
    segments: list[dict[str, Any]] = field(default_factory=list)
    emotion: str = ""
    hook: str = ""
    story_pattern: str = ""
    audience: str = ""
    platform: str = ""
    placement: str = ""
    country: str = ""
    dna: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "video_length": self.video_length,
            "segments": self.segments,
            "emotion": self.emotion,
            "hook": self.hook,
            "story_pattern": self.story_pattern,
            "audience": self.audience,
            "platform": self.platform,
            "placement": self.placement,
            "country": self.country,
            "dna": self.dna,
            "metadata": self.metadata,
        }


class BlueprintEngine:
    """Video Blueprint 核心引擎"""

    def generate(self, dna: VideoDNA, story_pattern: StoryPattern) -> VideoBlueprint:
        """根据 Video DNA 和 Story Pattern 生成 Blueprint"""
        duration = story_pattern.recommended_duration

        # 根据 Story Pattern 的段落比例计算时间
        segments = []
        current_time = 0.0
        for seg in story_pattern.segments:
            seg_duration = round(duration * seg.duration_ratio, 2)
            end_time = round(current_time + seg_duration, 2)
            segments.append({
                "name": seg.name,
                "start": current_time,
                "end": end_time,
                "duration": seg_duration,
                "description": seg.description,
                "required_elements": seg.required_elements,
            })
            current_time = end_time

        # 校正最后一段
        if segments:
            segments[-1]["end"] = duration
            segments[-1]["duration"] = round(duration - segments[-1]["start"], 2)

        return VideoBlueprint(
            variant_id=dna.variant_id,
            video_length=duration,
            segments=segments,
            emotion=dna.emotion,
            hook=dna.hook,
            story_pattern=dna.story_pattern,
            audience=dna.audience,
            platform=dna.platform,
            placement=dna.placement,
            country=dna.metadata.get("country", "US"),
            dna=dna.to_dict(),
            metadata={
                "pattern_id": story_pattern.pattern_id,
                "gameplay_type": story_pattern.gameplay_type,
                "total_segments": len(segments),
            },
        )
