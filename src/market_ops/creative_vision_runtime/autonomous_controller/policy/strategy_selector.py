"""E11.6 — Strategy Selector。

根据 LearningSignal 和 FitnessScore 选择 MutationStrategy 和参数。

核心职责：
  1. 映射 LearningDirection → MutationStrategy
  2. 根据 fitness 细分强度
  3. 确定目标基因集
  4. 计算 mutation_rate
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    MutationStrategy,
    MUTATION_RATE_MAP,
    TARGET_GENES_MAP,
)
from ..feedback.models import LearningSignal, LearningDirection, FitnessScore

logger = logging.getLogger(__name__)


class StrategySelector:
    """突变策略选择器。

    根据 LearningSignal 和 FitnessScore 选择最优的突变策略和参数。

    Attributes:
        select_count: 已选择次数
    """

    # ── Direction → Strategy 映射 ────────────────────────

    DIRECTION_STRATEGY_MAP: dict[LearningDirection, MutationStrategy] = {
        LearningDirection.KEEP: MutationStrategy.SMALL,
        LearningDirection.IMPROVE: MutationStrategy.MEDIUM,
        LearningDirection.MUTATE: MutationStrategy.LARGE,
        LearningDirection.RETIRE: MutationStrategy.SMALL,
    }

    def __init__(self) -> None:
        self._select_count: int = 0

    # ── 核心接口 ──────────────────────────────────────────

    def select(
        self,
        learning_signal: LearningSignal,
        fitness: FitnessScore | None = None,
    ) -> MutationStrategy:
        """选择突变策略。

        Args:
            learning_signal: 学习信号
            fitness:         适应度评分（可选）

        Returns:
            MutationStrategy
        """
        strategy = self._select_by_direction(learning_signal.direction)
        strategy = self._refine_by_fitness(strategy, fitness)
        self._select_count += 1
        return strategy

    def select_batch(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> list[MutationStrategy]:
        """批量选择。"""
        fit_map = fitness_map or {}
        return [
            self.select(ls, fit_map.get(ls.genome_id))
            for ls in learning_signals
        ]

    # ── 策略选择 ──────────────────────────────────────────

    def _select_by_direction(
        self, direction: LearningDirection
    ) -> MutationStrategy:
        """根据学习方向选择基础策略。"""
        return self.DIRECTION_STRATEGY_MAP.get(
            direction, MutationStrategy.MEDIUM
        )

    @staticmethod
    def _refine_by_fitness(
        strategy: MutationStrategy,
        fitness: FitnessScore | None,
    ) -> MutationStrategy:
        """根据 fitness 细分策略强度。

        细分规则：
          - 接近阈值边界时，降级策略强度
          - 极端值时，升级策略强度
        """
        if fitness is None:
            return strategy

        score = fitness.overall_score

        # 边界降级：接近 winner 边缘但仍被判定为 IMPROVE → 降为 SMALL
        if strategy == MutationStrategy.MEDIUM and score >= 75:
            return MutationStrategy.SMALL

        # 深度失败：远低于阈值 → 升级为 RADICAL
        if strategy == MutationStrategy.LARGE and score <= 20:
            return MutationStrategy.RADICAL

        # 接近失败边缘但仍被判定为 MUTATE → 降为 MEDIUM
        if strategy == MutationStrategy.LARGE and score >= 45:
            return MutationStrategy.MEDIUM

        return strategy

    # ── 参数获取 ──────────────────────────────────────────

    @staticmethod
    def get_mutation_rate(strategy: MutationStrategy) -> float:
        """获取突变率。"""
        return MUTATION_RATE_MAP.get(strategy, 0.3)

    @staticmethod
    def get_target_genes(strategy: MutationStrategy) -> list[str]:
        """获取目标基因列表。"""
        return list(TARGET_GENES_MAP.get(strategy, []))

    @staticmethod
    def get_strategy_params(
        strategy: MutationStrategy,
    ) -> dict[str, Any]:
        """获取策略的完整参数。"""
        return {
            "strategy": strategy.value,
            "mutation_rate": MUTATION_RATE_MAP.get(strategy, 0.3),
            "target_genes": TARGET_GENES_MAP.get(strategy, []),
        }

    # ── Stats ─────────────────────────────────────────────

    @property
    def select_count(self) -> int:
        return self._select_count

    def reset(self) -> None:
        self._select_count = 0

    def __repr__(self) -> str:
        return f"StrategySelector(selected={self._select_count})"