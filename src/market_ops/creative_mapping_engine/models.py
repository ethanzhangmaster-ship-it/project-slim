"""Creative Mapping Engine — 数据模型.

定义创意映射相关的核心数据结构：
  - CreativeMappingRecord: 映射记录
  - MappingScores: 6 维度评分
  - MappingStatus: 映射状态枚举
  - ReviewTask: 人工审核任务
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MappingStatus(str, Enum):
    """映射状态枚举。"""

    PENDING = "pending"
    MATCHED = "matched"
    NEEDS_REVIEW = "needs_review"
    REVIEW_APPROVED = "approved"
    REVIEW_REJECTED = "rejected"
    NO_MATCH = "no_match"
    ARCHIVED = "archived"


class MappingDeliveryStatus(str, Enum):
    """映射记录的投递状态 (v1.5)。

    与 MappingStatus 正交：前者描述"映射是否完成"，
    后者描述"是否已推送到投放系统"。
    """

    UNDISPATCHED = "undispatched"   # 未投递（默认）
    DISPATCHED = "dispatched"       # 已投递到 Publisher，等待 Facebook 确认
    PUBLISHED = "published"         # 已上线（拿到 ad_id）
    FAILED = "failed"               # 投递失败（见 delivery_error）
    ARCHIVED = "archived"           # 已归档（不再投递）


@dataclass
class MappingScores:
    """6 维度独立评分，每个维度 0.0-1.0。"""

    name_similarity: float = 0.0
    duration_match: float = 0.0
    resolution_match: float = 0.0
    creation_time_match: float = 0.0
    frame_similarity: float = 0.0
    file_hash_match: float = 0.0

    DEFAULT_WEIGHTS: dict[str, float] = field(
        default_factory=lambda: {
            "name_similarity": 0.25,
            "duration_match": 0.15,
            "resolution_match": 0.10,
            "creation_time_match": 0.10,
            "frame_similarity": 0.25,
            "file_hash_match": 0.15,
        },
        repr=False,
        compare=False,
    )

    def weighted_total(self, weights: dict[str, float] | None = None) -> float:
        """加权综合评分。"""
        w = weights or self.DEFAULT_WEIGHTS
        total = (
            w["name_similarity"] * self.name_similarity
            + w["duration_match"] * self.duration_match
            + w["resolution_match"] * self.resolution_match
            + w["creation_time_match"] * self.creation_time_match
            + w["frame_similarity"] * self.frame_similarity
            + w["file_hash_match"] * self.file_hash_match
        )
        return round(total, 4)

    def to_dict(self) -> dict[str, float]:
        return {
            "name_similarity": round(self.name_similarity, 4),
            "duration_match": round(self.duration_match, 4),
            "resolution_match": round(self.resolution_match, 4),
            "creation_time_match": round(self.creation_time_match, 4),
            "frame_similarity": round(self.frame_similarity, 4),
            "file_hash_match": round(self.file_hash_match, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MappingScores:
        return cls(
            name_similarity=float(data.get("name_similarity", 0.0)),
            duration_match=float(data.get("duration_match", 0.0)),
            resolution_match=float(data.get("resolution_match", 0.0)),
            creation_time_match=float(data.get("creation_time_match", 0.0)),
            frame_similarity=float(data.get("frame_similarity", 0.0)),
            file_hash_match=float(data.get("file_hash_match", 0.0)),
        )


@dataclass
class CreativeMappingRecord:
    """创意映射记录 — Facebook creative 与内部素材的映射关系。"""

    mapping_id: str
    facebook_creative_id: str
    facebook_creative_name: str
    facebook_account_id: str = ""

    eagle_filename: str = ""
    eagle_path: str = ""
    local_path: str = ""

    scores: MappingScores = field(default_factory=MappingScores)
    confidence: float = 0.0
    match_method: str = ""
    status: MappingStatus = MappingStatus.PENDING

    created_at: str = ""
    updated_at: str = ""
    reviewed_by: str = ""
    review_note: str = ""

    # ── v1.5 Delivery Bridge 新增字段 ──
    delivery_status: MappingDeliveryStatus = MappingDeliveryStatus.UNDISPATCHED
    publish_id: str = ""
    ad_id: str = ""
    ad_creative_id: str = ""
    delivered_at: str = ""
    delivery_error: str = ""
    delivery_attempts: int = 0

    # ── v1.6 Auto-Structure 新增字段 ──
    auto_campaign_id: str = ""
    auto_adset_id: str = ""
    auto_strategy: str = ""

    # ── v1.7 Performance 新增字段 ──
    performance: Any = None  # CreativePerformance | None (Any 避免循环引用)

    # ── v1.8 Strategy 新增字段 ──
    performance_score: float = 0.0
    delivery_priority: float = 0.0
    auto_archived: bool = False
    auto_archived_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        perf = None
        if self.performance is not None:
            perf = (
                self.performance.to_dict()
                if hasattr(self.performance, "to_dict")
                else dict(self.performance)
            )
        return {
            "mapping_id": self.mapping_id,
            "facebook_creative_id": self.facebook_creative_id,
            "facebook_creative_name": self.facebook_creative_name,
            "facebook_account_id": self.facebook_account_id,
            "eagle_filename": self.eagle_filename,
            "eagle_path": self.eagle_path,
            "local_path": self.local_path,
            "scores": self.scores.to_dict(),
            "confidence": round(self.confidence, 4),
            "match_method": self.match_method,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_by": self.reviewed_by,
            "review_note": self.review_note,
            "delivery_status": self.delivery_status.value,
            "publish_id": self.publish_id,
            "ad_id": self.ad_id,
            "ad_creative_id": self.ad_creative_id,
            "delivered_at": self.delivered_at,
            "delivery_error": self.delivery_error,
            "delivery_attempts": self.delivery_attempts,
            "auto_campaign_id": self.auto_campaign_id,
            "auto_adset_id": self.auto_adset_id,
            "auto_strategy": self.auto_strategy,
            "performance": perf,
            "performance_score": round(self.performance_score, 4),
            "delivery_priority": round(self.delivery_priority, 4),
            "auto_archived": self.auto_archived,
            "auto_archived_reason": self.auto_archived_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeMappingRecord:
        status_raw = data.get("status", "pending")
        status = MappingStatus(status_raw) if isinstance(status_raw, str) else status_raw
        ds_raw = data.get("delivery_status", "undispatched")
        delivery_status = (
            MappingDeliveryStatus(ds_raw) if isinstance(ds_raw, str) else ds_raw
        )
        # v1.7 performance: 惰性解析，避免循环导入
        perf_data = data.get("performance")
        performance = None
        if perf_data and isinstance(perf_data, dict):
            try:
                from market_ops.creative_mapping_engine.insights_ingester import (
                    CreativePerformance,
                )
                performance = CreativePerformance.from_dict(perf_data)
            except Exception:
                performance = None
        return cls(
            mapping_id=data.get("mapping_id", ""),
            facebook_creative_id=data.get("facebook_creative_id", ""),
            facebook_creative_name=data.get("facebook_creative_name", ""),
            facebook_account_id=data.get("facebook_account_id", ""),
            eagle_filename=data.get("eagle_filename", ""),
            eagle_path=data.get("eagle_path", ""),
            local_path=data.get("local_path", ""),
            scores=MappingScores.from_dict(data.get("scores", {})),
            confidence=float(data.get("confidence", 0.0)),
            match_method=data.get("match_method", ""),
            status=status,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            reviewed_by=data.get("reviewed_by", ""),
            review_note=data.get("review_note", ""),
            delivery_status=delivery_status,
            publish_id=data.get("publish_id", ""),
            ad_id=data.get("ad_id", ""),
            ad_creative_id=data.get("ad_creative_id", ""),
            delivered_at=data.get("delivered_at", ""),
            delivery_error=data.get("delivery_error", ""),
            delivery_attempts=int(data.get("delivery_attempts", 0)),
            auto_campaign_id=data.get("auto_campaign_id", ""),
            auto_adset_id=data.get("auto_adset_id", ""),
            auto_strategy=data.get("auto_strategy", ""),
            performance=performance,
            performance_score=float(data.get("performance_score", 0.0)),
            delivery_priority=float(data.get("delivery_priority", 0.0)),
            auto_archived=bool(data.get("auto_archived", False)),
            auto_archived_reason=data.get("auto_archived_reason", ""),
        )


@dataclass
class ReviewTask:
    """人工审核任务。"""

    task_id: str
    mapping_id: str
    facebook_creative_id: str
    candidates: list[dict] = field(default_factory=list)
    created_at: str = ""
    status: str = "open"
    assigned_to: str = ""
    resolution: str = ""
    resolved_at: str = ""
    resolved_by: str = ""
    review_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mapping_id": self.mapping_id,
            "facebook_creative_id": self.facebook_creative_id,
            "candidates": list(self.candidates),
            "created_at": self.created_at,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "review_note": self.review_note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewTask:
        return cls(
            task_id=data.get("task_id", ""),
            mapping_id=data.get("mapping_id", ""),
            facebook_creative_id=data.get("facebook_creative_id", ""),
            candidates=list(data.get("candidates", [])),
            created_at=data.get("created_at", ""),
            status=data.get("status", "open"),
            assigned_to=data.get("assigned_to", ""),
            resolution=data.get("resolution", ""),
            resolved_at=data.get("resolved_at", ""),
            resolved_by=data.get("resolved_by", ""),
            review_note=data.get("review_note", ""),
        )


def now_iso() -> str:
    """当前 UTC 时间 ISO 格式。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "MappingStatus",
    "MappingDeliveryStatus",
    "MappingScores",
    "CreativeMappingRecord",
    "ReviewTask",
    "now_iso",
]
