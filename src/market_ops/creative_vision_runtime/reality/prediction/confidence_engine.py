"""E12.3 Phase 2 — Prediction Confidence Engine。

评估预测可信程度，防止低质量预测触发 E11 误操作。

公式:
  confidence = data_volume × 0.35 + trend_consistency × 0.45 + metric_stability × 0.20

因素:
  - data_volume:       总安装量 + 天数（数据越多越可靠）
  - trend_consistency: 趋势一致性（R² / 单调性）
  - metric_stability:  指标波动性（CV 越低越稳定）

与 E12.2 ConfidenceEngine 的区别:
  - E12.2: 诊断置信度（当前状态）
  - E12.3: 预测置信度（未来趋势）
"""

from __future__ import annotations

import math

from .models import (
    DecayPrediction,
    LifecyclePrediction,
    PredictionConfidence,
    RealityHistoryPoint,
    RealityPrediction,
)

# ── Constants ──────────────────────────────────────────────

WEIGHT_DATA_VOLUME = 0.35
WEIGHT_TREND_CONSISTENCY = 0.45
WEIGHT_METRIC_STABILITY = 0.20

# 数据量阈值
MIN_INSTALLS_RELIABLE = 5000
MIN_INSTALLS_DECENT = 1000
MIN_INSTALLS_MINIMAL = 100

MIN_DAYS_RELIABLE = 14
MIN_DAYS_DECENT = 7
MIN_DAYS_MINIMAL = 3


class PredictionConfidenceEngine:
    """预测置信度引擎。

    对每个预测评估其可信程度，输出 PredictionConfidence。

    Usage:
        >>> engine = PredictionConfidenceEngine()
        >>> conf = engine.evaluate_prediction(prediction, history)
        >>> print(conf.score, conf.is_reliable)
    """

    def evaluate_prediction(
        self,
        prediction: RealityPrediction,
        history: list[RealityHistoryPoint],
    ) -> PredictionConfidence:
        """评估 RealityPrediction 的置信度。

        Args:
            prediction: Phase 1 预测结果
            history: 历史数据

        Returns:
            PredictionConfidence
        """
        data_volume = self._score_data_volume(history)
        trend_consistency = self._score_trend_consistency(history)
        metric_stability = self._score_metric_stability(history)

        score = (
            data_volume * WEIGHT_DATA_VOLUME
            + trend_consistency * WEIGHT_TREND_CONSISTENCY
            + metric_stability * WEIGHT_METRIC_STABILITY
        )
        score = min(1.0, max(0.0, score))

        return PredictionConfidence(
            prediction_id=prediction.prediction_id,
            score=score,
            data_volume=data_volume,
            trend_consistency=trend_consistency,
            metric_stability=metric_stability,
            breakdown={
                "data_volume": round(data_volume, 4),
                "trend_consistency": round(trend_consistency, 4),
                "metric_stability": round(metric_stability, 4),
            },
        )

    def evaluate_lifecycle(
        self,
        lifecycle: LifecyclePrediction,
        history: list[RealityHistoryPoint],
    ) -> PredictionConfidence:
        """评估 LifecyclePrediction 的置信度。"""
        data_volume = self._score_data_volume(history)
        trend_consistency = self._score_trend_consistency(history)
        metric_stability = self._score_metric_stability(history)

        score = (
            data_volume * WEIGHT_DATA_VOLUME
            + trend_consistency * WEIGHT_TREND_CONSISTENCY
            + metric_stability * WEIGHT_METRIC_STABILITY
        )
        score = min(1.0, max(0.0, score))

        return PredictionConfidence(
            prediction_id=lifecycle.prediction_id,
            score=score,
            data_volume=data_volume,
            trend_consistency=trend_consistency,
            metric_stability=metric_stability,
        )

    def evaluate_decay(
        self,
        decay: DecayPrediction,
        history: list[RealityHistoryPoint],
    ) -> PredictionConfidence:
        """评估 DecayPrediction 的置信度。"""
        # 提取对应指标的值
        values = [getattr(p, decay.metric) for p in history]

        data_volume = self._score_data_volume(history)
        trend_consistency = self._score_trend_consistency(history)
        metric_stability = self._score_metric_stability_single(values)

        score = (
            data_volume * WEIGHT_DATA_VOLUME
            + trend_consistency * WEIGHT_TREND_CONSISTENCY
            + metric_stability * WEIGHT_METRIC_STABILITY
        )
        score = min(1.0, max(0.0, score))

        return PredictionConfidence(
            prediction_id=decay.prediction_id,
            score=score,
            data_volume=data_volume,
            trend_consistency=trend_consistency,
            metric_stability=metric_stability,
        )

    def evaluate_batch(
        self,
        predictions: list[RealityPrediction],
        history_by_creative: dict[str, list[RealityHistoryPoint]],
    ) -> dict[str, PredictionConfidence]:
        """批量评估预测置信度。

        Returns:
            {prediction_id: PredictionConfidence}
        """
        results: dict[str, PredictionConfidence] = {}
        for pred in predictions:
            history = history_by_creative.get(pred.target_id, [])
            if history:
                results[pred.prediction_id] = self.evaluate_prediction(pred, history)
        return results

    def filter_reliable(
        self,
        predictions: list[RealityPrediction],
        history_by_creative: dict[str, list[RealityHistoryPoint]],
        min_confidence: float = 0.7,
    ) -> list[RealityPrediction]:
        """过滤出可靠预测。

        Args:
            predictions: 预测列表
            history_by_creative: 历史数据
            min_confidence: 最低置信度阈值

        Returns:
            可靠预测列表
        """
        confidences = self.evaluate_batch(predictions, history_by_creative)
        return [
            p for p in predictions
            if confidences.get(p.prediction_id, PredictionConfidence(score=0)).score >= min_confidence
        ]

    # ── Scoring Helpers ────────────────────────────────────

    @staticmethod
    def _score_data_volume(history: list[RealityHistoryPoint]) -> float:
        """评分数据量。

        基于总安装量和天数。
        """
        total_installs = sum(p.installs for p in history)
        days = len(history)

        # 安装量评分
        if total_installs >= MIN_INSTALLS_RELIABLE:
            install_score = 1.0
        elif total_installs >= MIN_INSTALLS_DECENT:
            install_score = 0.7 + 0.3 * (
                (total_installs - MIN_INSTALLS_DECENT)
                / (MIN_INSTALLS_RELIABLE - MIN_INSTALLS_DECENT)
            )
        elif total_installs >= MIN_INSTALLS_MINIMAL:
            install_score = 0.3 + 0.4 * (
                (total_installs - MIN_INSTALLS_MINIMAL)
                / (MIN_INSTALLS_DECENT - MIN_INSTALLS_MINIMAL)
            )
        else:
            install_score = 0.1

        # 天数评分
        if days >= MIN_DAYS_RELIABLE:
            day_score = 1.0
        elif days >= MIN_DAYS_DECENT:
            day_score = 0.7 + 0.3 * (
                (days - MIN_DAYS_DECENT) / (MIN_DAYS_RELIABLE - MIN_DAYS_DECENT)
            )
        elif days >= MIN_DAYS_MINIMAL:
            day_score = 0.3 + 0.4 * (
                (days - MIN_DAYS_MINIMAL) / (MIN_DAYS_DECENT - MIN_DAYS_MINIMAL)
            )
        else:
            day_score = 0.1

        return install_score * 0.6 + day_score * 0.4

    @staticmethod
    def _score_trend_consistency(history: list[RealityHistoryPoint]) -> float:
        """评分趋势一致性。

        检查 CTR 和 ROAS 是否单调变化。
        """
        ctr_values = [p.ctr for p in history]
        roas_values = [p.roas for p in history]

        ctr_consistent = PredictionConfidenceEngine._is_monotonic(ctr_values)
        roas_consistent = PredictionConfidenceEngine._is_monotonic(roas_values)

        if ctr_consistent and roas_consistent:
            return 1.0
        elif ctr_consistent or roas_consistent:
            return 0.7
        else:
            return 0.3

    @staticmethod
    def _score_metric_stability(history: list[RealityHistoryPoint]) -> float:
        """评分指标稳定性（综合 CTR + ROAS）。"""
        ctr_values = [p.ctr for p in history]
        roas_values = [p.roas for p in history]

        ctr_cv = PredictionConfidenceEngine._coefficient_of_variation(ctr_values)
        roas_cv = PredictionConfidenceEngine._coefficient_of_variation(roas_values)

        avg_cv = (ctr_cv + roas_cv) / 2
        # CV 越低越稳定，1 - CV 作为得分
        return max(0.0, min(1.0, 1.0 - avg_cv))

    @staticmethod
    def _score_metric_stability_single(values: list[float]) -> float:
        """评分单个指标的稳定性。"""
        cv = PredictionConfidenceEngine._coefficient_of_variation(values)
        return max(0.0, min(1.0, 1.0 - cv))

    @staticmethod
    def _coefficient_of_variation(values: list[float]) -> float:
        """计算变异系数（CV）。"""
        if not values or len(values) < 2:
            return 1.0
        mean = sum(values) / len(values)
        if mean == 0:
            return 1.0
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance) / mean

    @staticmethod
    def _is_monotonic(values: list[float]) -> bool:
        """检查序列是否单调。"""
        if len(values) < 3:
            return True
        increasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
        decreasing = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
        return increasing or decreasing

    def __repr__(self) -> str:
        return "PredictionConfidenceEngine()"