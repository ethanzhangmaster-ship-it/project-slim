"""E12.7.1 — Event Bus。

Growth OS 事件总线 —— 模块间解耦通信。

功能:
  - 发布/订阅模式
  - 事件优先级排序
  - 事件过滤
  - 事件历史记录
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from .models import (
    EventPriority,
    EventType,
    GrowthEvent,
    _gen_id,
    _now,
)


EventHandler = Callable[[GrowthEvent], None]


class EventBus:
    """事件总线。

    发布/订阅模式的事件分发系统。
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._global_subscribers: list[EventHandler] = []
        self._history: list[GrowthEvent] = []
        self._max_history = max_history
        self._bus_id = _gen_id("EB")

    # ── Subscribe ──────────────────────────────────────────

    def subscribe(
        self,
        handler: EventHandler,
        event_type: EventType | None = None,
    ) -> None:
        """订阅事件。

        Args:
            handler:    事件处理回调
            event_type: 事件类型（None 表示订阅所有事件）
        """
        if event_type is None:
            self._global_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def unsubscribe(
        self,
        handler: EventHandler,
        event_type: EventType | None = None,
    ) -> bool:
        """取消订阅。

        Returns:
            True 如果成功取消
        """
        if event_type is None:
            if handler in self._global_subscribers:
                self._global_subscribers.remove(handler)
                return True
        elif event_type in self._subscribers:
            subs = self._subscribers[event_type]
            if handler in subs:
                subs.remove(handler)
                return True
        return False

    # ── Publish ────────────────────────────────────────────

    def publish(self, event: GrowthEvent) -> None:
        """发布事件。

        通知所有匹配的订阅者。

        Args:
            event: 要发布的事件
        """
        # 记录历史
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 通知类型订阅者
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                pass  # 事件处理异常不中断总线

        # 通知全局订阅者
        for handler in self._global_subscribers:
            try:
                handler(event)
            except Exception:
                pass

    def publish_many(self, events: list[GrowthEvent]) -> None:
        """批量发布事件。"""
        for event in events:
            self.publish(event)

    # ── Query ──────────────────────────────────────────────

    def get_history(
        self,
        event_type: EventType | None = None,
        product_id: str | None = None,
        priority: EventPriority | None = None,
        limit: int = 100,
    ) -> list[GrowthEvent]:
        """查询事件历史。

        Args:
            event_type: 按事件类型过滤
            product_id: 按产品 ID 过滤
            priority:   按优先级过滤
            limit:      返回数量限制

        Returns:
            匹配的事件列表
        """
        results = self._history

        if event_type is not None:
            results = [e for e in results if e.event_type == event_type]
        if product_id is not None:
            results = [e for e in results if e.product_id == product_id]
        if priority is not None:
            results = [e for e in results if e.priority == priority]

        return results[-limit:]

    def get_latest(self, event_type: EventType | None = None) -> GrowthEvent | None:
        """获取最新事件。"""
        if event_type is None:
            return self._history[-1] if self._history else None
        for e in reversed(self._history):
            if e.event_type == event_type:
                return e
        return None

    # ── Priority Queue ─────────────────────────────────────

    def get_priority_queue(self, limit: int = 100) -> list[GrowthEvent]:
        """获取按优先级排序的事件队列。

        CRITICAL > HIGH > MEDIUM > LOW
        """
        pending = [e for e in self._history if e.timestamp is not None]
        pending.sort(key=lambda e: (e.priority_order, e.timestamp), reverse=True)
        return pending[:limit]

    # ── Stats ──────────────────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        return len(self._global_subscribers) + sum(
            len(subs) for subs in self._subscribers.values()
        )

    @property
    def history_count(self) -> int:
        return len(self._history)

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息。"""
        type_counts: dict[str, int] = {}
        for e in self._history:
            key = e.event_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        return {
            "bus_id": self._bus_id,
            "subscriber_count": self.subscriber_count,
            "history_count": self.history_count,
            "type_subscribers": sum(len(s) for s in self._subscribers.values()),
            "global_subscribers": len(self._global_subscribers),
            "event_type_counts": type_counts,
        }

    def clear_history(self) -> None:
        """清除事件历史。"""
        self._history.clear()

    def __repr__(self) -> str:
        return (
            f"EventBus(subscribers={self.subscriber_count}, "
            f"history={self.history_count})"
        )