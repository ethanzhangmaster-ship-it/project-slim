"""E12.4 — Learning Feedback。

闭环学习：记录预测 vs 实际结果，计算误差，用于未来校准。

功能:
  Phase 1:
    1. 记录 PredictionOutcome（预测值 vs 实际值）
    2. 计算预测误差
    3. 生成校准建议（调整 threshold/confidence/predictor weight）
    4. 聚合统计（总体准确率、平均误差）

  Phase 2:
    5. 记录 EvolutionLearningRecord（完整闭环：Prediction → Mutation → Experiment → Result）
    6. 进化学习洞察（跨实验模式识别）
    7. 突变成功率统计

与 E12.2 ConfidenceEngine 的区别:
  - E12.2: 预测前的置信度（事前）
  - E12.4: 预测后的准确率（事后）
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    EvolutionLearningRecord,
    PredictionOutcome,
)


@dataclass
class PredictionAccuracy:
    """预测准确率统计。

    Attributes:
        total_predictions:  总预测数
        successful:         成功预测数（误差 < 20%）
        failed:             失败预测数
        success_rate:       成功率
        mean_error:         平均误差
        mean_error_pct:     平均误差百分比
        overestimate_count: 高估次数
        underestimate_count: 低估次数
        outcomes:           所有结果
    """

    total_predictions: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    mean_error: float = 0.0
    mean_error_pct: float = 0.0
    overestimate_count: int = 0
    underestimate_count: int = 0
    outcomes: list[PredictionOutcome] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"PredictionAccuracy(total={self.total_predictions}, "
            f"success={self.success_rate:.0%}, "
            f"mean_err={self.mean_error_pct:.0%})"
        )


class LearningFeedback:
    """闭环学习反馈引擎。

    记录预测结果，计算准确率，生成校准建议。

    Usage:
        >>> lf = LearningFeedback()
        >>> outcome = lf.record_outcome(
        ...     prediction_id="rp_001", creative_id="c001",
        ...     metric="roas", predicted_value=0.55, actual_value=0.48,
        ... )
        >>> accuracy = lf.get_accuracy()
        >>> print(accuracy.success_rate)
    """

    def __init__(self) -> None:
        self._outcomes: list[PredictionOutcome] = []
        self._evolution_records: list[EvolutionLearningRecord] = []

    def record_outcome(
        self,
        prediction_id: str,
        creative_id: str,
        metric: str,
        predicted_value: float,
        actual_value: float,
        horizon_days: int = 7,
    ) -> PredictionOutcome:
        """记录一个预测结果。

        Args:
            prediction_id:   预测 ID
            creative_id:     创意 ID
            metric:          指标名称
            predicted_value: 预测值
            actual_value:    实际值
            horizon_days:    预测时间范围

        Returns:
            PredictionOutcome（含自动计算的误差）
        """
        outcome = PredictionOutcome(
            prediction_id=prediction_id,
            creative_id=creative_id,
            metric=metric,
            predicted_value=predicted_value,
            actual_value=actual_value,
            horizon_days=horizon_days,
        )
        self._outcomes.append(outcome)
        return outcome

    def record_outcome_from_prediction(
        self,
        prediction_id: str,
        creative_id: str,
        metric: str,
        predicted_value: float,
        actual_value: float,
        horizon_days: int = 7,
    ) -> PredictionOutcome:
        """从预测结果记录（同 record_outcome）。"""
        return self.record_outcome(
            prediction_id=prediction_id,
            creative_id=creative_id,
            metric=metric,
            predicted_value=predicted_value,
            actual_value=actual_value,
            horizon_days=horizon_days,
        )

    def get_accuracy(self) -> PredictionAccuracy:
        """获取预测准确率统计。

        Returns:
            PredictionAccuracy
        """
        if not self._outcomes:
            return PredictionAccuracy()

        successful = [o for o in self._outcomes if o.is_success]
        failed = [o for o in self._outcomes if not o.is_success]
        total = len(self._outcomes)

        errors = [o.error for o in self._outcomes]
        error_pcts = [o.error_pct for o in self._outcomes]

        return PredictionAccuracy(
            total_predictions=total,
            successful=len(successful),
            failed=len(failed),
            success_rate=len(successful) / total if total > 0 else 0.0,
            mean_error=sum(errors) / len(errors) if errors else 0.0,
            mean_error_pct=sum(error_pcts) / len(error_pcts) if error_pcts else 0.0,
            overestimate_count=len(
                [o for o in self._outcomes if o.error_direction == "overestimate"]
            ),
            underestimate_count=len(
                [o for o in self._outcomes if o.error_direction == "underestimate"]
            ),
            outcomes=list(self._outcomes),
        )

    def get_calibration_suggestions(self) -> list[str]:
        """生成校准建议。

        基于历史预测准确率，建议调整 threshold/confidence/predictor weight。

        Returns:
            建议列表
        """
        accuracy = self.get_accuracy()
        suggestions: list[str] = []

        if accuracy.total_predictions < 5:
            suggestions.append(
                "Insufficient data for calibration — need at least 5 outcomes"
            )
            return suggestions

        # 成功率过低 → 提高阈值
        if accuracy.success_rate < 0.5:
            suggestions.append(
                f"Low success rate ({accuracy.success_rate:.0%}): "
                "consider increasing FATIGUE_PROBABILITY threshold to 0.85"
            )

        # 高估过多 → 预测偏乐观
        if accuracy.overestimate_count > accuracy.underestimate_count * 2:
            suggestions.append(
                "Prediction tends to overestimate: "
                "consider applying a 0.9 decay factor to predicted values"
            )

        # 低估过多 → 预测偏悲观
        if accuracy.underestimate_count > accuracy.overestimate_count * 2:
            suggestions.append(
                "Prediction tends to underestimate: "
                "consider reducing confidence thresholds"
            )

        # 平均误差过高
        if accuracy.mean_error_pct > 0.30:
            suggestions.append(
                f"High mean error ({accuracy.mean_error_pct:.0%}): "
                "consider increasing MIN_CONFIDENCE threshold"
            )

        if not suggestions:
            suggestions.append(
                f"Predictions are well-calibrated "
                f"(success_rate={accuracy.success_rate:.0%}, "
                f"mean_error={accuracy.mean_error_pct:.0%})"
            )

        return suggestions

    def get_outcomes_by_creative(
        self,
        creative_id: str,
    ) -> list[PredictionOutcome]:
        """获取指定创意的所有结果。"""
        return [o for o in self._outcomes if o.creative_id == creative_id]

    def get_outcomes_by_metric(
        self,
        metric: str,
    ) -> list[PredictionOutcome]:
        """获取指定指标的所有结果。"""
        return [o for o in self._outcomes if o.metric == metric]

    def record_batch(
        self,
        outcomes: list[dict],
    ) -> list[PredictionOutcome]:
        """批量记录结果。

        Args:
            outcomes: [{prediction_id, creative_id, metric, predicted_value, actual_value}, ...]

        Returns:
            PredictionOutcome 列表
        """
        results: list[PredictionOutcome] = []
        for o in outcomes:
            results.append(self.record_outcome(
                prediction_id=o.get("prediction_id", ""),
                creative_id=o.get("creative_id", ""),
                metric=o.get("metric", ""),
                predicted_value=o.get("predicted_value", 0.0),
                actual_value=o.get("actual_value", 0.0),
                horizon_days=o.get("horizon_days", 7),
            ))
        return results

    # ── Phase 2: Evolution Learning ───────────────────────

    def record_evolution(
        self,
        prediction_id: str,
        mutation_request_id: str,
        experiment_id: str,
        prediction_accuracy: float,
        mutation_success: bool,
        winner_dna: dict | None = None,
        insight: str = "",
    ) -> EvolutionLearningRecord:
        """记录一次完整的进化学习。

        Prediction → Mutation → Experiment → Result 完整闭环。

        Args:
            prediction_id:       预测 ID
            mutation_request_id: 突变请求 ID
            experiment_id:       实验 ID
            prediction_accuracy: 预测准确率（0-1）
            mutation_success:    突变是否成功
            winner_dna:          赢家 DNA 特征
            insight:             学习洞察

        Returns:
            EvolutionLearningRecord
        """
        record = EvolutionLearningRecord(
            prediction_id=prediction_id,
            mutation_request_id=mutation_request_id,
            experiment_id=experiment_id,
            prediction_accuracy=prediction_accuracy,
            mutation_success=mutation_success,
            winner_dna=winner_dna or {},
            insight=insight,
        )
        self._evolution_records.append(record)
        return record

    def record_evolution_from_evaluation(
        self,
        prediction_id: str,
        mutation_request_id: str,
        experiment_id: str,
        prediction_accuracy: float,
        mutation_success: bool,
        winner_dna: dict | None = None,
        insight: str = "",
    ) -> EvolutionLearningRecord:
        """从评估结果记录进化学习（同 record_evolution）。"""
        return self.record_evolution(
            prediction_id=prediction_id,
            mutation_request_id=mutation_request_id,
            experiment_id=experiment_id,
            prediction_accuracy=prediction_accuracy,
            mutation_success=mutation_success,
            winner_dna=winner_dna,
            insight=insight,
        )

    def get_evolution_records(self) -> list[EvolutionLearningRecord]:
        """获取所有进化学习记录。"""
        return list(self._evolution_records)

    def get_evolution_insights(self) -> list[str]:
        """获取所有进化学习洞察。

        Returns:
            洞察列表（按时间倒序）
        """
        return [
            r.insight for r in reversed(self._evolution_records)
            if r.insight
        ]

    def get_evolution_stats(self) -> dict:
        """获取进化学习统计。

        Returns:
            {
                total_records, mutation_success_rate,
                mean_prediction_accuracy, successful_mutations,
                failed_mutations, insights
            }
        """
        if not self._evolution_records:
            return {
                "total_records": 0,
                "mutation_success_rate": 0.0,
                "mean_prediction_accuracy": 0.0,
                "successful_mutations": 0,
                "failed_mutations": 0,
                "insights": [],
            }

        total = len(self._evolution_records)
        successful = len([r for r in self._evolution_records if r.mutation_success])
        failed = total - successful
        avg_accuracy = (
            sum(r.prediction_accuracy for r in self._evolution_records) / total
        )

        return {
            "total_records": total,
            "mutation_success_rate": successful / total if total > 0 else 0.0,
            "mean_prediction_accuracy": round(avg_accuracy, 4),
            "successful_mutations": successful,
            "failed_mutations": failed,
            "insights": self.get_evolution_insights(),
        }

    def get_evolution_records_by_experiment(
        self,
        experiment_id: str,
    ) -> list[EvolutionLearningRecord]:
        """获取指定实验的学习记录。"""
        return [
            r for r in self._evolution_records
            if r.experiment_id == experiment_id
        ]

    def get_successful_mutations(self) -> list[EvolutionLearningRecord]:
        """获取成功的突变记录。"""
        return [r for r in self._evolution_records if r.mutation_success]

    def get_failed_mutations(self) -> list[EvolutionLearningRecord]:
        """获取失败的突变记录。"""
        return [r for r in self._evolution_records if not r.mutation_success]

    def get_evolution_recommendations(self) -> list[str]:
        """基于进化历史生成推荐。

        Returns:
            推荐列表
        """
        stats = self.get_evolution_stats()
        recommendations: list[str] = []

        if stats["total_records"] < 3:
            recommendations.append(
                "Insufficient evolution data — need at least 3 records for recommendations"
            )
            return recommendations

        # 突变成功率低
        if stats["mutation_success_rate"] < 0.3:
            recommendations.append(
                f"Low mutation success rate ({stats['mutation_success_rate']:.0%}): "
                "consider reducing mutation aggressiveness or increasing generation count"
            )

        # 预测准确率低但突变成功 → 预测需要校准
        if stats["mean_prediction_accuracy"] < 0.5 and stats["mutation_success_rate"] > 0.5:
            recommendations.append(
                "Prediction accuracy low but mutations succeed: "
                "predictions may be too conservative — consider lowering thresholds"
            )

        # 预测准确率高但突变失败 → 突变策略需要调整
        if stats["mean_prediction_accuracy"] > 0.7 and stats["mutation_success_rate"] < 0.3:
            recommendations.append(
                "Predictions are accurate but mutations fail: "
                "mutation strategy may be misaligned — consider different DNA constraints"
            )

        if not recommendations:
            recommendations.append(
                f"Evolution loop is healthy "
                f"(prediction_accuracy={stats['mean_prediction_accuracy']:.0%}, "
                f"mutation_success={stats['mutation_success_rate']:.0%})"
            )

        return recommendations

    def clear(self) -> None:
        """清空所有记录。"""
        self._outcomes.clear()
        self._evolution_records.clear()

    @property
    def total_outcomes(self) -> int:
        return len(self._outcomes)

    @property
    def total_evolution_records(self) -> int:
        return len(self._evolution_records)

    def __repr__(self) -> str:
        accuracy = self.get_accuracy()
        evo_stats = self.get_evolution_stats()
        return (
            f"LearningFeedback(outcomes={self.total_outcomes}, "
            f"success_rate={accuracy.success_rate:.0%}, "
            f"evolution_records={self.total_evolution_records}, "
            f"mutation_success={evo_stats['mutation_success_rate']:.0%})"
        )