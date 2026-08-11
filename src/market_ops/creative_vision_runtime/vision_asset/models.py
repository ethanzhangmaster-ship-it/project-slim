"""E11.3.1 — Vision Asset Models。

VisionAsset: E11.3 Vision Pipeline 的内部标准数据对象。

职责：
  - 不包含 AI 特征（embedding, CLIP）
  - 不包含 DNA 推理结果
  - 只是视频资产的标准化描述，供下游 Frame Extractor 和 Feature Store 消费

数据来源：
  CreativeEntity.asset → VisionAsset
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VisionAssetStatus(str, Enum):
    """VisionAsset 处理状态。"""
    PENDING = "pending"       # 待处理
    VALIDATED = "validated"   # 文件验证通过
    INVALID = "invalid"       # 文件验证失败
    FRAMES_EXTRACTED = "frames_extracted"  # 帧已提取
    FEATURES_STORED = "features_stored"    # 特征已存储
    DNA_READY = "dna_ready"   # 待 DNA 分析
    DNA_COMPLETE = "dna_complete"  # DNA 分析完成
    ERROR = "error"           # 处理错误


@dataclass
class VisionAsset:
    """E11.3 Vision Pipeline 的标准资产对象。

    从 CreativeEntity.asset 提取，不包含 AI 推理结果。

    Attributes:
        asset_id:       唯一标识
        creative_id:    Facebook creative_id
        creative_asset_id: CreativeEntity 内部 ID
        video_path:     Eagle 视频文件路径
        eagle_filename: Eagle 文件名
        source_type:    素材来源 (EAGLE/FACEBOOK/LOVART)
        match_method:   匹配方法 (a_number/filename/exact_id)
        match_confidence: 匹配置信度
        performance:    投放效果数据（spend/revenue/roas/impressions）
        lifecycle_status: 素材生命周期状态 (WINNER/TESTING/MATCHED/...)
        metadata:       扩展元数据
        status:         Vision Pipeline 处理状态
        error_message:  错误信息
        created_at:     创建时间
        updated_at:     更新时间
    """

    asset_id: str = ""
    creative_id: str = ""
    creative_asset_id: str = ""

    # ── Asset ────────────────────────────────────────
    video_path: str = ""
    eagle_filename: str = ""
    source_type: str = ""       # EAGLE / FACEBOOK / LOVART
    match_method: str = ""      # a_number / filename / exact_id
    match_confidence: float = 0.0

    # ── Performance ──────────────────────────────────
    performance: dict[str, Any] = field(default_factory=dict)

    # ── Lifecycle ────────────────────────────────────
    lifecycle_status: str = ""

    # ── Metadata ─────────────────────────────────────
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Processing Status ────────────────────────────
    status: str = VisionAssetStatus.PENDING.value
    error_message: str = ""

    # ── Timestamps ───────────────────────────────────
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.asset_id:
            self.asset_id = f"va_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    # ── Properties ───────────────────────────────────

    @property
    def has_video(self) -> bool:
        return bool(self.video_path)

    @property
    def has_performance(self) -> bool:
        return bool(self.performance)

    @property
    def is_winner(self) -> bool:
        return self.lifecycle_status == "WINNER"

    @property
    def is_eagle_source(self) -> bool:
        return self.source_type.upper() == "EAGLE"

    @property
    def roas(self) -> float:
        return float(self.performance.get("roas", 0.0))

    @property
    def spend(self) -> float:
        return float(self.performance.get("spend", 0.0))

    @property
    def revenue(self) -> float:
        return float(self.performance.get("revenue", 0.0))

    @property
    def impressions(self) -> int:
        return int(self.performance.get("impressions", 0))

    # ── Serialization ────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "creative_id": self.creative_id,
            "creative_asset_id": self.creative_asset_id,
            "video_path": self.video_path,
            "eagle_filename": self.eagle_filename,
            "source_type": self.source_type,
            "match_method": self.match_method,
            "match_confidence": self.match_confidence,
            "performance": self.performance,
            "lifecycle_status": self.lifecycle_status,
            "metadata": self.metadata,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisionAsset:
        return cls(
            asset_id=data.get("asset_id", ""),
            creative_id=data.get("creative_id", ""),
            creative_asset_id=data.get("creative_asset_id", ""),
            video_path=data.get("video_path", ""),
            eagle_filename=data.get("eagle_filename", ""),
            source_type=data.get("source_type", ""),
            match_method=data.get("match_method", ""),
            match_confidence=float(data.get("match_confidence", 0.0)),
            performance=data.get("performance", {}),
            lifecycle_status=data.get("lifecycle_status", ""),
            metadata=data.get("metadata", {}),
            status=data.get("status", VisionAssetStatus.PENDING.value),
            error_message=data.get("error_message", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def __repr__(self) -> str:
        return (
            f"VisionAsset(id={self.asset_id}, "
            f"creative={self.creative_id or self.creative_asset_id}, "
            f"source={self.source_type}, "
            f"status={self.status})"
        )