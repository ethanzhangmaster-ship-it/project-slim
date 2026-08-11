"""E11.2 Mutation Strategy — 变异策略基类与上下文。

StrategyContext — 封装 Genome 当前状态，供策略决策
MutationStrategy — 抽象基类，定义策略接口

数据流：
  StrategyContext → MutationStrategy.evaluate() → MutationRule
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .mutation_schema import MutationRule


# ═══════════════════════════════════════════════════════════
# StrategyContext — 策略决策上下文
# ═══════════════════════════════════════════════════════════

@dataclass
class StrategyContext:
    """封装 Genome 当前状态，供策略层决策。

    字段：
      genome_id: 目标 Genome ID
      fitness: 性能指标 {ctr, cpi, roas_d7, ...}
      weak_genes: 弱基因列表（需要增强或替换）
      strong_genes: 强基因列表（需要保护）
      gene_details: 各基因的详细信息 {gene_name: {value, confidence, ...}}
    """
    genome_id: str = ""
    fitness: dict[str, float] = field(default_factory=dict)
    weak_genes: list[str] = field(default_factory=list)
    strong_genes: list[str] = field(default_factory=list)
    gene_details: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "fitness": self.fitness,
            "weak_genes": self.weak_genes,
            "strong_genes": self.strong_genes,
            "gene_details": self.gene_details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyContext:
        return cls(
            genome_id=data.get("genome_id", ""),
            fitness=data.get("fitness", {}),
            weak_genes=data.get("weak_genes", []),
            strong_genes=data.get("strong_genes", []),
            gene_details=data.get("gene_details", {}),
        )

    @classmethod
    def from_genome(
        cls,
        genome_id: str,
        fitness: dict[str, float],
        genes: dict[str, dict[str, Any]],
        weak_threshold: float = 0.5,
        strong_threshold: float = 0.8,
    ) -> StrategyContext:
        """从 Genome 数据构建 StrategyContext。

        自动计算 weak_genes 和 strong_genes：
          - weak_genes: 基因中数值型字段 < weak_threshold 的槽位
          - strong_genes: 基因中数值型字段 >= strong_threshold 的槽位

        Args:
            genome_id: Genome ID
            fitness: 性能指标
            genes: 基因槽位字典
            weak_threshold: 弱基因判定阈值
            strong_threshold: 强基因判定阈值
        """
        weak: list[str] = []
        strong: list[str] = []

        for gene_name, gene_data in genes.items():
            if not gene_data:
                weak.append(gene_name)
                continue
            # 取基因中数值型字段的最大值作为强度指标
            numeric_vals = [v for v in gene_data.values() if isinstance(v, (int, float))]
            if numeric_vals:
                max_val = max(numeric_vals)
                if max_val >= strong_threshold:
                    strong.append(gene_name)
                elif max_val < weak_threshold:
                    weak.append(gene_name)

        return cls(
            genome_id=genome_id,
            fitness=fitness,
            weak_genes=weak,
            strong_genes=strong,
            gene_details=genes,
        )


# ═══════════════════════════════════════════════════════════
# MutationStrategy — 抽象策略基类
# ═══════════════════════════════════════════════════════════

class MutationStrategy(ABC):
    """变异策略抽象基类。

    每个具体策略实现 evaluate(context) → MutationRule。
    策略是 deterministic 的：相同 context → 相同 rule。
    """

    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> MutationRule | None:
        """评估上下文，返回变异规则。

        Args:
            context: 当前 Genome 状态

        Returns:
            MutationRule（如果不需要变异则返回 None）
        """
        ...

    def __repr__(self) -> str:
        return f"{self.name}()"