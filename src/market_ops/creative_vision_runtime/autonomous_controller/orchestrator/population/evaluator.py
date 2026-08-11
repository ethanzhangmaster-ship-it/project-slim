"""E11.7.3 — Population Evaluator。

负责对种群进行适应度评估和排名。

核心职责：
  - 对个体列表按 fitness_score 排名
  - 计算种群统计（avg/min/max fitness）
  - 生成 PopulationSnapshot
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    GenomeIndividual,
    GenomeStatus,
    PopulationSnapshot,
    PopulationSummary,
)

logger = logging.getLogger(__name__)


class PopulationEvaluator:
    """种群评估器。

    Attributes:
        evaluate_count: 评估次数
    """

    def __init__(self) -> None:
        self._evaluate_count: int = 0
        self._snapshots: list[PopulationSnapshot] = []

    # ── 核心接口 ──────────────────────────────────────────

    def evaluate(
        self,
        individuals: list[GenomeIndividual],
        generation: int = 0,
    ) -> PopulationSnapshot:
        """评估种群。

        Args:
            individuals: 个体列表
            generation:  代数

        Returns:
            PopulationSnapshot
        """
        self._evaluate_count += 1

        if not individuals:
            snapshot = PopulationSnapshot(generation=generation)
            self._snapshots.append(snapshot)
            return snapshot

        fitnesses = [ind.fitness_score for ind in individuals]
        avg_fitness = sum(fitnesses) / len(fitnesses)
        min_fitness = min(fitnesses)
        max_fitness = max(fitnesses)

        elite_count = sum(1 for ind in individuals if ind.is_elite)

        snapshot = PopulationSnapshot(
            generation=generation,
            individuals=individuals,
            avg_fitness=round(avg_fitness, 2),
            min_fitness=min_fitness,
            max_fitness=max_fitness,
            elite_count=elite_count,
            total_count=len(individuals),
        )
        self._snapshots.append(snapshot)
        return snapshot

    def evaluate_batch(
        self,
        individuals: list[GenomeIndividual],
        generations: list[int] | None = None,
    ) -> list[PopulationSnapshot]:
        """批量评估多代种群。"""
        gens = generations or [0] * len(individuals)
        return [self.evaluate([ind], gen) for ind, gen in zip(individuals, gens)]

    # ── 排名 ──────────────────────────────────────────────

    @staticmethod
    def rank(
        individuals: list[GenomeIndividual],
    ) -> list[GenomeIndividual]:
        """按 fitness_score 降序排名并返回带排名标记的列表。

        排名存储在每个个体的 metadata["rank"] 中。
        """
        sorted_individuals = sorted(
            individuals, key=lambda ind: ind.fitness_score, reverse=True
        )
        for rank, ind in enumerate(sorted_individuals, start=1):
            ind.metadata["rank"] = rank
        return sorted_individuals

    @staticmethod
    def get_top_n(
        individuals: list[GenomeIndividual],
        n: int,
    ) -> list[GenomeIndividual]:
        """获取 top N 个体。"""
        sorted_individuals = sorted(
            individuals, key=lambda ind: ind.fitness_score, reverse=True
        )
        return sorted_individuals[:n]

    @staticmethod
    def get_bottom_n(
        individuals: list[GenomeIndividual],
        n: int,
    ) -> list[GenomeIndividual]:
        """获取 bottom N 个体。"""
        sorted_individuals = sorted(
            individuals, key=lambda ind: ind.fitness_score
        )
        return sorted_individuals[:n]

    @staticmethod
    def get_middle(
        individuals: list[GenomeIndividual],
        top_ratio: float = 0.2,
        bottom_ratio: float = 0.3,
    ) -> list[GenomeIndividual]:
        """获取中间层个体（top_ratio ~ 1-bottom_ratio）。"""
        sorted_individuals = sorted(
            individuals, key=lambda ind: ind.fitness_score, reverse=True
        )
        total = len(sorted_individuals)
        top_n = int(total * top_ratio)
        bottom_n = int(total * bottom_ratio)
        return sorted_individuals[top_n : total - bottom_n]

    # ── 统计 ──────────────────────────────────────────────

    @staticmethod
    def summary(
        individuals: list[GenomeIndividual],
        diversity_score: float = 0.0,
    ) -> PopulationSummary:
        """生成种群汇总统计。"""
        if not individuals:
            return PopulationSummary()

        fitnesses = [ind.fitness_score for ind in individuals]
        return PopulationSummary(
            total_individuals=len(individuals),
            active_count=sum(1 for ind in individuals if ind.is_active),
            elite_count=sum(1 for ind in individuals if ind.is_elite),
            retired_count=sum(1 for ind in individuals if ind.is_retired),
            avg_fitness=round(sum(fitnesses) / len(fitnesses), 2),
            best_fitness=max(fitnesses),
            diversity_score=round(diversity_score, 4),
        )

    # ── 快照查询 ──────────────────────────────────────────

    def get_latest_snapshot(self) -> PopulationSnapshot | None:
        return self._snapshots[-1] if self._snapshots else None

    def get_snapshots(self) -> list[PopulationSnapshot]:
        return list(self._snapshots)

    def get_snapshot_by_generation(
        self, generation: int
    ) -> PopulationSnapshot | None:
        for snap in self._snapshots:
            if snap.generation == generation:
                return snap
        return None

    # ── Stats ─────────────────────────────────────────────

    @property
    def evaluate_count(self) -> int:
        return self._evaluate_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "evaluate_count": self._evaluate_count,
            "snapshots_count": len(self._snapshots),
        }

    def reset(self) -> None:
        self._evaluate_count = 0
        self._snapshots.clear()

    def __repr__(self) -> str:
        return f"PopulationEvaluator(evaluated={self._evaluate_count})"