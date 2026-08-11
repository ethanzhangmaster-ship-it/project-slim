"""E13.3 Decision Models — Growth Decision Engine 数据模型.

模块:
  - InsightType: 洞察类型枚举
  - ActionType: 决策动作类型枚举
  - DecisionConfidence: 决策置信度
  - GrowthInsight: 增长洞察
  - GrowthOpportunity: 增长机会
  - CreativeRanking: 创意排名
  - BudgetAction: 预算调整
  - DecisionAction: 决策动作
  - DecisionReport: 决策报告
  - DecisionResult: 决策结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class InsightType(str, Enum):
    """洞察类型."""
    WINNER_DISCOVERY = "winner_discovery"
    CREATIVE_FATIGUE = "creative_fatigue"
    ROAS_DROP = "roas_drop"
    SCALE_OPPORTUNITY = "scale_opportunity"
    BUDGET_MISALLOCATION = "budget_misallocation"
    NEW_PATTERN = "new_pattern"
    HYBRID_WINNER = "hybrid_winner"
    RETENTION_SIGNAL = "retention_signal"
    CPI_ALERT = "cpi_alert"
    UNDERPERFORMING = "underperforming"


class ActionType(str, Enum):
    """决策动作类型."""
    SCALE = "scale"
    STOP = "stop"
    PAUSE = "pause"
    MUTATE = "mutate"
    INCREASE_BUDGET = "increase_budget"
    DECREASE_BUDGET = "decrease_budget"
    REDISTRIBUTE_BUDGET = "redistribute_budget"
    LAUNCH_EXPERIMENT = "launch_experiment"
    HOLD = "hold"
    MONITOR = "monitor"
    REPLACE_CREATIVE = "replace_creative"
    DUPLICATE_WINNER = "duplicate_winner"


class DecisionConfidence(str, Enum):
    """决策置信度等级."""
    HIGH = "high"          # >= 0.85
    MEDIUM = "medium"      # >= 0.70
    LOW = "low"            # >= 0.50
    SPECULATIVE = "speculative"  # < 0.50


class OpportunitySeverity(str, Enum):
    """机会严重程度."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ═══════════════════════════════════════════════════════════════
# Growth Insight
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthInsight:
    """增长洞察 — 从 CreativeFitnessVector 分析得出的洞察.

    例如:
      - "D30 ROAS 高于品类均值 40%，属于 Winner"
      - "CTR 连续下降 3 天，素材疲劳"
      - "CPI 低于目标 30%，存在放量空间"
    """
    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    insight_type: InsightType = InsightType.WINNER_DISCOVERY
    creative_id: str = ""
    creative_name: str = ""
    genome_id: str = ""
    product_id: str = ""

    # Core metrics
    reason: str = ""
    confidence: float = 0.0
    severity: OpportunitySeverity = OpportunitySeverity.MEDIUM

    # Supporting data
    metrics: dict[str, float] = field(default_factory=dict)
    benchmark: dict[str, float] = field(default_factory=dict)
    trend: list[float] = field(default_factory=list)

    # Source
    source_vector: Any = None  # CreativeFitnessVector

    # Time
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "genome_id": self.genome_id,
            "product_id": self.product_id,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "severity": self.severity.value,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
            "benchmark": {k: round(v, 4) for k, v in self.benchmark.items()},
            "date": self.date,
            "detected_at": self.detected_at,
        }

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.85

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.70

    @property
    def confidence_level(self) -> DecisionConfidence:
        if self.confidence >= 0.85:
            return DecisionConfidence.HIGH
        elif self.confidence >= 0.70:
            return DecisionConfidence.MEDIUM
        elif self.confidence >= 0.50:
            return DecisionConfidence.LOW
        return DecisionConfidence.SPECULATIVE


# ═══════════════════════════════════════════════════════════════
# Growth Opportunity
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthOpportunity:
    """增长机会 — 可执行的具体增长机会."""
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: ActionType = ActionType.SCALE
    creative_id: str = ""
    creative_name: str = ""
    product_id: str = ""

    # Motivation
    reason: str = ""
    confidence: float = 0.0
    severity: OpportunitySeverity = OpportunitySeverity.MEDIUM

    # Expected impact
    expected_impact: dict[str, float] = field(default_factory=dict)
    budget_multiplier: float = 1.0
    target_budget: float = 0.0
    current_budget: float = 0.0

    # Source insight
    source_insight: GrowthInsight | None = None

    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "action": self.action.value,
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "product_id": self.product_id,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "severity": self.severity.value,
            "expected_impact": {k: round(v, 4) for k, v in self.expected_impact.items()},
            "budget_multiplier": round(self.budget_multiplier, 2),
            "target_budget": round(self.target_budget, 2),
            "current_budget": round(self.current_budget, 2),
        }

    @property
    def is_scale_action(self) -> bool:
        return self.action in {ActionType.SCALE, ActionType.INCREASE_BUDGET}

    @property
    def is_stop_action(self) -> bool:
        return self.action in {ActionType.STOP, ActionType.PAUSE}

    @property
    def is_creative_action(self) -> bool:
        return self.action in {ActionType.MUTATE, ActionType.REPLACE_CREATIVE, ActionType.DUPLICATE_WINNER}


# ═══════════════════════════════════════════════════════════════
# Creative Ranking
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeRanking:
    """创意排名 — 基于 Growth Fitness Score 的统一评分."""
    creative_id: str = ""
    creative_name: str = ""
    genome_id: str = ""
    product_id: str = ""

    # Rank
    rank: int = 0
    total_creatives: int = 0

    # Composite score
    fitness_score: float = 0.0
    roas_score: float = 0.0
    ltv_score: float = 0.0
    retention_score: float = 0.0
    ctr_score: float = 0.0
    revenue_score: float = 0.0
    scale_score: float = 0.0
    confidence_score: float = 0.0

    # Status
    is_winner: bool = False
    is_fatigued: bool = False
    decision_confidence: DecisionConfidence = DecisionConfidence.MEDIUM

    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "genome_id": self.genome_id,
            "product_id": self.product_id,
            "rank": self.rank,
            "total_creatives": self.total_creatives,
            "fitness_score": round(self.fitness_score, 4),
            "roas_score": round(self.roas_score, 4),
            "ltv_score": round(self.ltv_score, 4),
            "retention_score": round(self.retention_score, 4),
            "ctr_score": round(self.ctr_score, 4),
            "revenue_score": round(self.revenue_score, 4),
            "scale_score": round(self.scale_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "is_winner": self.is_winner,
            "is_fatigued": self.is_fatigued,
            "decision_confidence": self.decision_confidence.value,
        }

    @property
    def is_top_performer(self) -> bool:
        return self.rank <= 3 and self.fitness_score >= 0.7

    @property
    def percentile(self) -> float:
        if self.total_creatives <= 1:
            return 100.0
        return round((1 - (self.rank - 1) / (self.total_creatives - 1)) * 100, 1)


# ═══════════════════════════════════════════════════════════════
# Budget Action
# ═══════════════════════════════════════════════════════════════


@dataclass
class BudgetAction:
    """预算调整动作."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    campaign_id: str = ""

    # Budget
    current_budget: float = 0.0
    target_budget: float = 0.0
    budget_delta: float = 0.0
    budget_multiplier: float = 1.0

    # Action
    action: ActionType = ActionType.HOLD
    reason: str = ""
    confidence: float = 0.0

    # Timing
    effective_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "current_budget": round(self.current_budget, 2),
            "target_budget": round(self.target_budget, 2),
            "budget_delta": round(self.budget_delta, 2),
            "budget_multiplier": round(self.budget_multiplier, 2),
            "action": self.action.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
        }

    @property
    def is_increase(self) -> bool:
        return self.budget_delta > 0

    @property
    def is_decrease(self) -> bool:
        return self.budget_delta < 0

    @property
    def delta_percentage(self) -> float:
        if self.current_budget == 0:
            return 0.0
        return round(self.budget_delta / self.current_budget * 100, 1)


# ═══════════════════════════════════════════════════════════════
# Decision Action
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionAction:
    """决策动作 — 最终输出给 E12 Feedback Controller 和 E11 Evolution Engine."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: ActionType = ActionType.HOLD
    creative_id: str = ""
    genome_id: str = ""
    product_id: str = ""

    # Priority
    priority: int = 0
    confidence: float = 0.0
    severity: OpportunitySeverity = OpportunitySeverity.MEDIUM

    # Motivation
    reason: str = ""
    expected_roas_impact: float = 0.0
    expected_revenue_impact: float = 0.0

    # Budget
    budget_action: BudgetAction | None = None

    # Source
    source_insight: GrowthInsight | None = None
    source_opportunity: GrowthOpportunity | None = None

    # Approval
    requires_approval: bool = False
    approval_level: int = 0

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        result = {
            "action_id": self.action_id,
            "action": self.action.value,
            "creative_id": self.creative_id,
            "genome_id": self.genome_id,
            "product_id": self.product_id,
            "priority": self.priority,
            "confidence": round(self.confidence, 2),
            "severity": self.severity.value,
            "reason": self.reason,
            "expected_roas_impact": round(self.expected_roas_impact, 4),
            "expected_revenue_impact": round(self.expected_revenue_impact, 4),
            "requires_approval": self.requires_approval,
            "approval_level": self.approval_level,
        }
        if self.budget_action:
            result["budget_action"] = self.budget_action.to_dict()
        return result

    @property
    def is_autonomous(self) -> bool:
        """Level 0: 完全自主执行."""
        return self.approval_level == 0 and not self.requires_approval

    @property
    def is_level1_approval(self) -> bool:
        """Level 1: 需要人工确认."""
        return self.approval_level == 1

    @property
    def is_level2_approval(self) -> bool:
        """Level 2: 需要人工审批."""
        return self.approval_level == 2


# ═══════════════════════════════════════════════════════════════
# Decision Report
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionReport:
    """决策报告 — Growth Decision Engine 的最终输出."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: str = ""
    product_id: str = ""

    # Summary
    total_creatives_analyzed: int = 0
    total_insights: int = 0
    total_opportunities: int = 0
    total_decisions: int = 0

    # Decisions (sorted by priority)
    decisions: list[DecisionAction] = field(default_factory=list)

    # Rankings
    rankings: list[CreativeRanking] = field(default_factory=list)

    # Insights
    insights: list[GrowthInsight] = field(default_factory=list)

    # Opportunities
    opportunities: list[GrowthOpportunity] = field(default_factory=list)

    # Stats
    winners_count: int = 0
    fatigued_count: int = 0
    scale_actions: int = 0
    stop_actions: int = 0
    mutate_actions: int = 0

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "product_id": self.product_id,
            "summary": {
                "total_creatives_analyzed": self.total_creatives_analyzed,
                "total_insights": self.total_insights,
                "total_opportunities": self.total_opportunities,
                "total_decisions": self.total_decisions,
                "winners_count": self.winners_count,
                "fatigued_count": self.fatigued_count,
                "scale_actions": self.scale_actions,
                "stop_actions": self.stop_actions,
                "mutate_actions": self.mutate_actions,
            },
            "rankings": [r.to_dict() for r in self.rankings[:10]],
            "decisions": [d.to_dict() for d in self.decisions],
            "insights": [i.to_dict() for i in self.insights[:10]],
            "opportunities": [o.to_dict() for o in self.opportunities[:10]],
        }

    @property
    def has_decisions(self) -> bool:
        return len(self.decisions) > 0

    @property
    def top_decision(self) -> DecisionAction | None:
        return self.decisions[0] if self.decisions else None

    @property
    def autonomous_decisions(self) -> list[DecisionAction]:
        return [d for d in self.decisions if d.is_autonomous]

    @property
    def approval_required_decisions(self) -> list[DecisionAction]:
        return [d for d in self.decisions if not d.is_autonomous]

    def get_decisions_by_action(self, action: ActionType) -> list[DecisionAction]:
        return [d for d in self.decisions if d.action == action]

    def get_decisions_by_creative(self, creative_id: str) -> list[DecisionAction]:
        return [d for d in self.decisions if d.creative_id == creative_id]


# ═══════════════════════════════════════════════════════════════
# Decision Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionResult:
    """决策执行结果."""
    action_id: str = ""
    success: bool = False
    error_message: str = ""
    executed_at: str = ""
    result_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "success": self.success,
            "error_message": self.error_message,
            "executed_at": self.executed_at,
            "result_data": self.result_data,
        }