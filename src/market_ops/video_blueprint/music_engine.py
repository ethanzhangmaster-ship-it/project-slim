"""Music Engine - 音乐引擎

生成完整 Timeline:
Intro / Build / Drop / Reward Rise / CTA Rise / Ending

每段:
Start / End / Energy / Mood / BPM / Genre / Beat Marker
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MusicSegment:
    """音乐段落"""
    name: str
    start: float
    end: float
    energy: str
    mood: str
    bpm: int
    genre: str = ""
    beat_marker: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "energy": self.energy,
            "mood": self.mood,
            "bpm": self.bpm,
            "genre": self.genre,
            "beat_marker": self.beat_marker,
        }


@dataclass
class MusicProfile:
    """音乐配置"""
    variant_id: str
    bpm: int
    mood: str
    genre: str
    segments: list[MusicSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "bpm": self.bpm,
            "mood": self.mood,
            "genre": self.genre,
            "segments": [s.to_dict() for s in self.segments],
        }


class MusicEngine:
    """音乐引擎"""

    STYLE_CONFIG: dict[str, dict[str, Any]] = {
        "Epic": {"bpm": 130, "mood": "Dramatic", "genre": "Epic Orchestral"},
        "Upbeat": {"bpm": 140, "mood": "Excited", "genre": "Electronic Pop"},
        "Ambient": {"bpm": 100, "mood": "Calm", "genre": "Ambient"},
        "Dramatic": {"bpm": 120, "mood": "Tense", "genre": "Dramatic Cinematic"},
    }

    def generate(self, dna: VideoDNA, blueprint: VideoBlueprint) -> MusicProfile:
        """根据 Video DNA 和 Blueprint 生成音乐配置"""
        config = self.STYLE_CONFIG.get(dna.music_style, self.STYLE_CONFIG["Upbeat"])
        duration = blueprint.video_length
        bpm = config["bpm"]
        genre = config["genre"]

        segments = []
        blueprint_segs = blueprint.segments
        n = len(blueprint_segs)

        for i, seg in enumerate(blueprint_segs):
            name = seg["name"]
            start = seg["start"]
            end = seg["end"]

            if i == 0:
                music_name = "Intro"
                energy = "low"
            elif i == n - 1:
                music_name = "CTA Rise"
                energy = "peak"
            elif name in ("Boss", "Battle", "Attack"):
                music_name = "Drop"
                energy = "high"
            elif name in ("Reward", "Victory", "LevelUp"):
                music_name = "Reward Rise"
                energy = "high"
            elif i < n // 2:
                music_name = "Build"
                energy = "medium"
            else:
                music_name = "Build"
                energy = "medium"

            beat_marker = self._generate_beat_markers(start, end, bpm)

            segments.append(MusicSegment(
                name=music_name,
                start=start,
                end=end,
                energy=energy,
                mood=config["mood"],
                bpm=bpm,
                genre=genre,
                beat_marker=beat_marker,
            ))

        return MusicProfile(
            variant_id=dna.variant_id,
            bpm=bpm,
            mood=config["mood"],
            genre=genre,
            segments=segments,
        )

    def _generate_beat_markers(self, start: float, end: float, bpm: int) -> list[float]:
        """生成节拍标记"""
        beat_interval = 60.0 / bpm
        markers = []
        t = start
        while t <= end:
            markers.append(round(t, 2))
            t += beat_interval
        return markers[:8]  # 最多8个标记
