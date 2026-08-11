"""E13.7.4.1 Runtime Events — 事件系统.

Runtime Event System 为 Health Monitor、Reporter、Alert 等下游模块
提供统一的运行时事件流。

事件类型:
  - AGENT_STARTED / AGENT_STOPPED
  - CYCLE_STARTED / CYCLE_COMPLETED / CYCLE_FAILED
  - OBSERVATION_COMPLETED / REASONING_COMPLETED
  - PLAN_CREATED / EXECUTION_COMPLETED
  - LEARNING_COMPLETED
  - ERROR_OCCURRED / SAFE_MODE_ENTERED / SAFE_MODE_EXITED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class RuntimeEventType(str, Enum):
    """运行时事件类型."""
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_PAUSED = "agent_paused"
    AGENT_RESUMED = "agent_resumed"
    CYCLE_STARTED = "cycle_started"
    CYCLE_COMPLETED = "cycle_completed"
    CYCLE_FAILED = "cycle_failed"
    OBSERVATION_COMPLETED = "observation_completed"
    REASONING_COMPLETED = "reasoning_completed"
    PLAN_CREATED = "plan_created"
    EXECUTION_COMPLETED = "execution_completed"
    LEARNING_COMPLETED = "learning_completed"
    ERROR_OCCURRED = "error_occurred"
    SAFE_MODE_ENTERED = "safe_mode_entered"
    SAFE_MODE_EXITED = "safe_mode_exited"
    HEALTH_CHECK_COMPLETED = "health_check_completed"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"


@dataclass
class RuntimeEvent:
    """运行时事件.

    Attributes:
        event_id: 事件唯一 ID
        event_type: 事件类型
        timestamp: 事件时间
        source: 事件来源
        data: 事件数据
        error: 错误信息
        metadata: 扩展元数据
    """
    event_id: str = ""
    event_type: RuntimeEventType = RuntimeEventType.CYCLE_STARTED
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


# 事件处理器类型
EventHandler = Callable[[RuntimeEvent], None]


@dataclass
class EventBus:
    """事件总线 — 发布/订阅事件.

    支持:
      - 按事件类型订阅
      - 全局订阅 (所有事件)
      - 事件历史查询
    """

    # 最大事件历史数
    MAX_HISTORY = 1000

    def __init__(self):
        self._handlers: dict[RuntimeEventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._history: list[RuntimeEvent] = []
        self._event_counter: int = 0

    # ── 订阅 ──────────────────────────────────────────────────

    def subscribe(
        self,
        event_type: RuntimeEventType | None,
        handler: EventHandler,
    ) -> None:
        """订阅事件.

        Args:
            event_type: 事件类型 (None = 全局订阅)
            handler: 处理器
        """
        if event_type is None:
            self._global_handlers.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: RuntimeEventType | None,
        handler: EventHandler,
    ) -> None:
        """取消订阅."""
        if event_type is None:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
        elif event_type in self._handlers:
            handlers = self._handlers[event_type]
            if handler in handlers:
                handlers.remove(handler)

    # ── 发布 ──────────────────────────────────────────────────

    def publish(self, event: RuntimeEvent) -> None:
        """发布事件.

        所有匹配的处理器按顺序调用。单个处理器异常不影响其他处理器。
        """
        # 事件 ID
        self._event_counter += 1
        event.event_id = f"evt_{self._event_counter}"

        # 存储历史
        self._history.append(event)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

        # 全局处理器
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                pass

        # 类型处理器
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass

    def emit(
        self,
        event_type: RuntimeEventType,
        source: str = "",
        data: dict[str, Any] | None = None,
        error: str = "",
    ) -> RuntimeEvent:
        """快捷发布事件.

        Args:
            event_type: 事件类型
            source: 来源
            data: 数据
            error: 错误信息

        Returns:
            RuntimeEvent: 发布的事件
        """
        event = RuntimeEvent(
            event_type=event_type,
            source=source,
            data=data or {},
            error=error,
        )
        self.publish(event)
        return event

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 50) -> list[RuntimeEvent]:
        """获取最近 N 条事件."""
        return self._history[-n:]

    def get_by_type(self, event_type: RuntimeEventType, n: int = 50) -> list[RuntimeEvent]:
        """按类型获取事件."""
        return [e for e in self._history if e.event_type == event_type][-n:]

    def event_count(self) -> int:
        return self._event_counter

    def handler_count(self) -> int:
        return sum(len(h) for h in self._handlers.values()) + len(self._global_handlers)

    def clear(self) -> None:
        """清空历史."""
        self._history.clear()
        self._event_counter = 0


def create_event_bus() -> EventBus:
    """创建默认事件总线."""
    return EventBus()