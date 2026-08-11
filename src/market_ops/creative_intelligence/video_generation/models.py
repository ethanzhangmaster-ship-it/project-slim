"""Video Generation 数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from enum import Enum


class GenerationStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"


@dataclass
class VideoScore:
    """视频质量评分"""
    hook_score: float = 0.0      # 0-100
    action_score: float = 0.0    # 0-100
    gameplay_score: float = 0.0  # 0-100
    visual_score: float = 0.0    # 0-100
    total_score: float = 0.0     # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_score": round(self.hook_score, 1),
            "action_score": round(self.action_score, 1),
            "gameplay_score": round(self.gameplay_score, 1),
            "visual_score": round(self.visual_score, 1),
            "total_score": round(self.total_score, 1),
        }


@dataclass
class VideoValidation:
    """视频技术验证结果"""
    valid: bool = False
    resolution: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0
    codec: str = ""
    frame_count: int = 0
    file_size: int = 0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "resolution": self.resolution,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "duration": round(self.duration, 2),
            "codec": self.codec,
            "frame_count": self.frame_count,
            "file_size": self.file_size,
            "issues": self.issues,
        }


@dataclass
class GenerationResult:
    """生成结果"""
    video_id: str
    status: GenerationStatus
    winner_dna_id: str
    prompt: str
    negative_prompt: str
    video_path: str = ""
    workflow_path: str = ""
    score: VideoScore = field(default_factory=VideoScore)
    validation: VideoValidation = field(default_factory=VideoValidation)
    comfyui_prompt_id: str = ""
    seed: int = 0
    model_preset: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "status": self.status.value,
            "winner_dna_id": self.winner_dna_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "video_path": self.video_path,
            "workflow_path": self.workflow_path,
            "score": self.score.to_dict(),
            "validation": self.validation.to_dict(),
            "comfyui_prompt_id": self.comfyui_prompt_id,
            "seed": self.seed,
            "model_preset": self.model_preset,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class BatchConfig:
    """批量生成配置"""
    seeds: list[int] = field(default_factory=list)
    camera_variations: list[str] = field(default_factory=list)
    action_variations: list[str] = field(default_factory=list)
    count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "seeds": self.seeds,
            "camera_variations": self.camera_variations,
            "action_variations": self.action_variations,
            "count": self.count,
        }
