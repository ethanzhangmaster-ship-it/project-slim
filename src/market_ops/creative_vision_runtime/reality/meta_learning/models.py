"""E12.5.1 — Meta Learning Experience Models。

将 E12.4 实验结果沉淀为长期经验记忆，支持跨产品、
跨市场、跨生命周期的知识积累。

核心模型:
  ExperienceRecord:    完整实验经验记录（核心存储单元）
  MutationDetail:      突变详情（改了什么基因，前后值）
  ExperimentDetail:    实验详情（基线 vs 赢家指标）
  ContextDetail:       上下文（产品、市场、国家、平台）
  ExperienceResult:    结果（成功/失败 + 原因）
  ExperienceQuery:     查询条件
  ExperienceStats:     聚合统计
  ExperiencePattern:   经验模式（向量化）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums ──────────────────────────────────────────────────


class ExperienceOutcome(str, Enum):
    """经验结果类型。"""

    SUCCESS = "success"           # 突变成功（improvement > 0.15）
    MARGINAL = "marginal"         # 边际改善（0 < improvement ≤ 0.15）
    FAILURE = "failure"           # 突变失败（improvement ≤ 0）
    INCONCLUSIVE = "inconclusive" # 数据不足，无法判断


class GeneCategory(str, Enum):
    """基因类别（7 维 DNA）。"""

    HOOK = "hook"
    VISUAL_STYLE = "visual_style"
    GAMEPLAY = "gameplay"
    MONETIZATION = "monetization"
    AUDIENCE = "audience"
    PSYCHOLOGY = "psychology"
    CONTEXT = "context"


class MutationType(str, Enum):
    """突变类型。"""

    REFRESH_HOOK = "refresh_hook"
    VISUAL_VARIATION = "visual_variation"
    GAMEPLAY_CLARITY = "gameplay_clarity"
    OFFER_CHANGE = "offer_change"
    FULL_REBUILD = "full_rebuild"


# ── Detail Models ─────────────────────────────────────────


@dataclass
class MutationDetail:
    """突变详情——记录改了什么基因、前后值。

    Attributes:
        mutation_type:  突变类型
        changed_genes:  修改的基因列表
        gene_before:    突变前基因值
        gene_after:     突变后基因值
        constraints:    DNA 约束（keep/change）
    """

    mutation_type: MutationType = MutationType.REFRESH_HOOK
    changed_genes: list[str] = field(default_factory=list)
    gene_before: dict[str, str] = field(default_factory=dict)
    gene_after: dict[str, str] = field(default_factory=dict)
    constraints: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_type": self.mutation_type.value,
            "changed_genes": self.changed_genes,
            "gene_before": self.gene_before,
            "gene_after": self.gene_after,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MutationDetail:
        """从 dict 反序列化。"""
        mt = data.get("mutation_type", MutationType.REFRESH_HOOK.value)
        if isinstance(mt, str):
            try:
                mt = MutationType(mt)
            except ValueError:
                mt = MutationType.REFRESH_HOOK
        return cls(
            mutation_type=mt,
            changed_genes=data.get("changed_genes", []),
            gene_before=data.get("gene_before", {}),
            gene_after=data.get("gene_after", {}),
            constraints=data.get("constraints", {}),
        )


@dataclass
class ExperimentDetail:
    """实验详情——基线 vs 赢家指标对比。

    Attributes:
        baseline_metrics:  原始创意指标
        winner_metrics:    赢家变体指标
        improvement:       综合改善幅度
        metrics_delta:     逐指标变化
        winner_id:         赢家变体 ID
        variant_count:     变体总数
        confidence:        评估置信度
    """

    baseline_metrics: dict[str, float] = field(default_factory=dict)
    winner_metrics: dict[str, float] = field(default_factory=dict)
    improvement: float = 0.0
    metrics_delta: dict[str, float] = field(default_factory=dict)
    winner_id: str = ""
    variant_count: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_metrics": self.baseline_metrics,
            "winner_metrics": self.winner_metrics,
            "improvement": round(self.improvement, 4),
            "metrics_delta": {k: round(v, 4) for k, v in self.metrics_delta.items()},
            "winner_id": self.winner_id,
            "variant_count": self.variant_count,
            "confidence": round(self.confidence, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentDetail:
        """从 dict 反序列化。"""
        return cls(
            baseline_metrics=data.get("baseline_metrics", {}),
            winner_metrics=data.get("winner_metrics", {}),
            improvement=data.get("improvement", 0.0),
            metrics_delta=data.get("metrics_delta", {}),
            winner_id=data.get("winner_id", ""),
            variant_count=data.get("variant_count", 0),
            confidence=data.get("confidence", 0.0),
        )


@dataclass
class ContextDetail:
    """上下文详情——记录实验发生的环境。

    Attributes:
        product_id:  产品 ID
        product_name: 产品名称
        market:      市场（US/EU/JP/...）
        country:     国家
        audience:    受众标签
        platform:    平台（facebook/google/tiktok/...）
        campaign_type: 投放类型（IAA/Hybrid/IAP）
        metadata:    额外上下文
    """

    product_id: str = ""
    product_name: str = ""
    market: str = ""
    country: str = ""
    audience: str = ""
    platform: str = "facebook"
    campaign_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def domain_key(self) -> str:
        """生成领域标识键（用于跨域匹配）。"""
        return f"{self.product_id}:{self.market}:{self.platform}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "market": self.market,
            "country": self.country,
            "audience": self.audience,
            "platform": self.platform,
            "campaign_type": self.campaign_type,
            "domain_key": self.domain_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextDetail:
        """从 dict 反序列化。"""
        return cls(
            product_id=data.get("product_id", ""),
            product_name=data.get("product_name", ""),
            market=data.get("market", ""),
            country=data.get("country", ""),
            audience=data.get("audience", ""),
            platform=data.get("platform", "facebook"),
            campaign_type=data.get("campaign_type", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExperienceResult:
    """经验结果——成功/失败 + 原因 + 洞察。

    Attributes:
        outcome:        结果类型
        success:        是否成功
        failure_reason: 失败原因
        insight:        学习洞察
        key_finding:    关键发现
    """

    outcome: ExperienceOutcome = ExperienceOutcome.INCONCLUSIVE
    success: bool = False
    failure_reason: str = ""
    insight: str = ""
    key_finding: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.outcome in (
            ExperienceOutcome.SUCCESS,
            ExperienceOutcome.FAILURE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "insight": self.insight,
            "key_finding": self.key_finding,
            "is_actionable": self.is_actionable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceResult:
        """从 dict 反序列化。"""
        oc = data.get("outcome", ExperienceOutcome.INCONCLUSIVE.value)
        if isinstance(oc, str):
            try:
                oc = ExperienceOutcome(oc)
            except ValueError:
                oc = ExperienceOutcome.INCONCLUSIVE
        return cls(
            outcome=oc,
            success=data.get("success", False),
            failure_reason=data.get("failure_reason", ""),
            insight=data.get("insight", ""),
            key_finding=data.get("key_finding", ""),
        )


# ── Core Model ────────────────────────────────────────────


@dataclass
class ExperienceRecord:
    """长期经验记忆——核心存储单元。

    将 E12.4 的完整实验闭环（Prediction → Mutation → Experiment → Result）
    沉淀为一条结构化经验记录，支持跨产品、跨市场查询。

    Attributes:
        experience_id:   经验 ID
        product_id:      产品 ID
        creative_id:     创意 ID
        genome_id:       基因组 ID
        mutation:        突变详情
        experiment:      实验详情
        context:         上下文
        result:          结果
        related_ids:     关联 ID（prediction_id, mutation_request_id, experiment_id）
        created_at:      创建时间
        metadata:        额外元数据
    """

    experience_id: str = ""
    product_id: str = ""
    creative_id: str = ""
    genome_id: str = ""

    mutation: MutationDetail = field(default_factory=MutationDetail)
    experiment: ExperimentDetail = field(default_factory=ExperimentDetail)
    context: ContextDetail = field(default_factory=ContextDetail)
    result: ExperienceResult = field(default_factory=ExperienceResult)

    related_ids: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.experience_id:
            self.experience_id = f"exp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    # ── Convenience properties ──────────────────────────

    @property
    def mutation_type(self) -> MutationType:
        return self.mutation.mutation_type

    @property
    def improvement(self) -> float:
        return self.experiment.improvement

    @property
    def domain_key(self) -> str:
        return self.context.domain_key

    @property
    def is_success(self) -> bool:
        return self.result.success

    @property
    def changed_genes(self) -> list[str]:
        return self.mutation.changed_genes

    @property
    def winner_id(self) -> str:
        return self.experiment.winner_id

    # ── Serialization ───────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "product_id": self.product_id,
            "creative_id": self.creative_id,
            "genome_id": self.genome_id,
            "mutation": self.mutation.to_dict(),
            "experiment": self.experiment.to_dict(),
            "context": self.context.to_dict(),
            "result": self.result.to_dict(),
            "related_ids": self.related_ids,
            "domain_key": self.domain_key,
            "is_success": self.is_success,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceRecord:
        """从 dict 反序列化 (用于持久化恢复)。

        忽略 to_dict 中的计算字段 (domain_key, is_success)。
        """
        return cls(
            experience_id=data.get("experience_id", ""),
            product_id=data.get("product_id", ""),
            creative_id=data.get("creative_id", ""),
            genome_id=data.get("genome_id", ""),
            mutation=MutationDetail.from_dict(data.get("mutation", {})),
            experiment=ExperimentDetail.from_dict(data.get("experiment", {})),
            context=ContextDetail.from_dict(data.get("context", {})),
            result=ExperienceResult.from_dict(data.get("result", {})),
            related_ids=data.get("related_ids", {}),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"ExperienceRecord({self.product_id}, "
            f"{self.mutation_type.value}, "
            f"improvement={self.improvement:+.2f}, "
            f"outcome={self.result.outcome.value})"
        )


# ── Query & Stats ─────────────────────────────────────────


@dataclass
class ExperienceQuery:
    """经验查询条件。

    Attributes:
        product_id:   产品 ID（精确匹配）
        market:       市场（精确匹配）
        platform:     平台（精确匹配）
        mutation_type: 突变类型（精确匹配）
        outcome:      结果类型（精确匹配）
        changed_gene: 修改的基因（精确匹配）
        min_improvement: 最低改善幅度
        min_confidence: 最低置信度
        min_sample:   最低样本数
        limit:        返回上限
        offset:       偏移量
    """

    product_id: str = ""
    market: str = ""
    platform: str = ""
    mutation_type: MutationType | None = None
    outcome: ExperienceOutcome | None = None
    changed_gene: str = ""
    min_improvement: float = 0.0
    min_confidence: float = 0.0
    min_sample: int = 0
    limit: int = 100
    offset: int = 0

    def matches(self, record: ExperienceRecord) -> bool:
        """检查记录是否匹配查询条件。"""
        if self.product_id and record.product_id != self.product_id:
            return False
        if self.market and record.context.market != self.market:
            return False
        if self.platform and record.context.platform != self.platform:
            return False
        if self.mutation_type and record.mutation.mutation_type != self.mutation_type:
            return False
        if self.outcome and record.result.outcome != self.outcome:
            return False
        if self.changed_gene and self.changed_gene not in record.mutation.changed_genes:
            return False
        if self.min_improvement and record.improvement < self.min_improvement:
            return False
        if self.min_confidence and record.experiment.confidence < self.min_confidence:
            return False
        return True


@dataclass
class ExperienceStats:
    """经验聚合统计。

    Attributes:
        total_records:      总记录数
        success_count:      成功数
        success_rate:       成功率
        mean_improvement:   平均改善幅度
        best_improvement:   最大改善幅度
        by_mutation_type:   按突变类型分组
        by_gene:            按基因分组
        by_outcome:         按结果分组
        top_insights:       最佳洞察
    """

    total_records: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    mean_improvement: float = 0.0
    best_improvement: float = 0.0
    by_mutation_type: dict[str, int] = field(default_factory=dict)
    by_gene: dict[str, int] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)
    top_insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "mean_improvement": round(self.mean_improvement, 4),
            "best_improvement": round(self.best_improvement, 4),
            "by_mutation_type": self.by_mutation_type,
            "by_gene": self.by_gene,
            "by_outcome": self.by_outcome,
            "top_insights": self.top_insights,
        }

    def __repr__(self) -> str:
        return (
            f"ExperienceStats(total={self.total_records}, "
            f"success_rate={self.success_rate:.0%}, "
            f"mean_improvement={self.mean_improvement:+.2f})"
        )


# ── Pattern Model ─────────────────────────────────────────


@dataclass
class ExperiencePattern:
    """经验模式——从多条记录中提取的规律。

    Attributes:
        pattern_id:    模式 ID
        pattern_type:  模式类型（gene_pattern/mutation_pattern/context_pattern）
        description:   模式描述
        genes:         涉及的基因
        success_rate:  成功率
        avg_improvement: 平均改善
        sample_size:   样本量
        evidence:      证据（关联的经验 ID 列表）
        confidence:    模式置信度
    """

    pattern_id: str = ""
    pattern_type: str = ""
    description: str = ""
    genes: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    avg_improvement: float = 0.0
    sample_size: int = 0
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.pattern_id:
            self.pattern_id = f"pat_{uuid.uuid4().hex[:12]}"

    @property
    def is_reliable(self) -> bool:
        return self.sample_size >= 3 and self.confidence >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "genes": self.genes,
            "success_rate": round(self.success_rate, 4),
            "avg_improvement": round(self.avg_improvement, 4),
            "sample_size": self.sample_size,
            "evidence_count": len(self.evidence),
            "confidence": round(self.confidence, 4),
            "is_reliable": self.is_reliable,
        }

    def __repr__(self) -> str:
        return (
            f"ExperiencePattern({self.pattern_type}, "
            f"success_rate={self.success_rate:.0%}, "
            f"n={self.sample_size})"
        )