"""E12.7.7 WebSocket Manager — 实时推送 Growth Events."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Callable

from .models import DashboardEvent, DashboardEventType


class Subscription:
    """WebSocket 订阅."""
    def __init__(self, client_id: str, event_types: set[DashboardEventType] | None = None):
        self.client_id = client_id
        self.event_types = event_types or set()


class WebSocketManager:
    """WebSocket 管理器 — 实时推送 Growth 事件.

    事件:
      - cycle_started / decision_created / task_completed
      - experiment_finished / pattern_learned / risk_alert
      - system_status_changed / product_updated

    使用方式:
      manager = WebSocketManager()
      manager.subscribe("client_1", [DashboardEventType.CYCLE_STARTED])
      manager.emit(event)  # 推送给所有订阅者
    """

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        self._callbacks: dict[str, list[Callable[[DashboardEvent], None]]] = defaultdict(list)
        self._event_history: list[DashboardEvent] = []
        self._emit_count: int = 0

    @property
    def emit_count(self) -> int:
        return self._emit_count

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    # ── Subscribe / Unsubscribe ───────────────────────────────

    def subscribe(
        self,
        client_id: str,
        event_types: list[DashboardEventType] | None = None,
    ) -> Subscription:
        """订阅事件."""
        sub = Subscription(
            client_id=client_id,
            event_types=set(event_types) if event_types else set(),
        )
        self._subscriptions[client_id] = sub
        return sub

    def unsubscribe(self, client_id: str) -> bool:
        """取消订阅."""
        if client_id in self._subscriptions:
            del self._subscriptions[client_id]
            return True
        return False

    def on(self, event_type: DashboardEventType, callback: Callable[[DashboardEvent], None]) -> None:
        """注册回调."""
        self._callbacks[event_type.value].append(callback)

    def off(self, event_type: DashboardEventType, callback: Callable[[DashboardEvent], None]) -> None:
        """移除回调."""
        key = event_type.value
        if key in self._callbacks and callback in self._callbacks[key]:
            self._callbacks[key].remove(callback)

    # ── Emit ──────────────────────────────────────────────────

    def emit(self, event: DashboardEvent) -> int:
        """推送事件给所有匹配的订阅者.

        Returns:
            推送到的订阅者数量
        """
        self._emit_count += 1
        self._event_history.append(event)
        if len(self._event_history) > 200:
            self._event_history = self._event_history[-200:]

        delivered = 0

        # Deliver to subscribers
        for sub in self._subscriptions.values():
            if not sub.event_types or event.event_type in sub.event_types:
                self._deliver(sub.client_id, event)
                delivered += 1

        # Deliver to callbacks
        if event.event_type.value in self._callbacks:
            for cb in self._callbacks[event.event_type.value]:
                cb(event)

        return delivered

    def emit_cycle_started(self, product_id: str, data: dict[str, Any] | None = None) -> DashboardEvent:
        """推送 cycle_started 事件."""
        event = DashboardEvent(
            event_type=DashboardEventType.CYCLE_STARTED,
            product_id=product_id,
            data=data or {},
        )
        self.emit(event)
        return event

    def emit_decision_created(self, product_id: str, data: dict[str, Any] | None = None) -> DashboardEvent:
        """推送 decision_created 事件."""
        event = DashboardEvent(
            event_type=DashboardEventType.DECISION_CREATED,
            product_id=product_id,
            data=data or {},
        )
        self.emit(event)
        return event

    def emit_task_completed(self, product_id: str, data: dict[str, Any] | None = None) -> DashboardEvent:
        """推送 task_completed 事件."""
        event = DashboardEvent(
            event_type=DashboardEventType.TASK_COMPLETED,
            product_id=product_id,
            data=data or {},
        )
        self.emit(event)
        return event

    def emit_experiment_finished(self, product_id: str, data: dict[str, Any] | None = None) -> DashboardEvent:
        """推送 experiment_finished 事件."""
        event = DashboardEvent(
            event_type=DashboardEventType.EXPERIMENT_FINISHED,
            product_id=product_id,
            data=data or {},
        )
        self.emit(event)
        return event

    def emit_pattern_learned(self, product_id: str, data: dict[str, Any] | None = None) -> DashboardEvent:
        """推送 pattern_learned 事件."""
        event = DashboardEvent(
            event_type=DashboardEventType.PATTERN_LEARNED,
            product_id=product_id,
            data=data or {},
        )
        self.emit(event)
        return event

    def emit_risk_alert(self, product_id: str, data: dict[str, Any] | None = None) -> DashboardEvent:
        """推送 risk_alert 事件."""
        event = DashboardEvent(
            event_type=DashboardEventType.RISK_ALERT,
            product_id=product_id,
            data=data or {},
        )
        self.emit(event)
        return event

    # ── History ───────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> list[DashboardEvent]:
        """获取事件历史."""
        return self._event_history[-limit:]

    def get_history_by_type(
        self, event_type: DashboardEventType, limit: int = 20,
    ) -> list[DashboardEvent]:
        """按类型获取事件历史."""
        return [
            e for e in self._event_history
            if e.event_type == event_type
        ][-limit:]

    # ── Serialization ─────────────────────────────────────────

    def serialize_event(self, event: DashboardEvent) -> str:
        """序列化事件为 JSON."""
        return json.dumps(event.to_dict())

    def serialize_events(self, events: list[DashboardEvent]) -> str:
        """序列化事件列表为 JSON."""
        return json.dumps([e.to_dict() for e in events])

    # ── Internal ──────────────────────────────────────────────

    def _deliver(self, client_id: str, event: DashboardEvent) -> None:
        """投递事件给客户端（内部方法，实际系统会通过 WebSocket 连接发送）."""
        # In production, this would send through the actual WebSocket connection
        pass

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "subscriber_count": self.subscriber_count,
            "emit_count": self._emit_count,
            "event_history_count": len(self._event_history),
            "event_types": [et.value for et in DashboardEventType],
        }