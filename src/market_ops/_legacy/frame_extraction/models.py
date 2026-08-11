"""E11.3.2 — Vision Frame Models。

VisionFrame:   单帧数据（路径 + 时间戳 + 视觉特征）
FrameSequence: 视频帧序列（6 帧 + 视频级评分 + 元数据）

职责：
  - 不包含 AI 推理（CLIP/OCR/目标检测）
  - 不包含 DNA 分析
  - 只包含结构级视觉特征（亮度/对比度/边缘密度/色彩熵）
  - 供下游 Feature Store 和 DNA Extractor 消费

特征来源：
  FrameAnalyzer (engine/frame_analyzer.py) — PIL + numpy，零外部依赖
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VisionFrame:
    """单帧视觉数据。

    Attributes:
        frame_id:       帧唯一 ID
        frame_index:    帧序号 (0-5)
        frame_path:     帧文件路径（jpg）
        timestamp_sec:  帧在视频中的时间戳（秒）
        ratio:          帧在视频中的位置比例 (0.0-1.0)

        # 结构级视觉特征（FrameAnalyzer 输出）
        brightness:     亮度 (0-1)
        contrast:       对比度 (0-1)
        edge_density:   边缘密度 (0-1)
        text_density:   文字密度 proxy (0-1)
        color_entropy:  色彩熵 (0-16)
        saturation:     饱和度 (0-1)
        top_color_ratio: 主色占比 (0-1)
        center_brightness: 中心区域亮度 (0-1)
        center_contrast:   中心区域对比度 (0-1)
    """

    frame_id: str = ""
    frame_index: int = 0
    frame_path: str = ""
    timestamp_sec: float = 0.0
    ratio: float = 0.0

    # ── Structural Features ────────────────────────────
    brightness: float = 0.0
    contrast: float = 0.0
    edge_density: float = 0.0
    text_density: float = 0.0
    color_entropy: float = 0.0
    saturation: float = 0.0
    top_color_ratio: float = 0.0
    center_brightness: float = 0.0
    center_contrast: float = 0.0

    def __post_init__(self) -> None:
        if not self.frame_id:
            self.frame_id = f"vf_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "frame_index": self.frame_index,
            "frame_path": self.frame_path,
            "timestamp_sec": self.timestamp_sec,
            "ratio": self.ratio,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "edge_density": self.edge_density,
            "text_density": self.text_density,
            "color_entropy": self.color_entropy,
            "saturation": self.saturation,
            "top_color_ratio": self.top_color_ratio,
            "center_brightness": self.center_brightness,
            "center_contrast": self.center_contrast,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisionFrame:
        return cls(
            frame_id=data.get("frame_id", ""),
            frame_index=data.get("frame_index", 0),
            frame_path=data.get("frame_path", ""),
            timestamp_sec=data.get("timestamp_sec", 0.0),
            ratio=data.get("ratio", 0.0),
            brightness=data.get("brightness", 0.0),
            contrast=data.get("contrast", 0.0),
            edge_density=data.get("edge_density", 0.0),
            text_density=data.get("text_density", 0.0),
            color_entropy=data.get("color_entropy", 0.0),
            saturation=data.get("saturation", 0.0),
            top_color_ratio=data.get("top_color_ratio", 0.0),
            center_brightness=data.get("center_brightness", 0.0),
            center_contrast=data.get("center_contrast", 0.0),
        )

    def __repr__(self) -> str:
        return f"VisionFrame(idx={self.frame_index}, ts={self.timestamp_sec:.1f}s)"


@dataclass
class FrameSequence:
    """视频帧序列。

    包含 6 个采样帧 + 视频级评分 + 元数据。

    Attributes:
        sequence_id:      序列 ID
        creative_id:      Facebook creative_id
        creative_asset_id: CreativeEntity 内部 ID
        video_path:       视频文件路径
        eagle_filename:   Eagle 文件名

        frames:           6 帧 VisionFrame 列表
        duration_sec:     视频时长（秒）
        resolution:       分辨率 (w,h)
        frame_count:      总帧数

        hook_score:       开头冲击力 (0-1)
        comprehension_score: 中段信息清晰度 (0-1)
        reward_score:     结尾视觉回报 (0-1)

        status:           处理状态
        error_message:    错误信息
        created_at:       创建时间
    """

    sequence_id: str = ""
    creative_id: str = ""
    creative_asset_id: str = ""
    video_path: str = ""
    eagle_filename: str = ""

    # ── Frames ─────────────────────────────────────────
    frames: list[VisionFrame] = field(default_factory=list)

    # ── Video Info ─────────────────────────────────────
    duration_sec: float = 0.0
    resolution: tuple[int, int] = (0, 0)
    frame_count: int = 0

    # ── Video-Level Scores ─────────────────────────────
    hook_score: float = 0.0
    comprehension_score: float = 0.0
    reward_score: float = 0.0

    # ── Status ────────────────────────────────────────
    status: str = "pending"
    error_message: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.sequence_id:
            self.sequence_id = f"fs_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    # ── Properties ─────────────────────────────────────

    @property
    def frame_count_loaded(self) -> int:
        return len(self.frames)

    @property
    def has_frames(self) -> bool:
        return len(self.frames) > 0

    @property
    def avg_brightness(self) -> float:
        if not self.frames:
            return 0.0
        return sum(f.brightness for f in self.frames) / len(self.frames)

    @property
    def avg_edge_density(self) -> float:
        if not self.frames:
            return 0.0
        return sum(f.edge_density for f in self.frames) / len(self.frames)

    @property
    def avg_saturation(self) -> float:
        if not self.frames:
            return 0.0
        return sum(f.saturation for f in self.frames) / len(self.frames)

    @property
    def avg_contrast(self) -> float:
        if not self.frames:
            return 0.0
        return sum(f.contrast for f in self.frames) / len(self.frames)

    @property
    def avg_color_entropy(self) -> float:
        if not self.frames:
            return 0.0
        return sum(f.color_entropy for f in self.frames) / len(self.frames)

    # ── Serialization ──────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "creative_id": self.creative_id,
            "creative_asset_id": self.creative_asset_id,
            "video_path": self.video_path,
            "eagle_filename": self.eagle_filename,
            "frames": [f.to_dict() for f in self.frames],
            "duration_sec": self.duration_sec,
            "resolution": list(self.resolution),
            "frame_count": self.frame_count,
            "hook_score": self.hook_score,
            "comprehension_score": self.comprehension_score,
            "reward_score": self.reward_score,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FrameSequence:
        frames = [VisionFrame.from_dict(f) for f in data.get("frames", [])]
        resolution = tuple(data.get("resolution", [0, 0]))
        return cls(
            sequence_id=data.get("sequence_id", ""),
            creative_id=data.get("creative_id", ""),
            creative_asset_id=data.get("creative_asset_id", ""),
            video_path=data.get("video_path", ""),
            eagle_filename=data.get("eagle_filename", ""),
            frames=frames,
            duration_sec=data.get("duration_sec", 0.0),
            resolution=resolution,
            frame_count=data.get("frame_count", 0),
            hook_score=data.get("hook_score", 0.0),
            comprehension_score=data.get("comprehension_score", 0.0),
            reward_score=data.get("reward_score", 0.0),
            status=data.get("status", "pending"),
            error_message=data.get("error_message", ""),
            created_at=data.get("created_at", ""),
        )

    def __repr__(self) -> str:
        return (
            f"FrameSequence(id={self.sequence_id}, "
            f"creative={self.creative_asset_id}, "
            f"frames={self.frame_count_loaded}, "
            f"hook={self.hook_score:.2f})"
        )