"""E11.2.3 — Asset Event Types（frozen dataclass，不可变事件）。

遵循 observability/events.py 的 BaseEvent 模式：
  - frozen=True：不可变，安全并发
  - event_id + timestamp 自动生成
  - to_dict() 支持序列化/日志/回放

事件链：
  EAGLE_ASSET_DISCOVERED → ASSET_MATCHED → ASSET_MATERIALIZED
  → PERFORMANCE_UPDATED → WINNER_DETECTED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"evt_{uuid.uuid4().hex[:12]}"


class AssetEventType(str, Enum):
    """资产事件类型枚举。"""

    # ── 扫描阶段 ──
    EAGLE_ASSET_DISCOVERED = "eagle_asset_discovered"
    """Eagle 库中发现了新素材。"""

    # ── 同步阶段 ──
    FACEBOOK_CREATIVE_SYNCED = "facebook_creative_synced"
    """Facebook 广告数据已同步。"""

    # ── 匹配阶段 ──
    ASSET_MATCHED = "asset_matched"
    """素材与广告已匹配成功。"""

    # ── 实体化阶段 ──
    ASSET_MATERIALIZED = "asset_materialized"
    """资产已写入 entity.json。"""

    ASSET_MATERIALIZE_FAILED = "asset_materialize_failed"
    """资产实体化失败。"""

    # ── 性能阶段 ──
    PERFORMANCE_UPDATED = "performance_updated"
    """广告性能数据已更新（spend/revenue/ROAS）。"""

    # ── 生命周期阶段 ──
    ASSET_WINNER_DETECTED = "winner_detected"
    """素材被标记为赢家（ROAS超过阈值）。"""

    ASSET_FAILED = "asset_failed"
    """素材被标记为失败（ROAS过低）。"""

    ASSET_ARCHIVED = "asset_archived"
    """素材被归档。"""

    # ── 系统事件 ──
    EAGLE_SCAN_COMPLETED = "eagle_scan_completed"
    """Eagle 扫描完成。"""

    BINDING_COMPLETED = "binding_completed"
    """绑定流程完成。"""


@dataclass(frozen=True)
class AssetEvent:
    """资产领域事件（不可变）。

    Attributes:
        event_id:     事件唯一 ID
        event_type:   事件类型
        creative_id:  关联的 Facebook creative_id
        eagle_v_number: Eagle v 号（如 v2601536）
        payload:      事件负载数据
        timestamp:    事件时间戳 (ISO 8601)
        retry_count:  重试次数（用于失败重试）
        error:        错误信息（仅失败事件）
    """

    event_id: str = field(default_factory=_new_id)
    event_type: AssetEventType = AssetEventType.EAGLE_ASSET_DISCOVERED
    creative_id: str = ""
    eagle_v_number: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)
    retry_count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于日志/持久化/回放）。"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "creative_id": self.creative_id,
            "eagle_v_number": self.eagle_v_number,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetEvent:
        """从 dict 反序列化。"""
        return cls(
            event_id=data.get("event_id", ""),
            event_type=AssetEventType(data.get("event_type", "")),
            creative_id=data.get("creative_id", ""),
            eagle_v_number=data.get("eagle_v_number", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            retry_count=data.get("retry_count", 0),
            error=data.get("error", ""),
        )

    def with_retry(self) -> AssetEvent:
        """返回一个新的重试事件（retry_count + 1）。"""
        return AssetEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            creative_id=self.creative_id,
            eagle_v_number=self.eagle_v_number,
            payload=self.payload,
            timestamp=_now(),
            retry_count=self.retry_count + 1,
            error=self.error,
        )

    def with_error(self, error: str) -> AssetEvent:
        """返回一个新的带错误信息的事件。"""
        return AssetEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            creative_id=self.creative_id,
            eagle_v_number=self.eagle_v_number,
            payload=self.payload,
            timestamp=self.timestamp,
            retry_count=self.retry_count,
            error=error,
        )

    def __repr__(self) -> str:
        return (
            f"AssetEvent({self.event_type.value}, "
            f"creative={self.creative_id or 'N/A'}, "
            f"eagle={self.eagle_v_number or 'N/A'})"
        )