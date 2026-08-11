"""
E15.1.1 — Asset Validator
==========================

Checks generated asset specs against hard store rules BEFORE they are
ever handed to a human for rendering/submit. Pure rule checks.

Rules (deterministic, documented):
  - screenshots: 2..8 frames
  - headline length <= 45 chars
  - subheadline length <= 60 chars
  - every screenshot has a non-empty layout + palette
  - icon present (IconSpec) with glyph + base_color
  - video total_seconds <= 30, each scene <= 15
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from operation.publishing_factory.asset_pipeline.screenshot_generator import (
    ScreenshotSet,
)
from operation.publishing_factory.asset_pipeline.icon_generator import IconSpec
from operation.publishing_factory.asset_pipeline.video_generator import (
    VideoStoryboard,
)

_HEADLINE_MAX = 45
_SUBHEAD_MAX = 60
_SS_MIN, _SS_MAX = 2, 8
_VIDEO_MAX = 30
_SCENE_MAX = 15


@dataclass
class AssetValidationReport:
    game_id: str
    valid: bool
    issues: List[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "valid": self.valid,
                "issues": list(self.issues), "checks": dict(self.checks)}


class AssetValidator:
    """Validates a full asset bundle (screenshots + icon + video)."""

    def validate(self, game_id: str, screenshots: ScreenshotSet,
                 icon: IconSpec, video: VideoStoryboard) -> AssetValidationReport:
        issues: List[str] = []
        checks: dict = {}

        # screenshots
        n = len(screenshots.screenshots)
        checks["screenshot_count"] = n
        if not (_SS_MIN <= n <= _SS_MAX):
            issues.append(f"screenshot count {n} not in [{_SS_MIN},{_SS_MAX}]")
        for s in screenshots.screenshots:
            if not s.headline or len(s.headline) > _HEADLINE_MAX:
                issues.append(f"ss#{s.index} headline len {len(s.headline)} > {_HEADLINE_MAX}")
            if len(s.subheadline) > _SUBHEAD_MAX:
                issues.append(f"ss#{s.index} subhead len {len(s.subheadline)} > {_SUBHEAD_MAX}")
            if not s.layout or not s.palette:
                issues.append(f"ss#{s.index} missing layout/palette")

        # icon
        checks["icon_present"] = bool(icon)
        if not icon or not icon.glyph or not icon.base_color:
            issues.append("icon missing glyph/base_color")

        # video
        checks["video_seconds"] = video.total_seconds
        if video.total_seconds > _VIDEO_MAX:
            issues.append(f"video {video.total_seconds}s > {_VIDEO_MAX}s")
        for sc in video.scenes:
            if sc.duration_s > _SCENE_MAX:
                issues.append(f"scene#{sc.index} {sc.duration_s}s > {_SCENE_MAX}s")

        return AssetValidationReport(
            game_id=game_id, valid=len(issues) == 0,
            issues=issues, checks=checks)


__all__ = ["AssetValidator", "AssetValidationReport",
           "_HEADLINE_MAX", "_SUBHEAD_MAX", "_SS_MIN", "_SS_MAX",
           "_VIDEO_MAX", "_SCENE_MAX"]
