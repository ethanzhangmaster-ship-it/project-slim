"""E13.7.6 Evaluation Models — 学习有效性评估数据模型.

Day 7.6:
  定义评估学习效果所需的核心数据模型，
  回答: "学习之后，系统真的变聪明了吗？"

核心模型:
  - DecisionQualitySnapshot: 单次决策的质量快照 (before/after learning)
  - LearningImpactMetric: 学习影响力指标
  - LearningEffectiveness: 学习有效性评估聚合
  - ImprovementTrend: 改进趋势 (多周期)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. DecisionQualitySnapshot
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionQualitySnapshot:
    """决策质量快照 — 单次决策的 before/after 质量评估.

    记录每次决策在学习增强前后的质量对比，
    以及实际执行结果，用于计算 learning gain。

    Attributes:
        snapshot_id: 快照唯一标识
        decision_id: 关联的决策 ID
        decision_type: 决策类型 (EXECUTE/TEST/HOLD/BLOCK/ESCALATE)
        strategy_name: 策略名称
        action_type: 动作类型 (increase_budget/refresh_creative/...)
        opportunity_type: 机会类型
        baseline_score: 学习增强前的评分
        baseline_confidence: 学习增强前的置信度
        enhanced_score: 学习增强后的评分 (如果 learning_enhanced)
        enhanced_confidence: 学习增强后的置信度
        learning_enhanced: 是否使用了学习增强
        enhancer_recommendation: 增强器推荐 (approve/reject/...)
        enhancer_confidence: 增强器置信度
        score_adjustment: 评分调整量
        actual_outcome: 实际执行结果 (success/failure/pending)
        actual_reward: 实际奖励值
        created_at: 创建时间
        metadata: 扩展元数据
    """

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    decision_type: str = ""
    strategy_name: str = ""
    action_type: str = ""
    opportunity_type: str = ""
    # Baseline (before learning)
    baseline_score: float = 0.0
    baseline_confidence: float = 0.0
    # Enhanced (after learning)
    enhanced_score: float = 0.0
    enhanced_confidence: float = 0.0
    # Learning influence
    learning_enhanced: bool = False
    enhancer_recommendation: str = ""
    enhancer_confidence: float = 0.0
    score_adjustment: float = 0.0
    # Outcome
    actual_outcome: str = "pending"
    actual_reward: float = 0.0
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_outcome(self) -> bool:
        """是否已有实际结果."""
        return self.actual_outcome != "pending"

    @property
    def is_success(self) -> bool:
        """实际结果是否成功."""
        return self.actual_outcome == "success"

    @property
    def learning_impact(self) -> float:
        """学习影响力: 增强后评分 - 基线评分."""
        if not self.learning_enhanced:
            return 0.0
        return self.enhanced_score - self.baseline_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "strategy_name": self.strategy_name,
            "action_type": self.action_type,
            "opportunity_type": self.opportunity_type,
            "baseline_score": round(self.baseline_score, 4),
            "baseline_confidence": round(self.baseline_confidence, 4),
            "enhanced_score": round(self.enhanced_score, 4),
            "enhanced_confidence": round(self.enhanced_confidence, 4),
            "learning_enhanced": self.learning_enhanced,
            "enhancer_recommendation": self.enhancer_recommendation,
            "enhancer_confidence": round(self.enhancer_confidence, 4),
            "score_adjustment": round(self.score_adjustment, 4),
            "actual_outcome": self.actual_outcome,
            "actual_reward": round(self.actual_reward, 4),
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 2. LearningImpactMetric
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningImpactMetric:
    """学习影响力指标 — 单个维度的 before/after 对比.

    Attributes:
        metric_name: 指标名称
        baseline_value: 基线值 (无学习增强)
        enhanced_value: 增强值 (有学习增强)
        absolute_change: 绝对变化量
        relative_change: 相对变化百分比
        is_improvement: 是否改善
        confidence: 该指标的置信度
    """

    metric_name: str = ""
    baseline_value: float = 0.0
    enhanced_value: float = 0.0
    absolute_change: float = 0.0
    relative_change: float = 0.0
    is_improvement: bool = False
    confidence: float = 0.0

    @property
    def improvement_percentage(self) -> float:
        """改进百分比 (正数=改善)."""
        return self.relative_change * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "baseline_value": round(self.baseline_value, 4),
            "enhanced_value": round(self.enhanced_value, 4),
            "absolute_change": round(self.absolute_change, 4),
            "relative_change": round(self.relative_change, 4),
            "is_improvement": self.is_improvement,
            "confidence": round(self.confidence, 4),
        }


# ═══════════════════════════════════════════════════════════════
# 3. LearningEffectiveness
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningEffectiveness:
    """学习有效性评估 — 整体学习效果的综合评估.

    回答核心问题: "学习之后，决策质量是否提升？"

    Attributes:
        evaluation_id: 评估唯一标识
        total_decisions: 总决策数
        learning_enhanced_count: 使用学习增强的决策数
        baseline_success_rate: 基线成功率 (无学习)
        enhanced_success_rate: 增强成功率 (有学习)
        learning_gain: 学习增益 (enhanced - baseline)
        baseline_avg_confidence: 基线平均置信度
        enhanced_avg_confidence: 增强平均置信度
        baseline_avg_score: 基线平均评分
        enhanced_avg_score: 增强平均评分
        impact_metrics: 各维度影响力指标
        is_effective: 学习是否有效
        effectiveness_score: 有效性评分 [0, 1]
        recommendations: 改进建议
        created_at: 创建时间
        metadata: 扩展元数据
    """

    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_decisions: int = 0
    learning_enhanced_count: int = 0
    # Success rates
    baseline_success_rate: float = 0.0
    enhanced_success_rate: float = 0.0
    learning_gain: float = 0.0
    # Confidence
    baseline_avg_confidence: float = 0.0
    enhanced_avg_confidence: float = 0.0
    # Scores
    baseline_avg_score: float = 0.0
    enhanced_avg_score: float = 0.0
    # Impact
    impact_metrics: list[LearningImpactMetric] = field(default_factory=list)
    # Summary
    is_effective: bool = False
    effectiveness_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def learning_gain_percentage(self) -> float:
        """学习增益百分比."""
        return self.learning_gain * 100

    @property
    def enhancement_rate(self) -> float:
        """学习增强使用率."""
        if self.total_decisions == 0:
            return 0.0
        return self.learning_enhanced_count / self.total_decisions

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "total_decisions": self.total_decisions,
            "learning_enhanced_count": self.learning_enhanced_count,
            "baseline_success_rate": round(self.baseline_success_rate, 4),
            "enhanced_success_rate": round(self.enhanced_success_rate, 4),
            "learning_gain": round(self.learning_gain, 4),
            "baseline_avg_confidence": round(self.baseline_avg_confidence, 4),
            "enhanced_avg_confidence": round(self.enhanced_avg_confidence, 4),
            "baseline_avg_score": round(self.baseline_avg_score, 4),
            "enhanced_avg_score": round(self.enhanced_avg_score, 4),
            "impact_metrics": [m.to_dict() for m in self.impact_metrics],
            "is_effective": self.is_effective,
            "effectiveness_score": round(self.effectiveness_score, 4),
            "recommendations": self.recommendations,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 4. ImprovementTrend
# ═══════════════════════════════════════════════════════════════


@dataclass
class ImprovementTrend:
    """改进趋势 — 多周期学习效果追踪.

    Attributes:
        trend_id: 趋势唯一标识
        periods: 追踪的周期数
        baseline_values: 各周期基线值
        enhanced_values: 各周期增强值
        learning_gains: 各周期学习增益
        trend_direction: 趋势方向 (improving/stable/declining)
        trend_slope: 趋势斜率 (正=改善, 负=恶化)
        avg_gain: 平均增益
        max_gain: 最大增益
        min_gain: 最小增益
        is_improving: 是否持续改善
        reliability: 趋势可靠性 [0, 1]
        summary: 趋势摘要文本
        created_at: 创建时间
        metadata: 扩展元数据
    """

    trend_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    periods: int = 0
    baseline_values: list[float] = field(default_factory=list)
    enhanced_values: list[float] = field(default_factory=list)
    learning_gains: list[float] = field(default_factory=list)
    trend_direction: str = "stable"
    trend_slope: float = 0.0
    avg_gain: float = 0.0
    max_gain: float = 0.0
    min_gain: float = 0.0
    is_improving: bool = False
    reliability: float = 0.0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        """是否有数据."""
        return self.periods > 0 and len(self.learning_gains) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend_id": self.trend_id,
            "periods": self.periods,
            "baseline_values": [round(v, 4) for v in self.baseline_values],
            "enhanced_values": [round(v, 4) for v in self.enhanced_values],
            "learning_gains": [round(v, 4) for v in self.learning_gains],
            "trend_direction": self.trend_direction,
            "trend_slope": round(self.trend_slope, 4),
            "avg_gain": round(self.avg_gain, 4),
            "max_gain": round(self.max_gain, 4),
            "min_gain": round(self.min_gain, 4),
            "is_improving": self.is_improving,
            "reliability": round(self.reliability, 4),
            "summary": self.summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }