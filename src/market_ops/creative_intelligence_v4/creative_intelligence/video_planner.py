"""V4.0: Video Planner — hybrid AI + Eagle gameplay planning.

Video production pipeline:
  AI Opening (Lovart/Seedance/Runway)
    → Eagle Gameplay (real footage)
    → Reward Showcase
    → AI Ending + CTA

This is a planner, not a renderer. It produces a VideoPlan
that the VideoGenerator can execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..dna.video_dna import VideoDNA


@dataclass
class VideoSegment:
    """A single segment in a video plan."""
    segment_type: str = ""     # "ai_opening", "eagle_gameplay", "reward", "ai_ending"
    source: str = ""           # "ai" or "eagle"
    duration_ms: int = 0
    start_ms: int = 0
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoPlan:
    """Complete video production plan."""
    plan_id: str = ""
    total_duration_ms: int = 0
    segments: list[VideoSegment] = field(default_factory=list)
    target_aspect_ratio: str = "9:16"
    target_platform: str = "facebook"
    dna_source: VideoDNA | None = None
    strategy: str = "balanced"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "total_duration_ms": self.total_duration_ms,
            "segments": [
                {
                    "segment_type": s.segment_type,
                    "source": s.source,
                    "duration_ms": s.duration_ms,
                    "start_ms": s.start_ms,
                    "description": s.description,
                    "params": s.params,
                }
                for s in self.segments
            ],
            "target_aspect_ratio": self.target_aspect_ratio,
            "target_platform": self.target_platform,
            "strategy": self.strategy,
        }


class VideoPlanner:
    """Plans video production using hybrid AI + Eagle gameplay.

    The video structure:
      [0-3s]   AI Opening (Hook)
      [3s-N-3s] Eagle Gameplay (real footage)
      [N-3s-N]  Reward Showcase
      [N-15s]   AI Ending + CTA
    """

    # Standard video durations per platform
    DURATIONS = {
        "facebook": 15000,   # 15s
        "instagram": 15000,  # 15s
        "tiktok": 15000,     # 15s
    }

    def __init__(self) -> None:
        pass

    def plan(self, dna: VideoDNA, platform: str = "facebook") -> VideoPlan:
        """Create a video production plan from Video DNA."""
        total_duration = self.DURATIONS.get(platform, 15000)
        opening_duration = 3000
        ending_duration = 2000
        reward_duration = 2000

        gameplay_duration = total_duration - opening_duration - ending_duration
        if gameplay_duration < 0:
            gameplay_duration = 5000
            total_duration = opening_duration + gameplay_duration + ending_duration

        segments = []

        # 1. AI Opening
        segments.append(VideoSegment(
            segment_type="ai_opening",
            source="ai",
            duration_ms=opening_duration,
            start_ms=0,
            description=f"AI-generated opening hook: {dna.opening_hook}",
            params={
                "hook_type": dna.opening_hook,
                "emotion": dna.emotion_curve,
                "ai_opening": dna.ai_opening,
            },
        ))

        # 2. Eagle Gameplay
        segments.append(VideoSegment(
            segment_type="eagle_gameplay",
            source="eagle",
            duration_ms=gameplay_duration,
            start_ms=opening_duration,
            description=f"Real gameplay featuring {dna.gameplay_structure}",
            params={
                "eagle_path": dna.eagle_local_path,
                "structure": dna.gameplay_structure,
                "camera_motion": dna.camera_motion,
            },
        ))

        # 3. Reward Showcase
        reward_start = opening_duration + gameplay_duration
        segments.append(VideoSegment(
            segment_type="reward",
            source="eagle",
            duration_ms=reward_duration,
            start_ms=reward_start,
            description=f"Reward moment: {dna.reward_type}",
            params={
                "reward_type": dna.reward_type,
                "music": dna.music,
                "sfx": dna.sfx,
            },
        ))

        # 4. AI Ending + CTA
        ending_start = reward_start + reward_duration
        segments.append(VideoSegment(
            segment_type="ai_ending",
            source="ai",
            duration_ms=ending_duration,
            start_ms=ending_start,
            description=f"AI-generated ending with CTA: {dna.cta_text}",
            params={
                "cta_text": dna.cta_text,
                "ending_type": dna.ending_type,
                "brand": dna.brand,
            },
        ))

        return VideoPlan(
            plan_id=f"video_plan_{dna.source_creative_id}",
            total_duration_ms=total_duration,
            segments=segments,
            target_aspect_ratio="9:16",
            target_platform=platform,
            dna_source=dna,
        )