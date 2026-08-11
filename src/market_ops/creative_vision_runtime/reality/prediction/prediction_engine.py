"""E12.3 — Prediction Engine (Phase 2 Upgrade)。

统一预测入口，编排所有预测器：
  - Phase 1: FatiguePredictor, ROASPredictor
  - Phase 2: LifecyclePredictor, DecayPredictor, ConfidenceEngine, ExplanationEngine

流程:
  RealityHistory
       │
       ├── FatiguePredictor    → fatigue predictions
       ├── ROASPredictor       → ROAS predictions
       ├── LifecyclePredictor  → lifecycle predictions  (Phase 2)
       ├── DecayPredictor      → decay predictions      (Phase 2)
       │
       ├── ConfidenceEngine    → confidence scores      (Phase 2)
       ├── ExplanationEngine   → explanations           (Phase 2)
       │
       └── Risk Ranking        → sorted prediction list
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .confidence_engine import PredictionConfidenceEngine
from .decay_predictor import DecayPredictor
from .explanation_engine import ExplanationEngine
from .fatigue_predictor import FatiguePredictor
from .lifecycle_predictor import LifecyclePredictor
from .models import (
    DecayPrediction,
    LifecyclePrediction,
    PredictionConfidence,
    PredictionExplanation,
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
)
from .roas_predictor import ROASPredictor


# ── Risk weight for ranking ────────────────────────────────

RISK_WEIGHTS: dict[RiskLevel, int] = {
    RiskLevel.CRITICAL: 4,
    RiskLevel.HIGH: 3,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 1,
}


@dataclass
class PredictionResult:
    """PredictionEngine 的批量预测结果 (Phase 2)。

    Attributes:
        predictions:     Phase 1 预测列表
        lifecycles:      Phase 2.1 生命周期预测
        decays:          Phase 2.2 衰减速度预测
        confidences:     Phase 2.3 置信度评分
        explanations:    Phase 2.4 预测解释
        actionable:      需要行动的预测
        top_risks:       按风险排序的 TOP N
        summary:         人类可读摘要
    """

    predictions: list[RealityPrediction] = field(default_factory=list)
    lifecycles: list[LifecyclePrediction] = field(default_factory=list)
    decays: list[DecayPrediction] = field(default_factory=list)
    confidences: dict[str, PredictionConfidence] = field(default_factory=dict)
    explanations: list[PredictionExplanation] = field(default_factory=list)
    actionable: list[RealityPrediction] = field(default_factory=list)
    top_risks: list[RealityPrediction] = field(default_factory=list)
    summary: str = ""

    def __repr__(self) -> str:
        return (
            f"PredictionResult(total={len(self.predictions)}, "
            f"lifecycles={len(self.lifecycles)}, "
            f"decays={len(self.decays)}, "
            f"actionable={len(self.actionable)}, "
            f"critical={len([p for p in self.predictions if p.risk_level == RiskLevel.CRITICAL])})"
        )


class PredictionEngine:
    """E12.3 统一预测引擎 (Phase 2)。

    消费 E12.1 的 RealitySnapshot 历史数据，运行所有预测器，
    生成完整的预测结果（趋势 + 生命周期 + 衰减 + 置信度 + 解释）。

    Usage:
        >>> engine = PredictionEngine()
        >>> result = engine.predict_full(history_by_creative, horizon_days=7)
        >>> for exp in result.explanations:
        ...     print(exp.summary)
    """

    def __init__(self) -> None:
        # Phase 1
        self.fatigue_predictor = FatiguePredictor()
        self.roas_predictor = ROASPredictor()
        # Phase 2
        self.lifecycle_predictor = LifecyclePredictor()
        self.decay_predictor = DecayPredictor()
        self.confidence_engine = PredictionConfidenceEngine()
        self.explanation_engine = ExplanationEngine()

    # ── Phase 1 API (backward compatible) ───────────────────

    def predict(
        self,
        history_by_creative: dict[str, list[RealityHistoryPoint]],
        horizon_days: int = 7,
    ) -> PredictionResult:
        """Phase 1 兼容：只运行 fatigue + ROAS 预测。"""
        all_predictions: list[RealityPrediction] = []

        fatigue_predictions = self.fatigue_predictor.predict_batch(
            history_by_creative, horizon_days
        )
        all_predictions.extend(fatigue_predictions)

        roas_predictions = self.roas_predictor.predict_batch(
            history_by_creative, horizon_days
        )
        all_predictions.extend(roas_predictions)

        ranked = self._rank_by_risk(all_predictions)
        actionable = [p for p in ranked if p.is_actionable]
        top_risks = self._get_top_risks(ranked)
        summary = self._build_summary(ranked, actionable)

        return PredictionResult(
            predictions=ranked,
            actionable=actionable,
            top_risks=top_risks,
            summary=summary,
        )

    def predict_single_creative(
        self,
        history: list[RealityHistoryPoint],
        horizon_days: int = 7,
    ) -> list[RealityPrediction]:
        """Phase 1 兼容：单创意预测。"""
        predictions: list[RealityPrediction] = []

        fatigue_pred = self.fatigue_predictor.predict(history, horizon_days)
        if fatigue_pred is not None:
            predictions.append(fatigue_pred)

        roas_pred = self.roas_predictor.predict(history, horizon_days)
        if roas_pred is not None:
            predictions.append(roas_pred)

        return self._rank_by_risk(predictions)

    # ── Phase 2 Full API ────────────────────────────────────

    def predict_full(
        self,
        history_by_creative: dict[str, list[RealityHistoryPoint]],
        horizon_days: int = 7,
    ) -> PredictionResult:
        """运行完整 Phase 2 预测管线。

        包括:
          1. Phase 1: Fatigue + ROAS 预测
          2. Phase 2.1: Lifecycle 预测
          3. Phase 2.2: Decay 预测
          4. Phase 2.3: Confidence 评分
          5. Phase 2.4: 解释生成

        Args:
            history_by_creative: {creative_id: [history_points]} 映射
            horizon_days: 预测时间范围

        Returns:
            完整的 PredictionResult
        """
        all_predictions: list[RealityPrediction] = []
        all_lifecycles: list[LifecyclePrediction] = []
        all_decays: list[DecayPrediction] = []
        all_confidences: dict[str, PredictionConfidence] = {}
        all_explanations: list[PredictionExplanation] = []

        # 1. Phase 1: Fatigue + ROAS
        fatigue_predictions = self.fatigue_predictor.predict_batch(
            history_by_creative, horizon_days
        )
        all_predictions.extend(fatigue_predictions)

        roas_predictions = self.roas_predictor.predict_batch(
            history_by_creative, horizon_days
        )
        all_predictions.extend(roas_predictions)

        # 2. Phase 2.1: Lifecycle
        all_lifecycles = self.lifecycle_predictor.predict_batch(history_by_creative)

        # 3. Phase 2.2: Decay (all metrics for each creative)
        for creative_id, points in history_by_creative.items():
            decays = self.decay_predictor.predict_all_metrics(points, horizon_days)
            all_decays.extend(decays)

        # 4. Phase 2.3: Confidence
        all_confidences = self.confidence_engine.evaluate_batch(
            all_predictions, history_by_creative
        )

        # 5. Phase 2.4: Explanations
        all_explanations = self.explanation_engine.explain_all(
            all_predictions, all_lifecycles, all_decays, history_by_creative
        )

        # 6. Risk ranking
        ranked = self._rank_by_risk(all_predictions)
        actionable = [p for p in ranked if p.is_actionable]
        top_risks = self._get_top_risks(ranked)
        summary = self._build_summary_full(ranked, all_lifecycles, all_decays, actionable)

        return PredictionResult(
            predictions=ranked,
            lifecycles=all_lifecycles,
            decays=all_decays,
            confidences=all_confidences,
            explanations=all_explanations,
            actionable=actionable,
            top_risks=top_risks,
            summary=summary,
        )

    def predict_lifecycle_only(
        self,
        history_by_creative: dict[str, list[RealityHistoryPoint]],
    ) -> list[LifecyclePrediction]:
        """仅运行生命周期预测。"""
        return self.lifecycle_predictor.predict_batch(history_by_creative)

    def predict_decay_only(
        self,
        history_by_creative: dict[str, list[RealityHistoryPoint]],
        metric: str = "ctr",
        horizon_days: int = 7,
    ) -> list[DecayPrediction]:
        """仅运行衰减速度预测。"""
        return self.decay_predictor.predict_batch(
            history_by_creative, metric, horizon_days
        )

    def get_reliable_predictions(
        self,
        result: PredictionResult,
        min_confidence: float = 0.7,
    ) -> list[RealityPrediction]:
        """过滤出可靠预测（置信度 >= min_confidence）。"""
        return [
            p for p in result.predictions
            if result.confidences.get(p.prediction_id, PredictionConfidence(score=0)).score >= min_confidence
        ]

    def get_critical_risks(
        self,
        predictions: list[RealityPrediction],
    ) -> list[RealityPrediction]:
        """获取 CRITICAL 级别的风险预测。"""
        return [p for p in predictions if p.risk_level == RiskLevel.CRITICAL]

    def get_by_type(
        self,
        predictions: list[RealityPrediction],
        prediction_type: PredictionType,
    ) -> list[RealityPrediction]:
        """按预测类型筛选。"""
        return [p for p in predictions if p.prediction_type == prediction_type]

    # ── Private methods ────────────────────────────────────

    @staticmethod
    def _rank_by_risk(
        predictions: list[RealityPrediction],
    ) -> list[RealityPrediction]:
        """按风险等级 + 概率排序。"""
        return sorted(
            predictions,
            key=lambda p: (
                RISK_WEIGHTS.get(p.risk_level, 0),
                p.probability,
            ),
            reverse=True,
        )

    @staticmethod
    def _get_top_risks(
        predictions: list[RealityPrediction],
        n: int = 10,
    ) -> list[RealityPrediction]:
        """获取 TOP N 风险。"""
        risky = [
            p
            for p in predictions
            if p.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        ]
        return risky[:n]

    @staticmethod
    def _build_summary(
        predictions: list[RealityPrediction],
        actionable: list[RealityPrediction],
    ) -> str:
        """构建 Phase 1 摘要。"""
        total = len(predictions)
        critical = len(
            [p for p in predictions if p.risk_level == RiskLevel.CRITICAL]
        )
        high = len(
            [p for p in predictions if p.risk_level == RiskLevel.HIGH]
        )
        medium = len(
            [p for p in predictions if p.risk_level == RiskLevel.MEDIUM]
        )

        fatigue_count = len(
            [p for p in predictions
             if p.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK]
        )
        roas_count = len(
            [p for p in predictions
             if p.prediction_type == PredictionType.ROAS_DECAY_RISK]
        )
        scale_count = len(
            [p for p in predictions
             if p.prediction_type == PredictionType.SCALE_OPPORTUNITY]
        )

        parts = [
            f"Total predictions: {total}",
            f"Critical: {critical}, High: {high}, Medium: {medium}",
            f"Fatigue risks: {fatigue_count}, ROAS risks: {roas_count}, "
            f"Scale opportunities: {scale_count}",
            f"Actionable: {len(actionable)}",
        ]

        return " | ".join(parts)

    @staticmethod
    def _build_summary_full(
        predictions: list[RealityPrediction],
        lifecycles: list[LifecyclePrediction],
        decays: list[DecayPrediction],
        actionable: list[RealityPrediction],
    ) -> str:
        """构建 Phase 2 完整摘要。"""
        phase1 = PredictionEngine._build_summary(predictions, actionable)

        # Lifecycle summary
        degrading = len([lc for lc in lifecycles if lc.is_degrading])
        transitioning = len([lc for lc in lifecycles if lc.is_transitioning_soon])

        # Decay summary
        accelerating = len([d for d in decays if d.is_accelerating])
        critical_decay = len([d for d in decays if d.decline_severity == "critical"])

        parts = [
            phase1,
            f"Lifecycles: {len(lifecycles)} total, {degrading} degrading, "
            f"{transitioning} transitioning soon",
            f"Decays: {len(decays)} metrics, {accelerating} accelerating, "
            f"{critical_decay} critical",
        ]

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"PredictionEngine(fatigue={self.fatigue_predictor}, "
            f"roas={self.roas_predictor}, "
            f"lifecycle={self.lifecycle_predictor}, "
            f"decay={self.decay_predictor})"
        )