"""E15.3.3 Goal Management Models — 目标管理数据模型.

定义:
  - GoalType:         目标类型
  - GoalStatus:       目标状态
  - GoalPriority:     目标优先级
  - Goal:             业务目标
  - SubGoal:          子目标
  - GoalProgress:     目标进度
  - GoalResult:       目标结果
  - GoalAdaptation:   目标调整记录
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


class GoalType(str, Enum):
    """目标类型."""
    OPTIMIZATION = "optimization"       # 优化现有指标
    GROWTH = "growth"                   # 增长目标
    RISK_MITIGATION = "risk_mitigation" # 风险缓解
    EXPLORATION = "exploration"         # 探索性目标
    MAINTENANCE = "maintenance"         # 维持目标


class GoalStatus(str, Enum):
    """目标生命周期状态."""
    CREATED = "created"
    ACTIVE = "active"
    ACHIEVED = "achieved"
    FAILED = "failed"
    PAUSED = "paused"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class GoalPriority(int, Enum):
    """目标优先级 (1=最高, 5=最低)."""
    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4
    P5 = 5


class SubGoalStrategy(str, Enum):
    """子目标执行策略."""
    CREATIVE_EVOLUTION = "creative_evolution"
    BUDGET_OPTIMIZATION = "budget_optimization"
    AUDIENCE_EXPANSION = "audience_expansion"
    BID_OPTIMIZATION = "bid_optimization"
    PRICING_OPTIMIZATION = "pricing_optimization"
    RETENTION_IMPROVEMENT = "retention_improvement"
    MONETIZATION_OPTIMIZATION = "monetization_optimization"
    CPI_REDUCTION = "cpi_reduction"
    CUSTOM = "custom"


class ProgressTrend(str, Enum):
    """进度趋势."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Goal
# ═══════════════════════════════════════════════════════════════


@dataclass
class Goal:
    """业务目标 — 最高层级的运营目标.

    Attributes:
        goal_id:        目标唯一标识
        name:           目标名称
        description:    目标描述
        type:           目标类型
        metric:         核心指标
        current_value:  当前值
        target_value:   目标值
        baseline_value: 基线值 (起始值)
        direction:      方向 ("above"=高于目标, "below"=低于目标)
        priority:       优先级
        status:         生命周期状态
        deadline:       截止时间 (ISO 8601)
        tags:           标签
        parent_goal:    父目标 ID (None=顶层目标)
        created_at:     创建时间
        updated_at:     更新时间
        metadata:       扩展元数据
    """
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    type: GoalType = GoalType.OPTIMIZATION
    metric: str = ""
    current_value: float = 0.0
    target_value: float = 0.0
    baseline_value: float = 0.0
    direction: str = "above"  # above=高于目标值, below=低于目标值
    priority: GoalPriority = GoalPriority.P3
    status: GoalStatus = GoalStatus.CREATED
    deadline: str = ""
    tags: list[str] = field(default_factory=list)
    parent_goal: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE

    def is_achieved(self) -> bool:
        if self.direction == "above":
            return self.current_value >= self.target_value
        return self.current_value <= self.target_value

    def is_expired(self) -> bool:
        if not self.deadline:
            return False
        return datetime.now(timezone.utc).isoformat() > self.deadline

    def gap(self) -> float:
        """计算差距 (归一化)."""
        if self.target_value == self.baseline_value:
            return 0.0
        if self.direction == "above":
            return (self.target_value - self.current_value) / (self.target_value - self.baseline_value)
        return (self.current_value - self.target_value) / (self.baseline_value - self.target_value)

    def progress(self) -> float:
        """计算进度 [0, 1]."""
        if self.target_value == self.baseline_value:
            return 0.0
        if self.direction == "above":
            p = (self.current_value - self.baseline_value) / (self.target_value - self.baseline_value)
        else:
            p = (self.baseline_value - self.current_value) / (self.baseline_value - self.target_value)
        return round(min(1.0, max(0.0, p)), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "metric": self.metric,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "baseline_value": self.baseline_value,
            "direction": self.direction,
            "priority": self.priority.value,
            "status": self.status.value,
            "deadline": self.deadline,
            "tags": self.tags,
            "parent_goal": self.parent_goal,
            "progress": self.progress(),
            "gap": self.gap(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ═══════════════════════════════════════════════════════════════
# SubGoal
# ═══════════════════════════════════════════════════════════════


@dataclass
class SubGoal:
    """子目标 — 将高层目标拆解为可执行的子目标.

    Attributes:
        subgoal_id:      子目标唯一标识
        parent_goal_id:  父目标 ID
        objective:       子目标描述
        metric:          指标
        current_value:   当前值
        target:          目标值
        baseline:        基线值
        direction:       方向
        strategy:        执行策略
        status:          状态
        priority:        优先级
        progress:        进度 [0, 1]
        created_at:      创建时间
        metadata:        扩展元数据
    """
    subgoal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_goal_id: str = ""
    objective: str = ""
    metric: str = ""
    current_value: float = 0.0
    target: float = 0.0
    baseline: float = 0.0
    direction: str = "above"
    strategy: SubGoalStrategy = SubGoalStrategy.CUSTOM
    status: GoalStatus = GoalStatus.CREATED
    priority: GoalPriority = GoalPriority.P3
    progress: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_progress(self, current: float) -> None:
        """更新进度."""
        self.current_value = current
        if self.target == self.baseline:
            self.progress = 0.0
        elif self.direction == "above":
            self.progress = round(min(1.0, max(0.0, (current - self.baseline) / (self.target - self.baseline))), 4)
        else:
            self.progress = round(min(1.0, max(0.0, (self.baseline - current) / (self.baseline - self.target))), 4)

    def is_achieved(self) -> bool:
        if self.direction == "above":
            return self.current_value >= self.target
        return self.current_value <= self.target

    def to_dict(self) -> dict[str, Any]:
        return {
            "subgoal_id": self.subgoal_id,
            "parent_goal_id": self.parent_goal_id,
            "objective": self.objective,
            "metric": self.metric,
            "current_value": self.current_value,
            "target": self.target,
            "baseline": self.baseline,
            "direction": self.direction,
            "strategy": self.strategy.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
        }


# ═══════════════════════════════════════════════════════════════
# GoalProgress
# ═══════════════════════════════════════════════════════════════


@dataclass
class GoalProgress:
    """目标进度 — 追踪目标的实时进度.

    Attributes:
        goal_id:        目标 ID
        progress:       进度 [0, 1]
        current_value:  当前值
        target_value:   目标值
        baseline_value: 基线值
        remaining_gap:  剩余差距
        trend:          进度趋势
        trend_data:     历史数据点 (用于趋势计算)
        estimated_completion: 预计完成时间
        updated_at:     更新时间
    """
    goal_id: str = ""
    progress: float = 0.0
    current_value: float = 0.0
    target_value: float = 0.0
    baseline_value: float = 0.0
    remaining_gap: float = 0.0
    trend: ProgressTrend = ProgressTrend.UNKNOWN
    trend_data: list[dict[str, Any]] = field(default_factory=list)
    estimated_completion: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "progress": self.progress,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "baseline_value": self.baseline_value,
            "remaining_gap": self.remaining_gap,
            "trend": self.trend.value,
            "trend_data": self.trend_data,
            "estimated_completion": self.estimated_completion,
            "updated_at": self.updated_at,
        }


# ═══════════════════════════════════════════════════════════════
# GoalResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class GoalResult:
    """目标结果 — 目标完成后的总结.

    Attributes:
        goal_id:         目标 ID
        goal_name:       目标名称
        status:          最终状态
        final_value:     最终值
        target_value:    目标值
        achievement_rate: 达成率
        duration_days:   耗时天数
        subgoals_completed: 子目标完成数
        subgoals_total:  子目标总数
        lessons:         经验教训
        completed_at:    完成时间
    """
    goal_id: str = ""
    goal_name: str = ""
    status: GoalStatus = GoalStatus.FAILED
    final_value: float = 0.0
    target_value: float = 0.0
    achievement_rate: float = 0.0
    duration_days: float = 0.0
    subgoals_completed: int = 0
    subgoals_total: int = 0
    lessons: list[str] = field(default_factory=list)
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_name": self.goal_name,
            "status": self.status.value,
            "final_value": self.final_value,
            "target_value": self.target_value,
            "achievement_rate": self.achievement_rate,
            "duration_days": self.duration_days,
            "subgoals_completed": self.subgoals_completed,
            "subgoals_total": self.subgoals_total,
            "lessons": self.lessons,
            "completed_at": self.completed_at,
        }


# ═══════════════════════════════════════════════════════════════
# GoalAdaptation
# ═══════════════════════════════════════════════════════════════


@dataclass
class GoalAdaptation:
    """目标调整记录 — 记录目标策略的调整历史.

    Attributes:
        adaptation_id:  调整 ID
        goal_id:        目标 ID
        reason:         调整原因
        previous_target: 调整前目标值
        new_target:     调整后目标值
        previous_strategy: 调整前策略
        new_strategy:   调整后策略
        previous_subgoals: 调整前子目标
        new_subgoals:   调整后子目标
        created_at:     调整时间
    """
    adaptation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    reason: str = ""
    previous_target: float = 0.0
    new_target: float = 0.0
    previous_strategy: str = ""
    new_strategy: str = ""
    previous_subgoals: list[str] = field(default_factory=list)
    new_subgoals: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "adaptation_id": self.adaptation_id,
            "goal_id": self.goal_id,
            "reason": self.reason,
            "previous_target": self.previous_target,
            "new_target": self.new_target,
            "previous_strategy": self.previous_strategy,
            "new_strategy": self.new_strategy,
            "previous_subgoals": self.previous_subgoals,
            "new_subgoals": self.new_subgoals,
            "created_at": self.created_at,
        }


__all__ = [
    # Enums
    "GoalType",
    "GoalStatus",
    "GoalPriority",
    "SubGoalStrategy",
    "ProgressTrend",
    # Models
    "Goal",
    "SubGoal",
    "GoalProgress",
    "GoalResult",
    "GoalAdaptation",
]