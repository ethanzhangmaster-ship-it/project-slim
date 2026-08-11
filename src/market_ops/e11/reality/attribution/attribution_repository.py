"""E11.6.3 AttributionRepository — 归因结果持久化。

存储和查询 Genome 归因结果，支持历史查询和趋势分析。
"""

from __future__ import annotations

from typing import Any

from .attribution_schema import (
    CreativeRevenueAttribution,
    GeneRevenueImpact,
    GenomeAttributionResult,
)


# ═══════════════════════════════════════════════════════════
# AttributionRepository
# ═══════════════════════════════════════════════════════════

class AttributionRepository:
    """归因结果存储。

    Usage:
        repo = AttributionRepository()
        repo.save_genome_results(results)
        top = repo.get_top_genomes(limit=10)
    """

    def __init__(self) -> None:
        self._genome_results: dict[str, GenomeAttributionResult] = {}
        self._creative_attrs: dict[str, CreativeRevenueAttribution] = {}
        self._gene_impacts: list[GeneRevenueImpact] = []
        self._history: list[dict[str, Any]] = []

    # ── 存储 ──────────────────────────────────────────

    def save_genome_results(
        self,
        results: list[GenomeAttributionResult],
    ) -> None:
        """保存 Genome 归因结果。

        Args:
            results: GenomeAttributionResult 列表
        """
        for result in results:
            self._genome_results[result.genome_id] = result

        self._history.append({
            "action": "save_genome_results",
            "count": len(results),
            "genome_ids": [r.genome_id for r in results],
        })

    def save_creative_attrs(
        self,
        attrs: list[CreativeRevenueAttribution],
    ) -> None:
        """保存 Creative 归因数据。

        Args:
            attrs: CreativeRevenueAttribution 列表
        """
        for attr in attrs:
            self._creative_attrs[attr.creative_id] = attr

        self._history.append({
            "action": "save_creative_attrs",
            "count": len(attrs),
        })

    def save_gene_impacts(
        self,
        impacts: list[GeneRevenueImpact],
    ) -> None:
        """保存基因影响力数据。

        Args:
            impacts: GeneRevenueImpact 列表
        """
        self._gene_impacts = list(impacts)

        self._history.append({
            "action": "save_gene_impacts",
            "count": len(impacts),
        })

    # ── 查询 ──────────────────────────────────────────

    def get_genome_result(self, genome_id: str) -> GenomeAttributionResult | None:
        """获取单个 Genome 的归因结果。"""
        return self._genome_results.get(genome_id)

    def get_top_genomes(
        self,
        limit: int = 10,
        by: str = "total_revenue",
    ) -> list[GenomeAttributionResult]:
        """获取收入最高的 Genome。

        Args:
            limit: 返回数量
            by: 排序字段 (total_revenue, attribution_score, iap_revenue)

        Returns:
            GenomeAttributionResult 列表
        """
        results = list(self._genome_results.values())
        results.sort(key=lambda r: getattr(r, by, 0), reverse=True)
        return results[:limit]

    def get_creative_attr(self, creative_id: str) -> CreativeRevenueAttribution | None:
        """获取单个 Creative 的归因数据。"""
        return self._creative_attrs.get(creative_id)

    def get_gene_impacts(self) -> list[GeneRevenueImpact]:
        """获取所有基因影响力数据。"""
        return list(self._gene_impacts)

    def get_high_impact_genes(
        self,
        min_score: float = 0.5,
    ) -> list[GeneRevenueImpact]:
        """获取高影响力基因。

        Args:
            min_score: 最低 impact_score

        Returns:
            GeneRevenueImpact 列表
        """
        return [
            imp for imp in self._gene_impacts
            if imp.impact_score >= min_score
        ]

    # ── 查询统计 ──────────────────────────────────────

    @property
    def genome_count(self) -> int:
        return len(self._genome_results)

    @property
    def creative_count(self) -> int:
        return len(self._creative_attrs)

    @property
    def gene_impact_count(self) -> int:
        return len(self._gene_impacts)

    @property
    def history_count(self) -> int:
        return len(self._history)

    def clear(self) -> None:
        """清空所有数据。"""
        self._genome_results.clear()
        self._creative_attrs.clear()
        self._gene_impacts.clear()
        self._history.clear()

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_results": {
                gid: r.to_dict() for gid, r in self._genome_results.items()
            },
            "creative_attrs": {
                cid: a.to_dict() for cid, a in self._creative_attrs.items()
            },
            "gene_impacts": [imp.to_dict() for imp in self._gene_impacts],
            "history": self._history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttributionRepository:
        repo = cls()
        for gid, gdata in data.get("genome_results", {}).items():
            repo._genome_results[gid] = GenomeAttributionResult.from_dict(gdata)
        for cid, cdata in data.get("creative_attrs", {}).items():
            repo._creative_attrs[cid] = CreativeRevenueAttribution.from_dict(cdata)
        repo._gene_impacts = [
            GeneRevenueImpact.from_dict(imp)
            for imp in data.get("gene_impacts", [])
        ]
        repo._history = data.get("history", [])
        return repo

    def __repr__(self) -> str:
        return (
            f"AttributionRepository(genomes={self.genome_count}, "
            f"creatives={self.creative_count}, "
            f"impacts={self.gene_impact_count})"
        )