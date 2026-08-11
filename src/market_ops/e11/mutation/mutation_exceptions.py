"""E11.2 Mutation Exceptions — 变异操作异常体系。"""

from __future__ import annotations


class MutationError(Exception):
    """Mutation 模块基础异常。"""
    pass


class UnsupportedMutationType(MutationError):
    """不支持的变异类型。"""

    def __init__(self, mutation_type: str) -> None:
        self.mutation_type = mutation_type
        super().__init__(f"Unsupported mutation type: {mutation_type!r}")


class GeneNotFoundError(MutationError):
    """目标基因槽位不存在。"""

    def __init__(self, gene_name: str, genome_id: str = "") -> None:
        self.gene_name = gene_name
        self.genome_id = genome_id
        msg = f"Gene {gene_name!r} not found"
        if genome_id:
            msg += f" in genome {genome_id!r}"
        super().__init__(msg)


class GeneSlotEmptyError(MutationError):
    """基因槽位为空，无法执行变异。"""

    def __init__(self, gene_name: str, genome_id: str = "") -> None:
        self.gene_name = gene_name
        self.genome_id = genome_id
        msg = f"Gene slot {gene_name!r} is empty"
        if genome_id:
            msg += f" in genome {genome_id!r}"
        super().__init__(msg)


class CombineSourceError(MutationError):
    """COMBINE 操作缺少源 Genome。"""

    def __init__(self) -> None:
        super().__init__("COMBINE mutation requires a source_genome parameter")


class EnhanceNotNumericError(MutationError):
    """ENHANCE 目标值不是数值类型。"""

    def __init__(self, gene_name: str, value: object) -> None:
        self.gene_name = gene_name
        super().__init__(
            f"Cannot enhance non-numeric value in {gene_name!r}: {value!r}"
        )