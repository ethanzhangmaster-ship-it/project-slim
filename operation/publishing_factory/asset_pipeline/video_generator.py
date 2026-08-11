"""
E15.1.1 — Video (Preview) Generator
===================================

Deterministic App Preview / trailer storyboard. Emits a sequence of
scenes (caption + duration + shot type) — the brief, not rendered video.

Total duration capped at 30s (store limit). One scene per selling
point, deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from operation.publishing_factory.catalog.product_profile import GameProduct

_MAX_SECONDS = 30
_SCENE_SECONDS = 5


@dataclass
class VideoScene:
    index: int
    caption: str
    shot: str          # "gameplay" | "text_overlay" | "logo_sting"
    duration_s: int = _SCENE_SECONDS

    def to_dict(self) -> dict:
        return {"index": self.index, "caption": self.caption,
                "shot": self.shot, "duration_s": self.duration_s}


@dataclass
class VideoStoryboard:
    game_id: str
    total_seconds: int
    scenes: List[VideoScene] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "total_seconds": self.total_seconds,
                "scenes": [s.to_dict() for s in self.scenes]}


class VideoGenerator:
    """Builds a ≤30s preview storyboard from selling points."""

    def generate(self, product: GameProduct,
                 max_seconds: int = _MAX_SECONDS) -> VideoStoryboard:
        points = product.default_selling_points()
        n = max(1, min(len(points), max_seconds // _SCENE_SECONDS))
        scenes: List[VideoScene] = []
        for i in range(n):
            sp = points[i]
            if i == 0:
                shot, cap = "gameplay", f"Tap to {sp.lower()}"
            elif i == n - 1:
                shot, cap = "logo_sting", f"{product.display_name or product.game_id}"
            else:
                shot, cap = "text_overlay", sp
            scenes.append(VideoScene(index=i, caption=cap, shot=shot))
        total = min(n * _SCENE_SECONDS, max_seconds)
        return VideoStoryboard(game_id=product.game_id,
                               total_seconds=total, scenes=scenes)


__all__ = ["VideoGenerator", "VideoScene", "VideoStoryboard", "_MAX_SECONDS"]
