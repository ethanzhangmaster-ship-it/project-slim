"""Pacing Engine - 节奏控制引擎

输出完整 Timeline:
0~2: Fast
2~5: Normal
5~8: Explosion
8~10: Reward
10~15: CTA

同时输出:
Shot Density / Subtitle Speed / Transition Speed / Music Timeline
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PacingProfile:
    """节奏配置"""
    variant_id: str
    duration: float
    segments: list[dict[str, Any]] = field(default_factory=list)
    music_timeline: list[dict[str, Any]] = field(default_factory=list)
    shots_per_second: float = 0.0
    avg_shot_length: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "duration": self.duration,
            "segments": self.segments,
            "music_timeline": self.music_timeline,
            "shots_per_second": self.shots_per_second,
            "avg_shot_length": self.avg_shot_length,
        }


class PacingEngine:
    """节奏控制引擎"""

    def generate(self, dna: VideoDNA, blueprint: VideoBlueprint, shotlist: Shotlist) -> PacingProfile:
        """根据 Video DNA 和 Blueprint 生成节奏配置"""
        duration = blueprint.video_length
        rhythm = dna.rhythm

        # 基础节奏段
        if rhythm == "Fast":
            base_segments = [
                {"start": 0, "end": 2, "label": "Fast", "shots_per_sec": 1.5, "transition_speed": "fast", "subtitle_speed": "fast"},
                {"start": 2, "end": 5, "label": "Normal", "shots_per_sec": 1.0, "transition_speed": "normal", "subtitle_speed": "normal"},
                {"start": 5, "end": 8, "label": "Explosion", "shots_per_sec": 1.5, "transition_speed": "fastest", "subtitle_speed": "fast"},
                {"start": 8, "end": 10, "label": "Reward", "shots_per_sec": 1.0, "transition_speed": "normal", "subtitle_speed": "normal"},
                {"start": 10, "end": duration, "label": "CTA", "shots_per_sec": 1.5, "transition_speed": "fast", "subtitle_speed": "fast"},
            ]
        elif rhythm == "Medium":
            base_segments = [
                {"start": 0, "end": 3, "label": "Normal", "shots_per_sec": 1.0, "transition_speed": "normal", "subtitle_speed": "normal"},
                {"start": 3, "end": 8, "label": "Build", "shots_per_sec": 0.8, "transition_speed": "normal", "subtitle_speed": "normal"},
                {"start": 8, "end": 12, "label": "Reward", "shots_per_sec": 1.0, "transition_speed": "normal", "subtitle_speed": "normal"},
                {"start": 12, "end": duration, "label": "CTA", "shots_per_sec": 1.2, "transition_speed": "fast", "subtitle_speed": "fast"},
            ]
        else:  # Slow / Explosive
            base_segments = [
                {"start": 0, "end": 3, "label": "Slow", "shots_per_sec": 0.6, "transition_speed": "slow", "subtitle_speed": "slow"},
                {"start": 3, "end": 8, "label": "Build", "shots_per_sec": 0.8, "transition_speed": "normal", "subtitle_speed": "normal"},
                {"start": 8, "end": 12, "label": "Explosion", "shots_per_sec": 1.5, "transition_speed": "fastest", "subtitle_speed": "fast"},
                {"start": 12, "end": duration, "label": "CTA", "shots_per_sec": 1.0, "transition_speed": "normal", "subtitle_speed": "normal"},
            ]

        # 缩放
        segments = []
        scale = duration / 15.0
        for seg in base_segments:
            s_start = round(seg["start"] * scale, 1)
            s_end = round(min(seg["end"] * scale, duration), 1)
            if s_end > s_start:
                segments.append({
                    "start": s_start,
                    "end": s_end,
                    "label": seg["label"],
                    "shots_per_sec": seg["shots_per_sec"],
                    "transition_speed": seg["transition_speed"],
                    "subtitle_speed": seg["subtitle_speed"],
                })

        # Music Timeline
        music_timeline = self._build_music_timeline(duration, blueprint)

        # Shot stats
        shots_per_sec = shotlist.total_shots / max(1, shotlist.total_duration)
        avg_shot_length = shotlist.total_duration / max(1, shotlist.total_shots)

        return PacingProfile(
            variant_id=dna.variant_id,
            duration=duration,
            segments=segments,
            music_timeline=music_timeline,
            shots_per_second=round(shots_per_sec, 2),
            avg_shot_length=round(avg_shot_length, 2),
        )

    def _build_music_timeline(self, duration: float, blueprint: VideoBlueprint) -> list[dict[str, Any]]:
        """构建音乐时间线"""
        segments = blueprint.segments
        music_segments = []

        for seg in segments:
            name = seg["name"]
            energy = "medium"
            if name in ("Hook", "Opening"):
                energy = "low"
            elif name in ("Boss", "Explosion", "Victory"):
                energy = "high"
            elif name == "Reward":
                energy = "high"
            elif name == "CTA":
                energy = "peak"

            music_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "name": name,
                "energy": energy,
            })

        return music_segments
