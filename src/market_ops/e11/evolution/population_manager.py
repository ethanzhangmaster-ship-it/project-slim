"""E11.3.2 Population Manager — 基因组种群管理器。

提供种群生命周期管理：

  create_population()  — 创建种群
  add_genome()         — 加入 Genome
  remove_genome()      — 移除 Genome
  update_fitness()     — 更新评分
  get_top_candidates() — 精英查询
  rank_members()       — 排名重算
  mark_elite()         — 精英标记

数据流：
  Genome Pool → PopulationManager → GenomePopulation → Elite Selection
"""

from __future__ import annotations

from typing import Any

from .fitness_schema import FitnessScore
from .population_schema import (
    PopulationStatus,
    GenomePopulation,
    PopulationMember,
)


class PopulationManager:
    """基因组种群管理器。

    Usage:
        manager = PopulationManager()
        pop = manager.create_population("pop_001", generation=1)
        manager.add_genome(pop, genome_id="genome_001")
        manager.update_fitness(pop, "genome_001", fitness_score)
        top = manager.get_top_candidates(pop, top_k=3)
    """

    # ── Create ─────────────────────────────────────────

    def create_population(
        self,
        population_id: str = "",
        generation: int = 1,
    ) -> GenomePopulation:
        """创建空种群。

        Args:
            population_id: 种群 ID（默认自动生成）
            generation: 世代编号

        Returns:
            新创建的 GenomePopulation
        """
        pop = GenomePopulation(
            population_id=population_id or "",
            generation=generation,
            status=PopulationStatus.CREATED,
        )
        return pop

    def create_population_from_genomes(
        self,
        genome_ids: list[str],
        population_id: str = "",
        generation: int = 1,
    ) -> GenomePopulation:
        """从 Genome ID 列表创建种群。

        Args:
            genome_ids: Genome ID 列表
            population_id: 种群 ID
            generation: 世代编号

        Returns:
            GenomePopulation
        """
        pop = GenomePopulation(
            population_id=population_id or "",
            generation=generation,
            status=PopulationStatus.ACTIVE,
        )
        for gid in genome_ids:
            pop.members.append(PopulationMember(genome_id=gid))
        return pop

    # ── Add / Remove ───────────────────────────────────

    def add_genome(
        self,
        population: GenomePopulation,
        genome_id: str,
        fitness: FitnessScore | None = None,
    ) -> PopulationMember:
        """向种群添加 Genome。

        Args:
            population: 目标种群
            genome_id: Genome ID
            fitness: 初始 FitnessScore（可选）

        Returns:
            新创建的 PopulationMember

        Raises:
            ValueError: genome_id 已存在
        """
        if population.has_genome(genome_id):
            raise ValueError(
                f"Genome {genome_id!r} already exists in population "
                f"{population.population_id!r}"
            )

        member = PopulationMember(
            genome_id=genome_id,
            fitness=fitness,
            rank=0,
            is_elite=False,
        )
        population.members.append(member)
        return member

    def remove_genome(
        self,
        population: GenomePopulation,
        genome_id: str,
    ) -> None:
        """从种群移除 Genome。

        Args:
            population: 目标种群
            genome_id: 要移除的 Genome ID

        Raises:
            ValueError: genome_id 不存在
        """
        member = population.get_member(genome_id)
        if member is None:
            raise ValueError(
                f"Genome {genome_id!r} not found in population "
                f"{population.population_id!r}"
            )
        population.members.remove(member)

    # ── Fitness ────────────────────────────────────────

    def update_fitness(
        self,
        population: GenomePopulation,
        genome_id: str,
        fitness: FitnessScore,
    ) -> PopulationMember:
        """更新成员的 FitnessScore。

        Args:
            population: 目标种群
            genome_id: Genome ID
            fitness: 新的 FitnessScore

        Returns:
            更新后的 PopulationMember

        Raises:
            ValueError: genome_id 不存在
        """
        member = population.get_member(genome_id)
        if member is None:
            raise ValueError(
                f"Genome {genome_id!r} not found in population "
                f"{population.population_id!r}"
            )
        member.fitness = fitness
        return member

    def update_fitness_batch(
        self,
        population: GenomePopulation,
        fitness_map: dict[str, FitnessScore],
    ) -> None:
        """批量更新 FitnessScore。

        Args:
            population: 目标种群
            fitness_map: {genome_id: FitnessScore} 映射
        """
        for genome_id, fitness in fitness_map.items():
            self.update_fitness(population, genome_id, fitness)

    # ── Ranking ────────────────────────────────────────

    def rank_members(self, population: GenomePopulation) -> None:
        """按评分重新排名所有成员。

        排名后更新每个成员的 rank 字段（1-based）。
        评分为 0 的成员排在最后。
        """
        sorted_members = sorted(
            population.members,
            key=lambda m: m.score,
            reverse=True,
        )
        for i, member in enumerate(sorted_members):
            member.rank = i + 1

    def mark_elite(
        self,
        population: GenomePopulation,
        top_k: int = 3,
        min_score: float = 0.5,
    ) -> None:
        """标记精英成员。

        精英条件：
          - rank <= top_k
          - score >= min_score

        Args:
            population: 目标种群
            top_k: 精英数量上限
            min_score: 最低评分阈值
        """
        # 先排名
        self.rank_members(population)

        for member in population.members:
            member.is_elite = (
                member.rank <= top_k
                and member.score >= min_score
            )

    # ── Query ──────────────────────────────────────────

    def get_top_candidates(
        self,
        population: GenomePopulation,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[PopulationMember]:
        """获取评分最高的候选成员。

        Args:
            population: 目标种群
            top_k: 返回数量
            min_score: 最低评分阈值

        Returns:
            按评分降序排列的成员列表
        """
        candidates = population.get_top_candidates(top_k)
        if min_score > 0:
            candidates = [c for c in candidates if c.score >= min_score]
        return candidates

    def get_elite_candidates(
        self,
        population: GenomePopulation,
    ) -> list[PopulationMember]:
        """获取精英成员。"""
        return population.get_elite_candidates()

    def get_healthy_candidates(
        self,
        population: GenomePopulation,
    ) -> list[PopulationMember]:
        """获取健康成员。"""
        return population.get_healthy_candidates()

    # ── Status ─────────────────────────────────────────

    def activate(self, population: GenomePopulation) -> None:
        """激活种群。"""
        population.status = PopulationStatus.ACTIVE

    def mark_evaluated(self, population: GenomePopulation) -> None:
        """标记为已评估。"""
        population.status = PopulationStatus.EVALUATED

    def archive(self, population: GenomePopulation) -> None:
        """归档种群。"""
        population.status = PopulationStatus.ARCHIVED

    # ── Stats ──────────────────────────────────────────

    def get_population_stats(self, population: GenomePopulation) -> dict[str, Any]:
        """获取种群统计信息。

        Returns:
            {
                "population_id": ...,
                "size": ...,
                "avg_score": ...,
                "best_score": ...,
                "best_genome": ...,
                "elite_count": ...,
                "healthy_count": ...,
                "status": ...,
            }
        """
        healthy = population.get_healthy_candidates()
        return {
            "population_id": population.population_id,
            "generation": population.generation,
            "size": population.size,
            "avg_score": population.avg_score,
            "best_score": population.best_score,
            "best_genome": population.best_member.genome_id if population.best_member else None,
            "elite_count": population.elite_count,
            "healthy_count": len(healthy),
            "status": population.status.value,
        }