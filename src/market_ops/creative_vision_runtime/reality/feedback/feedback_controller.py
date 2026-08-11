"""E12.4 — Reality Feedback Controller。

核心编排器：Prediction → Trigger → Signal → Action。

流程:
  E12.3 Predictions
       │
       ▼
  TriggerRules.evaluate()
       │
       ▼
  Create FeedbackSignal
       │
       ▼
  ActionMapper.map()
       │
       ▼
  E11 Evolution Actions
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .action_mapper import ActionMapper
from .models import (
    FeedbackSignalType,
    PredictionOutcome,
    RealityFeedbackSignal,
)
from .trigger_rules import TriggerRules

# Lazy imports for E12.3 types
from ..prediction.models import (
    LifecyclePrediction,
    PredictionType,
    RealityPrediction,
    RiskLevel,
)


# ── Signal type mapping ────────────────────────────────────

PREDICTION_TO_SIGNAL: dict[PredictionType, FeedbackSignalType] = {
    PredictionType.CREATIVE_FATIGUE_RISK: FeedbackSignalType.FATIGUE_WARNING,
    PredictionType.ROAS_DECAY_RISK: FeedbackSignalType.ROAS_DECLINE,
    PredictionType.SCALE_OPPORTUNITY: FeedbackSignalType.SCALE_OPPORTUNITY,
    PredictionType.BUDGET_BURN_RISK: FeedbackSignalType.CREATIVE_REPLACEMENT,
}


@dataclass
class FeedbackResult:
    """FeedbackController 的输出。

    Attributes:
        signals:              所有生成的反馈信号
        triggered:            触发行动的信号（通过 TriggerRules）
        actions:              映射后的 E11 行动
        evolution_opportunities: E11.9 EvolutionOpportunity 格式
        summary:              摘要
    """

    signals: list[RealityFeedbackSignal] = field(default_factory=list)
    triggered: list[RealityFeedbackSignal] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    evolution_opportunities: list[dict] = field(default_factory=list)
    summary: str = ""

    def __repr__(self) -> str:
        return (
            f"FeedbackResult(signals={len(self.signals)}, "
            f"triggered={len(self.triggered)}, "
            f"actions={len(self.actions)})"
        )


class FeedbackController:
    """E12.4 Reality Feedback Controller。

    核心编排：Predictions → Signals → Actions。

    Usage:
        >>> controller = FeedbackController()
        >>> result = controller.evaluate(predictions)
        >>> for action in result.actions:
        ...     print(action["action"], action["genes"])
    """

    def __init__(self) -> None:
        self.trigger_rules = TriggerRules()
        self.action_mapper = ActionMapper()

        # 统计
        self.total_predictions_processed: int = 0
        self.total_signals_generated: int = 0
        self.total_actions_triggered: int = 0

    # ── Main API ───────────────────────────────────────────

    def evaluate(
        self,
        predictions: list[RealityPrediction],
    ) -> FeedbackResult:
        """评估预测结果，生成反馈信号和行动。

        Args:
            predictions: E12.3 RealityPrediction 列表

        Returns:
            FeedbackResult 包含 signals, triggered, actions
        """
        self.total_predictions_processed += len(predictions)

        # 1. 转换为 FeedbackSignal
        signals = self._predictions_to_signals(predictions)
        self.total_signals_generated += len(signals)

        # 2. 触发规则过滤
        triggered = self.trigger_rules.evaluate(signals)

        # 3. 映射为 E11 行动
        actions = self.action_mapper.map_batch(triggered)
        self.total_actions_triggered += len(actions)

        # 4. 转换为 EvolutionOpportunity
        opportunities = self.action_mapper.to_evolution_opportunities(triggered)

        # 5. 摘要
        summary = self._build_summary(signals, triggered, actions)

        return FeedbackResult(
            signals=signals,
            triggered=triggered,
            actions=actions,
            evolution_opportunities=opportunities,
            summary=summary,
        )

    def evaluate_with_lifecycles(
        self,
        predictions: list[RealityPrediction],
        lifecycles: list[LifecyclePrediction],
    ) -> FeedbackResult:
        """评估预测结果 + 生命周期预测。

        LifecyclePrediction 提供额外的严重程度信息。
        """
        # 先做标准评估
        result = self.evaluate(predictions)

        # 增强：用 lifecycle 信息调整 severity
        lifecycle_map: dict[str, LifecyclePrediction] = {
            lc.creative_id: lc for lc in lifecycles
        }

        for signal in result.signals:
            lc = lifecycle_map.get(signal.creative_id)
            if lc is not None and lc.is_degrading:
                # 提升严重程度
                signal.severity = min(1.0, signal.severity + 0.1)
                signal.reason.append(
                    f"Lifecycle transitioning: {lc.current_stage.value} → {lc.predicted_stage.value}"
                )
                signal.metadata["lifecycle_stage"] = lc.current_stage.value
                signal.metadata["lifecycle_predicted"] = lc.predicted_stage.value
                signal.metadata["days_to_transition"] = lc.days_to_transition

        # 重新过滤
        result.triggered = self.trigger_rules.evaluate(result.signals)
        result.actions = self.action_mapper.map_batch(result.triggered)
        result.evolution_opportunities = self.action_mapper.to_evolution_opportunities(
            result.triggered
        )
        result.summary = self._build_summary(
            result.signals, result.triggered, result.actions
        )

        return result

    def get_actionable_signals(
        self,
        result: FeedbackResult,
        min_priority: float = 0.7,
    ) -> list[RealityFeedbackSignal]:
        """获取高优先级可行动信号。"""
        return [
            s for s in result.triggered
            if s.priority >= min_priority
        ]

    def get_signals_by_type(
        self,
        result: FeedbackResult,
        signal_type: FeedbackSignalType,
    ) -> list[RealityFeedbackSignal]:
        """按类型筛选信号。"""
        return [
            s for s in result.signals
            if s.signal_type == signal_type
        ]

    # ── Private methods ────────────────────────────────────

    def _predictions_to_signals(
        self,
        predictions: list[RealityPrediction],
    ) -> list[RealityFeedbackSignal]:
        """将预测转换为反馈信号。"""
        signals: list[RealityFeedbackSignal] = []

        for pred in predictions:
            signal_type = PREDICTION_TO_SIGNAL.get(
                pred.prediction_type, FeedbackSignalType.DATA_COLLECTION
            )

            signal = RealityFeedbackSignal(
                creative_id=pred.target_id,
                signal_type=signal_type,
                severity=pred.probability,
                confidence=pred.metadata.get("confidence", pred.probability),
                reason=list(pred.evidence),
                recommended_action=pred.recommended_action,
                source_prediction_id=pred.prediction_id,
                metadata={
                    "prediction_type": pred.prediction_type.value,
                    "risk_level": pred.risk_level.value,
                    "current_value": pred.current_value,
                    "predicted_value": pred.predicted_value,
                    "horizon_days": pred.horizon_days,
                    **pred.metadata,
                },
            )

            signals.append(signal)

        return signals

    @staticmethod
    def _build_summary(
        signals: list[RealityFeedbackSignal],
        triggered: list[RealityFeedbackSignal],
        actions: list[dict],
    ) -> str:
        """构建摘要。"""
        fatigue = len([
            s for s in signals
            if s.signal_type == FeedbackSignalType.FATIGUE_WARNING
        ])
        roas = len([
            s for s in signals
            if s.signal_type == FeedbackSignalType.ROAS_DECLINE
        ])
        scale = len([
            s for s in signals
            if s.signal_type == FeedbackSignalType.SCALE_OPPORTUNITY
        ])
        replace = len([
            s for s in signals
            if s.signal_type == FeedbackSignalType.CREATIVE_REPLACEMENT
        ])

        parts = [
            f"Signals: {len(signals)} total "
            f"(fatigue={fatigue}, roas={roas}, scale={scale}, replace={replace})",
            f"Triggered: {len(triggered)}",
            f"Actions: {len(actions)}",
        ]

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"FeedbackController(processed={self.total_predictions_processed}, "
            f"signals={self.total_signals_generated}, "
            f"actions={self.total_actions_triggered})"
        )