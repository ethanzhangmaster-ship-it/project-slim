"""E11.6.3 Attribution Schema — 创意 DNA 归因数据模型。

定义三种核心归因类型：

  CreativeRevenueAttribution  — 一个 Creative 的商业表现
  GeneRevenueImpact           — 某个 DNA 基因对收入的贡献
  GenomeAttributionResult     — Genome 最终价值（含 top_genes）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════
# CreativeRevenueAttribution — Creative 商业表现
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeRevenueAttribution:
    """一个 Creative 的完整商业表现。

    将 Adjust 收入数据聚合到单个 Creative 维度。

    字段：
        creative_id:   素材 ID
        genome_id:     关联的 Genome ID
        total_users:   总用户数
        total_revenue: 总收入
        iap_revenue:   内购收入
        ad_revenue:    广告收入
        payer_count:   付费用户数
        payer_rate:    付费率
        arpu:          ARPU
        d30_ltv:       D30 LTV

    例如：
        CreativeRevenueAttribution(
            creative_id="creative_001",
            genome_id="genome_dragon",
            total_users=10000,
            iap_revenue=25000.0,
            ad_revenue=8000.0,
            d30_ltv=3.3,
        )
    """
    creative_id: str = ""
    genome_id: str = ""
    total_users: int = 0
    total_revenue: float = 0.0
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    payer_count: int = 0
    payer_rate: float = 0.0
    arpu: float = 0.0
    d30_ltv: float = 0.0

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        return self.total_users > 0 and self.creative_id != ""

    @property
    def is_attributed(self) -> bool:
        return self.genome_id != ""

    @property
    def iap_ratio(self) -> float:
        """IAP 收入占比。"""
        if self.total_revenue <= 0:
            return 0.0
        return round(self.iap_revenue / self.total_revenue, 4)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "genome_id": self.genome_id,
            "total_users": self.total_users,
            "total_revenue": self.total_revenue,
            "iap_revenue": self.iap_revenue,
            "ad_revenue": self.ad_revenue,
            "payer_count": self.payer_count,
            "payer_rate": self.payer_rate,
            "arpu": self.arpu,
            "d30_ltv": self.d30_ltv,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeRevenueAttribution:
        return cls(
            creative_id=data.get("creative_id", ""),
            genome_id=data.get("genome_id", ""),
            total_users=data.get("total_users", 0),
            total_revenue=data.get("total_revenue", 0.0),
            iap_revenue=data.get("iap_revenue", 0.0),
            ad_revenue=data.get("ad_revenue", 0.0),
            payer_count=data.get("payer_count", 0),
            payer_rate=data.get("payer_rate", 0.0),
            arpu=data.get("arpu", 0.0),
            d30_ltv=data.get("d30_ltv", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"CreativeRevenueAttribution(creative={self.creative_id!r}, "
            f"genome={self.genome_id!r}, "
            f"users={self.total_users}, "
            f"revenue={self.total_revenue})"
        )


# ═══════════════════════════════════════════════════════════
# GeneRevenueImpact — 基因收入贡献
# ═══════════════════════════════════════════════════════════

@dataclass
class GeneRevenueImpact:
    """某个 DNA 基因值对收入的贡献。

    表示"hook=rescue 这个基因值带来了多少额外收入"。

    字段：
        gene_name:      基因名称 (e.g. "hook", "reward")
        gene_value:     基因值 (e.g. "rescue", "dragon")
        sample_count:   样本数（多少个 creative 使用了该基因值）
        avg_ltv:        平均 D30 LTV
        avg_revenue:    平均收入
        impact_score:   影响评分 (0.0~1.0)

    例如：
        GeneRevenueImpact(
            gene_name="reward",
            gene_value="dragon",
            sample_count=120,
            avg_ltv=4.2,
            impact_score=0.86,
        )
    """
    gene_name: str = ""
    gene_value: str = ""
    sample_count: int = 0
    avg_ltv: float = 0.0
    avg_revenue: float = 0.0
    impact_score: float = 0.0

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def gene_key(self) -> str:
        """基因键名 (e.g. "hook:rescue")。"""
        return f"{self.gene_name}:{self.gene_value}"

    @property
    def is_high_impact(self) -> bool:
        """是否高影响力（impact_score >= 0.7）。"""
        return self.impact_score >= 0.7

    @property
    def is_significant_sample(self) -> bool:
        """样本量是否显著（>= 30）。"""
        return self.sample_count >= 30

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_name": self.gene_name,
            "gene_value": self.gene_value,
            "sample_count": self.sample_count,
            "avg_ltv": self.avg_ltv,
            "avg_revenue": self.avg_revenue,
            "impact_score": self.impact_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeneRevenueImpact:
        return cls(
            gene_name=data.get("gene_name", ""),
            gene_value=data.get("gene_value", ""),
            sample_count=data.get("sample_count", 0),
            avg_ltv=data.get("avg_ltv", 0.0),
            avg_revenue=data.get("avg_revenue", 0.0),
            impact_score=data.get("impact_score", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"GeneRevenueImpact(gene={self.gene_key!r}, "
            f"score={self.impact_score}, "
            f"samples={self.sample_count})"
        )


# ═══════════════════════════════════════════════════════════
# GenomeAttributionResult — Genome 最终价值
# ═══════════════════════════════════════════════════════════

@dataclass
class GenomeAttributionResult:
    """一个 Genome 的完整归因结果。

    汇总该 Genome 下所有 Creative 的商业表现，
    并提取 top_genes（对收入贡献最大的基因）。

    字段：
        genome_id:     Genome ID
        creatives:     关联的 creative_id 列表
        total_users:   总用户数
        total_revenue: 总收入
        iap_revenue:   内购收入
        ad_revenue:    广告收入
        payer_count:   付费用户数
        payer_rate:    付费率
        arpu:          ARPU
        d30_ltv:       D30 LTV
        attribution_score: 归因评分（基于收入规模×效率×付费率，0.0~1.0）
        top_genes:         对收入贡献最大的基因 (list of "gene:value")

    注意：attribution_score 是归因层面的中间评分，
    最终 Fitness 由 E11.6.4 RevenueFitnessCalculator 计算。

    例如：
        GenomeAttributionResult(
            genome_id="dragon_rescue_01",
            creatives=["creative_001", "creative_002"],
            total_revenue=50000.0,
            attribution_score=0.92,
            top_genes=["reward:dragon", "hook:rescue"],
        )
    """
    genome_id: str = ""
    creatives: list[str] = field(default_factory=list)
    total_users: int = 0
    total_revenue: float = 0.0
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    payer_count: int = 0
    payer_rate: float = 0.0
    arpu: float = 0.0
    d30_ltv: float = 0.0
    attribution_score: float = 0.0
    top_genes: list[str] = field(default_factory=list)

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        return self.total_users > 0 and self.genome_id != ""

    @property
    def creative_count(self) -> int:
        return len(self.creatives)

    @property
    def iap_ratio(self) -> float:
        if self.total_revenue <= 0:
            return 0.0
        return round(self.iap_revenue / self.total_revenue, 4)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "creatives": self.creatives,
            "total_users": self.total_users,
            "total_revenue": self.total_revenue,
            "iap_revenue": self.iap_revenue,
            "ad_revenue": self.ad_revenue,
            "payer_count": self.payer_count,
            "payer_rate": self.payer_rate,
            "arpu": self.arpu,
            "d30_ltv": self.d30_ltv,
            "attribution_score": self.attribution_score,
            "top_genes": self.top_genes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomeAttributionResult:
        return cls(
            genome_id=data.get("genome_id", ""),
            creatives=data.get("creatives", []),
            total_users=data.get("total_users", 0),
            total_revenue=data.get("total_revenue", 0.0),
            iap_revenue=data.get("iap_revenue", 0.0),
            ad_revenue=data.get("ad_revenue", 0.0),
            payer_count=data.get("payer_count", 0),
            payer_rate=data.get("payer_rate", 0.0),
            arpu=data.get("arpu", 0.0),
            d30_ltv=data.get("d30_ltv", 0.0),
            attribution_score=data.get("attribution_score", 0.0),
            top_genes=data.get("top_genes", []),
        )

    def __repr__(self) -> str:
        return (
            f"GenomeAttributionResult(genome={self.genome_id!r}, "
            f"creatives={self.creative_count}, "
            f"revenue={self.total_revenue}, "
            f"attr_score={self.attribution_score})"
        )