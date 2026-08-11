"""E12.6.1 — Meta Decision Engine Models。

Meta Decision Engine 的核心数据模型。

核心模型:
  MetaDecisionType:  决策类型枚举
  DecisionContext:   决策上下文（输入）
  MetaDecision:      元决策（输出）
  DecisionPriority:  决策优先级（用于排序）
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


class MetaDecisionType(str, Enum):
    """元决策类型。

    优先级从上到下递减（ROLLBACK 最高，WAIT 最低）。
    """

    ROLLBACK = "rollback"
    STOP_EXPERIMENT = "stop_experiment"
    START_EXPERIMENT = "start_experiment"
    START_LEARNING = "start_learning"
    CONTINUE_EVOLUTION = "continue_evolution"
    SCALE_WINNER = "scale_winner"
    WAIT = "wait"


# 决策优先级映射（数值越大优先级越高）
_DECISION_PRIORITY: dict[MetaDecisionType, int] = {
    MetaDecisionType.ROLLBACK: 100,
    MetaDecisionType.STOP_EXPERIMENT: 90,
    MetaDecisionType.START_EXPERIMENT: 80,
    MetaDecisionType.START_LEARNING: 70,
    MetaDecisionType.CONTINUE_EVOLUTION: 60,
    MetaDecisionType.SCALE_WINNER: 50,
    MetaDecisionType.WAIT: 10,
}


def get_decision_priority(action: MetaDecisionType) -> int:
    """获取决策类型的优先级数值。"""
    return _DECISION_PRIORITY.get(action, 0)


# ── DecisionContext ────────────────────────────────────────


@dataclass
class DecisionContext:
    """决策上下文 —— 系统的当前状态快照。

    Attributes:
        product_id:             产品 ID
        active_experiments:     活跃实验数
        recent_roas:            最近 ROAS
        roas_trend:             ROAS 趋势（正=增长，负=下降）
        fatigue_score:          创意疲劳度 [0, 1]
        prediction_confidence:  预测置信度 [0, 1]
        knowledge_confidence:   知识置信度 [0, 1]
        population_diversity:   种群多样性 [0, 1]
        last_learning_time:     上次学习时间
        spend_last_7d:          过去 7 天花费
        mutation_count:         突变次数
        active_cycles:          活跃周期数
        ctr_trend:              CTR 趋势
        roas_drop_pct:          ROAS 下降百分比
        experiment_success_rate: 实验成功率
        budget_remaining:       剩余预算
        market_condition:       市场状态
    """

    product_id: str = ""

    active_experiments: int = 0
    recent_roas: float = 1.0
    roas_trend: float = 0.0
    fatigue_score: float = 0.0
    prediction_confidence: float = 0.0
    knowledge_confidence: float = 0.0
    population_diversity: float = 0.5

    last_learning_time: datetime | None = None
    spend_last_7d: float = 0.0
    mutation_count: int = 0
    active_cycles: int = 0

    ctr_trend: float = 0.0
    roas_drop_pct: float = 0.0
    experiment_success_rate: float = 0.0
    budget_remaining: float = 0.0
    market_condition: str = "stable"

    @property
    def is_fatigued(self) -> bool:
        """是否创意疲劳。"""
        return self.fatigue_score >= 0.80

    @property
    def is_roas_declining(self) -> bool:
        """ROAS 是否在下降。"""
        return self.roas_trend < -0.05

    @property
    def is_roas_growing(self) -> bool:
        """ROAS 是否在增长。"""
        return self.roas_trend > 0.15

    @property
    def has_sufficient_data(self) -> bool:
        """是否有足够数据。"""
        return self.prediction_confidence >= 0.60

    @property
    def is_population_healthy(self) -> bool:
        """种群是否健康。"""
        return self.population_diversity >= 0.30

    @property
    def is_population_degraded(self) -> bool:
        """种群是否退化。"""
        return self.population_diversity < 0.20

    @property
    def is_budget_sufficient(self) -> bool:
        """预算是否充足。"""
        return self.budget_remaining > 0 or self.spend_last_7d > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "active_experiments": self.active_experiments,
            "recent_roas": round(self.recent_roas, 4),
            "roas_trend": round(self.roas_trend, 4),
            "fatigue_score": round(self.fatigue_score, 4),
            "prediction_confidence": round(self.prediction_confidence, 4),
            "knowledge_confidence": round(self.knowledge_confidence, 4),
            "population_diversity": round(self.population_diversity, 4),
            "last_learning_time": self.last_learning_time.isoformat() if self.last_learning_time else None,
            "spend_last_7d": round(self.spend_last_7d, 2),
            "mutation_count": self.mutation_count,
            "is_fatigued": self.is_fatigued,
            "is_roas_declining": self.is_roas_declining,
            "is_population_degraded": self.is_population_degraded,
        }

    def __repr__(self) -> str:
        return (
            f"DecisionContext(product={self.product_id}, "
            f"roas={self.recent_roas:.2f}, "
            f"fatigue={self.fatigue_score:.2f}, "
            f"diversity={self.population_diversity:.2f})"
        )


# ── MetaDecision ───────────────────────────────────────────


@dataclass
class MetaDecision:
    """元决策 —— E12.6.1 核心输出。

    Attributes:
        decision_id:     决策 ID
        product_id:      产品 ID
        action:          决策动作
        confidence:      决策置信度 [0, 1]
        priority:        决策优先级
        reasons:         决策理由列表
        expected_impact: 预期影响
        created_at:      创建时间
        context_snapshot: 上下文快照
        explanation:     决策解释
        suggested_action: 建议行动
        risk_assessment:  风险评估
    """

    decision_id: str = ""
    product_id: str = ""
    action: MetaDecisionType = MetaDecisionType.WAIT
    confidence: float = 0.0
    priority: int = 0
    reasons: list[str] = field(default_factory=list)
    expected_impact: float = 0.0
    created_at: datetime = field(default_factory=_now)
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    suggested_action: str = ""
    risk_assessment: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = _gen_id("MD")
        if self.priority == 0:
            self.priority = get_decision_priority(self.action)

    @property
    def is_actionable(self) -> bool:
        """决策是否可执行。"""
        return self.action != MetaDecisionType.WAIT and self.confidence >= 0.50

    @property
    def is_high_confidence(self) -> bool:
        """决策是否高置信度。"""
        return self.confidence >= 0.80

    @property
    def is_risky(self) -> bool:
        """决策是否高风险。"""
        return self.action in (
            MetaDecisionType.ROLLBACK,
            MetaDecisionType.STOP_EXPERIMENT,
        )

    @property
    def action_label(self) -> str:
        """决策动作的人类可读标签。"""
        labels = {
            MetaDecisionType.ROLLBACK: "回滚实验",
            MetaDecisionType.STOP_EXPERIMENT: "停止实验",
            MetaDecisionType.START_EXPERIMENT: "启动新实验",
            MetaDecisionType.START_LEARNING: "启动学习周期",
            MetaDecisionType.CONTINUE_EVOLUTION: "继续进化",
            MetaDecisionType.SCALE_WINNER: "放大赢家",
            MetaDecisionType.WAIT: "等待更多数据",
        }
        return labels.get(self.action, self.action.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "product_id": self.product_id,
            "action": self.action.value,
            "action_label": self.action_label,
            "confidence": round(self.confidence, 4),
            "priority": self.priority,
            "reasons": self.reasons,
            "expected_impact": round(self.expected_impact, 4),
            "created_at": self.created_at.isoformat(),
            "is_actionable": self.is_actionable,
            "is_high_confidence": self.is_high_confidence,
            "is_risky": self.is_risky,
            "explanation": self.explanation,
            "suggested_action": self.suggested_action,
            "risk_assessment": self.risk_assessment,
        }

    def __repr__(self) -> str:
        return (
            f"MetaDecision(action={self.action.value}, "
            f"conf={self.confidence:.2f}, "
            f"priority={self.priority})"
        )