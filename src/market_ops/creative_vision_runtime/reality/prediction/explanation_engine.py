"""E12.3 Phase 2 — Prediction Explanation Engine。

为预测结果生成人类可读的解释，说明:
  - 为什么做出这个预测
  - 哪些因素导致了预测结果
  - 建议采取什么行动
  - 参考类似案例

输出 PredictionExplanation 供 E11 Decision Engine 消费。
"""

from __future__ import annotations

from .models import (
    CreativeLifecycleStage,
    DecayPrediction,
    LifecyclePrediction,
    PredictionExplanation,
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
)


# ── Action templates ───────────────────────────────────────

ACTION_DETAILS: dict[str, str] = {
    "MUTATE_HOOK": (
        "Generate a new creative variant with a different hook mechanism "
        "while preserving the proven psychological gene. Target: restore CTR "
        "to previous peak levels."
    ),
    "MUTATE_VISUAL": (
        "Generate a new creative variant with updated visual style. "
        "Keep the core gameplay and hook genes unchanged."
    ),
    "MUTATE_CREATIVE": (
        "Generate a comprehensive creative variant. Review hook, visual, "
        "and gameplay genes for potential mutations."
    ),
    "MUTATE_MONETIZATION": (
        "Adjust monetization gene to improve ROAS. Consider changing "
        "offer timing, reward structure, or pricing presentation."
    ),
    "PAUSE_AND_MUTATE": (
        "Pause current creative and generate a new variant. "
        "Current trajectory is unsustainable — ROAS will drop below "
        "acceptable threshold within prediction horizon."
    ),
    "INCREASE_BUDGET": (
        "Scale budget on this creative. ROAS trend is improving, "
        "suggesting untapped audience potential."
    ),
    "PREPARE_MUTATION": (
        "Start preparing mutation variants now. Creative will enter "
        "fatigue within the predicted window. Having variants ready "
        "will minimize downtime."
    ),
    "RETIRE_AND_REGENERATE": (
        "Retire this creative and generate a completely new one. "
        "Current ROAS is below viable threshold and continuing to decline."
    ),
    "SCALE_BUDGET": (
        "Increase budget allocation. Creative is at peak performance "
        "with strong CTR and ROAS."
    ),
    "COLLECT_DATA": (
        "Continue running with current settings. Insufficient data "
        "for reliable prediction — collect more data points."
    ),
    "MONITOR": (
        "No immediate action required. Continue monitoring performance "
        "trends. Re-evaluate in 3-5 days."
    ),
    "EVALUATE_AND_MUTATE": (
        "Evaluate current creative performance and prepare mutation "
        "if ROAS trend continues to decline. Set ROAS alert at 0.5."
    ),
}


URGENCY_MAP: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "immediate",
    RiskLevel.HIGH: "within_24h",
    RiskLevel.MEDIUM: "within_3d",
    RiskLevel.LOW: "within_7d",
}


class ExplanationEngine:
    """预测解释引擎。

    为预测结果生成结构化解释，支持:
      - RealityPrediction (Phase 1)
      - LifecyclePrediction (Phase 2.1)
      - DecayPrediction (Phase 2.2)

    Usage:
        >>> engine = ExplanationEngine()
        >>> explanation = engine.explain_prediction(prediction, history)
        >>> print(explanation.summary, explanation.reasons)
    """

    def explain_prediction(
        self,
        prediction: RealityPrediction,
        history: list[RealityHistoryPoint],
    ) -> PredictionExplanation:
        """为 RealityPrediction 生成解释。

        Args:
            prediction: Phase 1 预测结果
            history: 历史数据

        Returns:
            PredictionExplanation
        """
        reasons = self._build_reasons(prediction, history)
        summary = self._build_summary(prediction, history)
        action = prediction.recommended_action
        action_detail = ACTION_DETAILS.get(action, "Review and take appropriate action.")
        urgency = URGENCY_MAP.get(prediction.risk_level, "within_7d")

        return PredictionExplanation(
            prediction_id=prediction.prediction_id,
            creative_id=prediction.target_id,
            summary=summary,
            reasons=reasons,
            similar_cases=self._find_similar_cases(prediction),
            recommended_action=action,
            action_detail=action_detail,
            urgency=urgency,
        )

    def explain_lifecycle(
        self,
        lifecycle: LifecyclePrediction,
        history: list[RealityHistoryPoint],
    ) -> PredictionExplanation:
        """为 LifecyclePrediction 生成解释。"""
        reasons: list[str] = []

        reasons.append(
            f"Creative is currently in {lifecycle.current_stage.value} stage"
        )

        if lifecycle.predicted_stage != lifecycle.current_stage:
            reasons.append(
                f"Predicted to transition to {lifecycle.predicted_stage.value} "
                f"in approximately {lifecycle.days_to_transition} days"
            )

        if lifecycle.is_degrading:
            reasons.append("Performance metrics are trending downward")
            if lifecycle.is_transitioning_soon:
                reasons.append(
                    "Transition is imminent — action recommended within 7 days"
                )

        # 添加数据证据
        if history:
            first = history[0]
            last = history[-1]
            if first.ctr > 0:
                ctr_change = (last.ctr - first.ctr) / first.ctr
                reasons.append(f"CTR changed {ctr_change:+.0%} over observation period")
            if first.roas > 0:
                roas_change = (last.roas - first.roas) / first.roas
                reasons.append(f"ROAS changed {roas_change:+.0%} over observation period")

        summary = (
            f"Creative {lifecycle.creative_id}: "
            f"{lifecycle.current_stage.value} → {lifecycle.predicted_stage.value} "
            f"({lifecycle.days_to_transition}d)"
        )

        action = lifecycle.recommended_action
        action_detail = ACTION_DETAILS.get(action, "Monitor and re-evaluate.")

        return PredictionExplanation(
            prediction_id=lifecycle.prediction_id,
            creative_id=lifecycle.creative_id,
            summary=summary,
            reasons=reasons,
            similar_cases=[],
            recommended_action=action,
            action_detail=action_detail,
            urgency="within_24h" if lifecycle.is_transitioning_soon else "within_7d",
        )

    def explain_decay(
        self,
        decay: DecayPrediction,
        history: list[RealityHistoryPoint],
    ) -> PredictionExplanation:
        """为 DecayPrediction 生成解释。"""
        reasons: list[str] = []

        direction = "declining" if decay.velocity < 0 else "improving" if decay.velocity > 0 else "stable"
        reasons.append(
            f"{decay.metric.upper()} is {direction} at {decay.velocity:.6f}/day"
        )

        reasons.append(
            f"Current {decay.metric.upper()}: {decay.current_value:.4f}, "
            f"predicted in {decay.horizon_days}d: {decay.predicted_value:.4f}"
        )

        if decay.is_accelerating:
            reasons.append(
                f"WARNING: {decay.metric.upper()} decay is accelerating — "
                f"recent velocity exceeds historical average"
            )

        if decay.is_declining:
            severity = decay.decline_severity
            if severity == "critical":
                reasons.append(f"CRITICAL: {decay.metric.upper()} decline rate is severe")
            elif severity == "high":
                reasons.append(f"HIGH: {decay.metric.upper()} decline rate is significant")

        summary = (
            f"{decay.metric.upper()} prediction for {decay.creative_id}: "
            f"{decay.current_value:.4f} → {decay.predicted_value:.4f} "
            f"({decay.horizon_days}d, v={decay.velocity:.4f}/day)"
        )

        action = "MUTATE_CREATIVE" if decay.is_declining else "MONITOR"
        action_detail = ACTION_DETAILS.get(action, "Review and take appropriate action.")

        return PredictionExplanation(
            prediction_id=decay.prediction_id,
            creative_id=decay.creative_id,
            summary=summary,
            reasons=reasons,
            similar_cases=[],
            recommended_action=action,
            action_detail=action_detail,
            urgency="immediate" if decay.decline_severity == "critical" else "within_7d",
        )

    def explain_batch(
        self,
        predictions: list[RealityPrediction],
        history_by_creative: dict[str, list[RealityHistoryPoint]],
    ) -> list[PredictionExplanation]:
        """批量生成解释。"""
        explanations: list[PredictionExplanation] = []
        for pred in predictions:
            history = history_by_creative.get(pred.target_id, [])
            if history:
                explanations.append(self.explain_prediction(pred, history))
        return explanations

    def explain_all(
        self,
        predictions: list[RealityPrediction],
        lifecycles: list[LifecyclePrediction],
        decays: list[DecayPrediction],
        history_by_creative: dict[str, list[RealityHistoryPoint]],
    ) -> list[PredictionExplanation]:
        """为所有预测类型生成解释。"""
        explanations: list[PredictionExplanation] = []

        for pred in predictions:
            history = history_by_creative.get(pred.target_id, [])
            if history:
                explanations.append(self.explain_prediction(pred, history))

        for lc in lifecycles:
            history = history_by_creative.get(lc.creative_id, [])
            if history:
                explanations.append(self.explain_lifecycle(lc, history))

        for decay in decays:
            history = history_by_creative.get(decay.creative_id, [])
            if history:
                explanations.append(self.explain_decay(decay, history))

        return explanations

    # ── Private methods ────────────────────────────────────

    def _build_reasons(
        self,
        prediction: RealityPrediction,
        history: list[RealityHistoryPoint],
    ) -> list[str]:
        """构建原因列表。"""
        reasons: list[str] = list(prediction.evidence)

        if history:
            first = history[0]
            last = history[-1]

            if prediction.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK:
                if first.ctr > 0:
                    ctr_change = (last.ctr - first.ctr) / first.ctr
                    reasons.append(
                        f"CTR decreased {ctr_change:+.0%} from {first.ctr:.4f} to {last.ctr:.4f}"
                    )
                if first.frequency > 0 and last.frequency > first.frequency * 2:
                    reasons.append(
                        f"Frequency increased from {first.frequency:.1f} to {last.frequency:.1f} "
                        f"(audience saturation risk)"
                    )

            elif prediction.prediction_type == PredictionType.ROAS_DECAY_RISK:
                if first.roas > 0:
                    roas_change = (last.roas - first.roas) / first.roas
                    reasons.append(
                        f"ROAS decreased {roas_change:+.0%} from {first.roas:.2f} to {last.roas:.2f}"
                    )

            elif prediction.prediction_type == PredictionType.SCALE_OPPORTUNITY:
                reasons.append("Performance metrics show consistent improvement trend")

        return reasons

    def _build_summary(
        self,
        prediction: RealityPrediction,
        history: list[RealityHistoryPoint],
    ) -> str:
        """构建一句话总结。"""
        type_name = prediction.prediction_type.value.replace("_", " ").title()

        if prediction.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK:
            return (
                f"Creative {prediction.target_id} will likely fatigue "
                f"within {prediction.horizon_days} days "
                f"(probability: {prediction.probability:.0%})"
            )

        elif prediction.prediction_type == PredictionType.ROAS_DECAY_RISK:
            return (
                f"ROAS for {prediction.target_id} predicted to decline "
                f"from {prediction.current_value:.2f} to {prediction.predicted_value:.2f} "
                f"in {prediction.horizon_days} days"
            )

        elif prediction.prediction_type == PredictionType.SCALE_OPPORTUNITY:
            return (
                f"Scale opportunity detected for {prediction.target_id}: "
                f"ROAS improving from {prediction.current_value:.2f} "
                f"to {prediction.predicted_value:.2f}"
            )

        else:
            return (
                f"{type_name} prediction for {prediction.target_id}: "
                f"{prediction.current_value:.2f} → {prediction.predicted_value:.2f}"
            )

    @staticmethod
    def _find_similar_cases(prediction: RealityPrediction) -> list[str]:
        """查找类似案例（简化版）。"""
        if prediction.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK:
            return [
                "Similar creative DNA patterns typically fatigue after 14-21 days",
                "Hook-based fatigue is the most common pattern in this category",
            ]
        elif prediction.prediction_type == PredictionType.ROAS_DECAY_RISK:
            return [
                "ROAS decay typically stabilizes after 30 days if not addressed",
                "Early mutation (within 7 days) has 60%+ recovery rate",
            ]
        return []

    def __repr__(self) -> str:
        return "ExplanationEngine()"