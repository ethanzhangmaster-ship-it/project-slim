"""E11.5.3 Fitness Engine — 真实市场适应度引擎。

将 MarketSignal 转换为 GenomeFitness，并驱动 Genome 的
适应度更新和排名。

核心能力：
  - evaluate: MarketSignal → GenomeFitness
  - update_genome: 更新 Genome.fitness 为真实市场评分
  - rank_genomes: 按适应度排名
  - history: 追踪适应度历史

数据流：
  MarketSignal → FitnessEngine.evaluate() → GenomeFitness
  GenomeFitness → FitnessEngine.update_genome() → CreativeGenome.fitness
  [Genome...] → FitnessEngine.rank_genomes() → sorted [Genome...]
"""

from __future__ import annotations

from typing import Any

from ..genome.schema import CreativeGenome
from .market_signal_schema import MarketSignal
from .fitness_schema import GenomeFitness, FitnessHistory, FitnessHistoryEntry
from .fitness_calculator import FitnessCalculator


class FitnessEngine:
    """真实市场适应度引擎。

    将 MarketSignal 转换为 GenomeFitness，驱动 Genome 进化。

    Usage:
        engine = FitnessEngine()
        fitness = engine.evaluate(signal)
        engine.update_genome(genome, fitness)
        ranked = engine.rank_genomes([genome_a, genome_b])
    """

    def __init__(
        self,
        calculator: FitnessCalculator | None = None,
    ) -> None:
        """初始化。

        Args:
            calculator: FitnessCalculator（默认创建新实例）
        """
        self._calculator = calculator or FitnessCalculator()
        self._histories: dict[str, FitnessHistory] = {}

    @property
    def calculator(self) -> FitnessCalculator:
        return self._calculator

    # ── 评估 ──────────────────────────────────────────

    def evaluate(self, signal: MarketSignal) -> GenomeFitness:
        """评估 MarketSignal 生成 GenomeFitness。

        Args:
            signal: MarketSignal 实例

        Returns:
            GenomeFitness
        """
        return self._calculator.calculate(signal)

    def evaluate_batch(
        self,
        signals: list[MarketSignal],
    ) -> list[GenomeFitness]:
        """批量评估。

        Args:
            signals: MarketSignal 列表

        Returns:
            GenomeFitness 列表
        """
        return self._calculator.calculate_batch(signals)

    # ── Genome 更新 ───────────────────────────────────

    def update_genome(
        self,
        genome: CreativeGenome,
        fitness: GenomeFitness,
    ) -> CreativeGenome:
        """更新 Genome 的适应度为真实市场评分。

        将 genome.fitness 替换为真实商业结果驱动的评分。

        Args:
            genome: CreativeGenome 实例
            fitness: GenomeFitness 实例

        Returns:
            更新后的 CreativeGenome
        """
        # 更新 fitness 数据
        genome.fitness = {
            "fitness_score": fitness.fitness_score,
            "monetization_score": fitness.monetization_score,
            "retention_score": fitness.retention_score,
            "acquisition_score": fitness.acquisition_score,
            "ltv_score": fitness.ltv_score,
            "confidence": fitness.confidence,
            "sample_size": fitness.sample_size,
            "source": "real_market",  # 标记为真实市场数据
        }

        # 更新基因强度（映射 fitness 到基因槽位）
        genome.genes = self._update_gene_strengths(genome, fitness)

        return genome

    def _update_gene_strengths(
        self,
        genome: CreativeGenome,
        fitness: GenomeFitness,
    ) -> dict[str, Any]:
        """根据 fitness 更新基因强度。

        Args:
            genome: 当前 Genome
            fitness: 适应度评分

        Returns:
            更新后的 genes 字典
        """
        genes = dict(genome.genes)

        # 映射 fitness 维度到基因槽位
        gene_mapping = {
            "hook": fitness.acquisition_score,
            "visual": fitness.acquisition_score,
            "reward": fitness.monetization_score,
            "emotion": fitness.retention_score,
            "gameplay": fitness.retention_score,
        }

        for gene_name, score in gene_mapping.items():
            if gene_name in genes:
                gene_data = genes[gene_name]
                if isinstance(gene_data, dict):
                    gene_data["strength"] = score
                    gene_data["fitness_source"] = "real_market"
                else:
                    genes[gene_name] = {
                        "type": gene_data,
                        "strength": score,
                        "fitness_source": "real_market",
                    }

        return genes

    # ── 排名 ──────────────────────────────────────────

    def rank_genomes(
        self,
        genomes: list[CreativeGenome],
    ) -> list[CreativeGenome]:
        """按适应度排名 Genome。

        Args:
            genomes: CreativeGenome 列表

        Returns:
            按 fitness_score 降序排列的列表
        """
        return sorted(
            genomes,
            key=lambda g: self._extract_fitness_score(g),
            reverse=True,
        )

    def get_top_genomes(
        self,
        genomes: list[CreativeGenome],
        top_n: int = 5,
    ) -> list[CreativeGenome]:
        """获取 Top N 精英 Genome。

        Args:
            genomes: CreativeGenome 列表
            top_n: 返回数量

        Returns:
            Top N 列表
        """
        ranked = self.rank_genomes(genomes)
        return ranked[:top_n]

    def _extract_fitness_score(self, genome: CreativeGenome) -> float:
        """从 Genome 提取适应度评分。

        Args:
            genome: CreativeGenome

        Returns:
            fitness_score
        """
        if isinstance(genome.fitness, dict):
            return genome.fitness.get("fitness_score", 0.0)
        return 0.0

    # ── 历史 ──────────────────────────────────────────

    def record_fitness(
        self,
        genome: CreativeGenome,
        fitness: GenomeFitness,
        date: str = "",
    ) -> FitnessHistory:
        """记录一次适应度评估。

        Args:
            genome: CreativeGenome
            fitness: GenomeFitness
            date: 日期

        Returns:
            更新后的 FitnessHistory
        """
        history = self._get_or_create_history(genome.genome_id)
        history.add_from_fitness(fitness, date=date)
        return history

    def get_history(self, genome_id: str) -> FitnessHistory | None:
        """获取 Genome 的适应度历史。"""
        return self._histories.get(genome_id)

    def _get_or_create_history(self, genome_id: str) -> FitnessHistory:
        """获取或创建 FitnessHistory。"""
        if genome_id not in self._histories:
            self._histories[genome_id] = FitnessHistory(genome_id=genome_id)
        return self._histories[genome_id]

    def get_all_histories(self) -> dict[str, FitnessHistory]:
        """获取所有历史记录。"""
        return dict(self._histories)

    def get_declining_genomes(self) -> list[str]:
        """获取衰退中的 Genome ID 列表。"""
        return [
            gid for gid, h in self._histories.items()
            if h.is_declining()
        ]

    def get_improving_genomes(self) -> list[str]:
        """获取改善中的 Genome ID 列表。"""
        return [
            gid for gid, h in self._histories.items()
            if h.is_improving()
        ]

    def clear_histories(self) -> None:
        """清空所有历史。"""
        self._histories.clear()

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            gid: h.to_dict()
            for gid, h in self._histories.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessEngine:
        engine = cls()
        for gid, h_data in data.items():
            engine._histories[gid] = FitnessHistory.from_dict(h_data)
        return engine

    def __repr__(self) -> str:
        return (
            f"FitnessEngine(histories={len(self._histories)})"
        )