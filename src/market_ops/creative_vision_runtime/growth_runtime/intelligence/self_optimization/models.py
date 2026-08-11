"""E15.3.4 Self Optimization Models — 自我优化数据模型.

定义:
  - MetricSeverity:     指标严重程度
  - OptimizationArea:   优化领域
  - OptimizationMetric: 系统性能指标
  - OptimizationOpportunity: 优化机会
  - OptimizationAction: 优化动作
  - OptimizationResult:  优化结果
  - StrategyPerformance: 策略性能
  - SystemDiagnosis:     系统诊断
  - OptimizationPolicy:  优化策略配置
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


class MetricSeverity(str, Enum):
    """指标严重程度."""
    CRITICAL = "critical"
    WARNING = "warning"
    NORMAL = "normal"
    GOOD = "good"


class OptimizationArea(str, Enum):
    """优化领域."""
    DECISION_ACCURACY = "decision_accuracy"
    EXECUTION_SUCCESS = "execution_success"
    RISK_ENGINE = "risk_engine"
    ACTION_SELECTION = "action_selection"
    REASONING = "reasoning"
    MEMORY = "memory"
    LEARNING = "learning"
    PLANNING = "planning"
    WORKFLOW = "workflow"


class OptimizationStatus(str, Enum):
    """优化动作状态."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    REVERTED = "reverted"
    EVALUATED = "evaluated"


class TrendDirection(str, Enum):
    """趋势方向."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# OptimizationMetric
# ═══════════════════════════════════════════════════════════════


@dataclass
class OptimizationMetric:
    """系统性能指标 — 监控 Operator 自身表现.

    Attributes:
        metric_name:   指标名称
        current_value: 当前值
        target_value:  目标值
        baseline_value: 基线值
        trend:         趋势方向
        severity:      严重程度
        history:       历史数据点
        source:        数据来源
        updated_at:    更新时间
    """
    metric_name: str = ""
    current_value: float = 0.0
    target_value: float = 0.0
    baseline_value: float = 0.0
    trend: TrendDirection = TrendDirection.UNKNOWN
    severity: MetricSeverity = MetricSeverity.NORMAL
    history: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def gap(self) -> float:
        """计算与目标的差距."""
        if self.target_value == self.baseline_value:
            return 0.0
        return (self.target_value - self.current_value) / (self.target_value - self.baseline_value)

    def is_degraded(self) -> bool:
        """是否已退化."""
        return self.trend == TrendDirection.DECLINING and self.severity in (
            MetricSeverity.CRITICAL, MetricSeverity.WARNING
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "baseline_value": self.baseline_value,
            "trend": self.trend.value,
            "severity": self.severity.value,
            "gap": self.gap(),
            "source": self.source,
            "updated_at": self.updated_at,
        }


# ═══════════════════════════════════════════════════════════════
# OptimizationOpportunity
# ═══════════════════════════════════════════════════════════════


@dataclass
class OptimizationOpportunity:
    """优化机会 — 系统发现的改进空间.

    Attributes:
        opportunity_id:   机会 ID
        area:             优化领域
        problem:          问题描述
        evidence:         证据列表
        expected_gain:    预期收益
        confidence:       置信度
        suggested_change: 建议变更
        priority:         优先级
        created_at:       创建时间
    """
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    area: OptimizationArea = OptimizationArea.DECISION_ACCURACY
    problem: str = ""
    evidence: list[str] = field(default_factory=list)
    expected_gain: float = 0.0
    confidence: float = 0.0
    suggested_change: str = ""
    priority: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_actionable(self) -> bool:
        """是否可执行."""
        return self.confidence >= 0.6 and self.expected_gain > 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "area": self.area.value,
            "problem": self.problem,
            "evidence": self.evidence,
            "expected_gain": self.expected_gain,
            "confidence": self.confidence,
            "suggested_change": self.suggested_change,
            "priority": self.priority,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# OptimizationAction
# ═══════════════════════════════════════════════════════════════


@dataclass
class OptimizationAction:
    """优化动作 — 具体的参数调整.

    Attributes:
        action_id:     动作 ID
        opportunity_id: 关联机会 ID
        area:          优化领域
        parameter:     参数名
        old_value:     旧值
        new_value:     新值
        reason:        调整原因
        risk_level:    风险等级
        status:        状态
        applied_at:    应用时间
        metadata:      扩展元数据
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str = ""
    area: OptimizationArea = OptimizationArea.DECISION_ACCURACY
    parameter: str = ""
    old_value: Any = None
    new_value: Any = None
    reason: str = ""
    risk_level: str = "low"
    status: OptimizationStatus = OptimizationStatus.PROPOSED
    applied_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "opportunity_id": self.opportunity_id,
            "area": self.area.value,
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "applied_at": self.applied_at,
        }


# ═══════════════════════════════════════════════════════════════
# OptimizationResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class OptimizationResult:
    """优化结果 — 优化动作应用后的效果评估.

    Attributes:
        result_id:      结果 ID
        action_id:      关联动作 ID
        area:           优化领域
        parameter:      参数名
        old_value:      旧值
        new_value:      新值
        before_metric:  优化前指标值
        after_metric:   优化后指标值
        improvement:    改进幅度
        is_successful:  是否成功
        observation:    观察结论
        evaluated_at:   评估时间
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    area: OptimizationArea = OptimizationArea.DECISION_ACCURACY
    parameter: str = ""
    old_value: Any = None
    new_value: Any = None
    before_metric: float = 0.0
    after_metric: float = 0.0
    improvement: float = 0.0
    is_successful: bool = False
    observation: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "area": self.area.value,
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "before_metric": self.before_metric,
            "after_metric": self.after_metric,
            "improvement": self.improvement,
            "is_successful": self.is_successful,
            "observation": self.observation,
            "evaluated_at": self.evaluated_at,
        }


# ═══════════════════════════════════════════════════════════════
# StrategyPerformance
# ═══════════════════════════════════════════════════════════════


@dataclass
class StrategyPerformance:
    """策略性能 — 评估某个策略/动作类型的长期效果.

    Attributes:
        strategy_name:  策略名称
        total_attempts: 总尝试次数
        success_count:  成功次数
        success_rate:   成功率
        avg_reward:     平均收益
        recent_trend:   近期趋势
        degraded:       是否退化
        degradation_rate: 退化速度
        evaluated_at:   评估时间
    """
    strategy_name: str = ""
    total_attempts: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    recent_trend: TrendDirection = TrendDirection.UNKNOWN
    degraded: bool = False
    degradation_rate: float = 0.0
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_attempts": self.total_attempts,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
            "avg_reward": self.avg_reward,
            "recent_trend": self.recent_trend.value,
            "degraded": self.degraded,
            "degradation_rate": self.degradation_rate,
            "evaluated_at": self.evaluated_at,
        }


# ═══════════════════════════════════════════════════════════════
# SystemDiagnosis
# ═══════════════════════════════════════════════════════════════


@dataclass
class SystemDiagnosis:
    """系统诊断 — 对 Operator 自身运行状况的诊断.

    Attributes:
        diagnosis_id:   诊断 ID
        observations:   观察发现
        hypotheses:     假设列表
        root_causes:    根因列表
        confidence:     诊断置信度
        recommendations: 建议列表
        severity:       严重程度
        created_at:     创建时间
    """
    diagnosis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    observations: list[str] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    severity: MetricSeverity = MetricSeverity.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "observations": self.observations,
            "hypotheses": self.hypotheses,
            "root_causes": self.root_causes,
            "confidence": self.confidence,
            "recommendations": self.recommendations,
            "severity": self.severity.value,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# OptimizationPolicy
# ═══════════════════════════════════════════════════════════════


@dataclass
class OptimizationPolicy:
    """优化策略配置 — 控制 SelfOptimizer 行为的参数.

    Attributes:
        min_confidence:         最小置信度阈值
        max_risk_level:         最大允许风险等级
        cooldown_cycles:        同一参数冷却周期
        max_actions_per_cycle:  每周期最大优化动作数
        evaluation_window:      评估窗口大小
        degradation_threshold:  退化检测阈值
        metric_targets:         各指标目标值
    """
    min_confidence: float = 0.6
    max_risk_level: str = "medium"
    cooldown_cycles: int = 3
    max_actions_per_cycle: int = 5
    evaluation_window: int = 30
    degradation_threshold: float = 0.15
    metric_targets: dict[str, float] = field(default_factory=lambda: {
        "decision_accuracy": 0.85,
        "execution_success_rate": 0.90,
        "reasoning_confidence": 0.80,
        "memory_hit_rate": 0.70,
        "strategy_success_rate": 0.75,
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_confidence": self.min_confidence,
            "max_risk_level": self.max_risk_level,
            "cooldown_cycles": self.cooldown_cycles,
            "max_actions_per_cycle": self.max_actions_per_cycle,
            "evaluation_window": self.evaluation_window,
            "degradation_threshold": self.degradation_threshold,
            "metric_targets": self.metric_targets,
        }


__all__ = [
    # Enums
    "MetricSeverity",
    "OptimizationArea",
    "OptimizationStatus",
    "TrendDirection",
    # Models
    "OptimizationMetric",
    "OptimizationOpportunity",
    "OptimizationAction",
    "OptimizationResult",
    "StrategyPerformance",
    "SystemDiagnosis",
    "OptimizationPolicy",
]