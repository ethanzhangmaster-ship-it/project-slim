"""E12.7.1 — Growth Kernel Models。

Growth OS 内核的核心数据模型。

核心模型:
  GrowthState:     增长周期状态机（OBSERVE→ANALYZE→...→OPTIMIZE）
  GrowthEvent:     增长事件
  GrowthAction:    增长动作
  GrowthCycle:     增长周期
  GrowthRuntime:   增长运行时
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


# ── GrowthState ────────────────────────────────────────────


class GrowthState(str, Enum):
    """增长周期状态机。

    生命周期:
      OBSERVE → ANALYZE → DECIDE → PLAN → EXECUTE → EVALUATE → LEARN → OPTIMIZE
    """

    IDLE = "idle"
    OBSERVE = "observe"
    ANALYZE = "analyze"
    DECIDE = "decide"
    PLAN = "plan"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    LEARN = "learn"
    OPTIMIZE = "optimize"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


# 状态转移表
_STATE_TRANSITIONS: dict[GrowthState, list[GrowthState]] = {
    GrowthState.IDLE: [GrowthState.OBSERVE],
    GrowthState.OBSERVE: [GrowthState.ANALYZE, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.ANALYZE: [GrowthState.DECIDE, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.DECIDE: [GrowthState.PLAN, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.PLAN: [GrowthState.EXECUTE, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.EXECUTE: [GrowthState.EVALUATE, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.EVALUATE: [GrowthState.LEARN, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.LEARN: [GrowthState.OPTIMIZE, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.OPTIMIZE: [GrowthState.OBSERVE, GrowthState.COMPLETED, GrowthState.ERROR, GrowthState.PAUSED],
    GrowthState.PAUSED: [GrowthState.OBSERVE, GrowthState.ANALYZE, GrowthState.DECIDE,
                         GrowthState.PLAN, GrowthState.EXECUTE, GrowthState.EVALUATE,
                         GrowthState.LEARN, GrowthState.OPTIMIZE, GrowthState.ERROR],
    GrowthState.ERROR: [GrowthState.IDLE, GrowthState.PAUSED],
    GrowthState.COMPLETED: [GrowthState.IDLE, GrowthState.OBSERVE],
}

# 状态顺序（用于排序）
_STATE_ORDER: dict[GrowthState, int] = {
    GrowthState.IDLE: 0,
    GrowthState.OBSERVE: 1,
    GrowthState.ANALYZE: 2,
    GrowthState.DECIDE: 3,
    GrowthState.PLAN: 4,
    GrowthState.EXECUTE: 5,
    GrowthState.EVALUATE: 6,
    GrowthState.LEARN: 7,
    GrowthState.OPTIMIZE: 8,
    GrowthState.COMPLETED: 9,
    GrowthState.PAUSED: 10,
    GrowthState.ERROR: 11,
}


def can_transition(from_state: GrowthState, to_state: GrowthState) -> bool:
    """检查状态转移是否合法。"""
    return to_state in _STATE_TRANSITIONS.get(from_state, [])


def get_next_state(current: GrowthState) -> GrowthState | None:
    """获取正常流程中的下一个状态。"""
    order = _STATE_ORDER.get(current, -1)
    if order < 0:
        return None
    # 按顺序查找下一个可转移状态
    for state, idx in sorted(_STATE_ORDER.items(), key=lambda x: x[1]):
        if idx > order and can_transition(current, state):
            return state
    return None


def get_state_order(state: GrowthState) -> int:
    """获取状态顺序值。"""
    return _STATE_ORDER.get(state, -1)


# ── GrowthEvent ────────────────────────────────────────────


class EventPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_PRIORITY_ORDER: dict[EventPriority, int] = {
    EventPriority.LOW: 0,
    EventPriority.MEDIUM: 1,
    EventPriority.HIGH: 2,
    EventPriority.CRITICAL: 3,
}


class EventType(str, Enum):
    """增长事件类型。"""

    # 市场信号
    MARKET_SIGNAL = "market_signal"
    ROAS_CHANGE = "roas_change"
    CTR_CHANGE = "ctr_change"

    # 创意状态
    CREATIVE_FATIGUE = "creative_fatigue"
    CREATIVE_WINNER = "creative_winner"
    CREATIVE_EXHAUSTION = "creative_exhaustion"

    # 产品状态
    PRODUCT_LIFECYCLE_CHANGE = "product_lifecycle_change"
    PRODUCT_SCALE = "product_scale"
    PRODUCT_SUNSET = "product_sunset"

    # 预算相关
    BUDGET_THRESHOLD = "budget_threshold"
    BUDGET_EXHAUSTED = "budget_exhausted"

    # 实验相关
    EXPERIMENT_COMPLETE = "experiment_complete"
    EXPERIMENT_START = "experiment_start"

    # 系统事件
    CYCLE_START = "cycle_start"
    CYCLE_COMPLETE = "cycle_complete"
    CYCLE_ERROR = "cycle_error"
    STATE_CHANGE = "state_change"

    # 自定义
    CUSTOM = "custom"


@dataclass
class GrowthEvent:
    """增长事件。

    系统内所有模块通过 GrowthEvent 通信。

    Attributes:
        event_id:     事件 ID
        event_type:   事件类型
        product_id:   产品 ID（可选）
        source:       事件来源模块
        priority:     优先级
        severity:     严重程度 [0, 1]
        data:         事件数据
        timestamp:    时间戳
        metadata:     附加元数据
    """

    event_id: str = ""
    event_type: EventType = EventType.CUSTOM
    product_id: str = ""
    source: str = ""
    priority: EventPriority = EventPriority.MEDIUM
    severity: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = _gen_id("EVT")

    @property
    def is_critical(self) -> bool:
        return self.priority == EventPriority.CRITICAL

    @property
    def is_high_severity(self) -> bool:
        return self.severity >= 0.80

    @property
    def priority_order(self) -> int:
        return _PRIORITY_ORDER.get(self.priority, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "product_id": self.product_id,
            "source": self.source,
            "priority": self.priority.value,
            "severity": round(self.severity, 4),
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "is_critical": self.is_critical,
        }

    def __repr__(self) -> str:
        return (
            f"GrowthEvent(type={self.event_type.value}, "
            f"product={self.product_id or 'global'}, "
            f"priority={self.priority.value})"
        )


# ── GrowthAction ───────────────────────────────────────────


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(str, Enum):
    """增长动作类型。"""

    # 创意动作
    GENERATE_CREATIVE = "generate_creative"
    MUTATE_DNA = "mutate_dna"
    TEST_WINNER = "test_winner"

    # UA 动作
    INCREASE_BUDGET = "increase_budget"
    DECREASE_BUDGET = "decrease_budget"
    CHANGE_ALLOCATION = "change_allocation"

    # 产品动作
    SCALE_PRODUCT = "scale_product"
    MAINTAIN_PRODUCT = "maintain_product"
    SUNSET_PRODUCT = "sunset_product"

    # 实验动作
    START_EXPERIMENT = "start_experiment"
    STOP_EXPERIMENT = "stop_experiment"

    # 学习动作
    COLLECT_DATA = "collect_data"
    UPDATE_MODEL = "update_model"

    # 系统动作
    STATE_TRANSITION = "state_transition"
    CUSTOM = "custom"


@dataclass
class GrowthAction:
    """增长动作。

    系统执行的基本操作单元。

    Attributes:
        action_id:    动作 ID
        action_type:  动作类型
        product_id:   产品 ID
        target:       动作目标
        params:       动作参数
        priority:     优先级
        status:       状态
        result:       执行结果
        error:        错误信息
        created_at:   创建时间
        started_at:   开始时间
        completed_at: 完成时间
        metadata:     附加元数据
    """

    action_id: str = ""
    action_type: ActionType = ActionType.CUSTOM
    product_id: str = ""
    target: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.MEDIUM
    status: ActionStatus = ActionStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id:
            self.action_id = _gen_id("ACT")

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
            ActionStatus.CANCELLED,
        )

    @property
    def is_successful(self) -> bool:
        return self.status == ActionStatus.COMPLETED

    @property
    def priority_order(self) -> int:
        return _PRIORITY_ORDER.get(self.priority, 0)

    @property
    def duration_ms(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "product_id": self.product_id,
            "target": self.target,
            "params": self.params,
            "priority": self.priority.value,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "is_terminal": self.is_terminal,
            "is_successful": self.is_successful,
        }

    def __repr__(self) -> str:
        return (
            f"GrowthAction(type={self.action_type.value}, "
            f"product={self.product_id or 'global'}, "
            f"status={self.status.value})"
        )


# ── GrowthCycle ────────────────────────────────────────────


@dataclass
class GrowthCycle:
    """增长周期。

    代表一次完整的 OBSERVE → OPTIMIZE 循环。

    Attributes:
        cycle_id:      周期 ID
        product_id:    产品 ID
        state:         当前状态
        state_history: 状态历史
        events:        周期内事件
        actions:       周期内动作
        start_time:    开始时间
        end_time:      结束时间
        cycle_number:  周期编号
        result:        周期结果
        metadata:      附加元数据
    """

    cycle_id: str = ""
    product_id: str = ""
    state: GrowthState = GrowthState.IDLE
    state_history: list[tuple[GrowthState, datetime]] = field(default_factory=list)
    events: list[GrowthEvent] = field(default_factory=list)
    actions: list[GrowthAction] = field(default_factory=list)
    start_time: datetime = field(default_factory=_now)
    end_time: datetime | None = None
    cycle_number: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cycle_id:
            self.cycle_id = _gen_id("CYC")
        if not self.state_history:
            self.state_history = [(self.state, self.start_time)]

    def transition_to(self, new_state: GrowthState) -> bool:
        """状态转移。

        Args:
            new_state: 目标状态

        Returns:
            True 如果转移成功
        """
        if not can_transition(self.state, new_state):
            return False
        self.state = new_state
        self.state_history.append((new_state, _now()))
        return True

    @property
    def is_active(self) -> bool:
        return self.state not in (
            GrowthState.COMPLETED,
            GrowthState.ERROR,
            GrowthState.IDLE,
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in (GrowthState.COMPLETED, GrowthState.ERROR)

    @property
    def duration_seconds(self) -> float | None:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (_now() - self.start_time).total_seconds()

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def successful_action_count(self) -> int:
        return sum(1 for a in self.actions if a.is_successful)

    def add_event(self, event: GrowthEvent) -> None:
        self.events.append(event)

    def add_action(self, action: GrowthAction) -> None:
        self.actions.append(action)

    def complete(self) -> None:
        """标记周期完成。"""
        self.state = GrowthState.COMPLETED
        self.end_time = _now()
        self.state_history.append((GrowthState.COMPLETED, self.end_time))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "product_id": self.product_id,
            "state": self.state.value,
            "cycle_number": self.cycle_number,
            "event_count": self.event_count,
            "action_count": self.action_count,
            "successful_action_count": self.successful_action_count,
            "is_active": self.is_active,
            "is_terminal": self.is_terminal,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    def __repr__(self) -> str:
        return (
            f"GrowthCycle(product={self.product_id}, "
            f"state={self.state.value}, "
            f"#{self.cycle_number})"
        )


# ── GrowthRuntime ──────────────────────────────────────────


@dataclass
class GrowthRuntime:
    """增长运行时。

    管理整个 Growth OS 的生命周期。

    Attributes:
        runtime_id:     运行时 ID
        cycles:         活跃周期
        cycle_history:  历史周期
        events:         全局事件队列
        actions:        全局动作队列
        status:         运行时状态
        started_at:     启动时间
        metadata:       附加元数据
    """

    runtime_id: str = ""
    cycles: dict[str, GrowthCycle] = field(default_factory=dict)
    cycle_history: list[GrowthCycle] = field(default_factory=list)
    events: list[GrowthEvent] = field(default_factory=list)
    actions: list[GrowthAction] = field(default_factory=list)
    status: str = "initialized"
    started_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.runtime_id:
            self.runtime_id = _gen_id("RT")

    @property
    def active_cycle_count(self) -> int:
        return sum(1 for c in self.cycles.values() if c.is_active)

    @property
    def total_cycle_count(self) -> int:
        return len(self.cycle_history) + len(self.cycles)

    @property
    def total_event_count(self) -> int:
        return len(self.events)

    @property
    def total_action_count(self) -> int:
        return len(self.actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "status": self.status,
            "active_cycle_count": self.active_cycle_count,
            "total_cycle_count": self.total_cycle_count,
            "total_event_count": self.total_event_count,
            "total_action_count": self.total_action_count,
            "started_at": self.started_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"GrowthRuntime(cycles={self.active_cycle_count}/{self.total_cycle_count}, "
            f"events={self.total_event_count})"
        )