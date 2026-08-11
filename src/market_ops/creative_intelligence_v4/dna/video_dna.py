"""V4.0: Video DNA — structured creative DNA for video ads.

Extracted from Facebook video ads. 24 dimensions.
Compatible with existing video_intelligence/models.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoDNA:
    """Complete Video Creative DNA from Facebook ad analysis.

    Compatible with existing video_intelligence VideoDNA model.
    """
    dna_type: str = "video"

    # Opening
    opening_hook: str = ""           # "merge_surprise", "fail_react", "collection_showcase"
    ai_opening: bool = False         # AI-generated opening or real footage
    opening_duration_ms: int = 0     # first 3 seconds

    # Gameplay
    gameplay_start_ms: int = 0
    gameplay_structure: str = ""     # "linear", "loop", "spiral", "showcase"
    gameplay_density: float = 0.0    # how much gameplay is shown

    # Reward
    reward_timing_ms: int = 0        # when reward is shown
    reward_type: str = ""            # "evolution", "treasure", "collection", "victory"

    # Ending
    ending_type: str = ""            # "cta", "logo", "gameplay_loop", "reward_showcase"
    ending_duration_ms: int = 0

    # CTA
    cta_text: str = ""               # "Play Now", "Download"
    cta_timing_ms: int = 0

    # Camera
    camera_motion: str = ""          # "static", "pan", "zoom", "tracking"
    camera_distance: str = ""        # "close_up", "medium", "wide", "extreme_close"
    transitions: str = ""            # "cut", "dissolve", "wipe", "zoom_transition"

    # Editing
    cut_rhythm: str = ""             # "fast", "medium", "slow", "variable"
    duration_ms: int = 0

    # Audio
    music: str = ""                  # "epic", "upbeat", "magical", "tense", "none"
    sfx: str = ""                    # "merge_sound", "reward_chime", "level_up"
    voice: str = ""                  # "narrator", "character", "none"

    # Story & Emotion
    emotion_curve: str = ""          # "surprise→excitement", "tension→relief", "curiosity→satisfaction"
    story_arc: str = ""              # "problem→solution", "challenge→reward", "collection→complete"
    hook_type: str = ""              # "question", "shock", "curiosity", "fail", "challenge"

    # Brand
    brand: str = ""
    style: str = ""                  # "cartoon", "gameplay_capture", "mixed_media"

    # Source
    source_creative_id: str = ""
    facebook_video_id: str = ""
    eagle_local_path: str = ""
    confidence: float = 0.0

    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_type": self.dna_type,
            "opening_hook": self.opening_hook,
            "ai_opening": self.ai_opening,
            "opening_duration_ms": self.opening_duration_ms,
            "gameplay_start_ms": self.gameplay_start_ms,
            "gameplay_structure": self.gameplay_structure,
            "gameplay_density": self.gameplay_density,
            "reward_timing_ms": self.reward_timing_ms,
            "reward_type": self.reward_type,
            "ending_type": self.ending_type,
            "ending_duration_ms": self.ending_duration_ms,
            "cta_text": self.cta_text,
            "cta_timing_ms": self.cta_timing_ms,
            "camera_motion": self.camera_motion,
            "camera_distance": self.camera_distance,
            "transitions": self.transitions,
            "cut_rhythm": self.cut_rhythm,
            "duration_ms": self.duration_ms,
            "music": self.music,
            "sfx": self.sfx,
            "voice": self.voice,
            "emotion_curve": self.emotion_curve,
            "story_arc": self.story_arc,
            "hook_type": self.hook_type,
            "brand": self.brand,
            "style": self.style,
            "source_creative_id": self.source_creative_id,
            "facebook_video_id": self.facebook_video_id,
            "eagle_local_path": self.eagle_local_path,
            "confidence": self.confidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VideoDNA:
        return cls(
            dna_type=data.get("dna_type", "video"),
            opening_hook=data.get("opening_hook", ""),
            ai_opening=data.get("ai_opening", False),
            opening_duration_ms=data.get("opening_duration_ms", 0),
            gameplay_start_ms=data.get("gameplay_start_ms", 0),
            gameplay_structure=data.get("gameplay_structure", ""),
            gameplay_density=data.get("gameplay_density", 0),
            reward_timing_ms=data.get("reward_timing_ms", 0),
            reward_type=data.get("reward_type", ""),
            ending_type=data.get("ending_type", ""),
            ending_duration_ms=data.get("ending_duration_ms", 0),
            cta_text=data.get("cta_text", ""),
            cta_timing_ms=data.get("cta_timing_ms", 0),
            camera_motion=data.get("camera_motion", ""),
            camera_distance=data.get("camera_distance", ""),
            transitions=data.get("transitions", ""),
            cut_rhythm=data.get("cut_rhythm", ""),
            duration_ms=data.get("duration_ms", 0),
            music=data.get("music", ""),
            sfx=data.get("sfx", ""),
            voice=data.get("voice", ""),
            emotion_curve=data.get("emotion_curve", ""),
            story_arc=data.get("story_arc", ""),
            hook_type=data.get("hook_type", ""),
            brand=data.get("brand", ""),
            style=data.get("style", ""),
            source_creative_id=data.get("source_creative_id", ""),
            facebook_video_id=data.get("facebook_video_id", ""),
            eagle_local_path=data.get("eagle_local_path", ""),
            confidence=data.get("confidence", 0),
            notes=data.get("notes", ""),
        )