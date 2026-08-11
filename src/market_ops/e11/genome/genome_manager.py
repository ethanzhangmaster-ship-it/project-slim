"""E11.1 Genome Manager — 创意基因组生命周期管理。

提供：
  - create_genome: 从基因字典创建 Genome
  - clone_genome: 克隆 Genome 用于 mutation
  - update_genome: 更新 Genome 基因或 fitness
  - query_genome: 按 ID 查询 Genome
  - list_genomes: 列出所有 Genome
  - get_lineage: 获取谱系链
"""

from __future__ import annotations

from typing import Any

from .schema import CreativeGenome, GenomeLineage
from .exceptions import (
    GenomeNotFoundError,
    GenomeDuplicateError,
    GenomeValidationError,
)


class GenomeManager:
    """Genome 生命周期管理器。

    Usage:
        manager = GenomeManager()
        genome = manager.create_genome(
            genome_id="genome_001",
            genes={...},
            source="winner_001",
        )
        child = manager.clone_genome("genome_001", new_id="genome_002")
    """

    def __init__(self) -> None:
        self._genomes: dict[str, CreativeGenome] = {}
        self._counter: int = 0

    # ── Create ─────────────────────────────────────────

    def create_genome(
        self,
        genome_id: str,
        genes: dict[str, dict[str, Any]],
        fitness: dict[str, float] | None = None,
        source: str = "",
        created_by: str = "dna_mapper",
    ) -> CreativeGenome:
        """从基因字典创建新 Genome。

        Args:
            genome_id: 唯一标识
            genes: 五个基因槽位字典
            fitness: 性能指标（可选）
            source: 原始来源（如 winner_001）
            created_by: 创建者标识

        Returns:
            新创建的 CreativeGenome

        Raises:
            GenomeDuplicateError: genome_id 已存在
        """
        if genome_id in self._genomes:
            raise GenomeDuplicateError(genome_id)

        genome = CreativeGenome(
            genome_id=genome_id,
            parent_id=None,
            generation=0,
            genes=genes,
            fitness=fitness or {},
            lineage=GenomeLineage(
                source=source,
                created_by=created_by,
            ),
        )
        self._genomes[genome_id] = genome
        self._counter += 1
        return genome

    # ── Clone ──────────────────────────────────────────

    def clone_genome(
        self,
        genome_id: str,
        new_id: str | None = None,
        created_by: str = "mutation_engine",
    ) -> CreativeGenome:
        """克隆 Genome，产生子代。

        parent → child（generation + 1）

        Args:
            genome_id: 父代 Genome ID
            new_id: 子代 ID（默认自动生成）
            created_by: 创建者标识

        Returns:
            克隆的子代 CreativeGenome

        Raises:
            GenomeNotFoundError: 父代不存在
        """
        parent = self._genomes.get(genome_id)
        if parent is None:
            raise GenomeNotFoundError(genome_id)

        child_id = new_id or f"{genome_id}_v{parent.generation + 1}"
        if child_id in self._genomes:
            raise GenomeDuplicateError(child_id)

        # 深拷贝基因
        import copy
        child_genes = copy.deepcopy(parent.genes)

        child = CreativeGenome(
            genome_id=child_id,
            parent_id=genome_id,
            generation=parent.generation + 1,
            genes=child_genes,
            fitness=dict(parent.fitness),  # 浅拷贝数值
            lineage=GenomeLineage(
                source=parent.lineage.source,
                created_by=created_by,
            ),
        )
        self._genomes[child_id] = child
        self._counter += 1
        return child

    # ── Update ─────────────────────────────────────────

    def update_genome(
        self,
        genome_id: str,
        genes: dict[str, dict[str, Any]] | None = None,
        fitness: dict[str, float] | None = None,
    ) -> CreativeGenome:
        """更新 Genome 的基因或 fitness。

        Args:
            genome_id: 目标 Genome ID
            genes: 要更新的基因槽位
            fitness: 要更新的性能指标

        Returns:
            更新后的 CreativeGenome

        Raises:
            GenomeNotFoundError: Genome 不存在
        """
        genome = self._genomes.get(genome_id)
        if genome is None:
            raise GenomeNotFoundError(genome_id)

        if genes is not None:
            genome.genes.update(genes)
        if fitness is not None:
            genome.fitness.update(fitness)

        return genome

    # ── Query ──────────────────────────────────────────

    def query_genome(self, genome_id: str) -> CreativeGenome:
        """按 ID 查询 Genome。

        Raises:
            GenomeNotFoundError: 不存在
        """
        genome = self._genomes.get(genome_id)
        if genome is None:
            raise GenomeNotFoundError(genome_id)
        return genome

    def list_genomes(self) -> list[CreativeGenome]:
        """返回所有 Genome 列表。"""
        return list(self._genomes.values())

    def count(self) -> int:
        """返回 Genome 总数。"""
        return len(self._genomes)

    # ── Lineage ────────────────────────────────────────

    def get_lineage(self, genome_id: str) -> list[str]:
        """获取从原始祖先到指定 Genome 的谱系链。

        Returns:
            [ancestor_id, ..., parent_id, genome_id] 有序列表
        """
        chain: list[str] = []
        current_id: str | None = genome_id

        while current_id is not None:
            chain.append(current_id)
            genome = self._genomes.get(current_id)
            if genome is None:
                break
            current_id = genome.parent_id

        chain.reverse()
        return chain

    def get_ancestor(self, genome_id: str) -> CreativeGenome:
        """获取指定 Genome 的原始祖先。

        Returns:
            谱系链最顶端的 CreativeGenome
        """
        lineage = self.get_lineage(genome_id)
        ancestor_id = lineage[0]
        return self.query_genome(ancestor_id)