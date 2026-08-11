"""E12.6.4 — Cross Product Intelligence Models。

核心数据模型:
  ProductProfile:        产品画像
  ProductFeature:        产品特征向量
  ProductCluster:        产品聚类
  UniversalPattern:      通用创意模式
  TransferDecision:      知识迁移决策
  KnowledgeTransfer:     知识迁移记录
  CrossLearningResult:   跨产品学习结果
  SimilarityResult:      相似度结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── ProductFeature ──────────────────────────────────────────


@dataclass
class ProductFeature:
    """产品特征向量。

    用于跨产品相似度计算。

    Attributes:
        product_id:       产品 ID
        genre:           品类（merge/puzzle/simulation/arcade/...）
        monetization:    变现模式（IAA/IAP/Hybrid）
        audience:        目标受众标签
        gameplay_tags:   玩法标签列表
        creative_patterns: 已成功的创意模式列表
        market:          市场（T1/T2/T3）
        performance:     性能指标（ROAS, CTR, etc.）
        metadata:        附加元数据
    """

    product_id: str = ""
    genre: str = ""
    monetization: str = ""
    audience: str = ""
    gameplay_tags: list[str] = field(default_factory=list)
    creative_patterns: list[str] = field(default_factory=list)
    market: str = ""
    performance: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> list[str]:
        """转换为特征向量（用于Jaccard相似度）。"""
        return (
            [self.genre]
            + [self.monetization]
            + [self.audience]
            + self.gameplay_tags
            + self.creative_patterns
            + [self.market]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "genre": self.genre,
            "monetization": self.monetization,
            "audience": self.audience,
            "gameplay_tags": self.gameplay_tags,
            "creative_patterns": self.creative_patterns,
            "market": self.market,
            "performance": self.performance,
        }

    def __repr__(self) -> str:
        return f"ProductFeature(product={self.product_id}, genre={self.genre})"


# ── ProductProfile ──────────────────────────────────────────


@dataclass
class ProductProfile:
    """产品画像。

    包含产品完整特征和成功模式。

    Attributes:
        product_id:           产品 ID
        features:             产品特征
        successful_patterns:  成功模式列表
        performance_summary:  性能摘要
        experiment_count:     实验总数
        winner_count:         winner 数量
        created_at:           创建时间
        updated_at:           更新时间
    """

    product_id: str = ""
    features: ProductFeature = field(default_factory=ProductFeature)
    successful_patterns: list[dict[str, Any]] = field(default_factory=list)
    performance_summary: dict[str, float] = field(default_factory=dict)
    experiment_count: int = 0
    winner_count: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.features.product_id == "":
            self.features.product_id = self.product_id

    @property
    def winner_rate(self) -> float:
        if self.experiment_count <= 0:
            return 0.0
        return self.winner_count / self.experiment_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "features": self.features.to_dict(),
            "successful_patterns": self.successful_patterns,
            "performance_summary": self.performance_summary,
            "experiment_count": self.experiment_count,
            "winner_count": self.winner_count,
            "winner_rate": round(self.winner_rate, 4),
        }

    def __repr__(self) -> str:
        return (
            f"ProductProfile(product={self.product_id}, "
            f"winners={self.winner_count}/{self.experiment_count})"
        )


# ── ProductCluster ──────────────────────────────────────────


@dataclass
class ProductCluster:
    """产品聚类。

    将相似产品分组。

    Attributes:
        cluster_id:     聚类 ID
        products:       产品 ID 列表
        shared_patterns: 共享模式
        avg_similarity: 平均相似度
        centroid:       聚类中心特征
        created_at:     创建时间
    """

    cluster_id: str = ""
    products: list[str] = field(default_factory=list)
    shared_patterns: list[str] = field(default_factory=list)
    avg_similarity: float = 0.0
    centroid: ProductFeature | None = None
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.cluster_id:
            self.cluster_id = _gen_id("CL")

    @property
    def size(self) -> int:
        return len(self.products)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "products": self.products,
            "size": self.size,
            "shared_patterns": self.shared_patterns,
            "avg_similarity": round(self.avg_similarity, 4),
        }

    def __repr__(self) -> str:
        return (
            f"ProductCluster(id={self.cluster_id}, "
            f"products={len(self.products)}, "
            f"similarity={self.avg_similarity:.2f})"
        )


# ── UniversalPattern ────────────────────────────────────────


@dataclass
class UniversalPattern:
    """通用创意模式。

    跨产品共享的创意规律。

    Attributes:
        pattern_id:           模式 ID
        pattern_type:         模式类型（hook/visual/genre/...）
        pattern_name:         模式名称
        source_products:      来源产品列表
        confidence:           置信度 [0, 1]
        performance_gain:     平均性能提升
        applicable_genres:    适用品类
        applicable_markets:   适用市场
        transfer_count:       已迁移次数
        success_count:        成功迁移次数
        created_at:           创建时间
        updated_at:           更新时间
        metadata:             附加元数据
    """

    pattern_id: str = ""
    pattern_type: str = ""
    pattern_name: str = ""
    source_products: list[str] = field(default_factory=list)
    confidence: float = 0.5
    performance_gain: float = 0.0
    applicable_genres: list[str] = field(default_factory=list)
    applicable_markets: list[str] = field(default_factory=list)
    transfer_count: int = 0
    success_count: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pattern_id:
            self.pattern_id = _gen_id("UP")

    @property
    def transfer_success_rate(self) -> float:
        if self.transfer_count <= 0:
            return 0.0
        return self.success_count / self.transfer_count

    @property
    def is_proven(self) -> bool:
        return self.confidence >= 0.70 and self.transfer_count >= 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "pattern_name": self.pattern_name,
            "source_products": self.source_products,
            "confidence": round(self.confidence, 4),
            "performance_gain": round(self.performance_gain, 4),
            "applicable_genres": self.applicable_genres,
            "applicable_markets": self.applicable_markets,
            "transfer_count": self.transfer_count,
            "success_count": self.success_count,
            "transfer_success_rate": round(self.transfer_success_rate, 4),
            "is_proven": self.is_proven,
        }

    def __repr__(self) -> str:
        return (
            f"UniversalPattern(id={self.pattern_id}, "
            f"type={self.pattern_type}, "
            f"confidence={self.confidence:.2f})"
        )


# ── TransferDecision ────────────────────────────────────────


class TransferRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TransferAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"


@dataclass
class TransferDecision:
    """知识迁移决策。

    Attributes:
        decision_id:         决策 ID
        source_product:      来源产品
        target_product:      目标产品
        pattern_id:          模式 ID
        action:              迁移动作
        confidence:          置信度
        risk_level:          风险等级
        similarity_score:    相似度评分
        expected_uplift:     预期性能提升
        mutation_strategy:   突变策略
        reasons:             决策理由
        created_at:          创建时间
    """

    decision_id: str = ""
    source_product: str = ""
    target_product: str = ""
    pattern_id: str = ""
    action: TransferAction = TransferAction.DENY
    confidence: float = 0.0
    risk_level: TransferRisk = TransferRisk.HIGH
    similarity_score: float = 0.0
    expected_uplift: float = 0.0
    mutation_strategy: str = ""
    reasons: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = _gen_id("TD")

    @property
    def is_allowed(self) -> bool:
        return self.action == TransferAction.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.action == TransferAction.DENY

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "source_product": self.source_product,
            "target_product": self.target_product,
            "pattern_id": self.pattern_id,
            "action": self.action.value,
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level.value,
            "similarity_score": round(self.similarity_score, 4),
            "expected_uplift": round(self.expected_uplift, 4),
            "mutation_strategy": self.mutation_strategy,
            "reasons": self.reasons,
            "is_allowed": self.is_allowed,
        }

    def __repr__(self) -> str:
        return (
            f"TransferDecision({self.source_product}→{self.target_product}, "
            f"action={self.action.value}, "
            f"confidence={self.confidence:.2f})"
        )


# ── KnowledgeTransfer ───────────────────────────────────────


@dataclass
class KnowledgeTransfer:
    """知识迁移记录。

    Attributes:
        transfer_id:       迁移 ID
        source_product:    来源产品
        target_product:    目标产品
        pattern_id:        模式 ID
        confidence:        置信度
        expected_uplift:   预期提升
        actual_uplift:     实际提升
        decision:          迁移决策
        created_at:        创建时间
        feedback_at:       反馈时间
        metadata:          附加元数据
    """

    transfer_id: str = ""
    source_product: str = ""
    target_product: str = ""
    pattern_id: str = ""
    confidence: float = 0.0
    expected_uplift: float = 0.0
    actual_uplift: float | None = None
    decision: TransferDecision | None = None
    created_at: datetime = field(default_factory=_now)
    feedback_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transfer_id:
            self.transfer_id = _gen_id("KT")

    @property
    def has_feedback(self) -> bool:
        return self.actual_uplift is not None

    @property
    def is_successful(self) -> bool:
        if self.actual_uplift is None:
            return False
        return self.actual_uplift > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "source_product": self.source_product,
            "target_product": self.target_product,
            "pattern_id": self.pattern_id,
            "confidence": round(self.confidence, 4),
            "expected_uplift": round(self.expected_uplift, 4),
            "actual_uplift": round(self.actual_uplift, 4) if self.actual_uplift is not None else None,
            "has_feedback": self.has_feedback,
            "is_successful": self.is_successful,
        }

    def __repr__(self) -> str:
        return (
            f"KnowledgeTransfer({self.source_product}→{self.target_product}, "
            f"uplift={self.actual_uplift})"
        )


# ── CrossLearningResult ─────────────────────────────────────


@dataclass
class CrossLearningResult:
    """跨产品学习结果。

    Attributes:
        result_id:             结果 ID
        source_products:       来源产品列表
        transferred_patterns:  已迁移模式数
        rejected_patterns:     被拒绝模式数
        confidence_gain:       置信度增益
        recommendations:       建议列表
        transfers:             迁移记录列表
        created_at:            创建时间
    """

    result_id: str = ""
    source_products: list[str] = field(default_factory=list)
    transferred_patterns: int = 0
    rejected_patterns: int = 0
    confidence_gain: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    transfers: list[KnowledgeTransfer] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.result_id:
            self.result_id = _gen_id("CLR")

    @property
    def total_evaluated(self) -> int:
        return self.transferred_patterns + self.rejected_patterns

    @property
    def transfer_rate(self) -> float:
        if self.total_evaluated <= 0:
            return 0.0
        return self.transferred_patterns / self.total_evaluated

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "source_products": self.source_products,
            "transferred_patterns": self.transferred_patterns,
            "rejected_patterns": self.rejected_patterns,
            "total_evaluated": self.total_evaluated,
            "transfer_rate": round(self.transfer_rate, 4),
            "confidence_gain": round(self.confidence_gain, 4),
            "recommendations": self.recommendations,
            "transfer_count": len(self.transfers),
        }

    def __repr__(self) -> str:
        return (
            f"CrossLearningResult(transferred={self.transferred_patterns}, "
            f"rejected={self.rejected_patterns})"
        )


# ── SimilarityResult ────────────────────────────────────────


@dataclass
class SimilarityResult:
    """相似度计算结果。

    Attributes:
        source_product:   来源产品
        target_product:   目标产品
        genre_similarity: 品类相似度
        audience_similarity: 受众相似度
        dna_similarity:   Creative DNA 相似度
        market_similarity: 市场相似度
        total_similarity: 总相似度
    """

    source_product: str = ""
    target_product: str = ""
    genre_similarity: float = 0.0
    audience_similarity: float = 0.0
    dna_similarity: float = 0.0
    market_similarity: float = 0.0
    total_similarity: float = 0.0

    @property
    def is_high_similarity(self) -> bool:
        return self.total_similarity >= 0.70

    @property
    def is_medium_similarity(self) -> bool:
        return 0.40 <= self.total_similarity < 0.70

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_product": self.source_product,
            "target_product": self.target_product,
            "genre_similarity": round(self.genre_similarity, 4),
            "audience_similarity": round(self.audience_similarity, 4),
            "dna_similarity": round(self.dna_similarity, 4),
            "market_similarity": round(self.market_similarity, 4),
            "total_similarity": round(self.total_similarity, 4),
            "is_high_similarity": self.is_high_similarity,
            "is_medium_similarity": self.is_medium_similarity,
        }

    def __repr__(self) -> str:
        return (
            f"SimilarityResult({self.source_product}→{self.target_product}, "
            f"total={self.total_similarity:.2f})"
        )