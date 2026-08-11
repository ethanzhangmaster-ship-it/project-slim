"""E11.2.5 — Winner Detector。

监听 WINNER_DETECTED 事件，提取完整 Winner Profile：
  - 素材信息（Eagle filename, creative_id, A-Number）
  - 性能数据（spend, revenue, ROAS, D7, D30）
  - 生命周期状态
  - 推荐动作（SCALE / ANALYZE / RETEST）

输出：WinnerProfile → 供 LearningSignalBuilder 使用
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..events.asset_events import AssetEvent, AssetEventType


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WinnerProfile:
    """Winner 素材完整画像。

    聚合了 E11 Asset Runtime 中所有已知信息：
      - 素材来源（Eagle）
      - 广告匹配（A-Number）
      - 性能数据（Facebook + Adjust）
      - 生命周期状态

    供 LearningSignalBuilder 转换为 V8.5 可消费的信号。
    """

    profile_id: str = ""
    creative_id: str = ""
    eagle_v_number: str = ""
    eagle_filename: str = ""
    a_number: str = ""

    # ── Performance ─────────────────────────────────────
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    revenue_d7: float = 0.0
    revenue_d30: float = 0.0
    impressions: int = 0
    installs: int = 0
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    payer_count_d30: int = 0

    # ── Lifecycle ───────────────────────────────────────
    status: str = "WINNER"

    # ── Recommendation ──────────────────────────────────
    recommended_action: str = "ANALYZE"  # SCALE / ANALYZE / RETEST
    action_confidence: float = 0.0

    # ── Meta ────────────────────────────────────────────
    detected_at: str = ""
    source_events: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.profile_id:
            self.profile_id = f"wp_{uuid.uuid4().hex[:12]}"
        if not self.detected_at:
            self.detected_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "creative_id": self.creative_id,
            "eagle_v_number": self.eagle_v_number,
            "eagle_filename": self.eagle_filename,
            "a_number": self.a_number,
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": self.roas,
            "revenue_d7": self.revenue_d7,
            "revenue_d30": self.revenue_d30,
            "impressions": self.impressions,
            "installs": self.installs,
            "retention_d1": self.retention_d1,
            "retention_d7": self.retention_d7,
            "payer_count_d30": self.payer_count_d30,
            "status": self.status,
            "recommended_action": self.recommended_action,
            "action_confidence": self.action_confidence,
            "detected_at": self.detected_at,
            "source_events": self.source_events,
        }

    def __repr__(self) -> str:
        return (
            f"WinnerProfile(id={self.profile_id}, "
            f"creative={self.creative_id}, "
            f"roas={self.roas:.1f}, "
            f"action={self.recommended_action})"
        )


class WinnerDetector:
    """Winner 检测器。

    监听 WINNER_DETECTED 事件，构建 WinnerProfile。
    不分析 DNA（交给 V8.5），只做数据聚合。

    Usage:
        detector = WinnerDetector()
        bus.subscribe("winner_detected", detector.on_winner)
        profile = detector.get_profile("v2601536")
    """

    def __init__(self) -> None:
        self._profiles: dict[str, WinnerProfile] = {}
        self._winner_count: int = 0

    # ── Event Handler ────────────────────────────────────

    def on_winner(self, event: AssetEvent) -> WinnerProfile | None:
        """处理 WINNER_DETECTED 事件。

        从事件 payload 中提取性能数据，构建 WinnerProfile。
        """
        creative_id = event.creative_id
        eagle_v = event.eagle_v_number
        payload = event.payload

        # 确定资产标识
        asset_id = eagle_v or creative_id
        if not asset_id:
            return None

        # 提取性能数据
        spend = float(payload.get("spend", 0))
        revenue = float(payload.get("revenue", 0))
        roas = float(payload.get("roas", 0))
        revenue_d7 = float(payload.get("revenue_d7", 0))
        revenue_d30 = float(payload.get("revenue_d30", 0))
        impressions = int(payload.get("impressions", 0))
        installs = int(payload.get("installs", 0))
        retention_d1 = float(payload.get("retention_d1", 0))
        retention_d7 = float(payload.get("retention_d7", 0))
        payer_count = int(payload.get("payer_count_d30", 0))

        # 推荐动作
        action, confidence = self._recommend_action(roas, spend, impressions)

        profile = WinnerProfile(
            creative_id=creative_id,
            eagle_v_number=eagle_v,
            eagle_filename=payload.get("eagle_filename", ""),
            a_number=payload.get("a_number", ""),
            spend=spend,
            revenue=revenue,
            roas=roas,
            revenue_d7=revenue_d7,
            revenue_d30=revenue_d30,
            impressions=impressions,
            installs=installs,
            retention_d1=retention_d1,
            retention_d7=retention_d7,
            payer_count_d30=payer_count,
            status=payload.get("status", "WINNER"),
            recommended_action=action,
            action_confidence=confidence,
            source_events=[event.event_id],
        )

        self._profiles[asset_id] = profile
        self._winner_count += 1

        return profile

    def on_performance_updated(self, event: AssetEvent) -> None:
        """处理 PERFORMANCE_UPDATED 事件，更新已有 Profile。

        如果 winner 之后有新的性能数据，更新 profile。
        """
        creative_id = event.creative_id
        eagle_v = event.eagle_v_number
        asset_id = eagle_v or creative_id

        existing = self._profiles.get(asset_id)
        if not existing:
            return

        payload = event.payload
        if "spend" in payload:
            existing.spend = float(payload.get("spend", existing.spend))
        if "revenue" in payload:
            existing.revenue = float(payload.get("revenue", existing.revenue))
        if "roas" in payload:
            existing.roas = float(payload.get("roas", existing.roas))
        if "revenue_d7" in payload:
            existing.revenue_d7 = float(payload.get("revenue_d7", existing.revenue_d7))
        if "revenue_d30" in payload:
            existing.revenue_d30 = float(payload.get("revenue_d30", existing.revenue_d30))
        if "impressions" in payload:
            existing.impressions = int(payload.get("impressions", existing.impressions))
        if "source" in payload:
            existing.source_events.append(event.event_id)

        # 重新评估推荐动作
        action, confidence = self._recommend_action(
            existing.roas, existing.spend, existing.impressions
        )
        existing.recommended_action = action
        existing.action_confidence = confidence

    # ── Query ────────────────────────────────────────────

    def get_profile(self, asset_id: str) -> WinnerProfile | None:
        return self._profiles.get(asset_id)

    def get_all_winners(self) -> list[WinnerProfile]:
        return list(self._profiles.values())

    def get_scale_candidates(self) -> list[WinnerProfile]:
        """获取推荐 SCALE 的 winner。"""
        return [p for p in self._profiles.values() if p.recommended_action == "SCALE"]

    def get_analyze_candidates(self) -> list[WinnerProfile]:
        """获取推荐 ANALYZE 的 winner。"""
        return [p for p in self._profiles.values() if p.recommended_action == "ANALYZE"]

    @property
    def winner_count(self) -> int:
        return self._winner_count

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _recommend_action(
        roas: float,
        spend: float,
        impressions: int,
    ) -> tuple[str, float]:
        """根据 ROAS 和花费推荐动作。

        规则：
          ROAS >= 3.0  → SCALE (高置信度)
          ROAS >= 1.5  → ANALYZE (中等置信度)
          ROAS >= 1.0  → RETEST (低置信度)
          ROAS < 1.0   → ANALYZE (需要理解为什么低)

        Returns:
            (action, confidence)
        """
        if roas >= 3.0:
            return ("SCALE", 0.9)
        elif roas >= 1.5:
            return ("ANALYZE", 0.8)
        elif roas >= 1.0:
            return ("RETEST", 0.6)
        else:
            return ("ANALYZE", 0.4)

    def __repr__(self) -> str:
        return f"WinnerDetector(winners={self._winner_count})"