"""E11.6.3 DNA Revenue Analyzer — Winner DNA Pattern 检测。

从大量 Creative + Revenue + DNA 数据中，发现高收入基因模式。

核心能力：
  1. 基因收入影响分析 (GeneRevenueImpact)
  2. Winner DNA 检测 (top N genes by impact)
  3. 基因榜单 (Gene Lift: 该基因值 vs 全局平均的提升倍数)
  4. 样本置信度 (小样本 vs 大样本区分)

公式：
  impact_score = revenue_lift × confidence × sample_factor
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .attribution_schema import (
    CreativeRevenueAttribution,
    GeneRevenueImpact,
    GenomeAttributionResult,
)


# ═══════════════════════════════════════════════════════════
# DNARevenueAnalyzer
# ═══════════════════════════════════════════════════════════

class DNARevenueAnalyzer:
    """DNA 收入分析器。

    从 Creative 归因数据中提取 Winner DNA Pattern。

    Usage:
        analyzer = DNARevenueAnalyzer()
        impacts = analyzer.analyze_gene_impact(creative_attrs, dna_map)
        winners = analyzer.detect_winner_genes(impacts, top_k=5)
    """

    def __init__(
        self,
        min_sample_size: int = 10,
        max_sample_factor: int = 1000,
    ) -> None:
        self._min_sample_size = min_sample_size
        self._max_sample_factor = max_sample_factor

    # ── 主入口 ────────────────────────────────────────

    def analyze_gene_impact(
        self,
        creative_attrs: list[CreativeRevenueAttribution],
        dna_map: dict[str, dict[str, str]],
    ) -> list[GeneRevenueImpact]:
        """分析每个基因值对收入的影响。

        Args:
            creative_attrs: CreativeRevenueAttribution 列表
            dna_map: {creative_id: {gene_name: gene_value, ...}}

        Returns:
            GeneRevenueImpact 列表（按 impact_score 降序）
        """
        if not creative_attrs or not dna_map:
            return []

        # 1. 计算全局平均 LTV
        valid_attrs = [a for a in creative_attrs if a.is_valid]
        if not valid_attrs:
            return []

        global_avg_ltv = sum(a.d30_ltv for a in valid_attrs) / len(valid_attrs)
        global_avg_revenue = sum(a.total_revenue for a in valid_attrs) / len(valid_attrs)

        # 2. 按基因值分组
        gene_groups: dict[str, list[CreativeRevenueAttribution]] = defaultdict(list)
        for attr in valid_attrs:
            cid = attr.creative_id
            if cid not in dna_map:
                continue
            for gene_name, gene_value in dna_map[cid].items():
                key = f"{gene_name}:{gene_value}"
                gene_groups[key].append(attr)

        # 3. 计算每个基因值的 impact_score
        impacts: list[GeneRevenueImpact] = []
        for gene_key, attrs in gene_groups.items():
            gene_name, gene_value = gene_key.split(":", 1)
            sample_count = len(attrs)

            avg_ltv = sum(a.d30_ltv for a in attrs) / sample_count
            avg_revenue = sum(a.total_revenue for a in attrs) / sample_count

            # 计算 lift
            ltv_lift = self._calc_lift(avg_ltv, global_avg_ltv)
            revenue_lift = self._calc_lift(avg_revenue, global_avg_revenue)

            # 综合 lift
            combined_lift = ltv_lift * 0.6 + revenue_lift * 0.4

            # 置信度
            confidence = self._calc_confidence(sample_count)

            # 样本量因子
            sample_factor = self._calc_sample_factor(sample_count)

            # impact_score = lift × confidence × sample_factor
            impact_score = round(
                min(combined_lift * confidence * sample_factor, 1.0),
                4,
            )

            impacts.append(GeneRevenueImpact(
                gene_name=gene_name,
                gene_value=gene_value,
                sample_count=sample_count,
                avg_ltv=round(avg_ltv, 2),
                avg_revenue=round(avg_revenue, 2),
                impact_score=impact_score,
            ))

        impacts.sort(key=lambda x: x.impact_score, reverse=True)
        return impacts

    def detect_winner_genes(
        self,
        impacts: list[GeneRevenueImpact],
        top_k: int = 5,
        min_impact: float = 0.3,
    ) -> list[GeneRevenueImpact]:
        """检测 Winner DNA 基因（高影响力且样本量显著）。

        Args:
            impacts: GeneRevenueImpact 列表
            top_k: 返回前 N 个
            min_impact: 最低 impact_score 阈值

        Returns:
            Winner GeneRevenueImpact 列表
        """
        # 筛选高影响力且样本量显著的
        candidates = [
            imp for imp in impacts
            if imp.impact_score >= min_impact and imp.is_significant_sample
        ]
        return candidates[:top_k]

    def get_gene_lift_table(
        self,
        impacts: list[GeneRevenueImpact],
    ) -> list[dict[str, Any]]:
        """生成基因提升量表。

        Args:
            impacts: GeneRevenueImpact 列表

        Returns:
            [{"gene": "hook:rescue", "lift": 2.5, "impact": 0.86, "samples": 120}, ...]
        """
        return [
            {
                "gene": imp.gene_key,
                "impact": imp.impact_score,
                "samples": imp.sample_count,
                "avg_ltv": imp.avg_ltv,
                "avg_revenue": imp.avg_revenue,
                "is_high_impact": imp.is_high_impact,
            }
            for imp in impacts
        ]

    def enrich_genome_results(
        self,
        results: list[GenomeAttributionResult],
        dna_map: dict[str, dict[str, str]],
        gene_impacts: list[GeneRevenueImpact] | None = None,
    ) -> list[GenomeAttributionResult]:
        """用 Top Genes 丰富 GenomeAttributionResult。

        Args:
            results: GenomeAttributionResult 列表
            dna_map: {creative_id: {gene_name: gene_value, ...}}
            gene_impacts: 预计算的基因影响力（可选）

        Returns:
            丰富后的 GenomeAttributionResult 列表
        """
        if gene_impacts is None:
            # 从 dna_map 中提取基因频率
            gene_impacts = self._extract_impacts_from_dna(results, dna_map)

        # 构建 impact 查找表
        impact_map: dict[str, dict[str, GeneRevenueImpact]] = {}
        for imp in gene_impacts:
            if imp.gene_name not in impact_map:
                impact_map[imp.gene_name] = {}
            impact_map[imp.gene_name][imp.gene_value] = imp

        for result in results:
            top_genes = self._find_top_genes_for_genome(
                result, dna_map, impact_map,
            )
            result.top_genes = top_genes

        return results

    # ── 内部计算 ──────────────────────────────────────

    @staticmethod
    def _calc_lift(value: float, baseline: float) -> float:
        """计算提升倍数。

        Args:
            value: 基因值组的平均值
            baseline: 全局平均值

        Returns:
            lift (>= 0.0)
        """
        if baseline <= 0:
            return 1.0
        lift = value / baseline
        return max(lift, 0.0)

    def _calc_confidence(self, sample_count: int) -> float:
        """计算样本置信度。

        使用简化的 Wilson score 近似：
          confidence = 1 - 1 / (1 + sample_count)

        Args:
            sample_count: 样本数

        Returns:
            confidence (0.0~1.0)
        """
        if sample_count <= 0:
            return 0.0
        return round(1.0 - 1.0 / (1.0 + sample_count), 4)

    def _calc_sample_factor(self, sample_count: int) -> float:
        """计算样本量因子。

        使用 sigmoid 函数平滑过渡：
          小样本 → 低权重
          大样本 → 趋近 1.0

        Args:
            sample_count: 样本数

        Returns:
            sample_factor (0.0~1.0)
        """
        if sample_count <= 0:
            return 0.0
        k = sample_count / self._max_sample_factor
        return round(1.0 / (1.0 + math.exp(-5 * (k - 0.1))), 4)

    def _extract_impacts_from_dna(
        self,
        results: list[GenomeAttributionResult],
        dna_map: dict[str, dict[str, str]],
    ) -> list[GeneRevenueImpact]:
        """从 Genome 结果和 DNA 映射中提取基因影响力。"""
        # 统计每个基因值出现的 creative 数
        gene_counts: dict[str, int] = defaultdict(int)
        gene_revenues: dict[str, float] = defaultdict(float)
        gene_ltvs: dict[str, float] = defaultdict(float)

        for result in results:
            for cid in result.creatives:
                if cid not in dna_map:
                    continue
                for gene_name, gene_value in dna_map[cid].items():
                    key = f"{gene_name}:{gene_value}"
                    gene_counts[key] += 1
                    gene_revenues[key] += result.total_revenue / max(result.creative_count, 1)
                    gene_ltvs[key] += result.d30_ltv / max(result.creative_count, 1)

        impacts: list[GeneRevenueImpact] = []
        for key, count in gene_counts.items():
            gene_name, gene_value = key.split(":", 1)
            impacts.append(GeneRevenueImpact(
                gene_name=gene_name,
                gene_value=gene_value,
                sample_count=count,
                avg_ltv=round(gene_ltvs[key] / count, 2),
                avg_revenue=round(gene_revenues[key] / count, 2),
                impact_score=round(min(count / 100.0, 1.0), 4),
            ))

        return impacts

    def _find_top_genes_for_genome(
        self,
        result: GenomeAttributionResult,
        dna_map: dict[str, dict[str, str]],
        impact_map: dict[str, dict[str, GeneRevenueImpact]],
    ) -> list[str]:
        """为 Genome 找到 top_genes。"""
        gene_scores: dict[str, float] = defaultdict(float)

        for cid in result.creatives:
            if cid not in dna_map:
                continue
            for gene_name, gene_value in dna_map[cid].items():
                gene_key = f"{gene_name}:{gene_value}"
                if gene_name in impact_map and gene_value in impact_map[gene_name]:
                    gene_scores[gene_key] = impact_map[gene_name][gene_value].impact_score
                else:
                    gene_scores[gene_key] = 0.5

        # 按分数排序
        sorted_genes = sorted(
            gene_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [gene for gene, _ in sorted_genes[:5]]

    def __repr__(self) -> str:
        return (
            f"DNARevenueAnalyzer(min_samples={self._min_sample_size}, "
            f"max_factor={self._max_sample_factor})"
        )