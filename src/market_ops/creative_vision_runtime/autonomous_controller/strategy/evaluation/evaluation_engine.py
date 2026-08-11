"""E11.8.3 — Evolution Evaluation Engine。

统一入口：将 Strategy + Before/After Metrics 转换为 EvolutionEvaluation。

流程：
  Strategy + Before/After
       ↓
  MetricEvaluator.compare()
       ↓
  ImprovementDetector.detect()
       ↓
  StrategyJudge.judge()
       ↓
  EvolutionEvaluation

这是 E11 闭环的最后一块拼图：
  Strategy → Execution → Evaluation → Knowledge → New Strategy
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import EvolutionStrategy
from .models import (
    EvolutionEvaluation,
    EvolutionRecommendation,
)
from .metric_evaluator import MetricEvaluator
from .improvement_detector import ImprovementDetector
from .strategy_judge import StrategyJudge

logger = logging.getLogger(__name__)


class EvolutionEvaluationEngine:
    """进化评估引擎。

    组合 MetricEvaluator + ImprovementDetector + StrategyJudge，
    提供统一评估入口。

    Attributes:
        metric_evaluator:     指标评估器
        improvement_detector: 改善检测器
        strategy_judge:       策略评判器
    """

    def __init__(
        self,
        metric_evaluator: MetricEvaluator | None = None,
        improvement_detector: ImprovementDetector | None = None,
        strategy_judge: StrategyJudge | None = None,
    ) -> None:
        self._metric_evaluator = metric_evaluator or MetricEvaluator()
        self._improvement_detector = improvement_detector or ImprovementDetector()
        self._strategy_judge = strategy_judge or StrategyJudge()

    # ── 主入口 ──────────────────────────────────────────

    def evaluate(
        self,
        before: dict[str, float],
        after: dict[str, float],
        strategy: EvolutionStrategy | None = None,
        consecutive_failures: int = 0,
    ) -> EvolutionEvaluation:
        """评估进化结果。

        完整流程：
          1. MetricEvaluator.compare() → MetricComparison[]
          2. ImprovementDetector.detect() → (EvaluationStatus, score)
          3. StrategyJudge.judge() → EvolutionRecommendation
          4. 组合为 EvolutionEvaluation

        Args:
            before:               进化前指标 {"ROI": 0.45, "CTR": 0.03, ...}
            after:                进化后指标 {"ROI": 0.62, "CTR": 0.035, ...}
            strategy:             原始策略（可选）
            consecutive_failures: 连续失败次数

        Returns:
            EvolutionEvaluation
        """
        # 1. 指标对比
        comparisons = self._metric_evaluator.compare(before, after)

        # 2. 检测改善
        status, score = self._improvement_detector.detect(comparisons)

        # 3. 构建评估（先构建基础版本用于 judge）
        evaluation = EvolutionEvaluation(
            strategy_id=strategy.strategy_id if strategy else "",
            status=status,
            score=score,
            improvements=comparisons,
            confidence=strategy.confidence if strategy else 0.5,
            metadata={
                "before": before,
                "after": after,
            },
        )

        # 4. 策略评判
        recommendation = self._strategy_judge.judge(
            evaluation, strategy, consecutive_failures
        )
        evaluation.recommendation = recommendation

        # 5. 构建理由
        evaluation.reason = self._build_evaluation_reason(
            evaluation, strategy, consecutive_failures
        )

        logger.info(
            f"Evaluation {evaluation.evaluation_id}: "
            f"status={status.value}, score={score:.1f}, "
            f"rec={recommendation.value}"
        )

        return evaluation

    def evaluate_batch(
        self,
        before_after_pairs: list[tuple[dict[str, float], dict[str, float]]],
        strategies: list[EvolutionStrategy] | None = None,
    ) -> list[EvolutionEvaluation]:
        """批量评估。

        Args:
            before_after_pairs: [(before, after), ...]
            strategies:         对应策略列表（可选）

        Returns:
            EvolutionEvaluation 列表
        """
        results: list[EvolutionEvaluation] = []
        for i, (before, after) in enumerate(before_after_pairs):
            strategy = strategies[i] if strategies and i < len(strategies) else None
            results.append(self.evaluate(before, after, strategy))
        return results

    def evaluate_with_focus(
        self,
        before: dict[str, float],
        after: dict[str, float],
        focus_metrics: list[str],
        strategy: EvolutionStrategy | None = None,
    ) -> EvolutionEvaluation:
        """只评估指定指标。

        Args:
            before:        进化前指标
            after:         进化后指标
            focus_metrics: 关注的指标列表
            strategy:      原始策略

        Returns:
            EvolutionEvaluation
        """
        comparisons = self._metric_evaluator.compare_focused(
            before, after, focus_metrics
        )
        status, score = self._improvement_detector.detect(comparisons)

        evaluation = EvolutionEvaluation(
            strategy_id=strategy.strategy_id if strategy else "",
            status=status,
            score=score,
            improvements=comparisons,
            confidence=strategy.confidence if strategy else 0.5,
            metadata={"before": before, "after": after, "focus": focus_metrics},
        )

        recommendation = self._strategy_judge.judge(evaluation, strategy)
        evaluation.recommendation = recommendation
        evaluation.reason = self._build_evaluation_reason(evaluation, strategy)

        return evaluation

    # ── 内部方法 ─────────────────────────────────────────

    def _build_evaluation_reason(
        self,
        evaluation: EvolutionEvaluation,
        strategy: EvolutionStrategy | None,
        consecutive_failures: int = 0,
    ) -> str:
        """构建评估理由。"""
        improved = evaluation.improved_count
        total = evaluation.total_metrics
        status = evaluation.status.value

        parts = [f"Status: {status}"]
        parts.append(
            f"Metrics: {improved}/{total} improved, "
            f"score={evaluation.score:.1f}"
        )
        parts.append(
            f"Recommendation: {evaluation.recommendation.value}"
        )

        if strategy:
            parts.append(
                f"Strategy: {strategy.strategy_type.value}, "
                f"focus={strategy.mutation_focus.value}"
            )

        return " | ".join(parts)

    # ── 属性 ────────────────────────────────────────────

    @property
    def metric_evaluator(self) -> MetricEvaluator:
        return self._metric_evaluator

    @property
    def improvement_detector(self) -> ImprovementDetector:
        return self._improvement_detector

    @property
    def strategy_judge(self) -> StrategyJudge:
        return self._strategy_judge

    def __repr__(self) -> str:
        return (
            f"EvolutionEvaluationEngine("
            f"metric={self._metric_evaluator}, "
            f"detector={self._improvement_detector}, "
            f"judge={self._strategy_judge})"
        )