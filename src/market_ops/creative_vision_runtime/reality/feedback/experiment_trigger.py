"""E12.4 Phase 2 — Experiment Trigger。

决定是否启动实验 —— 不是所有 Mutation 都需要执行。

安全规则:
  1. Prediction confidence >= 0.80
  2. Spend >= $100
  3. Expected Impact: fatigue probability > 0.75
  4. Cooldown: 同一 creative 7 天内不能重复实验

输出:
  ExperimentTriggerResult(should_trigger, reason)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from .models import (
    FeedbackSignalType,
    MutationRequest,
    RealityFeedbackSignal,
)


# ── Default thresholds ─────────────────────────────────────


class ExperimentTriggerThresholds:
    """实验触发阈值。"""

    MIN_CONFIDENCE = 0.80           # 最低置信度
    MIN_SPEND = 100.0               # 最低花费 $
    MIN_FATIGUE_PROBABILITY = 0.75  # 最低疲劳概率
    COOLDOWN_DAYS = 7               # 同一 creative 冷却天数
    MIN_IMPROVEMENT_EXPECTED = 0.05  # 最低预期改善幅度


@dataclass
class ExperimentTriggerResult:
    """实验触发判断结果。

    Attributes:
        should_trigger:  是否触发实验
        request_id:      关联的 MutationRequest ID
        reason:          触发/不触发原因列表
        thresholds_met:  满足的阈值列表
        thresholds_failed: 未满足的阈值列表
    """

    should_trigger: bool = False
    request_id: str = ""
    reason: list[str] = field(default_factory=list)
    thresholds_met: list[str] = field(default_factory=list)
    thresholds_failed: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"ExperimentTriggerResult(trigger={self.should_trigger}, "
            f"request={self.request_id}, "
            f"reasons={len(self.reason)})"
        )


class ExperimentTrigger:
    """实验触发引擎。

    对每个 MutationRequest 应用安全规则，决定是否启动实验。

    Usage:
        >>> trigger = ExperimentTrigger()
        >>> signal = RealityFeedbackSignal(...)
        >>> request = MutationRequest(...)
        >>> result = trigger.evaluate(signal, request)
        >>> if result.should_trigger:
        ...     print("Start experiment")
    """

    def __init__(self) -> None:
        self.thresholds = ExperimentTriggerThresholds()

        # 冷却追踪：{creative_id: last_trigger_time}
        self._cooldown_tracker: dict[str, datetime] = {}

        # 统计
        self.total_evaluated: int = 0
        self.total_triggered: int = 0
        self.total_rejected: int = 0

    # ── Main API ───────────────────────────────────────────

    def evaluate(
        self,
        signal: RealityFeedbackSignal,
        request: MutationRequest,
        current_time: datetime | None = None,
    ) -> ExperimentTriggerResult:
        """评估是否触发实验。

        Args:
            signal:       反馈信号（含 severity, confidence, spend）
            request:      突变请求（含 intent, creative_id）
            current_time: 当前时间（用于冷却检查）

        Returns:
            ExperimentTriggerResult
        """
        self.total_evaluated += 1

        if current_time is None:
            current_time = datetime.now(timezone.utc)

        met: list[str] = []
        failed: list[str] = []
        reasons: list[str] = []

        # 条件 1: Confidence >= 0.80
        if signal.confidence >= self.thresholds.MIN_CONFIDENCE:
            met.append("confidence")
        else:
            failed.append("confidence")
            reasons.append(
                f"Confidence too low: {signal.confidence:.2f} < "
                f"{self.thresholds.MIN_CONFIDENCE}"
            )

        # 条件 2: Spend >= $100
        spend = signal.metadata.get("spend", 0.0)
        if spend >= self.thresholds.MIN_SPEND:
            met.append("spend")
        else:
            failed.append("spend")
            reasons.append(
                f"Spend too low: ${spend:.0f} < ${self.thresholds.MIN_SPEND}"
            )

        # 条件 3: Fatigue probability > 0.75 (仅 FATIGUE_WARNING)
        if signal.signal_type == FeedbackSignalType.FATIGUE_WARNING:
            if signal.severity >= self.thresholds.MIN_FATIGUE_PROBABILITY:
                met.append("fatigue_probability")
            else:
                failed.append("fatigue_probability")
                reasons.append(
                    f"Fatigue probability too low: {signal.severity:.2f} < "
                    f"{self.thresholds.MIN_FATIGUE_PROBABILITY}"
                )
        else:
            # 非疲劳信号，检查 severity 作为通用影响指标
            if signal.severity >= self.thresholds.MIN_IMPROVEMENT_EXPECTED:
                met.append("expected_impact")
            else:
                failed.append("expected_impact")
                reasons.append(
                    f"Expected impact too low: {signal.severity:.2f} < "
                    f"{self.thresholds.MIN_IMPROVEMENT_EXPECTED}"
                )

        # 条件 4: Cooldown（7 天内不能重复实验同一 creative）
        if self._check_cooldown(signal.creative_id, current_time):
            met.append("cooldown")
        else:
            failed.append("cooldown")
            last_trigger = self._cooldown_tracker.get(signal.creative_id)
            if last_trigger:
                days_since = (current_time - last_trigger).days
                reasons.append(
                    f"Cooldown active: {days_since}d since last experiment "
                    f"(need {self.thresholds.COOLDOWN_DAYS}d)"
                )

        should_trigger = len(failed) == 0

        if should_trigger:
            self.total_triggered += 1
            self._cooldown_tracker[signal.creative_id] = current_time
            reasons.append("All thresholds met — experiment triggered")
        else:
            self.total_rejected += 1

        return ExperimentTriggerResult(
            should_trigger=should_trigger,
            request_id=request.request_id,
            reason=reasons,
            thresholds_met=met,
            thresholds_failed=failed,
        )

    def evaluate_batch(
        self,
        signals: list[RealityFeedbackSignal],
        requests: list[MutationRequest],
        current_time: datetime | None = None,
    ) -> list[ExperimentTriggerResult]:
        """批量评估。

        Args:
            signals:  反馈信号列表
            requests: 突变请求列表（与 signals 一一对应）
            current_time: 当前时间

        Returns:
            ExperimentTriggerResult 列表
        """
        results: list[ExperimentTriggerResult] = []
        for signal, request in zip(signals, requests):
            results.append(
                self.evaluate(signal, request, current_time)
            )
        return results

    def get_triggered(
        self,
        results: list[ExperimentTriggerResult],
    ) -> list[ExperimentTriggerResult]:
        """过滤出触发的结果。"""
        return [r for r in results if r.should_trigger]

    def get_rejected(
        self,
        results: list[ExperimentTriggerResult],
    ) -> list[ExperimentTriggerResult]:
        """过滤出未触发的结果。"""
        return [r for r in results if not r.should_trigger]

    # ── Cooldown management ────────────────────────────────

    def _check_cooldown(
        self,
        creative_id: str,
        current_time: datetime,
    ) -> bool:
        """检查冷却期是否已过。"""
        last_trigger = self._cooldown_tracker.get(creative_id)
        if last_trigger is None:
            return True  # 从未触发过，allowed

        days_since = (current_time - last_trigger).days
        return days_since >= self.thresholds.COOLDOWN_DAYS

    def reset_cooldown(self, creative_id: str) -> None:
        """重置指定创意的冷却（用于测试/TESTING）。"""
        self._cooldown_tracker.pop(creative_id, None)

    def reset_all_cooldowns(self) -> None:
        """重置所有冷却。"""
        self._cooldown_tracker.clear()

    def get_cooldown_remaining(
        self,
        creative_id: str,
        current_time: datetime | None = None,
    ) -> int:
        """获取剩余冷却天数。"""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        last_trigger = self._cooldown_tracker.get(creative_id)
        if last_trigger is None:
            return 0

        days_since = (current_time - last_trigger).days
        remaining = self.thresholds.COOLDOWN_DAYS - days_since
        return max(0, remaining)

    def __repr__(self) -> str:
        return (
            f"ExperimentTrigger(evaluated={self.total_evaluated}, "
            f"triggered={self.total_triggered}, "
            f"rejected={self.total_rejected})"
        )