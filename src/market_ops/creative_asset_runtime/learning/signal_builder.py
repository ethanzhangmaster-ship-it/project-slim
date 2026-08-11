"""E11.2.5 — Learning Signal Builder。

将 WinnerProfile 转换为 E10.1 LearningSignal 格式。

E11 职责：
  - 识别 Winner
  - 聚合性能数据
  - 输出标准化 LearningSignal

V8.5 职责：
  - 消费 LearningSignal
  - 执行 DNA 分析
  - 驱动 Mutation Engine
  - 生成新 Creative

连接点：
  E11 WinnerProfile → LearningSignal → V8.5 Growth Loop
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from market_ops.execution_runtime.schemas import (
    LearningSignal,
    FeedbackType,
)

from .winner_detector import WinnerProfile

if TYPE_CHECKING:
    from ..events.asset_events import AssetEvent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningSignalBuilder:
    """E11 Winner → V8.5 LearningSignal 转换器。

    将 WinnerProfile 转换为 E10.1 兼容的 LearningSignal，
    供 V8.5 Autonomous Growth Loop 消费。

    Usage:
        builder = LearningSignalBuilder()
        signal = builder.build(winner_profile)
        # → LearningSignal(feedback_type=SUCCESS, ...)
    """

    # 信号类型映射
    ACTION_TO_FEEDBACK = {
        "SCALE": FeedbackType.SUCCESS,
        "ANALYZE": FeedbackType.NEUTRAL,
        "RETEST": FeedbackType.NEUTRAL,
        "KILL": FeedbackType.WARNING,
    }

    def __init__(self) -> None:
        self._signals: list[LearningSignal] = []
        self._signal_count: int = 0

    # ── Public API ───────────────────────────────────────

    def build(self, profile: WinnerProfile) -> LearningSignal:
        """将 WinnerProfile 转换为 LearningSignal。

        Args:
            profile: WinnerProfile from WinnerDetector

        Returns:
            E10.1 LearningSignal
        """
        feedback_type = self.ACTION_TO_FEEDBACK.get(
            profile.recommended_action,
            FeedbackType.NEUTRAL,
        )

        # 构建 metrics
        metrics = {
            # ── Performance ──
            "spend": profile.spend,
            "revenue": profile.revenue,
            "roas": profile.roas,
            "revenue_d7": profile.revenue_d7,
            "revenue_d30": profile.revenue_d30,
            "impressions": profile.impressions,
            "installs": profile.installs,

            # ── Retention ──
            "retention_d1": profile.retention_d1,
            "retention_d7": profile.retention_d7,
            "payer_count_d30": profile.payer_count_d30,

            # ── Asset ──
            "creative_id": profile.creative_id,
            "eagle_v_number": profile.eagle_v_number,
            "eagle_filename": profile.eagle_filename,
            "a_number": profile.a_number,

            # ── Action ──
            "recommended_action": profile.recommended_action,
            "action_confidence": profile.action_confidence,
            "lifecycle_status": profile.status,
        }

        # 构建推荐
        recommendation = self._build_recommendation(profile)

        signal = LearningSignal(
            signal_id=f"ls_{uuid.uuid4().hex[:12]}",
            task_id=profile.profile_id,  # 关联 WinnerProfile
            action_type=profile.recommended_action,
            feedback_type=feedback_type.value,
            confidence=profile.action_confidence,
            metrics=metrics,
            recommendation=recommendation,
            created_at=_now(),
        )

        self._signals.append(signal)
        self._signal_count += 1

        return signal

    def build_from_event(self, event: AssetEvent) -> LearningSignal:
        """从 AssetEvent 直接构建 LearningSignal（简化路径）。

        Args:
            event: WINNER_DETECTED AssetEvent

        Returns:
            E10.1 LearningSignal
        """
        payload = event.payload
        roas = float(payload.get("roas", 0))

        if roas >= 3.0:
            action = "SCALE"
            feedback = FeedbackType.SUCCESS
            confidence = 0.9
        elif roas >= 1.5:
            action = "ANALYZE"
            feedback = FeedbackType.NEUTRAL
            confidence = 0.8
        else:
            action = "ANALYZE"
            feedback = FeedbackType.NEUTRAL
            confidence = 0.6

        return LearningSignal(
            signal_id=f"ls_{uuid.uuid4().hex[:12]}",
            task_id=event.creative_id,
            action_type=action,
            feedback_type=feedback.value,
            confidence=confidence,
            metrics={
                "creative_id": event.creative_id,
                "eagle_v_number": event.eagle_v_number,
                "spend": float(payload.get("spend", 0)),
                "revenue": float(payload.get("revenue", 0)),
                "roas": roas,
                "impressions": int(payload.get("impressions", 0)),
                "installs": int(payload.get("installs", 0)),
                "recommended_action": action,
                "lifecycle_status": payload.get("status", "WINNER"),
            },
            recommendation=self._build_simple_recommendation(
                action, roas,
                float(payload.get("spend", 0)),
            ),
            created_at=_now(),
        )

    def get_signals(self) -> list[LearningSignal]:
        return list(self._signals)

    def get_signals_by_type(self, feedback_type: FeedbackType) -> list[LearningSignal]:
        return [s for s in self._signals if s.feedback_type == feedback_type.value]

    @property
    def signal_count(self) -> int:
        return self._signal_count

    # ── Internal ────────────────────────────────────────

    def _build_recommendation(self, profile: WinnerProfile) -> str:
        """构建推荐文本。"""
        if profile.recommended_action == "SCALE":
            return (
                f"[SCALE] Creative {profile.creative_id} ({profile.eagle_filename}) "
                f"achieved ROAS {profile.roas:.1f}x with ${profile.spend:.0f} spend. "
                f"Recommend increasing budget by 50-100% and entering DNA analysis."
            )
        elif profile.recommended_action == "ANALYZE":
            return (
                f"[ANALYZE] Creative {profile.creative_id} ({profile.eagle_filename}) "
                f"achieved ROAS {profile.roas:.1f}x. "
                f"Recommend DNA analysis to identify winning genetic patterns."
            )
        else:
            return (
                f"[RETEST] Creative {profile.creative_id} ({profile.eagle_filename}) "
                f"achieved ROAS {profile.roas:.1f}x. "
                f"Recommend re-testing with larger audience before deciding."
            )

    def _build_simple_recommendation(
        self,
        action: str,
        roas: float,
        spend: float,
    ) -> str:
        """构建简化推荐文本。"""
        return (
            f"[{action}] ROAS {roas:.1f}x with ${spend:.0f} spend. "
            f"Recommend {action.lower()} action."
        )

    def __repr__(self) -> str:
        return f"LearningSignalBuilder(signals={self._signal_count})"