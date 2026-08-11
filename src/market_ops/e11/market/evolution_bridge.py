"""E11.5.4 Evolution Bridge — 市场反馈到进化层的桥梁。

连接 E11.5 Market Feedback 与 E11.3 Evolution，实现：

  MarketFeedback → Fitness → Population Update → Selection → Next Generation

核心能力：
  - apply_feedback: 将 MarketFeedback 应用到种群
  - update_population: 更新种群适应度排名
  - select_survivors: 执行选择
  - advance_generation: 推进到下一代

数据流：
  GenomeFitness → EvolutionBridge → Population → Selection → Next Generation
"""

from __future__ import annotations

from typing import Any

from ..genome.schema import CreativeGenome
from ..evolution.population_schema import GenomePopulation, PopulationMember
from ..evolution.population_manager import PopulationManager
from ..evolution.selection_schema import SelectionMode, SelectionPolicy, SelectionResult
from ..evolution.selection_manager import SelectionManager
from ..evolution.fitness_schema import FitnessScore, FitnessMetric, FitnessDirection
from .fitness_schema import GenomeFitness
from .feedback_loop_schema import EvolutionFeedbackEvent


class EvolutionBridge:
    """市场反馈到进化层的桥梁。

    将市场反馈转换为种群进化操作。

    Usage:
        bridge = EvolutionBridge()
        bridge.apply_feedback(population, genome, fitness)
        survivors = bridge.select_survivors(population, elite_count=5)
        bridge.advance_generation(population)
    """

    def __init__(self) -> None:
        self._population_manager = PopulationManager()
        self._selection_manager = SelectionManager()

    # ── 转换 ──────────────────────────────────────────

    @staticmethod
    def _genome_fitness_to_fitness_score(
        genome_id: str,
        genome_fitness: GenomeFitness,
    ) -> FitnessScore:
        """将 GenomeFitness (E11.5.3) 转换为 FitnessScore (E11.3.1)。

        直接使用 GenomeFitness.fitness_score 作为评分。

        Args:
            genome_id: Genome ID
            genome_fitness: E11.5.3 的 GenomeFitness

        Returns:
            E11.3.1 的 FitnessScore
        """
        metrics = [
            FitnessMetric(
                name="overall",
                value=genome_fitness.fitness_score,
                weight=1.0,
                direction=FitnessDirection.MAXIMIZE,
            ),
        ]
        return FitnessScore(genome_id=genome_id, metrics=metrics)

    # ── 主入口 ────────────────────────────────────────

    def apply_feedback(
        self,
        population: GenomePopulation,
        genome: CreativeGenome,
        fitness: GenomeFitness,
    ) -> EvolutionFeedbackEvent:
        """将市场反馈应用到种群。

        流程：
          1. 更新 Genome 的适应度
          2. 更新种群中对应成员的评分
          3. 重新排名
          4. 生成反馈事件

        Args:
            population: GenomePopulation
            genome: CreativeGenome
            fitness: GenomeFitness

        Returns:
            EvolutionFeedbackEvent
        """
        # 1. 更新或添加种群成员
        member = population.get_member(genome.genome_id)
        fs = self._genome_fitness_to_fitness_score(genome.genome_id, fitness)

        if member is None:
            # 新成员：加入种群
            self._population_manager.add_genome(
                population,
                genome_id=genome.genome_id,
                fitness=fs,
            )
        else:
            # 已有成员：更新适应度
            member.fitness = fs

        # 2. 重新排名
        self._population_manager.rank_members(population)

        # 3. 生成事件
        event = EvolutionFeedbackEvent(
            genome_id=genome.genome_id,
            creative_id=fitness.creative_id,
            feedback_id="",
            fitness_id=fitness.fitness_id,
            fitness_score=fitness.fitness_score,
            generation=population.generation,
            action="feedback_processed",
            details={
                "monetization_score": fitness.monetization_score,
                "retention_score": fitness.retention_score,
                "acquisition_score": fitness.acquisition_score,
                "population_size": population.size,
            },
        )
        return event

    # ── 种群操作 ──────────────────────────────────────

    def update_population(
        self,
        population: GenomePopulation,
        fitness_map: dict[str, GenomeFitness],
    ) -> list[EvolutionFeedbackEvent]:
        """批量更新种群适应度。

        Args:
            population: GenomePopulation
            fitness_map: {genome_id: GenomeFitness}

        Returns:
            事件列表
        """
        events = []
        for genome_id, fitness in fitness_map.items():
            member = population.get_member(genome_id)
            if member is not None:
                fs = self._genome_fitness_to_fitness_score(genome_id, fitness)
                member.fitness = fs
                events.append(EvolutionFeedbackEvent(
                    genome_id=genome_id,
                    creative_id=fitness.creative_id,
                    fitness_score=fitness.fitness_score,
                    generation=population.generation,
                    action="population_updated",
                ))

        self._population_manager.rank_members(population)
        return events

    def select_survivors(
        self,
        population: GenomePopulation,
        elite_count: int = 5,
        min_fitness: float = 0.3,
    ) -> SelectionResult:
        """执行精英选择。

        Args:
            population: GenomePopulation
            elite_count: 保留精英数量
            min_fitness: 最低适应度阈值

        Returns:
            SelectionResult
        """
        policy = SelectionPolicy(
            mode=SelectionMode.ELITE,
            top_k=elite_count,
            min_score=min_fitness,
        )
        return self._selection_manager.select(population, policy)

    def advance_generation(
        self,
        population: GenomePopulation,
    ) -> GenomePopulation:
        """推进到下一代。

        增加 population.generation 计数。

        Args:
            population: 当前种群

        Returns:
            更新后的种群
        """
        population.generation += 1
        return population

    # ── 精英标记 ──────────────────────────────────────

    def mark_elite(
        self,
        population: GenomePopulation,
        top_k: int = 5,
        min_score: float = 0.7,
    ) -> None:
        """标记精英成员。

        Args:
            population: GenomePopulation
            top_k: 精英数量
            min_score: 最低评分
        """
        self._population_manager.mark_elite(population, top_k=top_k, min_score=min_score)

    def get_top_candidates(
        self,
        population: GenomePopulation,
        top_k: int = 5,
    ) -> list[PopulationMember]:
        """获取 Top N 候选。

        Args:
            population: GenomePopulation
            top_k: 返回数量

        Returns:
            PopulationMember 列表
        """
        return self._population_manager.get_top_candidates(population, top_k=top_k)

    # ── 回滚支持 ──────────────────────────────────────

    def rollback_to_best(
        self,
        population: GenomePopulation,
        previous_best_fitness: float,
        previous_best_genome_id: str,
    ) -> bool:
        """回滚到之前的最佳状态。

        当新反馈导致适应度下降时使用。

        Args:
            population: 当前种群
            previous_best_fitness: 之前的最佳适应度
            previous_best_genome_id: 之前的最佳 Genome ID

        Returns:
            是否成功回滚
        """
        current_best = population.best_member
        if current_best is None:
            return False

        # 如果当前最佳不如之前，标记回滚
        if current_best.score < previous_best_fitness:
            # 标记前一个最佳为精英
            self._population_manager.mark_elite(
                population,
                top_k=population.size,
                min_score=previous_best_fitness,
            )
            return True
        return False

    def __repr__(self) -> str:
        return "EvolutionBridge()"