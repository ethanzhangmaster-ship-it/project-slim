"""E11.6.4 Fitness Calibration Schema — 收入驱动 Fitness 校准数据模型。

定义：

  RevenueFitnessProfile  — 一个 Genome 的真实商业评分
  ROASProfile             — D7/D30/D120 ROAS 数据
  RetentionProfile        — D1/D7/D30 留存数据
  CalibratedFitness       — 合并 Evolution + Revenue Fitness 的最终评分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════
# ROASProfile — ROAS 数据
# ═══════════════════════════════════════════════════════════

@dataclass
class ROASProfile:
    """ROAS 数据（D7 / D30 / D120）。

    字段：
        d7_roas:   D7 ROAS
        d30_roas:  D30 ROAS
        d120_roas: D120 ROAS

    例如：
        ROASProfile(d7_roas=0.3, d30_roas=0.5, d120_roas=1.2)
    """
    d7_roas: float = 0.0
    d30_roas: float = 0.0
    d120_roas: float = 0.0

    @property
    def is_valid(self) -> bool:
        return self.d30_roas > 0.0

    @property
    def is_positive(self) -> bool:
        """ROAS > 1.0 即为正向盈利。"""
        return self.d120_roas > 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "d7_roas": self.d7_roas,
            "d30_roas": self.d30_roas,
            "d120_roas": self.d120_roas,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ROASProfile:
        return cls(
            d7_roas=data.get("d7_roas", 0.0),
            d30_roas=data.get("d30_roas", 0.0),
            d120_roas=data.get("d120_roas", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"ROASProfile(d7={self.d7_roas}, "
            f"d30={self.d30_roas}, "
            f"d120={self.d120_roas})"
        )


# ═══════════════════════════════════════════════════════════
# RetentionProfile — 留存数据
# ═══════════════════════════════════════════════════════════

@dataclass
class RetentionProfile:
    """D1 / D7 / D30 留存率。

    字段：
        d1:  次日留存率
        d7:  7日留存率
        d30: 30日留存率

    例如：
        RetentionProfile(d1=0.45, d7=0.20, d30=0.08)
    """
    d1: float = 0.0
    d7: float = 0.0
    d30: float = 0.0

    @property
    def is_valid(self) -> bool:
        return self.d1 > 0.0

    @property
    def weighted_retention(self) -> float:
        """加权留存：d1×0.3 + d7×0.4 + d30×0.3。"""
        return round(self.d1 * 0.3 + self.d7 * 0.4 + self.d30 * 0.3, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "d1": self.d1,
            "d7": self.d7,
            "d30": self.d30,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetentionProfile:
        return cls(
            d1=data.get("d1", 0.0),
            d7=data.get("d7", 0.0),
            d30=data.get("d30", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"RetentionProfile(d1={self.d1}, "
            f"d7={self.d7}, "
            f"d30={self.d30})"
        )


# ═══════════════════════════════════════════════════════════
# RevenueFitnessProfile — 真实商业评分
# ═══════════════════════════════════════════════════════════

@dataclass
class RevenueFitnessProfile:
    """一个 Genome 的真实商业评分。

    基于 Adjust 等真实收入数据，计算多维度的商业价值。

    字段：
        genome_id:       Genome ID
        creative_score:  创意质量评分（来自 E11 Evolution）
        iap_ltv:         IAP D30 LTV
        ad_ltv:          Ad D30 LTV
        total_ltv:       IAP + Ad 总 LTV
        payer_rate:      付费率
        roi:             ROI
        revenue_fitness: 综合商业适应度评分

    例如：
        RevenueFitnessProfile(
            genome_id="genome_dragon",
            creative_score=85.0,
            iap_ltv=3.2,
            ad_ltv=1.5,
            revenue_fitness=0.91,
        )
    """
    genome_id: str = ""
    creative_score: float = 0.0
    iap_ltv: float = 0.0
    ad_ltv: float = 0.0
    total_ltv: float = 0.0
    payer_rate: float = 0.0
    roi: float = 0.0
    revenue_fitness: float = 0.0

    # 子维度
    revenue_score: float = 0.0
    roas_score: float = 0.0
    retention_score: float = 0.0
    payer_rate_score: float = 0.0

    # 置信度
    confidence: float = 0.0
    sample_size: int = 0

    # ROAS & Retention 明细
    roas: ROASProfile = field(default_factory=ROASProfile)
    retention: RetentionProfile = field(default_factory=RetentionProfile)

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        return self.genome_id != "" and self.sample_size > 0

    @property
    def is_elite(self) -> bool:
        return self.revenue_fitness >= 0.85

    @property
    def is_strong(self) -> bool:
        return self.revenue_fitness >= 0.70

    @property
    def is_weak(self) -> bool:
        return self.revenue_fitness < 0.40

    @property
    def is_cold_start(self) -> bool:
        """是否冷启动（样本量不足）。"""
        return self.sample_size < 100

    def dominant_dimension(self) -> str:
        """返回得分最高的维度名称。"""
        dims = {
            "revenue": self.revenue_score,
            "roas": self.roas_score,
            "retention": self.retention_score,
            "payer_rate": self.payer_rate_score,
        }
        return max(dims, key=dims.get)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "creative_score": self.creative_score,
            "iap_ltv": self.iap_ltv,
            "ad_ltv": self.ad_ltv,
            "total_ltv": self.total_ltv,
            "payer_rate": self.payer_rate,
            "roi": self.roi,
            "revenue_fitness": self.revenue_fitness,
            "revenue_score": self.revenue_score,
            "roas_score": self.roas_score,
            "retention_score": self.retention_score,
            "payer_rate_score": self.payer_rate_score,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "roas": self.roas.to_dict(),
            "retention": self.retention.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevenueFitnessProfile:
        return cls(
            genome_id=data.get("genome_id", ""),
            creative_score=data.get("creative_score", 0.0),
            iap_ltv=data.get("iap_ltv", 0.0),
            ad_ltv=data.get("ad_ltv", 0.0),
            total_ltv=data.get("total_ltv", 0.0),
            payer_rate=data.get("payer_rate", 0.0),
            roi=data.get("roi", 0.0),
            revenue_fitness=data.get("revenue_fitness", 0.0),
            revenue_score=data.get("revenue_score", 0.0),
            roas_score=data.get("roas_score", 0.0),
            retention_score=data.get("retention_score", 0.0),
            payer_rate_score=data.get("payer_rate_score", 0.0),
            confidence=data.get("confidence", 0.0),
            sample_size=data.get("sample_size", 0),
            roas=ROASProfile.from_dict(data.get("roas", {})),
            retention=RetentionProfile.from_dict(data.get("retention", {})),
        )

    def __repr__(self) -> str:
        return (
            f"RevenueFitnessProfile(genome={self.genome_id!r}, "
            f"revenue_fitness={self.revenue_fitness}, "
            f"ltv={self.total_ltv}, "
            f"samples={self.sample_size})"
        )


# ═══════════════════════════════════════════════════════════
# CalibratedFitness — 合并后的最终评分
# ═══════════════════════════════════════════════════════════

@dataclass
class CalibratedFitness:
    """合并 Evolution Fitness + Revenue Fitness 的最终评分。

    公式：
        final_fitness = evolution_weight × evolution_fitness
                      + revenue_weight × revenue_fitness

    默认：
        evolution_weight = 0.6
        revenue_weight   = 0.4

    字段：
        genome_id:            Genome ID
        evolution_fitness:    Evolution 创意质量评分
        revenue_fitness:      Revenue 商业评分
        final_fitness:        合并后的最终评分
        cold_start_adjusted:  是否已应用冷启动调整
        evolution_weight:     Evolution 权重
        revenue_weight:       Revenue 权重

    例如：
        CalibratedFitness(
            genome_id="genome_A",
            evolution_fitness=0.75,
            revenue_fitness=0.40,
            final_fitness=0.61,
        )
    """
    genome_id: str = ""
    evolution_fitness: float = 0.0
    revenue_fitness: float = 0.0
    final_fitness: float = 0.0
    cold_start_adjusted: bool = False
    evolution_weight: float = 0.6
    revenue_weight: float = 0.4
    confidence: float = 0.0
    sample_size: int = 0

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        return self.genome_id != ""

    @property
    def is_elite(self) -> bool:
        return self.final_fitness >= 0.85

    @property
    def is_strong(self) -> bool:
        return self.final_fitness >= 0.70

    @property
    def revenue_contribution(self) -> float:
        """Revenue 评分的贡献度。"""
        if self.final_fitness <= 0:
            return 0.0
        return round(self.revenue_fitness * self.revenue_weight / self.final_fitness, 4)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "evolution_fitness": self.evolution_fitness,
            "revenue_fitness": self.revenue_fitness,
            "final_fitness": self.final_fitness,
            "cold_start_adjusted": self.cold_start_adjusted,
            "evolution_weight": self.evolution_weight,
            "revenue_weight": self.revenue_weight,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibratedFitness:
        return cls(
            genome_id=data.get("genome_id", ""),
            evolution_fitness=data.get("evolution_fitness", 0.0),
            revenue_fitness=data.get("revenue_fitness", 0.0),
            final_fitness=data.get("final_fitness", 0.0),
            cold_start_adjusted=data.get("cold_start_adjusted", False),
            evolution_weight=data.get("evolution_weight", 0.6),
            revenue_weight=data.get("revenue_weight", 0.4),
            confidence=data.get("confidence", 0.0),
            sample_size=data.get("sample_size", 0),
        )

    def __repr__(self) -> str:
        return (
            f"CalibratedFitness(genome={self.genome_id!r}, "
            f"final={self.final_fitness}, "
            f"evol={self.evolution_fitness}, "
            f"rev={self.revenue_fitness})"
        )