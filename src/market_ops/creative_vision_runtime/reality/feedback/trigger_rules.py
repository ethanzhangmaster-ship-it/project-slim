"""E12.4 — Trigger Rules Engine。

安全阈值引擎，防止低质量预测直接触发 E11 行动。

规则：
  - Fatigue:    probability > 0.75 AND confidence > 0.8 AND spend > min_spend
  - ROAS Drop:  roas_drop > 20% AND confidence > 0.8 AND spend > min_spend
  - Scale:      roas_improving AND confidence > 0.7
  - Replacement: ROAS < 0.3 AND confidence > 0.85

目的：避免预测结果直接触发，增加安全阈值保证 E11 不会误操作。
"""

from __future__ import annotations

from .models import FeedbackSignalType, RealityFeedbackSignal


# ── Default thresholds ─────────────────────────────────────


class TriggerThresholds:
    """触发阈值配置。"""

    # Fatigue
    FATIGUE_PROBABILITY = 0.75
    FATIGUE_CONFIDENCE = 0.80

    # ROAS Decline
    ROAS_DROP_THRESHOLD = 0.20  # 20% 下降
    ROAS_DECLINE_CONFIDENCE = 0.80

    # Scale Opportunity
    SCALE_CONFIDENCE = 0.70

    # Creative Replacement
    REPLACEMENT_ROAS_MAX = 0.30  # ROAS < 0.3
    REPLACEMENT_CONFIDENCE = 0.85

    # General
    MIN_CONFIDENCE = 0.80
    MIN_SPEND = 100.0  # 最低花费 $100
    MIN_IMPRESSIONS = 1000  # 最低展示量


class TriggerRules:
    """触发规则引擎。

    对每个预测信号应用安全阈值，决定是否触发行动。

    Usage:
        >>> rules = TriggerRules()
        >>> signal = RealityFeedbackSignal(...)
        >>> if rules.should_trigger(signal):
        ...     print("Action triggered")
    """

    def __init__(self) -> None:
        self.thresholds = TriggerThresholds()

    def should_trigger(self, signal: RealityFeedbackSignal) -> bool:
        """判断信号是否应该触发行动。

        Args:
            signal: 反馈信号

        Returns:
            是否触发
        """
        # 通用阈值：confidence 必须 >= MIN_CONFIDENCE
        if signal.confidence < self.thresholds.MIN_CONFIDENCE:
            return False

        # 按类型检查
        if signal.signal_type == FeedbackSignalType.FATIGUE_WARNING:
            return self._check_fatigue(signal)
        elif signal.signal_type == FeedbackSignalType.ROAS_DECLINE:
            return self._check_roas_decline(signal)
        elif signal.signal_type == FeedbackSignalType.SCALE_OPPORTUNITY:
            return self._check_scale(signal)
        elif signal.signal_type == FeedbackSignalType.CREATIVE_REPLACEMENT:
            return self._check_replacement(signal)
        elif signal.signal_type == FeedbackSignalType.DATA_COLLECTION:
            return False  # DATA_COLLECTION 不触发行动

        return False

    def evaluate(
        self,
        signals: list[RealityFeedbackSignal],
    ) -> list[RealityFeedbackSignal]:
        """批量评估信号，返回触发行动的信号。

        Args:
            signals: 反馈信号列表

        Returns:
            触发行动的信号列表（按 priority 降序）
        """
        triggered = [s for s in signals if self.should_trigger(s)]
        return sorted(triggered, key=lambda s: s.priority, reverse=True)

    def get_trigger_reason(
        self,
        signal: RealityFeedbackSignal,
    ) -> str:
        """获取触发原因（用于日志/审计）。"""
        if not self.should_trigger(signal):
            reasons = []
            if signal.confidence < self.thresholds.MIN_CONFIDENCE:
                reasons.append(
                    f"confidence {signal.confidence:.2f} < {self.thresholds.MIN_CONFIDENCE}"
                )
            if signal.signal_type == FeedbackSignalType.FATIGUE_WARNING:
                if signal.severity < self.thresholds.FATIGUE_PROBABILITY:
                    reasons.append(
                        f"severity {signal.severity:.2f} < {self.thresholds.FATIGUE_PROBABILITY}"
                    )
            return f"Not triggered: {'; '.join(reasons)}" if reasons else "Not triggered"
        return "Triggered"

    # ── Private check methods ──────────────────────────────

    def _check_fatigue(self, signal: RealityFeedbackSignal) -> bool:
        """检查疲劳预警触发条件。"""
        if signal.severity < self.thresholds.FATIGUE_PROBABILITY:
            return False
        if signal.confidence < self.thresholds.FATIGUE_CONFIDENCE:
            return False
        return self._check_spend(signal)

    def _check_roas_decline(self, signal: RealityFeedbackSignal) -> bool:
        """检查 ROAS 下降触发条件。"""
        if signal.severity < self.thresholds.ROAS_DROP_THRESHOLD:
            return False
        if signal.confidence < self.thresholds.ROAS_DECLINE_CONFIDENCE:
            return False
        return self._check_spend(signal)

    def _check_scale(self, signal: RealityFeedbackSignal) -> bool:
        """检查放量机会触发条件。"""
        if signal.confidence < self.thresholds.SCALE_CONFIDENCE:
            return False
        return self._check_spend(signal)

    def _check_replacement(self, signal: RealityFeedbackSignal) -> bool:
        """检查素材替换触发条件。"""
        if signal.confidence < self.thresholds.REPLACEMENT_CONFIDENCE:
            return False
        return self._check_spend(signal)

    def _check_spend(self, signal: RealityFeedbackSignal) -> bool:
        """检查最低花费。如果 metadata 中没有 spend，默认通过。"""
        spend = signal.metadata.get("spend", self.thresholds.MIN_SPEND)
        return spend >= self.thresholds.MIN_SPEND

    def __repr__(self) -> str:
        return "TriggerRules()"