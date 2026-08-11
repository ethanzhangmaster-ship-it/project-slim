"""E11.5.3 — Learning Engine。

FitnessScore → LearningSignal。

核心职责：
  1. 根据适应度评分确定学习方向
  2. 生成基因级别洞察
  3. 推荐突变策略
  4. 跟踪连续失败次数

学习规则：
  - Winner (fitness >= 80):   KEEP → 增加种群权重
  - Average (50 <= fitness < 80): IMPROVE → 保留并优化
  - Failed (fitness < 50):    MUTATE → 需要改变
  - Dead (连续失败 >= 3):      RETIRE → 退役
"""

from __future__ import annotations

import logging
from typing import Any

from .models import FitnessScore, LearningSignal, LearningDirection, PerformanceSignal

logger = logging.getLogger(__name__)


class LearningEngine:
    """学习引擎。

    根据适应度评分生成学习信号，反馈给 Evolution Engine。

    Attributes:
        generate_count:     已生成信号数
        failure_history:    genome_id → 连续失败次数
    """

    # 阈值
    WINNER_THRESHOLD = 80
    AVERAGE_THRESHOLD = 50
    RETIRE_AFTER_FAILURES = 3

    def __init__(self) -> None:
        self._generate_count: int = 0
        self._failure_history: dict[str, int] = {}

    # ── 核心接口 ──────────────────────────────────────

    def generate(
        self,
        fitness: FitnessScore,
        performance: PerformanceSignal | None = None,
    ) -> LearningSignal:
        """根据适应度评分生成学习信号。

        Args:
            fitness:      适应度评分
            performance:  原始性能数据（可选，用于生成洞察）

        Returns:
            LearningSignal
        """
        direction = self._determine_direction(fitness)
        confidence = self._compute_confidence(fitness)
        insights = self._generate_insights(fitness, performance)
        mutations = self._recommend_mutations(direction, fitness, performance)

        # 跟踪失败
        consecutive = self._track_failure(fitness.genome_id, direction)

        signal = LearningSignal(
            genome_id=fitness.genome_id,
            direction=direction,
            confidence=confidence,
            insights=insights,
            recommended_mutations=mutations,
            consecutive_failures=consecutive,
        )

        self._generate_count += 1
        return signal

    def generate_batch(
        self,
        fitness_scores: list[FitnessScore],
        performance_map: dict[str, PerformanceSignal] | None = None,
    ) -> list[LearningSignal]:
        """批量生成学习信号。"""
        perf_map = performance_map or {}
        return [
            self.generate(f, perf_map.get(f.genome_id))
            for f in fitness_scores
        ]

    # ── 方向判定 ──────────────────────────────────────

    @classmethod
    def _determine_direction(cls, fitness: FitnessScore) -> LearningDirection:
        """根据适应度评分确定学习方向。"""
        if fitness.is_winner:
            return LearningDirection.KEEP
        elif fitness.is_average:
            return LearningDirection.IMPROVE
        else:
            return LearningDirection.MUTATE

    def _track_failure(
        self,
        genome_id: str,
        direction: LearningDirection,
    ) -> int:
        """跟踪连续失败次数。"""
        if direction in (LearningDirection.MUTATE, LearningDirection.RETIRE):
            self._failure_history[genome_id] = (
                self._failure_history.get(genome_id, 0) + 1
            )
        else:
            self._failure_history[genome_id] = 0

        consecutive = self._failure_history[genome_id]

        # 连续失败 >= RETIRE_AFTER_FAILURES → 一旦 MUTATE 判定为 applies
        if consecutive >= self.RETIRE_AFTER_FAILURES:
            return consecutive

        return consecutive

    def get_consecutive_failures(self, genome_id: str) -> int:
        """获取 genome 的连续失败次数。"""
        return self._failure_history.get(genome_id, 0)

    # ── 洞察生成 ──────────────────────────────────────

    @staticmethod
    def _generate_insights(
        fitness: FitnessScore,
        performance: PerformanceSignal | None,
    ) -> list[str]:
        """生成洞察列表。"""
        insights: list[str] = []

        if fitness.roi_score >= 80:
            insights.append("Strong ROI performance")
        elif fitness.roi_score <= 30:
            insights.append("ROI underperforming")

        if fitness.ctr_score >= 80:
            insights.append("High CTR engagement")
        elif fitness.ctr_score <= 30:
            insights.append("Low CTR engagement")

        if fitness.cvr_score >= 80:
            insights.append("Excellent conversion rate")
        elif fitness.cvr_score <= 30:
            insights.append("Poor conversion rate")

        if performance and performance.is_positive_roi:
            insights.append("Positive ROI achieved")

        if not insights:
            insights.append("Moderate performance across metrics")

        return insights

    # ── 突变推荐 ──────────────────────────────────────

    @staticmethod
    def _recommend_mutations(
        direction: LearningDirection,
        fitness: FitnessScore,
        performance: PerformanceSignal | None,
    ) -> list[str]:
        """推荐基因突变。"""
        mutations: list[str] = []

        if direction == LearningDirection.KEEP:
            mutations.append("Keep current gene configuration")

        elif direction == LearningDirection.IMPROVE:
            if fitness.roi_score < 80:
                mutations.append("improve_reward_reveal_curve")
            if fitness.ctr_score < 80:
                mutations.append("increase_hook_contrast")
            if fitness.cvr_score < 80:
                mutations.append("optimize_color_saturation")

        elif direction == LearningDirection.MUTATE:
            mutations.append("increase_hook_contrast")
            mutations.append("increase_transition_speed")
            mutations.append("optimize_reward_reveal_curve")
            if fitness.ctr_score < 60:
                mutations.append("adjust_color_brightness")
            if fitness.cvr_score < 60:
                mutations.append("increase_object_density")

        return mutations

    # ── 置信度计算 ────────────────────────────────────

    @staticmethod
    def _compute_confidence(fitness: FitnessScore) -> float:
        """根据评分计算置信度。"""
        if fitness.is_winner:
            return min(fitness.overall_score / 100, 1.0)
        elif fitness.is_average:
            return 0.5 + 0.3 * (fitness.overall_score - 50) / 30
        else:
            return max(0.1, 0.3 + 0.2 * fitness.overall_score / 50)

    # ── Stats ──────────────────────────────────────────

    @property
    def generate_count(self) -> int:
        return self._generate_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "generate_count": self._generate_count,
            "tracked_genomes": len(self._failure_history),
            "failure_counts": dict(self._failure_history),
        }

    def reset(self) -> None:
        self._generate_count = 0
        self._failure_history.clear()

    def __repr__(self) -> str:
        return (
            f"LearningEngine(generated={self._generate_count}, "
            f"tracked={len(self._failure_history)})"
        )