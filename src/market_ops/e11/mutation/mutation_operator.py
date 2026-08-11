"""E11.2 Mutation Operator — 基因组变异引擎核心。

实现四种基础变异操作：

  REPLACE — 替换基因值（hook A → hook B）
  ENHANCE — 增强数值型基因（curiosity 0.6 → 0.8）
  COMBINE — 合并两个 Genome 的基因
  REMOVE  — 删除弱基因槽位

所有操作保持：
  - deterministic（相同输入 → 相同输出）
  - explainable（每个变更可通过 MutationTarget 追踪）
  - lineage 保留（parent_id, generation++）

数据流：
  CreativeGenome + MutationRule → MutationResult + Child Genome
"""

from __future__ import annotations

import copy
from typing import Any

from ..genome.schema import CreativeGenome, GenomeLineage, GENE_SLOTS
from .mutation_schema import (
    MutationType,
    MutationTarget,
    MutationRule,
    MutationResult,
)
from .mutation_exceptions import (
    MutationError,
    UnsupportedMutationType,
    GeneNotFoundError,
    GeneSlotEmptyError,
    CombineSourceError,
    EnhanceNotNumericError,
)


class MutationOperator:
    """创意基因组变异引擎。

    接收 CreativeGenome + MutationRule，输出变异后的子代 Genome + MutationResult。

    Usage:
        operator = MutationOperator()
        result = operator.mutate(genome, rule)
        # result.child_genome 是变异后的子代
        # result 包含完整的变更记录

    可选传入 source_genome 用于 COMBINE 操作。
    """

    def __init__(self) -> None:
        self._mutation_count: int = 0

    # ── 主入口 ────────────────────────────────────────

    def mutate(
        self,
        genome: CreativeGenome,
        rule: MutationRule,
        source_genome: CreativeGenome | None = None,
    ) -> tuple[CreativeGenome, MutationResult]:
        """对 Genome 执行变异操作。

        Args:
            genome: 父代 CreativeGenome
            rule: 变异规则
            source_genome: COMBINE 操作的源 Genome（可选）

        Returns:
            (child_genome, mutation_result)

        Raises:
            UnsupportedMutationType: 不支持的变异类型
            GeneNotFoundError: 目标基因不存在
            CombineSourceError: COMBINE 缺少源 Genome
        """
        # 分发到具体变异方法
        if rule.mutation_type == MutationType.REPLACE:
            child, targets = self._replace(genome, rule)
        elif rule.mutation_type == MutationType.ENHANCE:
            child, targets = self._enhance(genome, rule)
        elif rule.mutation_type == MutationType.COMBINE:
            child, targets = self._combine(genome, rule, source_genome)
        elif rule.mutation_type == MutationType.REMOVE:
            child, targets = self._remove(genome, rule)
        else:
            raise UnsupportedMutationType(rule.mutation_type.value)

        # 构建结果
        result = MutationResult(
            parent_genome_id=genome.genome_id,
            child_genome_id=child.genome_id,
            changes=targets,
            success=True,
        )

        self._mutation_count += 1
        return child, result

    # ── REPLACE — 替换基因值 ───────────────────────────

    def _replace(
        self,
        genome: CreativeGenome,
        rule: MutationRule,
    ) -> tuple[CreativeGenome, MutationTarget]:
        """替换基因槽位的值。

        例如：hook: rescue → discovery
        """
        gene_name = rule.target_gene
        self._validate_gene(genome, gene_name)

        old_value = copy.deepcopy(genome.genes[gene_name])
        new_value = copy.deepcopy(old_value)

        # 根据 strategy 决定替换方式
        if rule.strategy == "winner_pattern":
            # 替换整个槽位值（保留结构，替换内容）
            # 实际替换值由外部传入，这里用 rule 的 priority 作为强度标记
            pass

        # 构建子代
        child = self._create_child(genome, created_by="mutation_engine")
        # 子代基因默认继承父代（已在 _create_child 中深拷贝）
        # 实际替换需要外部提供具体新旧值，这里用规则标记

        target = MutationTarget(
            gene_name=gene_name,
            old_value=old_value,
            new_value=new_value,
            confidence=rule.priority,
        )

        return child, [target]

    def replace(
        self,
        genome: CreativeGenome,
        gene_name: str,
        new_value: Any,
        confidence: float = 0.5,
    ) -> tuple[CreativeGenome, MutationTarget]:
        """直接替换指定基因槽位的值。

        Args:
            genome: 父代 Genome
            gene_name: 目标基因槽位名
            new_value: 新值
            confidence: 替换置信度

        Returns:
            (child_genome, mutation_target)
        """
        self._validate_gene(genome, gene_name)

        old_value = copy.deepcopy(genome.genes[gene_name])

        child = self._create_child(genome, created_by="mutation_engine")
        child.genes[gene_name] = copy.deepcopy(new_value)

        target = MutationTarget(
            gene_name=gene_name,
            old_value=old_value,
            new_value=new_value,
            confidence=confidence,
        )

        self._mutation_count += 1
        return child, target

    # ── ENHANCE — 增强基因值 ───────────────────────────

    def _enhance(
        self,
        genome: CreativeGenome,
        rule: MutationRule,
    ) -> tuple[CreativeGenome, MutationTarget]:
        """增强基因数值（仅处理数值型子字段）。

        例如：hook.strength 0.5 → 0.7（boost=0.4）
        """
        gene_name = rule.target_gene
        self._validate_gene(genome, gene_name)

        return self.enhance(genome, gene_name, boost=rule.priority)

    def enhance(
        self,
        genome: CreativeGenome,
        gene_name: str,
        boost: float = 0.2,
        sub_field: str | None = None,
    ) -> tuple[CreativeGenome, MutationTarget]:
        """增强基因的数值型属性。

        Args:
            genome: 父代 Genome
            gene_name: 目标基因槽位名
            boost: 增强比例（0.2 = +20%）
            sub_field: 子字段名（如 "strength", "intensity"），为 None 则增强所有数值字段

        Returns:
            (child_genome, mutation_target)
        """
        self._validate_gene(genome, gene_name)

        gene_data = genome.genes[gene_name]
        old_value = copy.deepcopy(gene_data)

        child = self._create_child(genome, created_by="mutation_engine")
        new_gene = child.genes[gene_name]

        if sub_field:
            # 增强指定子字段
            if sub_field not in new_gene:
                raise GeneNotFoundError(sub_field, genome.genome_id)
            if not isinstance(new_gene[sub_field], (int, float)):
                raise EnhanceNotNumericError(
                    f"{gene_name}.{sub_field}", new_gene[sub_field]
                )
            new_gene[sub_field] = round(new_gene[sub_field] * (1.0 + boost), 4)
        else:
            # 增强所有数值型子字段
            enhanced = False
            for key, val in new_gene.items():
                if isinstance(val, (int, float)):
                    new_gene[key] = round(val * (1.0 + boost), 4)
                    enhanced = True
            if not enhanced:
                raise EnhanceNotNumericError(gene_name, new_gene)

        child.genes[gene_name] = new_gene

        target = MutationTarget(
            gene_name=gene_name,
            old_value=old_value,
            new_value=copy.deepcopy(new_gene),
            confidence=0.5 + boost,  # 置信度随 boost 提升
        )

        self._mutation_count += 1
        return child, target

    # ── COMBINE — 合并基因 ─────────────────────────────

    def _combine(
        self,
        genome: CreativeGenome,
        rule: MutationRule,
        source_genome: CreativeGenome | None = None,
    ) -> tuple[CreativeGenome, list[MutationTarget]]:
        """合并两个 Genome 的基因。

        将 source_genome 中指定基因合并到当前 genome。
        """
        if source_genome is None:
            raise CombineSourceError()

        return self.combine(genome, source_genome, rule.target_gene)

    def combine(
        self,
        genome: CreativeGenome,
        source_genome: CreativeGenome,
        target_genes: str | list[str] | None = None,
    ) -> tuple[CreativeGenome, list[MutationTarget]]:
        """合并两个 Genome 的基因。

        Args:
            genome: 父代 Genome（作为基础）
            source_genome: 源 Genome（提供新基因）
            target_genes: 要合并的基因槽位（None = 全部非空基因）

        Returns:
            (child_genome, mutation_targets)
        """
        child = self._create_child(genome, created_by="mutation_engine")

        # 确定要合并的基因列表
        if target_genes is None:
            # 合并所有源基因中非空的槽位
            genes_to_merge = [
                g for g in GENE_SLOTS
                if source_genome.genes.get(g) and source_genome.genes[g]
            ]
        elif isinstance(target_genes, str):
            genes_to_merge = [target_genes]
        else:
            genes_to_merge = target_genes

        targets: list[MutationTarget] = []
        for gene_name in genes_to_merge:
            source_gene = source_genome.genes.get(gene_name)
            if not source_gene:
                continue

            old_value = copy.deepcopy(child.genes.get(gene_name, {}))
            new_value = copy.deepcopy(source_gene)

            child.genes[gene_name] = new_value

            target = MutationTarget(
                gene_name=gene_name,
                old_value=old_value if old_value else None,
                new_value=new_value,
                confidence=0.7,
            )
            targets.append(target)

        if not targets:
            # 没有可合并的基因，返回父代克隆
            target = MutationTarget(
                gene_name="none",
                old_value=None,
                new_value=None,
                confidence=0.0,
            )
            targets.append(target)

        self._mutation_count += 1
        return child, targets

    # ── REMOVE — 删除基因 ──────────────────────────────

    def _remove(
        self,
        genome: CreativeGenome,
        rule: MutationRule,
    ) -> tuple[CreativeGenome, list[MutationTarget]]:
        """删除指定基因槽位。"""
        return self.remove(genome, rule.target_gene)

    def remove(
        self,
        genome: CreativeGenome,
        gene_name: str,
    ) -> tuple[CreativeGenome, list[MutationTarget]]:
        """删除基因槽位（清空为默认空 dict）。

        Args:
            genome: 父代 Genome
            gene_name: 要删除的基因槽位名

        Returns:
            (child_genome, mutation_targets)
        """
        self._validate_gene(genome, gene_name)

        old_value = copy.deepcopy(genome.genes[gene_name])

        child = self._create_child(genome, created_by="mutation_engine")
        child.genes[gene_name] = {}

        target = MutationTarget(
            gene_name=gene_name,
            old_value=old_value,
            new_value={},
            confidence=0.9,
        )

        self._mutation_count += 1
        return child, [target]

    # ── 内部方法 ──────────────────────────────────────

    def _validate_gene(self, genome: CreativeGenome, gene_name: str) -> None:
        """验证基因槽位存在且非空。"""
        if gene_name not in GENE_SLOTS:
            raise GeneNotFoundError(gene_name, genome.genome_id)
        if gene_name not in genome.genes or not genome.genes[gene_name]:
            raise GeneSlotEmptyError(gene_name, genome.genome_id)

    def _create_child(
        self,
        parent: CreativeGenome,
        created_by: str = "mutation_engine",
    ) -> CreativeGenome:
        """创建子代 Genome，自动设置 lineage。

        - parent_id = parent.genome_id
        - generation = parent.generation + 1
        - genes 深拷贝自父代
        - fitness 浅拷贝自父代
        """
        child_id = f"{parent.genome_id}_v{parent.generation + 1}"

        return CreativeGenome(
            genome_id=child_id,
            parent_id=parent.genome_id,
            generation=parent.generation + 1,
            genes=copy.deepcopy(parent.genes),
            fitness=dict(parent.fitness),
            lineage=GenomeLineage(
                source=parent.lineage.source,
                created_by=created_by,
            ),
        )

    @property
    def mutation_count(self) -> int:
        """已执行的变异次数。"""
        return self._mutation_count