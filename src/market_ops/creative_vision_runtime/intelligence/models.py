"""E11.3.5 — Vision Intelligence Models。

VisualPattern:       视觉模式
HookAnalysis:        开头 Hook 分析
CompositionAnalysis: 构图分析
VisionInsight:       素材视觉洞察
WinnerVisualDNA:     Winner 视觉 DNA
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VisualPattern:
    """单个视觉模式。

    Attributes:
        pattern_id:      模式 ID
        name:            模式名称
        description:     模式描述
        confidence:      置信度 (0-1)
        category:        模式类别 (opening/composition/color/motion)
        evidence_count:  证据数量
        source_assets:   来源素材列表
        feature_values:  特征值（用于解释）
    """

    pattern_id: str = ""
    name: str = ""
    description: str = ""
    confidence: float = 0.0
    category: str = ""

    evidence_count: int = 0
    source_assets: list[str] = field(default_factory=list)
    feature_values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pattern_id:
            self.pattern_id = f"vp_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "confidence": self.confidence,
            "category": self.category,
            "evidence_count": self.evidence_count,
            "source_assets": self.source_assets,
            "feature_values": self.feature_values,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualPattern:
        return cls(
            pattern_id=data.get("pattern_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            confidence=float(data.get("confidence", 0.0)),
            category=data.get("category", ""),
            evidence_count=int(data.get("evidence_count", 0)),
            source_assets=data.get("source_assets", []),
            feature_values=data.get("feature_values", {}),
        )

    def __repr__(self) -> str:
        return (
            f"VisualPattern({self.name}, "
            f"conf={self.confidence:.2f}, "
            f"cat={self.category})"
        )


@dataclass
class HookAnalysis:
    """开头 Hook 分析结果。

    Attributes:
        hook_strength:      Hook 强度 (0-1)
        opening_type:       开头类型 (instant_reward/curiosity/motion/calm)
        visual_transition:  视觉变化程度 (low/medium/high)
        first_frame_brightness:  首帧亮度
        brightness_trend:   亮度变化趋势 (rising/falling/stable)
        contrast_trend:     对比度变化趋势
        edge_density_trend: 边缘密度变化趋势
        frame_by_frame:     逐帧分析
        description:        文字描述
    """

    hook_strength: float = 0.0
    opening_type: str = "calm"
    visual_transition: str = "low"

    first_frame_brightness: float = 0.0
    brightness_trend: str = "stable"
    contrast_trend: str = "stable"
    edge_density_trend: str = "stable"

    frame_by_frame: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_strength": self.hook_strength,
            "opening_type": self.opening_type,
            "visual_transition": self.visual_transition,
            "first_frame_brightness": self.first_frame_brightness,
            "brightness_trend": self.brightness_trend,
            "contrast_trend": self.contrast_trend,
            "edge_density_trend": self.edge_density_trend,
            "frame_by_frame": self.frame_by_frame,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"HookAnalysis(strength={self.hook_strength:.2f}, "
            f"type={self.opening_type})"
        )


@dataclass
class CompositionAnalysis:
    """构图分析结果。

    Attributes:
        composition_type:  构图类型 (single_subject/multi_subject/complex)
        subject_count:     主体数量估计
        color_palette:     色彩方案 (bright_saturated/dark_muted/neutral)
        motion_type:       运动类型 (fast_transition/slow_pan/static)
        avg_edge_density:  平均边缘密度
        avg_color_entropy: 平均色彩熵
        avg_saturation:    平均饱和度
        description:       文字描述
    """

    composition_type: str = "complex"
    subject_count: int = 0
    color_palette: str = "neutral"
    motion_type: str = "static"

    avg_edge_density: float = 0.0
    avg_color_entropy: float = 0.0
    avg_saturation: float = 0.0

    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition_type": self.composition_type,
            "subject_count": self.subject_count,
            "color_palette": self.color_palette,
            "motion_type": self.motion_type,
            "avg_edge_density": self.avg_edge_density,
            "avg_color_entropy": self.avg_color_entropy,
            "avg_saturation": self.avg_saturation,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"CompositionAnalysis(type={self.composition_type}, "
            f"color={self.color_palette})"
        )


@dataclass
class VisionInsight:
    """素材视觉洞察 — 单个素材的完整视觉分析结果。

    Attributes:
        insight_id:         洞察 ID
        creative_asset_id:  素材 ID
        visual_patterns:    检测到的视觉模式
        hook_analysis:      开头 Hook 分析
        composition_analysis: 构图分析
        winner_probability: Winner 概率 (0-1)
        similarity_to_winners: 与 Winner 的相似度
        summary:            文字总结
        created_at:         创建时间
    """

    insight_id: str = ""
    creative_asset_id: str = ""

    visual_patterns: list[VisualPattern] = field(default_factory=list)
    hook_analysis: HookAnalysis | None = None
    composition_analysis: CompositionAnalysis | None = None

    winner_probability: float = 0.0
    similarity_to_winners: float = 0.0
    summary: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.insight_id:
            self.insight_id = f"vi_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "creative_asset_id": self.creative_asset_id,
            "visual_patterns": [p.to_dict() for p in self.visual_patterns],
            "hook_analysis": self.hook_analysis.to_dict() if self.hook_analysis else None,
            "composition_analysis": self.composition_analysis.to_dict() if self.composition_analysis else None,
            "winner_probability": self.winner_probability,
            "similarity_to_winners": self.similarity_to_winners,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        n_patterns = len(self.visual_patterns)
        return (
            f"VisionInsight(asset={self.creative_asset_id}, "
            f"patterns={n_patterns}, "
            f"winner_prob={self.winner_probability:.2f})"
        )


@dataclass
class WinnerVisualDNA:
    """Winner 视觉 DNA — 多个 Winner 的聚合视觉特征。

    Attributes:
        dna_id:         DNA ID
        source_count:   来源 Winner 数量
        source_assets:  来源素材列表
        opening:        开头模式
        composition:    构图模式
        color:          色彩模式
        motion:         运动模式
        patterns:       检测到的所有模式
        aggregated_metrics: 聚合指标
        description:    文字描述
        created_at:     创建时间
    """

    dna_id: str = ""
    source_count: int = 0
    source_assets: list[str] = field(default_factory=list)

    opening: str = ""
    composition: str = ""
    color: str = ""
    motion: str = ""

    patterns: list[VisualPattern] = field(default_factory=list)
    aggregated_metrics: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.dna_id:
            self.dna_id = f"wdna_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_id": self.dna_id,
            "source_count": self.source_count,
            "source_assets": self.source_assets,
            "opening": self.opening,
            "composition": self.composition,
            "color": self.color,
            "motion": self.motion,
            "patterns": [p.to_dict() for p in self.patterns],
            "aggregated_metrics": self.aggregated_metrics,
            "description": self.description,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"WinnerVisualDNA(id={self.dna_id}, "
            f"sources={self.source_count}, "
            f"opening={self.opening})"
        )