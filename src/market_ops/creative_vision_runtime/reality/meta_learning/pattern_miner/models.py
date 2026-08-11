"""E12.5.2 — Pattern Mining Models。

从 Experience Memory 中挖掘 Winner Pattern，形成可复用的 Creative Knowledge。

核心模型:
  PatternType:          模式类型（7 种）
  MetaPattern:          元模式（核心输出）
  GeneCluster:          基因聚类
  GeneImpactScore:      基因影响力评分
  ExtractedGene:        从 Experience 中提取的结构化基因
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ── Enums ──────────────────────────────────────────────────


class PatternType(str, Enum):
    """模式类型 —— 对应创意 DNA 的 7 个维度。"""

    HOOK = "hook"
    VISUAL = "visual"
    GAMEPLAY = "gameplay"
    REWARD = "reward"
    AUDIENCE = "audience"
    MARKET = "market"
    PSYCHOLOGY = "psychology"
    FULL_CREATIVE = "full_creative"


# ── ExtractedGene ──────────────────────────────────────────


@dataclass
class ExtractedGene:
    """从 ExperienceRecord 中提取的结构化基因。

    将 mutation.gene_before/gene_after 的原始字符串映射为
    结构化的基因特征（emotion, conflict, character 等）。

    Attributes:
        gene_category:  基因类别
        features:       结构化特征 ({emotion: rescue, conflict: danger, ...})
        raw_value:      原始值（gene_after）
        confidence:     提取置信度
    """

    gene_category: str = ""
    features: dict[str, str] = field(default_factory=dict)
    raw_value: str = ""
    confidence: float = 0.0

    @property
    def feature_key(self) -> str:
        """生成特征键（用于聚类）。"""
        parts = sorted(f"{k}:{v}" for k, v in self.features.items())
        return "|".join(parts) if parts else self.raw_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "features": self.features,
            "raw_value": self.raw_value,
            "feature_key": self.feature_key,
            "confidence": round(self.confidence, 4),
        }

    def __repr__(self) -> str:
        return f"ExtractedGene({self.gene_category}, features={self.features})"


# ── GeneCluster ────────────────────────────────────────────


@dataclass
class GeneCluster:
    """基因聚类 —— 将相似基因值聚合在一起。

    Attributes:
        cluster_id:       聚类 ID
        gene_category:    基因类别
        feature_key:      特征键（聚类标识）
        members:          成员经验 ID 列表
        sample_count:     样本量
        success_count:    成功数
        success_rate:     成功率
        avg_roas_gain:    平均 ROAS 提升
        avg_ctr_gain:     平均 CTR 提升
        avg_cvr_gain:     平均 CVR 提升
        avg_improvement:  平均综合改善
        representative_genes: 代表性基因特征
    """

    cluster_id: str = ""
    gene_category: str = ""
    feature_key: str = ""

    members: list[str] = field(default_factory=list)
    sample_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0

    avg_roas_gain: float = 0.0
    avg_ctr_gain: float = 0.0
    avg_cvr_gain: float = 0.0
    avg_improvement: float = 0.0

    representative_genes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cluster_id:
            self.cluster_id = _gen_id("gc")
        self.sample_count = len(self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "gene_category": self.gene_category,
            "feature_key": self.feature_key,
            "sample_count": self.sample_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_roas_gain": round(self.avg_roas_gain, 4),
            "avg_ctr_gain": round(self.avg_ctr_gain, 4),
            "avg_cvr_gain": round(self.avg_cvr_gain, 4),
            "avg_improvement": round(self.avg_improvement, 4),
            "representative_genes": self.representative_genes,
        }

    def __repr__(self) -> str:
        return (
            f"GeneCluster({self.gene_category}, "
            f"key={self.feature_key[:20]}, "
            f"n={self.sample_count}, "
            f"sr={self.success_rate:.0%})"
        )


# ── MetaPattern ────────────────────────────────────────────


@dataclass
class MetaPattern:
    """元模式 —— 从历史经验中挖掘的 Winner Pattern。

    核心输出：可复用的创意知识，供 E11 Mutation Engine 使用。

    Attributes:
        pattern_id:       模式 ID
        pattern_type:     模式类型
        name:             模式名称
        genes:            基因特征
        sample_count:     样本量
        success_count:    成功数
        success_rate:     成功率
        avg_roas_gain:    平均 ROAS 提升
        avg_ctr_gain:     平均 CTR 提升
        avg_cvr_gain:     平均 CVR 提升
        confidence:       置信度
        markets:          适用市场
        products:         适用产品
        platforms:        适用平台
        evidence:         证据（关联经验 ID 列表）
        gene_impact_scores: 基因影响力评分
        rank_score:       排序评分
        insight:          模式洞察
        recommendation:   推荐策略
    """

    pattern_id: str = ""
    pattern_type: PatternType = PatternType.HOOK
    name: str = ""

    genes: dict[str, str] = field(default_factory=dict)
    sample_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0

    avg_roas_gain: float = 0.0
    avg_ctr_gain: float = 0.0
    avg_cvr_gain: float = 0.0
    confidence: float = 0.0

    markets: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)

    evidence: list[str] = field(default_factory=list)
    gene_impact_scores: dict[str, float] = field(default_factory=dict)
    rank_score: float = 0.0

    insight: str = ""
    recommendation: str = ""

    def __post_init__(self) -> None:
        if not self.pattern_id:
            self.pattern_id = _gen_id("PAT")

    @property
    def is_reliable(self) -> bool:
        """模式是否可靠。"""
        return self.sample_count >= 5 and self.confidence >= 0.60

    @property
    def is_strong(self) -> bool:
        """模式是否强信号。"""
        return self.sample_count >= 20 and self.confidence >= 0.80

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "name": self.name,
            "genes": self.genes,
            "sample_count": self.sample_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_roas_gain": round(self.avg_roas_gain, 4),
            "avg_ctr_gain": round(self.avg_ctr_gain, 4),
            "avg_cvr_gain": round(self.avg_cvr_gain, 4),
            "confidence": round(self.confidence, 4),
            "markets": self.markets,
            "products": self.products,
            "platforms": self.platforms,
            "evidence_count": len(self.evidence),
            "gene_impact_scores": {k: round(v, 4) for k, v in self.gene_impact_scores.items()},
            "rank_score": round(self.rank_score, 4),
            "insight": self.insight,
            "recommendation": self.recommendation,
            "is_reliable": self.is_reliable,
            "is_strong": self.is_strong,
        }

    def to_mutation_prior(self) -> dict[str, Any]:
        """转换为 E11 Mutation Engine 可用的突变先验。

        返回格式与 MutationRequest 兼容，可作为突变策略的优先级输入。
        """
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.name,
            "pattern_type": self.pattern_type.value,
            "priority": round(self.rank_score, 4),
            "confidence": round(self.confidence, 4),
            "success_rate": round(self.success_rate, 4),
            "recommended_genes": self.genes,
            "recommendation": self.recommendation,
            "evidence": {
                "sample_count": self.sample_count,
                "avg_roas_gain": round(self.avg_roas_gain, 4),
                "avg_ctr_gain": round(self.avg_ctr_gain, 4),
                "avg_cvr_gain": round(self.avg_cvr_gain, 4),
            },
        }

    def __repr__(self) -> str:
        return (
            f"MetaPattern({self.name}, "
            f"type={self.pattern_type.value}, "
            f"n={self.sample_count}, "
            f"sr={self.success_rate:.0%}, "
            f"score={self.rank_score:.2f})"
        )


# ── GeneImpactScore ────────────────────────────────────────


@dataclass
class GeneImpactScore:
    """基因影响力评分 —— 量化某个基因特征对结果的影响。

    Attributes:
        gene_category:  基因类别
        gene_feature:   基因特征名
        gene_value:     基因特征值
        impact_score:   影响力分数（-1 到 1，正数表示正向影响）
        sample_count:   样本量
        confidence:     置信度
        correlation:    相关性系数
        lift_pct:       提升百分比
    """

    gene_category: str = ""
    gene_feature: str = ""
    gene_value: str = ""
    impact_score: float = 0.0
    sample_count: int = 0
    confidence: float = 0.0
    correlation: float = 0.0
    lift_pct: float = 0.0

    @property
    def is_positive(self) -> bool:
        return self.impact_score > 0.05

    @property
    def is_negative(self) -> bool:
        return self.impact_score < -0.05

    @property
    def is_significant(self) -> bool:
        return abs(self.impact_score) > 0.10 and self.confidence >= 0.6

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "gene_feature": self.gene_feature,
            "gene_value": self.gene_value,
            "impact_score": round(self.impact_score, 4),
            "sample_count": self.sample_count,
            "confidence": round(self.confidence, 4),
            "correlation": round(self.correlation, 4),
            "lift_pct": round(self.lift_pct, 4),
            "is_positive": self.is_positive,
            "is_negative": self.is_negative,
            "is_significant": self.is_significant,
        }

    def __repr__(self) -> str:
        return (
            f"GeneImpactScore({self.gene_feature}={self.gene_value}, "
            f"impact={self.impact_score:+.3f}, "
            f"n={self.sample_count})"
        )


# ── PatternMiningResult ────────────────────────────────────


@dataclass
class PatternMiningResult:
    """模式挖掘结果 —— Pipeline 完整输出。

    Attributes:
        patterns:         挖掘出的元模式列表
        gene_impacts:     基因影响力评分列表
        total_experiences: 输入经验总数
        clusters_found:   发现的聚类数
        patterns_found:   生成的模式数
        mining_summary:   挖掘摘要
    """

    patterns: list[MetaPattern] = field(default_factory=list)
    gene_impacts: list[GeneImpactScore] = field(default_factory=list)
    total_experiences: int = 0
    clusters_found: int = 0
    patterns_found: int = 0
    mining_summary: str = ""

    def __post_init__(self) -> None:
        self.patterns_found = len(self.patterns)
        if not self.mining_summary:
            self.mining_summary = (
                f"Mined {self.patterns_found} patterns "
                f"from {self.total_experiences} experiences "
                f"({self.clusters_found} clusters)"
            )

    def get_top_patterns(self, n: int = 5) -> list[MetaPattern]:
        """获取 Top N 模式。"""
        sorted_patterns = sorted(self.patterns, key=lambda p: p.rank_score, reverse=True)
        return sorted_patterns[:n]

    def get_positive_impacts(self) -> list[GeneImpactScore]:
        """获取正向基因影响力。"""
        return [g for g in self.gene_impacts if g.is_positive]

    def get_negative_impacts(self) -> list[GeneImpactScore]:
        """获取负向基因影响力。"""
        return [g for g in self.gene_impacts if g.is_negative]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_experiences": self.total_experiences,
            "clusters_found": self.clusters_found,
            "patterns_found": self.patterns_found,
            "mining_summary": self.mining_summary,
            "patterns": [p.to_dict() for p in self.patterns],
            "gene_impacts": [g.to_dict() for g in self.gene_impacts],
            "top_patterns": [p.to_dict() for p in self.get_top_patterns()],
            "positive_impacts": [g.to_dict() for g in self.get_positive_impacts()],
            "negative_impacts": [g.to_dict() for g in self.get_negative_impacts()],
        }

    def __repr__(self) -> str:
        return (
            f"PatternMiningResult(patterns={self.patterns_found}, "
            f"impacts={len(self.gene_impacts)}, "
            f"from={self.total_experiences} experiences)"
        )