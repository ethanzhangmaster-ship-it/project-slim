"""E11.3.3 — Vision Feature Store Models。

VisionFeatureRecord:  视频级视觉特征记录
VisionFrameFeature:   帧级视觉特征记录
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


EXTRACTOR_VERSION = "e11.3.2"


@dataclass
class VisionFeatureRecord:
    """视频级视觉特征记录。"""

    feature_id: str = ""
    creative_asset_id: str = ""
    video_path: str = ""
    eagle_filename: str = ""

    frame_count: int = 0
    duration_seconds: float = 0.0
    resolution: tuple[int, int] = (0, 0)

    hook_score: float = 0.0
    comprehension_score: float = 0.0
    reward_score: float = 0.0

    avg_brightness: float = 0.0
    avg_contrast: float = 0.0
    avg_edge_density: float = 0.0
    avg_saturation: float = 0.0
    avg_color_entropy: float = 0.0

    metric: dict[str, Any] = field(default_factory=dict)
    lifecycle_status: str = ""
    is_winner: bool = False

    extractor_version: str = EXTRACTOR_VERSION
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.feature_id:
            self.feature_id = f"vfr_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "creative_asset_id": self.creative_asset_id,
            "video_path": self.video_path,
            "eagle_filename": self.eagle_filename,
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
            "resolution": list(self.resolution),
            "hook_score": self.hook_score,
            "comprehension_score": self.comprehension_score,
            "reward_score": self.reward_score,
            "avg_brightness": self.avg_brightness,
            "avg_contrast": self.avg_contrast,
            "avg_edge_density": self.avg_edge_density,
            "avg_saturation": self.avg_saturation,
            "avg_color_entropy": self.avg_color_entropy,
            "metric": self.metric,
            "lifecycle_status": self.lifecycle_status,
            "is_winner": self.is_winner,
            "extractor_version": self.extractor_version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisionFeatureRecord:
        return cls(
            feature_id=data.get("feature_id", ""),
            creative_asset_id=data.get("creative_asset_id", ""),
            video_path=data.get("video_path", ""),
            eagle_filename=data.get("eagle_filename", ""),
            frame_count=int(data.get("frame_count", 0)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            resolution=tuple(data.get("resolution", [0, 0])),
            hook_score=float(data.get("hook_score", 0.0)),
            comprehension_score=float(data.get("comprehension_score", 0.0)),
            reward_score=float(data.get("reward_score", 0.0)),
            avg_brightness=float(data.get("avg_brightness", 0.0)),
            avg_contrast=float(data.get("avg_contrast", 0.0)),
            avg_edge_density=float(data.get("avg_edge_density", 0.0)),
            avg_saturation=float(data.get("avg_saturation", 0.0)),
            avg_color_entropy=float(data.get("avg_color_entropy", 0.0)),
            metric=data.get("metric", {}),
            lifecycle_status=data.get("lifecycle_status", ""),
            is_winner=bool(data.get("is_winner", False)),
            extractor_version=data.get("extractor_version", EXTRACTOR_VERSION),
            created_at=data.get("created_at", ""),
        )

    def __repr__(self) -> str:
        return (
            f"VisionFeatureRecord(id={self.feature_id}, "
            f"asset={self.creative_asset_id}, "
            f"hook={self.hook_score:.2f}, "
            f"winner={self.is_winner})"
        )


@dataclass
class VisionFrameFeature:
    """帧级视觉特征记录。"""

    frame_id: str = ""
    feature_id: str = ""
    frame_index: int = 0
    timestamp_sec: float = 0.0
    frame_path: str = ""

    brightness: float = 0.0
    contrast: float = 0.0
    edge_density: float = 0.0
    saturation: float = 0.0
    color_entropy: float = 0.0

    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.frame_id:
            self.frame_id = f"vff_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "feature_id": self.feature_id,
            "frame_index": self.frame_index,
            "timestamp_sec": self.timestamp_sec,
            "frame_path": self.frame_path,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "edge_density": self.edge_density,
            "saturation": self.saturation,
            "color_entropy": self.color_entropy,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisionFrameFeature:
        return cls(
            frame_id=data.get("frame_id", ""),
            feature_id=data.get("feature_id", ""),
            frame_index=int(data.get("frame_index", 0)),
            timestamp_sec=float(data.get("timestamp_sec", 0.0)),
            frame_path=data.get("frame_path", ""),
            brightness=float(data.get("brightness", 0.0)),
            contrast=float(data.get("contrast", 0.0)),
            edge_density=float(data.get("edge_density", 0.0)),
            saturation=float(data.get("saturation", 0.0)),
            color_entropy=float(data.get("color_entropy", 0.0)),
            tags=data.get("tags", []),
        )

    def __repr__(self) -> str:
        return (
            f"VisionFrameFeature(idx={self.frame_index}, "
            f"ts={self.timestamp_sec:.1f}s, "
            f"bright={self.brightness:.2f})"
        )