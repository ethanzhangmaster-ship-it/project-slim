"""E15.0.11 Event System — 执行事件总线.

采用发布-订阅模式，解耦业务代码与可观测性组件:
  - 业务代码 emit 事件
  - Observability 组件 subscribe 事件
  - 无需直接调用 Metrics/Logger/Tracer

事件类型覆盖完整 Action 生命周期:
  ACTION_CREATED → APPROVAL_REQUIRED → APPROVED/REJECTED
  → EXECUTION_STARTED → EXECUTION_SUCCESS/EXECUTION_FAILED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# Execution Event Type
# ═══════════════════════════════════════════════════════════════


class ExecutionEventType(str, Enum):
    """E15.0.11 执行事件类型 — 覆盖完整 Action 生命周期."""

    # ── Action 生命周期 ─────────────────────────────────────
    ACTION_CREATED = "action_created"
    ACTION_VALIDATED = "action_validated"
    ACTION_REJECTED = "action_rejected"

    # ── Approval 生命周期 ───────────────────────────────────
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"

    # ── Execution 生命周期 ──────────────────────────────────
    EXECUTION_STARTED = "execution_started"
    EXECUTION_SUCCESS = "execution_success"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_ROLLBACK = "execution_rollback"
    EXECUTION_TIMEOUT = "execution_timeout"

    # ── Adapter 生命周期 ────────────────────────────────────
    ADAPTER_CALLED = "adapter_called"
    ADAPTER_ERROR = "adapter_error"
    ADAPTER_RETRY = "adapter_retry"

    # ── System ──────────────────────────────────────────────
    SYSTEM_ERROR = "system_error"
    HEALTH_CHECK = "health_check"


# ═══════════════════════════════════════════════════════════════
# Execution Event
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionEvent:
    """E15.0.11 执行事件 — 统一事件模型.

    Attributes:
        event_id:     事件唯一标识
        event_type:   事件类型
        action_id:    关联的动作 ID
        game_id:      游戏 ID
        timestamp:    事件时间戳
        trace_id:     分布式追踪 ID
        payload:      事件负载 (平台特定数据)
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: ExecutionEventType = ExecutionEventType.ACTION_CREATED
    action_id: str = ""
    game_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "action_id": self.action_id,
            "game_id": self.game_id,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionEvent":
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=ExecutionEventType(data.get("event_type", "action_created")),
            action_id=data.get("action_id", ""),
            game_id=data.get("game_id", ""),
            timestamp=data.get("timestamp", ""),
            trace_id=data.get("trace_id", ""),
            payload=data.get("payload", {}),
        )

    def __repr__(self) -> str:
        return (
            f"ExecutionEvent(type={self.event_type.value}, "
            f"action={self.action_id[:8] if self.action_id else '...'}..., "
            f"game={self.game_id})"
        )


# ═══════════════════════════════════════════════════════════════
# Event Bus
# ═══════════════════════════════════════════════════════════════


class EventBus:
    """E15.0.11 事件总线 — 发布-订阅模式.

    用法:
        bus = EventBus()

        # 订阅
        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, on_success)
        bus.subscribe(ExecutionEventType.EXECUTION_FAILED, on_failure)

        # 发布
        event = ExecutionEvent(event_type=ExecutionEventType.EXECUTION_SUCCESS)
        bus.emit(event)

        # 通配订阅
        bus.subscribe_all(on_any_event)
    """

    def __init__(self):
        self._subscribers: dict[ExecutionEventType, list[Callable[[ExecutionEvent], None]]] = {}
        self._global_subscribers: list[Callable[[ExecutionEvent], None]] = []
        self._event_log: list[ExecutionEvent] = []
        self._max_log_size: int = 1000
        self._emit_count: int = 0

    # ── Subscribe ────────────────────────────────────────────

    def subscribe(
        self,
        event_type: ExecutionEventType,
        callback: Callable[[ExecutionEvent], None],
    ) -> None:
        """订阅特定事件类型.

        Args:
            event_type: 事件类型
            callback:   回调函数
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_all(
        self,
        callback: Callable[[ExecutionEvent], None],
    ) -> None:
        """订阅所有事件类型 (通配)."""
        self._global_subscribers.append(callback)

    def unsubscribe(
        self,
        event_type: ExecutionEventType,
        callback: Callable[[ExecutionEvent], None],
    ) -> None:
        """取消订阅."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb is not callback
            ]

    # ── Emit ─────────────────────────────────────────────────

    def emit(self, event: ExecutionEvent) -> None:
        """发布事件.

        Args:
            event: ExecutionEvent 实例
        """
        self._emit_count += 1
        self._event_log.append(event)
        self._trim_log()

        # 通知类型订阅者
        subscribers = self._subscribers.get(event.event_type, [])
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                pass  # 订阅者异常不影响事件传播

        # 通知全局订阅者
        for callback in self._global_subscribers:
            try:
                callback(event)
            except Exception:
                pass

    def emit_typed(
        self,
        event_type: ExecutionEventType,
        action_id: str = "",
        game_id: str = "",
        trace_id: str = "",
        **payload: Any,
    ) -> ExecutionEvent:
        """创建并发布事件.

        Args:
            event_type: 事件类型
            action_id:  动作 ID
            game_id:    游戏 ID
            trace_id:   追踪 ID
            **payload:  事件负载

        Returns:
            ExecutionEvent: 创建的事件
        """
        event = ExecutionEvent(
            event_type=event_type,
            action_id=action_id,
            game_id=game_id,
            trace_id=trace_id,
            payload=payload,
        )
        self.emit(event)
        return event

    # ── Query ────────────────────────────────────────────────

    def get_events(
        self,
        event_type: ExecutionEventType | None = None,
        action_id: str = "",
        limit: int = 50,
    ) -> list[ExecutionEvent]:
        """查询事件日志.

        Args:
            event_type: 按类型过滤 (None = 全部)
            action_id:  按 action_id 过滤
            limit:      返回数量限制

        Returns:
            list[ExecutionEvent]: 匹配的事件
        """
        results = self._event_log
        if event_type is not None:
            results = [e for e in results if e.event_type == event_type]
        if action_id:
            results = [e for e in results if e.action_id == action_id]
        return results[-limit:]

    def get_action_timeline(self, action_id: str) -> list[ExecutionEvent]:
        """获取某个动作的完整事件时间线."""
        return [e for e in self._event_log if e.action_id == action_id]

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for event in self._event_log:
            key = event.event_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        return {
            "total_events": len(self._event_log),
            "emit_count": self._emit_count,
            "subscribers": {
                et.value: len(cbs) for et, cbs in self._subscribers.items()
            },
            "global_subscribers": len(self._global_subscribers),
            "by_type": type_counts,
        }

    def clear(self) -> None:
        """清空事件日志."""
        self._event_log.clear()
        self._emit_count = 0

    # ── Internal ─────────────────────────────────────────────

    def _trim_log(self) -> None:
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

    def __repr__(self) -> str:
        return f"EventBus(events={len(self._event_log)}, subscribers={len(self._subscribers)})"


__all__ = [
    "ExecutionEventType",
    "ExecutionEvent",
    "EventBus",
]