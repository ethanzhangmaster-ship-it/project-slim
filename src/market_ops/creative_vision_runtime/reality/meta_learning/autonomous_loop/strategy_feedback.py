"""E12.5.5 — Strategy Feedback。

连接 E12.5.4 Meta Strategy 和 E11 Evolution。

流程:
  MetaStrategy → 执行 → Experiment Result → StrategyFeedback → 更新策略评分

核心功能:
  - 收集策略执行反馈
  - 计算预测准确度
  - 识别高估/低估策略
  - 更新策略权重
"""

from __future__ import annotations

from .models import StrategyFeedback
from ..strategy_optimizer.models import MetaStrategy


class StrategyFeedbackCollector:
    """策略反馈收集器。

    Usage:
        >>> collector = StrategyFeedbackCollector()
        >>> feedback = collector.collect(
        ...     strategy, actual_gain=0.31, predicted_gain=0.20, success=True
        ... )
        >>> # 更新策略评分
        >>> collector.update_strategy_score(strategy, feedback)
    """

    # 预测准确度对策略置信度的影响系数
    ACCURACY_IMPACT_FACTOR: float = 0.15

    def __init__(self, accuracy_impact: float = 0.15) -> None:
        self.ACCURACY_IMPACT_FACTOR = accuracy_impact
        self._feedbacks: dict[str, list[StrategyFeedback]] = {}

    # ── Collect Feedback ───────────────────────────────────

    def collect(
        self,
        strategy: MetaStrategy,
        actual_gain: float,
        success: bool,
        cycle_id: str = "",
        confidence: float = 0.8,
        notes: str = "",
    ) -> StrategyFeedback:
        """收集策略反馈。

        Args:
            strategy:       MetaStrategy
            actual_gain:    实际增益
            success:        是否成功
            cycle_id:       周期 ID
            confidence:     反馈置信度
            notes:          备注

        Returns:
            StrategyFeedback
        """
        # 预测增益 = 综合性能影响
        predicted_gain = strategy.performance_impact

        feedback = StrategyFeedback(
            strategy_id=strategy.strategy_id,
            cycle_id=cycle_id,
            predicted_gain=predicted_gain,
            actual_gain=actual_gain,
            success=success,
            confidence=confidence,
            notes=notes,
        )

        # 存储
        if strategy.strategy_id not in self._feedbacks:
            self._feedbacks[strategy.strategy_id] = []
        self._feedbacks[strategy.strategy_id].append(feedback)

        return feedback

    def collect_from_result(
        self,
        strategy: MetaStrategy,
        actual_ctr: float = 0.0,
        actual_roas: float = 0.0,
        actual_cvr: float = 0.0,
        actual_cpi: float = 0.0,
        success: bool = False,
        cycle_id: str = "",
    ) -> StrategyFeedback:
        """从实际指标收集反馈。

        Args:
            strategy:   MetaStrategy
            actual_ctr:  实际 CTR delta
            actual_roas: 实际 ROAS delta
            actual_cvr:  实际 CVR delta
            actual_cpi:  实际 CPI delta
            success:     是否成功
            cycle_id:    周期 ID

        Returns:
            StrategyFeedback
        """
        actual_gain = (actual_ctr + actual_roas + actual_cvr - actual_cpi) / 4.0
        return self.collect(strategy, actual_gain, success, cycle_id)

    # ── Update Strategy Score ──────────────────────────────

    def update_strategy_score(
        self,
        strategy: MetaStrategy,
        feedback: StrategyFeedback,
    ) -> MetaStrategy:
        """根据反馈更新策略评分。

        规则:
          - 预测准确（accuracy ≈ 1.0）→ 小幅提升置信度
          - 低估（accuracy > 1.0）→ 提升置信度
          - 高估（accuracy < 1.0）→ 降低置信度
          - 失败 → 大幅降低置信度

        Args:
            strategy: MetaStrategy
            feedback: StrategyFeedback

        Returns:
            更新后的策略
        """
        if feedback.success:
            # 成功：根据预测准确度调整
            accuracy = feedback.prediction_accuracy
            if accuracy >= 0.8:
                # 预测准确或低估
                adjustment = self.ACCURACY_IMPACT_FACTOR * min(accuracy, 2.0)
                strategy.confidence = min(1.0, strategy.confidence + adjustment)
            else:
                # 高估
                adjustment = self.ACCURACY_IMPACT_FACTOR * (1.0 - accuracy)
                strategy.confidence = max(0.0, strategy.confidence - adjustment)
        else:
            # 失败：降低置信度
            strategy.confidence = max(0.0, strategy.confidence - self.ACCURACY_IMPACT_FACTOR * 2.0)

        strategy.evidence_count += 1
        return strategy

    def update_strategies_batch(
        self,
        strategy_feedback_pairs: list[tuple[MetaStrategy, StrategyFeedback]],
    ) -> list[MetaStrategy]:
        """批量更新策略。

        Args:
            strategy_feedback_pairs: [(strategy, feedback), ...]

        Returns:
            更新后的策略列表
        """
        return [
            self.update_strategy_score(s, f)
            for s, f in strategy_feedback_pairs
        ]

    # ── Analysis ───────────────────────────────────────────

    def get_feedbacks(self, strategy_id: str) -> list[StrategyFeedback]:
        """获取策略的所有反馈。"""
        return self._feedbacks.get(strategy_id, [])

    def get_average_accuracy(self, strategy_id: str) -> float:
        """获取策略的平均预测准确度。"""
        feedbacks = self.get_feedbacks(strategy_id)
        if not feedbacks:
            return 0.0
        accuracies = [f.prediction_accuracy for f in feedbacks if f.predicted_gain != 0]
        if not accuracies:
            return 0.0
        return sum(accuracies) / len(accuracies)

    def get_success_rate(self, strategy_id: str) -> float:
        """获取策略的成功率。"""
        feedbacks = self.get_feedbacks(strategy_id)
        if not feedbacks:
            return 0.0
        return sum(1 for f in feedbacks if f.success) / len(feedbacks)

    def get_overall_accuracy(self) -> float:
        """获取全局平均预测准确度。"""
        all_feedbacks = [
            f for feedbacks in self._feedbacks.values() for f in feedbacks
            if f.predicted_gain != 0
        ]
        if not all_feedbacks:
            return 0.0
        return sum(f.prediction_accuracy for f in all_feedbacks) / len(all_feedbacks)

    def get_summary(self) -> dict:
        """获取反馈摘要。"""
        all_feedbacks = [
            f for feedbacks in self._feedbacks.values() for f in feedbacks
        ]
        total = len(all_feedbacks)
        successful = sum(1 for f in all_feedbacks if f.success)
        overestimated = sum(1 for f in all_feedbacks if f.is_overestimated)
        underestimated = sum(1 for f in all_feedbacks if f.is_underestimated)

        return {
            "total_feedbacks": total,
            "successful_feedbacks": successful,
            "success_rate": round(successful / total, 4) if total > 0 else 0.0,
            "overestimated": overestimated,
            "underestimated": underestimated,
            "average_accuracy": round(self.get_overall_accuracy(), 4),
            "strategy_count": len(self._feedbacks),
        }

    def clear(self) -> None:
        """清空所有反馈。"""
        self._feedbacks.clear()

    def __repr__(self) -> str:
        return f"StrategyFeedbackCollector(strategies={len(self._feedbacks)})"