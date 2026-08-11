"""E12.7.2 — Autonomous Growth Agent Models。

Agent 感知、推理、决策的核心数据模型。

核心模型:
  GrowthObservation:  Agent 感知世界
  RootCause:          根因分析
  GrowthHypothesis:   增长假设
  AgentDecision:      最终决策输出
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


# ── Enums ──────────────────────────────────────────────────


class ObservationSeverity(str, Enum):
    """观察严重程度。"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


_SEVERITY_ORDER: dict[ObservationSeverity, int] = {
    ObservationSeverity.NORMAL: 0,
    ObservationSeverity.WARNING: 1,
    ObservationSeverity.CRITICAL: 2,
    ObservationSeverity.FATAL: 3,
}


def get_severity_order(severity: ObservationSeverity) -> int:
    return _SEVERITY_ORDER.get(severity, 0)


class HypothesisStatus(str, Enum):
    """假设状态。"""
    PROPOSED = "proposed"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ── GrowthObservation ──────────────────────────────────────


@dataclass
class ProductMetrics:
    """产品核心指标。"""

    roas: float = 0.0
    cpi: float = 0.0
    ctr: float = 0.0
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    revenue: float = 0.0
    spend: float = 0.0
    installs: int = 0
    impressions: int = 0

    @property
    def is_roas_healthy(self) -> bool:
        return self.roas >= 1.0

    @property
    def is_spending(self) -> bool:
        return self.spend > 0 and self.installs > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "roas": round(self.roas, 4),
            "cpi": round(self.cpi, 4),
            "ctr": round(self.ctr, 4),
            "retention_d1": round(self.retention_d1, 4),
            "retention_d7": round(self.retention_d7, 4),
            "revenue": round(self.revenue, 2),
            "spend": round(self.spend, 2),
            "installs": self.installs,
            "is_roas_healthy": self.is_roas_healthy,
        }


@dataclass
class CreativeState:
    """创意状态。"""

    fatigue_score: float = 0.0
    diversity_score: float = 0.0
    winner_ratio: float = 0.0
    active_creatives: int = 0
    winning_creatives: int = 0
    total_creatives: int = 0

    @property
    def is_fatigued(self) -> bool:
        return self.fatigue_score >= 0.70

    @property
    def is_highly_fatigued(self) -> bool:
        return self.fatigue_score >= 0.85

    @property
    def is_diverse(self) -> bool:
        return self.diversity_score >= 0.50

    def to_dict(self) -> dict[str, Any]:
        return {
            "fatigue_score": round(self.fatigue_score, 4),
            "diversity_score": round(self.diversity_score, 4),
            "winner_ratio": round(self.winner_ratio, 4),
            "active_creatives": self.active_creatives,
            "winning_creatives": self.winning_creatives,
            "is_fatigued": self.is_fatigued,
            "is_diverse": self.is_diverse,
        }


@dataclass
class MarketState:
    """市场状态。"""

    trend_score: float = 0.5
    competition_score: float = 0.5
    market_size: float = 0.0
    growth_rate: float = 0.0

    @property
    def is_declining(self) -> bool:
        return self.trend_score < 0.30

    @property
    def is_highly_competitive(self) -> bool:
        return self.competition_score >= 0.70

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend_score": round(self.trend_score, 4),
            "competition_score": round(self.competition_score, 4),
            "market_size": round(self.market_size, 2),
            "growth_rate": round(self.growth_rate, 4),
            "is_declining": self.is_declining,
            "is_highly_competitive": self.is_highly_competitive,
        }


@dataclass
class GrowthObservation:
    """增长观察。

    Agent 对产品当前状态的全面感知。

    Attributes:
        observation_id: 观察 ID
        product_id:     产品 ID
        metrics:        核心指标
        creative_state: 创意状态
        market_state:   市场状态
        severity:       严重程度
        signals:        检测到的信号列表
        summary:        观察摘要
        timestamp:      时间戳
        metadata:       附加元数据
    """

    observation_id: str = ""
    product_id: str = ""
    metrics: ProductMetrics = field(default_factory=ProductMetrics)
    creative_state: CreativeState = field(default_factory=CreativeState)
    market_state: MarketState = field(default_factory=MarketState)
    severity: ObservationSeverity = ObservationSeverity.NORMAL
    signals: list[str] = field(default_factory=list)
    summary: str = ""
    timestamp: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id:
            self.observation_id = _gen_id("OBS")

    @property
    def severity_order(self) -> int:
        return get_severity_order(self.severity)

    @property
    def needs_attention(self) -> bool:
        return self.severity in (
            ObservationSeverity.WARNING,
            ObservationSeverity.CRITICAL,
            ObservationSeverity.FATAL,
        )

    @property
    def is_urgent(self) -> bool:
        return self.severity in (
            ObservationSeverity.CRITICAL,
            ObservationSeverity.FATAL,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "product_id": self.product_id,
            "severity": self.severity.value,
            "signals": self.signals,
            "summary": self.summary,
            "needs_attention": self.needs_attention,
            "is_urgent": self.is_urgent,
            "metrics": self.metrics.to_dict(),
            "creative_state": self.creative_state.to_dict(),
            "market_state": self.market_state.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"GrowthObservation(product={self.product_id}, "
            f"severity={self.severity.value}, "
            f"signals={len(self.signals)})"
        )


# ── RootCause ──────────────────────────────────────────────


@dataclass
class RootCause:
    """根因分析结果。

    Attributes:
        cause_id:      根因 ID
        category:      根因类别
        description:   根因描述
        confidence:    置信度 [0, 1]
        evidence:      支撑证据
        severity:      严重程度
        suggested_fix: 建议修复方向
    """

    cause_id: str = ""
    category: str = ""
    description: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    severity: ObservationSeverity = ObservationSeverity.NORMAL
    suggested_fix: str = ""

    def __post_init__(self) -> None:
        if not self.cause_id:
            self.cause_id = _gen_id("RC")

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.80

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < 0.30

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "category": self.category,
            "description": self.description,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "severity": self.severity.value,
            "suggested_fix": self.suggested_fix,
            "is_high_confidence": self.is_high_confidence,
        }

    def __repr__(self) -> str:
        return (
            f"RootCause(category={self.category}, "
            f"confidence={self.confidence:.2f})"
        )


# ── GrowthHypothesis ───────────────────────────────────────


@dataclass
class GrowthHypothesis:
    """增长假设。

    Agent 推理结果：问题 → 原因 → 建议动作。

    Attributes:
        hypothesis_id:      假设 ID
        problem:            发现的问题
        root_cause:         根因
        root_cause_category: 根因类别
        confidence:         置信度 [0, 1]
        expected_impact:    预期影响 [0, 1]
        recommended_actions: 建议动作列表
        rationale:          推理过程说明
        status:             假设状态
        target_module:      目标执行模块
        created_at:         创建时间
        metadata:           附加元数据
    """

    hypothesis_id: str = ""
    problem: str = ""
    root_cause: str = ""
    root_cause_category: str = ""
    confidence: float = 0.0
    expected_impact: float = 0.0
    recommended_actions: list[str] = field(default_factory=list)
    rationale: str = ""
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    target_module: str = ""
    created_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            self.hypothesis_id = _gen_id("HYP")

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.50 and self.expected_impact >= 0.10

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.80

    @property
    def risk_adjusted_impact(self) -> float:
        """风险调整后预期影响。"""
        return self.expected_impact * self.confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "problem": self.problem,
            "root_cause": self.root_cause,
            "root_cause_category": self.root_cause_category,
            "confidence": round(self.confidence, 4),
            "expected_impact": round(self.expected_impact, 4),
            "risk_adjusted_impact": round(self.risk_adjusted_impact, 4),
            "recommended_actions": self.recommended_actions,
            "rationale": self.rationale,
            "status": self.status.value,
            "target_module": self.target_module,
            "is_actionable": self.is_actionable,
        }

    def __repr__(self) -> str:
        return (
            f"GrowthHypothesis(problem={self.problem[:40]}, "
            f"confidence={self.confidence:.2f}, "
            f"impact={self.expected_impact:.2f})"
        )


# ── AgentDecision ──────────────────────────────────────────


@dataclass
class AgentDecision:
    """Agent 决策。

    输出给 Growth Kernel 的最终决策。

    Attributes:
        decision_id:   决策 ID
        product_id:    产品 ID
        action_type:   动作类型
        target_module: 目标模块
        parameters:    动作参数
        confidence:    置信度 [0, 1]
        reasoning:     推理过程
        hypothesis_id: 关联假设 ID
        observation_id: 关联观察 ID
        priority:      优先级
        created_at:    创建时间
        metadata:      附加元数据
    """

    decision_id: str = ""
    product_id: str = ""
    action_type: str = ""
    target_module: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    hypothesis_id: str = ""
    observation_id: str = ""
    priority: int = 0
    created_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = _gen_id("DEC")

    @property
    def is_high_priority(self) -> bool:
        return self.priority >= 80

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.50 and self.action_type != ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "action_type": self.action_type,
            "target_module": self.target_module,
            "parameters": self.parameters,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "hypothesis_id": self.hypothesis_id,
            "observation_id": self.observation_id,
            "priority": self.priority,
            "is_high_priority": self.is_high_priority,
            "is_actionable": self.is_actionable,
        }

    def __repr__(self) -> str:
        return (
            f"AgentDecision(product={self.product_id}, "
            f"action={self.action_type}, "
            f"priority={self.priority})"
        )