"""E11.3.3 Selection Manager — 自然选择管理器。

统一的选择入口，根据 SelectionPolicy 分发到具体策略。

数据流：
  GenomePopulation + SelectionPolicy → SelectionManager.select() → SelectionResult
"""

from __future__ import annotations

from .population_schema import GenomePopulation
from .selection_schema import (
    SelectionMode,
    SelectionPolicy,
    SelectionResult,
)
from .selection_policy import (
    EliteSelection,
    ThresholdSelection,
    DiversitySelection,
)


class SelectionManager:
    """自然选择管理器。

    根据 SelectionPolicy 自动分发到对应策略。

    Usage:
        manager = SelectionManager()
        policy = SelectionPolicy(mode=SelectionMode.ELITE, top_k=3)
        result = manager.select(population, policy)
        # result.survivors: 前 3 名存活
    """

    def __init__(self) -> None:
        self._elite = EliteSelection()
        self._threshold = ThresholdSelection()
        self._diversity = DiversitySelection()
        self._selection_count: int = 0

    def select(
        self,
        population: GenomePopulation,
        policy: SelectionPolicy,
    ) -> SelectionResult:
        """执行选择操作。

        根据 policy.mode 分发到对应策略。

        Args:
            population: 目标种群
            policy: 选择策略

        Returns:
            SelectionResult

        Raises:
            ValueError: 不支持的 SelectionMode
        """
        if policy.mode == SelectionMode.ELITE:
            result = self._elite.select(population, top_k=policy.top_k)
        elif policy.mode == SelectionMode.THRESHOLD:
            result = self._threshold.select(population, min_score=policy.min_score)
        elif policy.mode == SelectionMode.DIVERSITY:
            result = self._diversity.select(
                population, diversity_limit=policy.diversity_limit,
            )
        else:
            raise ValueError(f"Unsupported selection mode: {policy.mode!r}")

        self._selection_count += 1
        return result

    def select_elite(
        self,
        population: GenomePopulation,
        top_k: int = 5,
    ) -> SelectionResult:
        """精英选择快捷方法。"""
        result = self._elite.select(population, top_k=top_k)
        self._selection_count += 1
        return result

    def select_threshold(
        self,
        population: GenomePopulation,
        min_score: float = 0.5,
    ) -> SelectionResult:
        """阈值选择快捷方法。"""
        result = self._threshold.select(population, min_score=min_score)
        self._selection_count += 1
        return result

    def select_diversity(
        self,
        population: GenomePopulation,
        diversity_limit: int = 3,
    ) -> SelectionResult:
        """多样性选择快捷方法。"""
        result = self._diversity.select(population, diversity_limit=diversity_limit)
        self._selection_count += 1
        return result

    @property
    def selection_count(self) -> int:
        """已执行的选择次数。"""
        return self._selection_count