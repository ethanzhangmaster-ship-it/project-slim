"""E15.3.2 Decision Loop Models — 决策循环数据模型.

定义:
  - CycleState:         决策周期状态
  - EnvironmentState:   环境状态
  - GoalEvaluation:     目标评估
  - DecisionCycle:      决策周期
  - CycleResult:        周期结果
  - CycleSummary:       周期摘要
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


class CycleState(str, Enum):
    """决策周期状态."""
    CREATED = "created"
    OBSERVING = "observing"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    DECIDING = "deciding"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class GoalHealth(str, Enum):
    """目标健康状态."""
    ON_TRACK = "on_track"
    BEHIND = "behind"
    AHEAD = "ahead"
    ACHIEVED = "achieved"
    FAILED = "failed"


class CycleOutcome(str, Enum):
    """周期结果."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    NO_ACTION = "no_action"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════
# Environment State
# ═══════════════════════════════════════════════════════════════


@dataclass
class AnomalySignal:
    """异常信号."""
    metric: str = ""
    current: float = 0.0
    baseline: float = 0.0
    deviation: float = 0.0
    severity: str = "low"  # low/medium/high/critical
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "current": self.current,
            "baseline": self.baseline,
            "deviation": self.deviation,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class TrendSignal:
    """趋势信号."""
    metric: str = ""
    direction: str = "stable"  # up/down/stable
    strength: float = 0.0  # 0.0-1.0
    consecutive_periods: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "strength": self.strength,
            "consecutive_periods": self.consecutive_periods,
        }


@dataclass
class OpportunitySignal:
    """机会信号."""
    name: str = ""
    type: str = ""
    confidence: float = 0.0
    description: str = ""
    impacted_metrics: list[str] = field(default_factory=list)
    estimated_impact: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "confidence": self.confidence,
            "description": self.description,
            "impacted_metrics": self.impacted_metrics,
            "estimated_impact": self.estimated_impact,
        }


@dataclass
class EnvironmentState:
    """环境状态 — 综合环境感知.

    Attributes:
        metrics:       当前指标
        anomalies:     检测到的异常
        trends:        趋势信号
        opportunities: 发现的机会
        risks:         风险因素
        timestamp:     时间戳
    """
    metrics: dict[str, float] = field(default_factory=dict)
    anomalies: list[AnomalySignal] = field(default_factory=list)
    trends: list[TrendSignal] = field(default_factory=list)
    opportunities: list[OpportunitySignal] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "trends": [t.to_dict() for t in self.trends],
            "opportunities": [o.to_dict() for o in self.opportunities],
            "risks": self.risks,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# Goal Evaluation
# ═══════════════════════════════════════════════════════════════


@dataclass
class GoalEvaluation:
    """目标评估结果.

    Attributes:
        goal_id:        目标 ID
        goal_name:      目标名称
        metric:         指标
        target:         目标值
        current:        当前值
        health:         健康状态
        gap:            差距
        urgency:        紧急度
        recommendation: 建议
        progress:       进度 (0.0-1.0)
    """
    goal_id: str = ""
    goal_name: str = ""
    metric: str = ""
    target: float = 0.0
    current: float = 0.0
    health: GoalHealth = GoalHealth.ON_TRACK
    gap: float = 0.0
    urgency: str = "low"
    recommendation: str = ""
    progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_name": self.goal_name,
            "metric": self.metric,
            "target": self.target,
            "current": self.current,
            "health": self.health.value,
            "gap": self.gap,
            "urgency": self.urgency,
            "recommendation": self.recommendation,
            "progress": self.progress,
        }


# ═══════════════════════════════════════════════════════════════
# Decision Cycle
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionCycle:
    """决策周期 — 单次 observe→think→act→learn 周期.

    Attributes:
        cycle_id:           周期 ID
        operator_id:        所属 Operator
        state:              当前状态
        cycle_number:       周期编号
        started_at:         开始时间
        observation:        环境观察
        environment_state:  环境状态
        goal_evaluations:   目标评估
        candidate_actions:  候选动作
        risk_assessments:   风险评估
        selected_action:    选中动作
        execution_result:   执行结果
        reward:             奖励值
        completed_at:       完成时间
        error:              错误信息
        metadata:           扩展元数据
    """
    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operator_id: str = ""
    state: CycleState = CycleState.CREATED
    cycle_number: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    observation: dict[str, Any] = field(default_factory=dict)
    environment_state: EnvironmentState | None = None
    goal_evaluations: list[GoalEvaluation] = field(default_factory=list)
    candidate_actions: list[dict[str, Any]] = field(default_factory=list)
    risk_assessments: list[dict[str, Any]] = field(default_factory=list)
    selected_action: dict[str, Any] = field(default_factory=dict)
    execution_result: dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    completed_at: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def duration_seconds(self) -> float:
        """计算周期耗时."""
        if self.completed_at is None:
            return 0.0
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            return (end - start).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "operator_id": self.operator_id,
            "state": self.state.value,
            "cycle_number": self.cycle_number,
            "started_at": self.started_at,
            "environment_state": self.environment_state.to_dict() if self.environment_state else None,
            "goal_evaluations": [g.to_dict() for g in self.goal_evaluations],
            "candidate_actions": self.candidate_actions,
            "selected_action": self.selected_action,
            "execution_result": self.execution_result,
            "reward": self.reward,
            "completed_at": self.completed_at,
            "error": self.error,
            "duration_seconds": self.duration_seconds(),
        }


# ═══════════════════════════════════════════════════════════════
# Cycle Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class CycleResult:
    """周期结果 — 单个周期的汇总结果.

    Attributes:
        cycle_id:         周期 ID
        cycle_number:     周期编号
        outcome:          结果
        reward:           奖励值
        summary:          摘要
        action_taken:     执行的动作
        metrics_before:   执行前指标
        metrics_after:    执行后指标
        lessons:          经验教训
        duration_seconds: 耗时
        timestamp:        时间戳
    """
    cycle_id: str = ""
    cycle_number: int = 0
    outcome: CycleOutcome = CycleOutcome.NO_ACTION
    reward: float = 0.0
    summary: str = ""
    action_taken: str = ""
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    lessons: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "outcome": self.outcome.value,
            "reward": self.reward,
            "summary": self.summary,
            "action_taken": self.action_taken,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "lessons": self.lessons,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# Cycle Summary
# ═══════════════════════════════════════════════════════════════


@dataclass
class CycleSummary:
    """周期运行摘要 — 多周期汇总.

    Attributes:
        total_cycles:      总周期数
        successful:        成功数
        failed:            失败数
        partial:           部分成功数
        total_reward:      总奖励
        average_reward:    平均奖励
        average_duration:  平均耗时
        last_cycle_at:     最后周期时间
        top_lessons:       主要经验
    """
    total_cycles: int = 0
    successful: int = 0
    failed: int = 0
    partial: int = 0
    total_reward: float = 0.0
    average_reward: float = 0.0
    average_duration: float = 0.0
    last_cycle_at: str | None = None
    top_lessons: list[str] = field(default_factory=list)

    @classmethod
    def from_results(cls, results: list[CycleResult]) -> CycleSummary:
        """从结果列表生成摘要."""
        total = len(results)
        if total == 0:
            return cls()

        successful = sum(1 for r in results if r.outcome == CycleOutcome.SUCCESS)
        failed = sum(1 for r in results if r.outcome == CycleOutcome.FAILURE)
        partial = sum(1 for r in results if r.outcome == CycleOutcome.PARTIAL)
        total_reward = sum(r.reward for r in results)
        avg_duration = sum(r.duration_seconds for r in results) / total

        all_lessons: list[str] = []
        for r in results:
            all_lessons.extend(r.lessons)
        top_lessons = all_lessons[-5:] if all_lessons else []

        return cls(
            total_cycles=total,
            successful=successful,
            failed=failed,
            partial=partial,
            total_reward=round(total_reward, 4),
            average_reward=round(total_reward / total, 4) if total > 0 else 0.0,
            average_duration=round(avg_duration, 4),
            last_cycle_at=results[-1].timestamp if results else None,
            top_lessons=top_lessons,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cycles": self.total_cycles,
            "successful": self.successful,
            "failed": self.failed,
            "partial": self.partial,
            "total_reward": self.total_reward,
            "average_reward": self.average_reward,
            "average_duration": self.average_duration,
            "last_cycle_at": self.last_cycle_at,
            "top_lessons": self.top_lessons,
        }


__all__ = [
    # Enums
    "CycleState",
    "GoalHealth",
    "CycleOutcome",
    # Models
    "AnomalySignal",
    "TrendSignal",
    "OpportunitySignal",
    "EnvironmentState",
    "GoalEvaluation",
    "DecisionCycle",
    "CycleResult",
    "CycleSummary",
]