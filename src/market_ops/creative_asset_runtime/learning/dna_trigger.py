"""E11.2.5 — DNA Trigger。

监听 LearningSignal，触发 V8.5 DNA Engine。
E11 不自己分析 DNA，而是发出信号让 V8.5 来消费。

职责分离：
  E11:   "这个素材赢了，ROAS=3.0"
  V8.5:  "为什么赢？提取 DNA，生成 Mutation"

触发条件：
  - 推荐动作 = ANALYZE 或 SCALE
  - 置信度 >= 0.6
  - 样本量充足（impressions >= 1000）

输出：
  DNATriggerSignal → V8.5 DNA Engine
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.execution_runtime.schemas import LearningSignal, FeedbackType

from .winner_detector import WinnerProfile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DNATriggerSignal:
    """DNA 分析触发信号。

    发往 V8.5 DNA Engine，请求分析指定素材的创意 DNA。

    Attributes:
        trigger_id:      触发 ID
        creative_id:     Facebook creative_id
        eagle_v_number:  Eagle v 号
        eagle_filename:  Eagle 文件名
        learning_signal: 关联的 LearningSignal
        priority:        优先级 (HIGH/MEDIUM/LOW)
        reason:          触发原因
    """

    trigger_id: str = ""
    creative_id: str = ""
    eagle_v_number: str = ""
    eagle_filename: str = ""

    # ── V8.5 消费字段 ──────────────────────────────────
    learning_signal: dict[str, Any] = field(default_factory=dict)
    asset_reference: dict[str, Any] = field(default_factory=dict)

    priority: str = "MEDIUM"
    reason: str = ""
    triggered_at: str = ""

    def __post_init__(self) -> None:
        if not self.trigger_id:
            self.trigger_id = f"dna_trig_{uuid.uuid4().hex[:12]}"
        if not self.triggered_at:
            self.triggered_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "creative_id": self.creative_id,
            "eagle_v_number": self.eagle_v_number,
            "eagle_filename": self.eagle_filename,
            "learning_signal": self.learning_signal,
            "asset_reference": self.asset_reference,
            "priority": self.priority,
            "reason": self.reason,
            "triggered_at": self.triggered_at,
        }

    def __repr__(self) -> str:
        return (
            f"DNATriggerSignal(id={self.trigger_id}, "
            f"creative={self.creative_id}, "
            f"priority={self.priority})"
        )


class DNATrigger:
    """DNA 分析触发器。

    评估 LearningSignal，决定是否需要触发 DNA 分析。

    Usage:
        trigger = DNATrigger()
        dna_signal = trigger.evaluate(learning_signal)
        if dna_signal:
            send_to_v85_dna_engine(dna_signal)
    """

    # 触发阈值
    MIN_IMPRESSIONS = 1000
    MIN_CONFIDENCE = 0.6
    MIN_ROAS_ANALYZE = 1.0

    def __init__(self) -> None:
        self._triggers: list[DNATriggerSignal] = []
        self._trigger_count: int = 0

    # ── Public API ───────────────────────────────────────

    def evaluate(self, signal: LearningSignal) -> DNATriggerSignal | None:
        """评估 LearningSignal，决定是否触发 DNA 分析。

        触发条件：
          1. feedback_type in (SUCCESS, NEUTRAL)
          2. confidence >= MIN_CONFIDENCE
          3. impressions >= MIN_IMPRESSIONS
          4. roas >= MIN_ROAS_ANALYZE

        Args:
            signal: E10.1 LearningSignal

        Returns:
            DNATriggerSignal if triggered, None otherwise
        """
        metrics = signal.metrics if isinstance(signal.metrics, dict) else {}

        feedback = signal.feedback_type
        confidence = signal.confidence
        impressions = int(metrics.get("impressions", 0))
        roas = float(metrics.get("roas", 0))

        # 条件检查
        if feedback not in (FeedbackType.SUCCESS.value, FeedbackType.NEUTRAL.value):
            return None

        if confidence < self.MIN_CONFIDENCE:
            return None

        if impressions < self.MIN_IMPRESSIONS:
            return None

        if roas < self.MIN_ROAS_ANALYZE:
            return None

        # 确定优先级
        if roas >= 3.0:
            priority = "HIGH"
            reason = f"High ROAS {roas:.1f}x — prioritize DNA analysis"
        elif roas >= 1.5:
            priority = "MEDIUM"
            reason = f"Good ROAS {roas:.1f}x — standard DNA analysis"
        else:
            priority = "LOW"
            reason = f"Marginal ROAS {roas:.1f}x — optional DNA analysis"

        trigger = DNATriggerSignal(
            creative_id=metrics.get("creative_id", ""),
            eagle_v_number=metrics.get("eagle_v_number", ""),
            eagle_filename=metrics.get("eagle_filename", ""),
            learning_signal=signal.to_dict(),
            asset_reference={
                "creative_id": metrics.get("creative_id", ""),
                "eagle_v_number": metrics.get("eagle_v_number", ""),
                "eagle_filename": metrics.get("eagle_filename", ""),
                "a_number": metrics.get("a_number", ""),
            },
            priority=priority,
            reason=reason,
        )

        self._triggers.append(trigger)
        self._trigger_count += 1

        return trigger

    def evaluate_profile(self, profile: WinnerProfile) -> DNATriggerSignal | None:
        """从 WinnerProfile 直接评估（跳过 LearningSignal）。"""
        if profile.impressions < self.MIN_IMPRESSIONS:
            return None

        if profile.roas >= 3.0:
            priority = "HIGH"
        elif profile.roas >= 1.5:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        trigger = DNATriggerSignal(
            creative_id=profile.creative_id,
            eagle_v_number=profile.eagle_v_number,
            eagle_filename=profile.eagle_filename,
            asset_reference={
                "creative_id": profile.creative_id,
                "eagle_v_number": profile.eagle_v_number,
                "eagle_filename": profile.eagle_filename,
                "a_number": profile.a_number,
                "roas": profile.roas,
                "spend": profile.spend,
                "revenue": profile.revenue,
            },
            priority=priority,
            reason=f"Winner profile ROAS {profile.roas:.1f}x — DNA analysis recommended",
        )

        self._triggers.append(trigger)
        self._trigger_count += 1

        return trigger

    def get_triggers(self) -> list[DNATriggerSignal]:
        return list(self._triggers)

    def get_high_priority(self) -> list[DNATriggerSignal]:
        return [t for t in self._triggers if t.priority == "HIGH"]

    @property
    def trigger_count(self) -> int:
        return self._trigger_count

    def __repr__(self) -> str:
        return f"DNATrigger(triggers={self._trigger_count})"