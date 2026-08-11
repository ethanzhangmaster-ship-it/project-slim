"""E11.7.3 — Population Evolution Manager。

统一入口：种群注册 → 评估 → 选择 → 多样性检测 → 决策。

完整链路：
  GenomePopulation → PopulationEvaluator → DiversityEngine → PopulationSelector
    → PopulationDecision → Scheduler Tasks
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    GenomeIndividual,
    GenomeStatus,
    PopulationSnapshot,
    PopulationDecision,
    PopulationSummary,
)
from .evaluator import PopulationEvaluator
from .selector import PopulationSelector
from .diversity import DiversityEngine

logger = logging.getLogger(__name__)


class PopulationEvolutionManager:
    """种群进化管理器。

    统一入口：管理整个 Genome Population 的生命周期。

    Attributes:
        evaluator:  PopulationEvaluator
        selector:   PopulationSelector
        diversity:  DiversityEngine
        individuals: 当前所有个体
        generation:  当前代数
    """

    def __init__(
        self,
        evaluator: PopulationEvaluator | None = None,
        selector: PopulationSelector | None = None,
        diversity: DiversityEngine | None = None,
    ) -> None:
        self._evaluator = evaluator or PopulationEvaluator()
        self._selector = selector or PopulationSelector()
        self._diversity = diversity or DiversityEngine()
        self._individuals: dict[str, GenomeIndividual] = {}
        self._generation: int = 0
        self._decisions: list[PopulationDecision] = []

    # ── 注册 ──────────────────────────────────────────────

    def register(
        self,
        genome_id: str,
        fitness_score: float = 0.0,
        features: dict[str, Any] | None = None,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GenomeIndividual:
        """注册一个新个体。"""
        individual = GenomeIndividual(
            genome_id=genome_id,
            fitness_score=fitness_score,
            generation=self._generation,
            features=features or {},
            parent_id=parent_id,
            metadata=metadata or {},
        )
        self._individuals[genome_id] = individual
        return individual

    def register_batch(
        self,
        genomes: list[dict[str, Any]],
    ) -> list[GenomeIndividual]:
        """批量注册。"""
        return [
            self.register(
                genome_id=g.get("genome_id", ""),
                fitness_score=g.get("fitness_score", 0.0),
                features=g.get("features"),
                parent_id=g.get("parent_id"),
                metadata=g.get("metadata"),
            )
            for g in genomes
        ]

    def create_population(
        self,
        genomes: list[dict[str, Any]],
    ) -> list[GenomeIndividual]:
        """创建初始种群（重置并注册）。"""
        self._individuals.clear()
        self._generation = 0
        return self.register_batch(genomes)

    # ── 核心接口：evolve ─────────────────────────────────

    def evolve(self) -> PopulationDecision:
        """执行一代进化。

        完整链路：
          1. 评估种群 (PopulationEvaluator)
          2. 计算多样性 (DiversityEngine)
          3. 种群选择 (PopulationSelector)
          4. 返回 PopulationDecision

        Returns:
            PopulationDecision
        """
        individuals = self.get_active_individuals()

        # 1. 评估
        snapshot = self._evaluator.evaluate(individuals, self._generation)

        # 2. 多样性
        diversity_score = self._diversity.calculate(individuals)
        snapshot.diversity_score = diversity_score

        # 3. 选择
        decision = self._selector.select(
            individuals, self._generation, diversity_score
        )

        # 4. 更新状态
        self._apply_decision(decision)
        self._decisions.append(decision)
        self._generation += 1

        return decision

    def evolve_multiple(self, generations: int = 1) -> list[PopulationDecision]:
        """执行多代进化。"""
        return [self.evolve() for _ in range(generations)]

    # ── 应用决策 ──────────────────────────────────────────

    def _apply_decision(self, decision: PopulationDecision) -> None:
        """应用 PopulationDecision 更新个体状态。"""
        # 精英
        for genome_id in decision.elite:
            if genome_id in self._individuals:
                self._individuals[genome_id].status = GenomeStatus.ELITE

        # 突变
        for genome_id in decision.mutate:
            if genome_id in self._individuals:
                self._individuals[genome_id].status = GenomeStatus.MUTATING

        # 退役
        for genome_id in decision.retire:
            if genome_id in self._individuals:
                self._individuals[genome_id].status = GenomeStatus.RETIRED

    # ── 查询 ──────────────────────────────────────────────

    def get_individual(self, genome_id: str) -> GenomeIndividual | None:
        return self._individuals.get(genome_id)

    def get_active_individuals(self) -> list[GenomeIndividual]:
        return [ind for ind in self._individuals.values() if ind.is_active]

    def get_elite(self) -> list[GenomeIndividual]:
        return [ind for ind in self._individuals.values() if ind.is_elite]

    def get_retired(self) -> list[GenomeIndividual]:
        return [ind for ind in self._individuals.values() if ind.is_retired]

    def get_by_status(self, status: GenomeStatus) -> list[GenomeIndividual]:
        return [ind for ind in self._individuals.values() if ind.status == status]

    def get_individuals_by_generation(self, generation: int) -> list[GenomeIndividual]:
        return [ind for ind in self._individuals.values() if ind.generation == generation]

    def get_population_snapshot(self) -> PopulationSnapshot:
        """获取当前种群快照。"""
        active = self.get_active_individuals()
        diversity = self._diversity.get_latest_diversity()
        return self._evaluator.evaluate(active, self._generation)

    def get_summary(self) -> PopulationSummary:
        """获取种群汇总统计。"""
        active = self.get_active_individuals()
        diversity = self._diversity.get_latest_diversity()
        return PopulationEvaluator.summary(active, diversity)

    # ── 决策查询 ──────────────────────────────────────────

    def get_latest_decision(self) -> PopulationDecision | None:
        return self._decisions[-1] if self._decisions else None

    def get_decisions(self) -> list[PopulationDecision]:
        return list(self._decisions)

    # ── 属性 ──────────────────────────────────────────────

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def population_size(self) -> int:
        return len(self._individuals)

    @property
    def active_count(self) -> int:
        return len(self.get_active_individuals())

    @property
    def elite_count(self) -> int:
        return len(self.get_elite())

    @property
    def retired_count(self) -> int:
        return len(self.get_retired())

    # ── Stats ─────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        summary = self.get_summary()
        return {
            "generation": self._generation,
            "population_size": self.population_size,
            "active_count": self.active_count,
            "elite_count": self.elite_count,
            "retired_count": self.retired_count,
            "summary": summary.to_dict(),
            "evaluator": self._evaluator.get_stats(),
            "selector": self._selector.get_stats(),
            "diversity": self._diversity.get_stats(),
            "decisions_count": len(self._decisions),
        }

    def reset(self) -> None:
        self._individuals.clear()
        self._generation = 0
        self._decisions.clear()
        self._evaluator.reset()
        self._selector.reset()
        self._diversity.reset()

    def __repr__(self) -> str:
        return (
            f"PopulationEvolutionManager(gen={self._generation}, "
            f"size={self.population_size}, "
            f"active={self.active_count})"
        )