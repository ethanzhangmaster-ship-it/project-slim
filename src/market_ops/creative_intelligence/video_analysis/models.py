"""Video Analysis 数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class PredictionLevel(Enum):
    HIGH_POTENTIAL = "HIGH_POTENTIAL"
    MEDIUM_POTENTIAL = "MEDIUM_POTENTIAL"
    LOW_POTENTIAL = "LOW_POTENTIAL"
    REJECT = "REJECT"


@dataclass
class VideoInfo:
    """视频基础信息"""
    duration: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    resolution: str = ""
    codec: str = ""
    frame_count: int = 0
    file_size: int = 0
    valid: bool = False
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration": self.duration,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "codec": self.codec,
            "frame_count": self.frame_count,
            "file_size": self.file_size,
            "valid": self.valid,
            "issues": self.issues,
        }


@dataclass
class FrameInfo:
    """帧信息"""
    time: float
    path: str
    index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"time": self.time, "path": self.path, "index": self.index}


@dataclass
class VisualFeatures:
    """视觉特征"""
    objects: list[str] = field(default_factory=list)
    scenes: list[str] = field(default_factory=list)
    elements: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objects": self.objects,
            "scenes": self.scenes,
            "elements": self.elements,
            "characters": self.characters,
        }


@dataclass
class HookAnalysis:
    """Hook 分析结果"""
    score: float = 0.0
    subject_size: str = ""  # large / medium / small / none
    contrast_level: str = ""  # high / medium / low
    has_motion: bool = False
    has_conflict: bool = False
    has_transformation: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "subject_size": self.subject_size,
            "contrast_level": self.contrast_level,
            "has_motion": self.has_motion,
            "has_conflict": self.has_conflict,
            "has_transformation": self.has_transformation,
            "reasons": self.reasons,
        }


@dataclass
class ActionAnalysis:
    """动作分析结果"""
    score: float = 0.0
    detected_actions: list[str] = field(default_factory=list)
    banned_actions: list[str] = field(default_factory=list)
    action_intensity: str = ""  # high / medium / low / none

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "detected_actions": self.detected_actions,
            "banned_actions": self.banned_actions,
            "action_intensity": self.action_intensity,
        }


@dataclass
class GameplayAnalysis:
    """玩法分析结果"""
    score: float = 0.0
    detected_gameplay: list[str] = field(default_factory=list)
    has_merge: bool = False
    has_upgrade: bool = False
    has_reward: bool = False
    has_collection: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "detected_gameplay": self.detected_gameplay,
            "has_merge": self.has_merge,
            "has_upgrade": self.has_upgrade,
            "has_reward": self.has_reward,
            "has_collection": self.has_collection,
        }


@dataclass
class ConsistencyResult:
    """一致性检查结果"""
    character_consistency: float = 0.0
    color_consistency: float = 0.0
    style_consistency: float = 0.0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_consistency": round(self.character_consistency, 1),
            "color_consistency": round(self.color_consistency, 1),
            "style_consistency": round(self.style_consistency, 1),
            "issues": self.issues,
        }


@dataclass
class VideoAnalysisReport:
    """视频分析报告（最终输出）"""
    video_id: str = ""
    video_path: str = ""

    # 技术信息
    video_info: VideoInfo = field(default_factory=VideoInfo)
    frames: list[FrameInfo] = field(default_factory=list)

    # 视觉分析
    visual_features: VisualFeatures = field(default_factory=VisualFeatures)

    # 各维度评分
    hook_score: float = 0.0
    action_score: float = 0.0
    gameplay_score: float = 0.0
    visual_score: float = 0.0
    character_score: float = 0.0
    consistency_score: float = 0.0

    # 总分
    total_score: float = 0.0

    # 预测
    prediction: str = ""
    level: str = ""

    # 建议
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendation: str = ""

    # 详细结果
    hook_analysis: HookAnalysis = field(default_factory=HookAnalysis)
    action_analysis: ActionAnalysis = field(default_factory=ActionAnalysis)
    gameplay_analysis: GameplayAnalysis = field(default_factory=GameplayAnalysis)
    consistency: ConsistencyResult = field(default_factory=ConsistencyResult)

    # 元数据
    winner_dna_id: str = ""
    game_type: str = ""
    analyzed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "video_path": self.video_path,
            "video_info": self.video_info.to_dict(),
            "frames": [f.to_dict() for f in self.frames],
            "visual_features": self.visual_features.to_dict(),
            "scores": {
                "hook": round(self.hook_score, 1),
                "action": round(self.action_score, 1),
                "gameplay": round(self.gameplay_score, 1),
                "visual": round(self.visual_score, 1),
                "character": round(self.character_score, 1),
                "consistency": round(self.consistency_score, 1),
                "total": round(self.total_score, 1),
            },
            "prediction": self.prediction,
            "level": self.level,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendation": self.recommendation,
            "hook_analysis": self.hook_analysis.to_dict(),
            "action_analysis": self.action_analysis.to_dict(),
            "gameplay_analysis": self.gameplay_analysis.to_dict(),
            "consistency": self.consistency.to_dict(),
            "winner_dna_id": self.winner_dna_id,
            "game_type": self.game_type,
            "analyzed_at": self.analyzed_at,
        }
