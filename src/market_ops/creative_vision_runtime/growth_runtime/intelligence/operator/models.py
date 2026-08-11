"""E15.3.1 Operator Controller Models — 核心数据模型.

定义:
  - OperatorState:       Operator 生命周期状态
  - GoalStatus:          目标状态
  - TriggerType:         触发器类型
  - OperatorSession:     Operator 会话
  - OperatorGoal:        Operator 目标
  - OperatorObservation: 环境观察
  - OperatorTrigger:     触发器
  - OperatorCycleResult: 运行周期结果
  - OperatorExperience:  经验记录
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


class OperatorState(str, Enum):
    """Operator 生命周期状态."""
    IDLE = "idle"           # 空闲，未启动
    OBSERVING = "observing"  # 观察环境
    THINKING = "thinking"    # 推理分析
    DECIDING = "deciding"    # 决策中
    EXECUTING = "executing"  # 执行中
    LEARNING = "learning"    # 学习反馈
    PAUSED = "paused"        # 已暂停
    STOPPED = "stopped"      # 已停止
    ERROR = "error"          # 错误状态


class GoalStatus(str, Enum):
    """目标状态."""
    ACTIVE = "active"        # 活跃中
    ACHIEVED = "achieved"    # 已达成
    FAILED = "failed"        # 已失败
    EXPIRED = "expired"      # 已过期
    PAUSED = "paused"        # 已暂停


class TriggerType(str, Enum):
    """触发器类型."""
    TIME = "time"            # 定时触发
    EVENT = "event"          # 事件触发
    GOAL_PROGRESS = "goal_progress"  # 目标进度触发
    ANOMALY = "anomaly"      # 异常触发
    MANUAL = "manual"        # 手动触发


class CycleOutcome(str, Enum):
    """周期结果."""
    SUCCESS = "success"
    FAILURE = "failure"
    NO_ACTION = "no_action"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════
# Operator Goal
# ═══════════════════════════════════════════════════════════════


@dataclass
class OperatorGoal:
    """Operator 目标.

    Attributes:
        goal_id:     目标 ID
        name:        目标名称
        description: 目标描述
        metric:      目标指标
        target:      目标值
        current:     当前值
        direction:   方向 ("above"=高于目标, "below"=低于目标)
        deadline:    截止时间 (ISO 8601)
        priority:    优先级 (high/medium/low)
        status:      目标状态
        created_at:  创建时间
        progress:    进度 (0.0-1.0)
        metadata:    扩展元数据
    """
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    metric: str = ""
    target: float = 0.0
    current: float = 0.0
    direction: str = "above"  # above=高于目标即达成, below=低于目标即达成
    deadline: str = ""
    priority: str = "medium"
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_progress(self, current_value: float) -> None:
        """更新进度."""
        self.current = current_value
        if self.target == 0:
            self.progress = 0.0
        elif self.direction == "above":
            self.progress = round(min(1.0, max(0.0, self.current / self.target)), 4)
        else:
            self.progress = round(min(1.0, max(0.0, self.target / max(0.0001, self.current))), 4)

    def is_achieved(self) -> bool:
        """是否已达成."""
        if self.direction == "above":
            return self.current >= self.target
        return self.current <= self.target

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "name": self.name,
            "description": self.description,
            "metric": self.metric,
            "target": self.target,
            "current": self.current,
            "direction": self.direction,
            "deadline": self.deadline,
            "priority": self.priority,
            "status": self.status.value,
            "progress": self.progress,
        }


# ═══════════════════════════════════════════════════════════════
# Operator Observation
# ═══════════════════════════════════════════════════════════════


@dataclass
class OperatorObservation:
    """环境观察.

    Attributes:
        observation_id: 观察 ID
        metrics:        指标快照
        timestamp:      时间戳
        source:         数据来源
    """
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""

    def get_metric(self, name: str, default: float = 0.0) -> float:
        return self.metrics.get(name, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "source": self.source,
        }


# ═══════════════════════════════════════════════════════════════
# Operator Trigger
# ═══════════════════════════════════════════════════════════════


@dataclass
class OperatorTrigger:
    """触发器定义.

    Attributes:
        trigger_id:     触发器 ID
        type:           触发器类型
        name:           触发器名称
        condition:      触发条件
        enabled:        是否启用
        cooldown_seconds: 冷却时间 (秒)
        last_triggered: 上次触发时间
        metadata:       扩展元数据
    """
    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TriggerType = TriggerType.TIME
    name: str = ""
    condition: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: int = 0
    last_triggered: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "type": self.type.value,
            "name": self.name,
            "condition": self.condition,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "last_triggered": self.last_triggered,
        }


# ═══════════════════════════════════════════════════════════════
# Operator Session
# ═══════════════════════════════════════════════════════════════


@dataclass
class OperatorSession:
    """Operator 会话.

    Attributes:
        session_id:   会话 ID
        state:        当前状态
        goals:        目标列表
        triggers:     触发器列表
        current_cycle: 当前周期数
        total_cycles: 总周期数
        created_at:   创建时间
        started_at:   启动时间
        paused_at:    暂停时间
        stopped_at:   停止时间
        metadata:     扩展元数据
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: OperatorState = OperatorState.IDLE
    goals: list[OperatorGoal] = field(default_factory=list)
    triggers: list[OperatorTrigger] = field(default_factory=list)
    current_cycle: int = 0
    total_cycles: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    paused_at: str | None = None
    stopped_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_active_goals(self) -> list[OperatorGoal]:
        return [g for g in self.goals if g.status == GoalStatus.ACTIVE]

    def get_enabled_triggers(self) -> list[OperatorTrigger]:
        return [t for t in self.triggers if t.enabled]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "goals": [g.to_dict() for g in self.goals],
            "triggers": [t.to_dict() for t in self.triggers],
            "current_cycle": self.current_cycle,
            "total_cycles": self.total_cycles,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "stopped_at": self.stopped_at,
        }


# ═══════════════════════════════════════════════════════════════
# Operator Cycle Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class OperatorCycleResult:
    """运行周期结果.

    Attributes:
        cycle_id:      周期 ID
        cycle_number:  周期编号
        observation:   观察数据
        triggered_by:  触发来源
        goals_updated: 更新的目标
        decision:      决策
        action:        执行动作
        result:        执行结果
        outcome:       周期结果
        error:         错误信息
        timestamp:     时间戳
        metadata:      扩展元数据
    """
    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    observation: OperatorObservation | None = None
    triggered_by: str | None = None
    goals_updated: list[str] = field(default_factory=list)
    decision: str | None = None
    action: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    outcome: CycleOutcome = CycleOutcome.NO_ACTION
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "observation": self.observation.to_dict() if self.observation else None,
            "triggered_by": self.triggered_by,
            "goals_updated": self.goals_updated,
            "decision": self.decision,
            "action": self.action,
            "result": self.result,
            "outcome": self.outcome.value,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# Operator Experience
# ═══════════════════════════════════════════════════════════════


@dataclass
class OperatorExperience:
    """Operator 经验 — 对接 E15.1.5 Memory Feedback.

    Attributes:
        experience_id: 经验 ID
        goal:          目标
        action:        执行动作
        result:        执行结果
        outcome:       结果
        reward:        奖励值
        lesson:        经验教训
        context:       上下文
        timestamp:     时间戳
    """
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    action: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    reward: float = 0.0
    lesson: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "goal": self.goal,
            "action": self.action,
            "result": self.result,
            "outcome": self.outcome,
            "reward": self.reward,
            "lesson": self.lesson,
            "context": self.context,
            "timestamp": self.timestamp,
        }


__all__ = [
    # Enums
    "OperatorState",
    "GoalStatus",
    "TriggerType",
    "CycleOutcome",
    # Models
    "OperatorGoal",
    "OperatorObservation",
    "OperatorTrigger",
    "OperatorSession",
    "OperatorCycleResult",
    "OperatorExperience",
]