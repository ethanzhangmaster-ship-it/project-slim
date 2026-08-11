"""E12.6.3 — Safety Governor Models。

Governance Layer 的核心数据模型。

核心模型:
  SafetyAction:    安全动作枚举
  RiskLevel:       风险等级枚举
  SafetyContext:   安全评估上下文（输入）
  SafetyDecision:  安全决策（输出）
  RiskReport:      风险报告
  RollbackRecord:  回滚记录
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


# ── SafetyAction ────────────────────────────────────────────


class SafetyAction(str, Enum):
    """安全动作类型。

    按严重程度递增：
      ALLOW           → 完全放行
      MODIFY          → 限制后放行
      BLOCK           → 阻止
      ROLLBACK        → 回滚
      REQUIRE_REVIEW  → 需要人工审核
    """

    ALLOW = "allow"
    MODIFY = "modify"
    BLOCK = "block"
    ROLLBACK = "rollback"
    REQUIRE_REVIEW = "require_review"


# 安全动作优先级（数值越大越严格）
_SAFETY_ACTION_PRIORITY: dict[SafetyAction, int] = {
    SafetyAction.ALLOW: 0,
    SafetyAction.MODIFY: 30,
    SafetyAction.REQUIRE_REVIEW: 50,
    SafetyAction.BLOCK: 70,
    SafetyAction.ROLLBACK: 100,
}


def get_safety_action_priority(action: SafetyAction) -> int:
    return _SAFETY_ACTION_PRIORITY.get(action, 0)


# ── RiskLevel ───────────────────────────────────────────────


class RiskLevel(str, Enum):
    """风险等级。

    LOW:      低风险，可以放行
    MEDIUM:   中等风险，需要限制
    HIGH:     高风险，需要阻止
    CRITICAL: 严重风险，需要回滚
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# 风险等级分数阈值
_RISK_THRESHOLDS: dict[RiskLevel, tuple[float, float]] = {
    RiskLevel.LOW: (0.0, 0.25),
    RiskLevel.MEDIUM: (0.25, 0.50),
    RiskLevel.HIGH: (0.50, 0.75),
    RiskLevel.CRITICAL: (0.75, 1.0),
}


def risk_level_from_score(score: float) -> RiskLevel:
    """根据风险分数确定风险等级。"""
    score = max(0.0, min(1.0, score))
    if score < 0.25:
        return RiskLevel.LOW
    elif score < 0.50:
        return RiskLevel.MEDIUM
    elif score < 0.75:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


def get_risk_threshold(level: RiskLevel) -> tuple[float, float]:
    return _RISK_THRESHOLDS.get(level, (0.0, 1.0))


# ── SafetyContext ────────────────────────────────────────────


@dataclass
class SafetyContext:
    """安全评估上下文 —— 待评估的操作及其环境。

    Attributes:
        product_id:                    产品 ID
        action:                        待执行的动作
        predicted_impact:              预测影响
        spend_amount:                  花费金额
        mutation_distance:             突变距离 [0, 1]
        confidence:                    预测置信度 [0, 1]
        knowledge_confidence:          知识置信度 [0, 1]
        population_diversity:          种群多样性 [0, 1]
        historical_winner_similarity:  历史 winner 相似度 [0, 1]
        experiment_count:              实验数量
        daily_budget_limit:            日预算上限
        max_mutation_distance:         最大突变距离限制
        metadata:                      附加元数据
    """

    product_id: str = ""
    action: str = ""
    predicted_impact: float = 0.0
    spend_amount: float = 0.0
    mutation_distance: float = 0.0
    confidence: float = 0.5
    knowledge_confidence: float = 0.5
    population_diversity: float = 0.5
    historical_winner_similarity: float = 0.5
    experiment_count: int = 0
    daily_budget_limit: float = 10000.0
    max_mutation_distance: float = 0.70
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_spend(self) -> bool:
        return self.spend_amount > 5000.0

    @property
    def is_high_mutation(self) -> bool:
        return self.mutation_distance > 0.70

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < 0.50

    @property
    def is_low_knowledge(self) -> bool:
        return self.knowledge_confidence < 0.40

    @property
    def is_winner_divergent(self) -> bool:
        return self.historical_winner_similarity < 0.20

    @property
    def is_population_collapsed(self) -> bool:
        return self.population_diversity < 0.15

    @property
    def has_insufficient_data(self) -> bool:
        return self.experiment_count < 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "action": self.action,
            "predicted_impact": round(self.predicted_impact, 4),
            "spend_amount": round(self.spend_amount, 2),
            "mutation_distance": round(self.mutation_distance, 4),
            "confidence": round(self.confidence, 4),
            "knowledge_confidence": round(self.knowledge_confidence, 4),
            "population_diversity": round(self.population_diversity, 4),
            "historical_winner_similarity": round(self.historical_winner_similarity, 4),
            "experiment_count": self.experiment_count,
            "is_high_spend": self.is_high_spend,
            "is_high_mutation": self.is_high_mutation,
            "is_low_confidence": self.is_low_confidence,
        }

    def __repr__(self) -> str:
        return (
            f"SafetyContext(product={self.product_id}, "
            f"action={self.action}, "
            f"spend={self.spend_amount:.0f}, "
            f"mutation={self.mutation_distance:.2f})"
        )


# ── RiskReport ──────────────────────────────────────────────


@dataclass
class RiskReport:
    """风险报告 —— 风险评估结果。

    Attributes:
        report_id:         报告 ID
        product_id:        产品 ID
        total_score:       总风险评分 [0, 1]
        risk_level:        风险等级
        mutation_risk:     突变风险 [0, 1]
        spend_risk:        花费风险 [0, 1]
        prediction_risk:   预测风险（1 - confidence）
        knowledge_risk:    知识风险（1 - knowledge_confidence）
        diversity_risk:    多样性风险
        created_at:        创建时间
        details:           详细说明
    """

    report_id: str = ""
    product_id: str = ""
    total_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    mutation_risk: float = 0.0
    spend_risk: float = 0.0
    prediction_risk: float = 0.0
    knowledge_risk: float = 0.0
    diversity_risk: float = 0.0
    created_at: datetime = field(default_factory=_now)
    details: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = _gen_id("RR")

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "product_id": self.product_id,
            "total_score": round(self.total_score, 4),
            "risk_level": self.risk_level.value,
            "mutation_risk": round(self.mutation_risk, 4),
            "spend_risk": round(self.spend_risk, 4),
            "prediction_risk": round(self.prediction_risk, 4),
            "knowledge_risk": round(self.knowledge_risk, 4),
            "diversity_risk": round(self.diversity_risk, 4),
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"RiskReport(product={self.product_id}, "
            f"score={self.total_score:.2f}, "
            f"level={self.risk_level.value})"
        )


# ── SafetyDecision ──────────────────────────────────────────


@dataclass
class SafetyDecision:
    """安全决策 —— Safety Governor 核心输出。

    Attributes:
        decision_id:    决策 ID
        product_id:     产品 ID
        action:         安全动作
        risk_level:     风险等级
        score:          风险评分 [0, 1]
        reasons:        决策理由列表
        constraints:    约束条件（MODIFY 时使用）
        created_at:     创建时间
        risk_report:    关联的风险报告
        context_snapshot: 上下文快照
    """

    decision_id: str = ""
    product_id: str = ""
    action: SafetyAction = SafetyAction.ALLOW
    risk_level: RiskLevel = RiskLevel.LOW
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    risk_report: RiskReport | None = None
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = _gen_id("SD")

    @property
    def is_allowed(self) -> bool:
        return self.action == SafetyAction.ALLOW

    @property
    def is_blocked(self) -> bool:
        return self.action in (SafetyAction.BLOCK, SafetyAction.ROLLBACK)

    @property
    def is_modified(self) -> bool:
        return self.action == SafetyAction.MODIFY

    @property
    def needs_review(self) -> bool:
        return self.action == SafetyAction.REQUIRE_REVIEW

    @property
    def is_safe(self) -> bool:
        return self.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    @property
    def action_label(self) -> str:
        labels = {
            SafetyAction.ALLOW: "放行",
            SafetyAction.MODIFY: "限制后放行",
            SafetyAction.BLOCK: "阻止",
            SafetyAction.ROLLBACK: "回滚",
            SafetyAction.REQUIRE_REVIEW: "需要人工审核",
        }
        return labels.get(self.action, self.action.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "action": self.action.value,
            "action_label": self.action_label,
            "risk_level": self.risk_level.value,
            "score": round(self.score, 4),
            "reasons": self.reasons,
            "constraints": self.constraints,
            "created_at": self.created_at.isoformat(),
            "is_allowed": self.is_allowed,
            "is_blocked": self.is_blocked,
            "is_safe": self.is_safe,
            "needs_review": self.needs_review,
        }

    def __repr__(self) -> str:
        return (
            f"SafetyDecision(action={self.action.value}, "
            f"risk={self.risk_level.value}, "
            f"score={self.score:.2f})"
        )


# ── RollbackRecord ──────────────────────────────────────────


@dataclass
class RollbackRecord:
    """回滚记录。

    Attributes:
        record_id:      记录 ID
        product_id:     产品 ID
        target_type:    回滚目标类型（creative/budget/strategy）
        target_id:      回滚目标 ID
        before_state:   回滚前状态
        after_state:    回滚后状态
        reason:         回滚原因
        triggered_by:   触发者
        created_at:     创建时间
        metadata:       附加元数据
    """

    record_id: str = ""
    product_id: str = ""
    target_type: str = ""
    target_id: str = ""
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    triggered_by: str = "safety_governor"
    created_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = _gen_id("RB")

    @property
    def has_changes(self) -> bool:
        return self.before_state != self.after_state

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "product_id": self.product_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "created_at": self.created_at.isoformat(),
            "has_changes": self.has_changes,
        }

    def __repr__(self) -> str:
        return (
            f"RollbackRecord(product={self.product_id}, "
            f"type={self.target_type}, "
            f"reason={self.reason[:30]})"
        )