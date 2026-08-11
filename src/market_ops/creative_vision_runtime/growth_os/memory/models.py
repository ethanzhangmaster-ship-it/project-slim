"""E12.7.5 Growth Memory Models — GrowthExperience, GrowthPattern, MemoryType."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """记忆类型."""
    STRATEGY_MEMORY = "strategy_memory"
    CREATIVE_MEMORY = "creative_memory"
    EXPERIMENT_MEMORY = "experiment_memory"
    MARKET_MEMORY = "market_memory"
    FAILURE_MEMORY = "failure_memory"
    SUCCESS_PATTERN = "success_pattern"


class Outcome(str, Enum):
    """执行结果."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


# ── GrowthExperience ────────────────────────────────────────


@dataclass
class ExperienceContext:
    """经验上下文 — 市场、渠道、生命周期、创意状态."""

    market: str = ""
    channel: str = ""
    lifecycle: str = ""
    creative_state: str = ""
    product_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "channel": self.channel,
            "lifecycle": self.lifecycle,
            "creative_state": self.creative_state,
            "product_id": self.product_id,
            "extra": self.extra,
        }


@dataclass
class ExperienceMetrics:
    """经验指标 — 消耗、收入、ROAS、CTR、CVR、留存."""

    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    retention: float = 0.0
    impressions: int = 0
    installs: int = 0
    extra: dict[str, float] = field(default_factory=dict)

    @property
    def roi(self) -> float:
        if self.spend > 0:
            return (self.revenue - self.spend) / self.spend
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": self.roas,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "retention": self.retention,
            "impressions": self.impressions,
            "installs": self.installs,
            "roi": self.roi,
            "extra": self.extra,
        }


@dataclass
class GrowthExperience:
    """增长经验 — 核心经验单元.

    记录一次执行/实验的完整信息，包括上下文、动作、结果和指标。
    """

    experience_id: str = field(default_factory=lambda: f"EXP_{uuid.uuid4().hex[:8].upper()}")
    product_id: str = ""
    strategy_id: str = ""
    execution_id: str = ""
    memory_type: MemoryType = MemoryType.STRATEGY_MEMORY
    context: ExperienceContext = field(default_factory=ExperienceContext)
    action: dict[str, Any] = field(default_factory=dict)
    result: Outcome = Outcome.PARTIAL
    metrics: ExperienceMetrics = field(default_factory=ExperienceMetrics)
    learning_value: float = 0.0
    confidence: float = 0.5
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_success(self) -> bool:
        return self.result == Outcome.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self.result == Outcome.FAILURE

    @property
    def age_days(self) -> float:
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() / 86400.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "product_id": self.product_id,
            "strategy_id": self.strategy_id,
            "execution_id": self.execution_id,
            "memory_type": self.memory_type.value,
            "context": self.context.to_dict(),
            "action": self.action,
            "result": self.result.value,
            "metrics": self.metrics.to_dict(),
            "learning_value": self.learning_value,
            "confidence": self.confidence,
            "tags": self.tags,
            "summary": self.summary,
            "age_days": self.age_days,
            "is_success": self.is_success,
            "is_failure": self.is_failure,
        }


# ── GrowthPattern ────────────────────────────────────────────


@dataclass
class GrowthPattern:
    """增长模式 — 从大量经验中抽象出的规律.

    例如: "Merge Game + Rescue Hook + Before/After → ROAS 1.42, 成功率 78%"
    """

    pattern_id: str = field(default_factory=lambda: f"PAT_{uuid.uuid4().hex[:8].upper()}")
    pattern_type: MemoryType = MemoryType.SUCCESS_PATTERN
    conditions: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    success_rate: float = 0.0
    avg_roas: float = 0.0
    confidence: float = 0.5
    usage_count: int = 0
    source_experiences: list[str] = field(default_factory=list)
    market: str = ""
    product_id: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.6 and self.usage_count >= 3

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.80

    @property
    def age_days(self) -> float:
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() / 86400.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "conditions": self.conditions,
            "actions": self.actions,
            "success_rate": self.success_rate,
            "avg_roas": self.avg_roas,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "source_experiences": self.source_experiences,
            "market": self.market,
            "product_id": self.product_id,
            "description": self.description,
            "is_reliable": self.is_reliable,
            "is_high_confidence": self.is_high_confidence,
            "age_days": self.age_days,
        }


# ── MemoryQuery & Retrieval ─────────────────────────────────


@dataclass
class MemoryQuery:
    """记忆查询 — 用于检索相关经验."""

    product_id: str = ""
    market: str = ""
    channel: str = ""
    memory_type: MemoryType | None = None
    outcome: Outcome | None = None
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    min_learning_value: float = 0.0
    min_confidence: float = 0.0
    max_age_days: float = 365.0
    limit: int = 10
    sort_by: str = "learning_value"  # learning_value, confidence, created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "market": self.market,
            "channel": self.channel,
            "memory_type": self.memory_type.value if self.memory_type else None,
            "outcome": self.outcome.value if self.outcome else None,
            "tags": self.tags,
            "keywords": self.keywords,
            "min_learning_value": self.min_learning_value,
            "min_confidence": self.min_confidence,
            "max_age_days": self.max_age_days,
            "limit": self.limit,
            "sort_by": self.sort_by,
        }


@dataclass
class RetrievalResult:
    """检索结果."""

    experiences: list[GrowthExperience] = field(default_factory=list)
    patterns: list[GrowthPattern] = field(default_factory=list)
    query: MemoryQuery = field(default_factory=MemoryQuery)
    total_matches: int = 0
    retrieval_time_ms: float = 0.0

    @property
    def has_results(self) -> bool:
        return len(self.experiences) > 0 or len(self.patterns) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiences": [e.to_dict() for e in self.experiences],
            "patterns": [p.to_dict() for p in self.patterns],
            "total_matches": self.total_matches,
            "retrieval_time_ms": self.retrieval_time_ms,
            "has_results": self.has_results,
        }