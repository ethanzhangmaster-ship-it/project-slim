"""E11.8.3 — Strategy Judge。

职责：根据进化评估结果，判断策略是否正确，并给出后续行动建议。

输入：EvolutionEvaluation + EvolutionStrategy
输出：EvolutionRecommendation

规则：
  SUCCESS + high confidence → SCALE
  SUCCESS + moderate confidence → KEEP
  PARTIAL → ITERATE
  FAILED → ROLLBACK
  INCONCLUSIVE → KEEP（默认）
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import EvolutionStrategy, StrategyType
from .models import (
    EvaluationStatus,
    EvolutionEvaluation,
    EvolutionRecommendation,
)

logger = logging.getLogger(__name__)

# 置信度阈值
SCALE_CONFIDENCE_THRESHOLD = 0.8  # 高置信度 → 扩大
RETIRE_FAILURE_COUNT = 5          # 连续失败 5 次 → 退役


class StrategyJudge:
    """策略评判器。

    根据评估结果和原始策略，给出后续行动建议。

    Attributes:
        scale_threshold:   扩大投放的置信度阈值
        retire_threshold:  退役所需的连续失败次数
    """

    def __init__(
        self,
        scale_threshold: float = SCALE_CONFIDENCE_THRESHOLD,
        retire_threshold: int = RETIRE_FAILURE_COUNT,
    ) -> None:
        self._scale_threshold = scale_threshold
        self._retire_threshold = retire_threshold

    # ── 主入口 ──────────────────────────────────────────

    def judge(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None = None,
        consecutive_failures: int = 0,
    ) -> EvolutionRecommendation:
        """根据评估结果给出建议。

        Args:
            evaluation:           进化评估
            strategy:             原始策略（可选，用于上下文判断）
            consecutive_failures: 连续失败次数

        Returns:
            EvolutionRecommendation
        """
        status = evaluation.status

        if status == EvaluationStatus.SUCCESS:
            return self._judge_success(evaluation, strategy)

        elif status == EvaluationStatus.PARTIAL:
            return self._judge_partial(evaluation, strategy)

        elif status == EvaluationStatus.FAILED:
            return self._judge_failed(evaluation, strategy, consecutive_failures)

        else:  # INCONCLUSIVE
            return self._judge_inconclusive(evaluation, strategy)

    def judge_with_reason(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None = None,
        consecutive_failures: int = 0,
    ) -> dict[str, Any]:
        """评判并返回详细理由。

        Returns:
            {
                "recommendation": EvolutionRecommendation,
                "reason": str,
                "confidence": float,
            }
        """
        recommendation = self.judge(evaluation, strategy, consecutive_failures)

        reason = self._build_reason(
            recommendation, evaluation, strategy, consecutive_failures
        )
        confidence = self._compute_judge_confidence(
            evaluation, recommendation
        )

        return {
            "recommendation": recommendation,
            "reason": reason,
            "confidence": confidence,
        }

    # ── 判断逻辑 ─────────────────────────────────────────

    def _judge_success(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None,
    ) -> EvolutionRecommendation:
        """成功 → SCALE 或 KEEP。"""
        if evaluation.confidence >= self._scale_threshold:
            return EvolutionRecommendation.SCALE
        return EvolutionRecommendation.KEEP

    def _judge_partial(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None,
    ) -> EvolutionRecommendation:
        """部分成功 → ITERATE。"""
        return EvolutionRecommendation.ITERATE

    def _judge_failed(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None,
        consecutive_failures: int,
    ) -> EvolutionRecommendation:
        """失败 → ROLLBACK 或 RETIRE。"""
        if consecutive_failures >= self._retire_threshold:
            return EvolutionRecommendation.RETIRE
        return EvolutionRecommendation.ROLLBACK

    def _judge_inconclusive(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None,
    ) -> EvolutionRecommendation:
        """数据不足 → KEEP。"""
        return EvolutionRecommendation.KEEP

    # ── 辅助方法 ─────────────────────────────────────────

    def _build_reason(
        self,
        recommendation: EvolutionRecommendation,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None,
        consecutive_failures: int,
    ) -> str:
        """构建建议理由。"""
        status = evaluation.status.value
        improved = evaluation.improved_count
        total = evaluation.total_metrics

        if recommendation == EvolutionRecommendation.SCALE:
            return (
                f"High-confidence success: {improved}/{total} metrics improved, "
                f"score={evaluation.score:.1f}, confidence={evaluation.confidence:.2f}. "
                f"Recommend scaling."
            )
        elif recommendation == EvolutionRecommendation.KEEP:
            return (
                f"Strategy {status}: {improved}/{total} metrics improved. "
                f"Keep current genome, monitor further."
            )
        elif recommendation == EvolutionRecommendation.ITERATE:
            return (
                f"Partial improvement: {improved}/{total} metrics improved. "
                f"Continue iterating with adjusted parameters."
            )
        elif recommendation == EvolutionRecommendation.ROLLBACK:
            return (
                f"Strategy failed: only {improved}/{total} metrics improved. "
                f"Rollback to previous genome."
            )
        elif recommendation == EvolutionRecommendation.RETIRE:
            return (
                f"Strategy failed {consecutive_failures}+ times consecutively. "
                f"Retire this genome direction."
            )
        else:
            return f"Status: {status}, recommendation: {recommendation.value}"

    @staticmethod
    def _compute_judge_confidence(
        evaluation: EvolutionEvaluation,
        recommendation: EvolutionRecommendation,
    ) -> float:
        """计算评判置信度。"""
        if recommendation == EvolutionRecommendation.KEEP:
            return 0.3

        base = evaluation.confidence
        if evaluation.total_metrics >= 5:
            base = min(1.0, base + 0.1)

        return round(base, 3)

    def __repr__(self) -> str:
        return (
            f"StrategyJudge("
            f"scale_threshold={self._scale_threshold}, "
            f"retire_threshold={self._retire_threshold})"
        )