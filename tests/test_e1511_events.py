"""E15.0.11 Events 测试 — 事件总线测试.

测试覆盖:
  - ExecutionEvent 创建与序列化
  - EventBus 发布/订阅
  - 事件类型过滤
  - 事件时间线查询
  - 全局订阅
  - 取消订阅
  - 事件日志限制
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.observability.events import (
    EventBus,
    ExecutionEvent,
    ExecutionEventType,
)


class TestExecutionEvent:
    """ExecutionEvent 单元测试."""

    def test_create_event(self):
        event = ExecutionEvent(
            event_type=ExecutionEventType.ACTION_CREATED,
            action_id="act_001",
            game_id="merge_witch",
        )
        assert event.event_type == ExecutionEventType.ACTION_CREATED
        assert event.action_id == "act_001"
        assert event.game_id == "merge_witch"
        assert event.event_id != ""
        assert event.timestamp != ""

    def test_default_values(self):
        event = ExecutionEvent()
        assert event.event_type == ExecutionEventType.ACTION_CREATED
        assert event.action_id == ""
        assert event.game_id == ""
        assert event.payload == {}

    def test_payload(self):
        event = ExecutionEvent(
            payload={"adapter": "meta", "duration_ms": 320}
        )
        assert event.payload["adapter"] == "meta"
        assert event.payload["duration_ms"] == 320

    def test_to_dict(self):
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_SUCCESS,
            action_id="act_001",
            game_id="merge_witch",
            trace_id="trace_abc",
            payload={"adapter": "meta"},
        )
        d = event.to_dict()
        assert d["event_type"] == "execution_success"
        assert d["action_id"] == "act_001"
        assert d["game_id"] == "merge_witch"
        assert d["trace_id"] == "trace_abc"
        assert d["payload"]["adapter"] == "meta"

    def test_from_dict(self):
        data = {
            "event_id": "evt_001",
            "event_type": "execution_success",
            "action_id": "act_001",
            "game_id": "merge_witch",
            "trace_id": "trace_abc",
            "payload": {"adapter": "meta"},
        }
        event = ExecutionEvent.from_dict(data)
        assert event.event_id == "evt_001"
        assert event.event_type == ExecutionEventType.EXECUTION_SUCCESS
        assert event.action_id == "act_001"
        assert event.trace_id == "trace_abc"

    def test_event_id_unique(self):
        e1 = ExecutionEvent()
        e2 = ExecutionEvent()
        assert e1.event_id != e2.event_id

    def test_all_event_types(self):
        """所有 18 种事件类型都应该可创建."""
        for et in ExecutionEventType:
            event = ExecutionEvent(event_type=et)
            assert event.event_type == et


class TestEventBus:
    """EventBus 单元测试."""

    def test_emit_and_subscribe(self):
        bus = EventBus()
        received: list[ExecutionEvent] = []

        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, received.append)
        event = ExecutionEvent(event_type=ExecutionEventType.EXECUTION_SUCCESS)
        bus.emit(event)

        assert len(received) == 1
        assert received[0] is event

    def test_subscribe_wrong_type_not_called(self):
        bus = EventBus()
        received: list[ExecutionEvent] = []

        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, received.append)
        event = ExecutionEvent(event_type=ExecutionEventType.EXECUTION_FAILED)
        bus.emit(event)

        assert len(received) == 0

    def test_multiple_subscribers(self):
        bus = EventBus()
        results: list[str] = []

        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, lambda e: results.append("a"))
        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, lambda e: results.append("b"))
        bus.emit(ExecutionEvent(event_type=ExecutionEventType.EXECUTION_SUCCESS))

        assert results == ["a", "b"]

    def test_global_subscriber(self):
        bus = EventBus()
        received: list[ExecutionEvent] = []

        bus.subscribe_all(received.append)
        bus.emit(ExecutionEvent(event_type=ExecutionEventType.ACTION_CREATED))
        bus.emit(ExecutionEvent(event_type=ExecutionEventType.EXECUTION_SUCCESS))

        assert len(received) == 2
        assert received[0].event_type == ExecutionEventType.ACTION_CREATED
        assert received[1].event_type == ExecutionEventType.EXECUTION_SUCCESS

    def test_emit_typed(self):
        bus = EventBus()
        event = bus.emit_typed(
            ExecutionEventType.EXECUTION_SUCCESS,
            action_id="act_001",
            game_id="merge_witch",
            adapter="meta",
            duration_ms=320,
        )
        assert event.action_id == "act_001"
        assert event.payload["adapter"] == "meta"
        assert event.payload["duration_ms"] == 320

    def test_unsubscribe(self):
        bus = EventBus()
        received: list[ExecutionEvent] = []

        def cb(e): received.append(e)
        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, cb)
        bus.unsubscribe(ExecutionEventType.EXECUTION_SUCCESS, cb)
        bus.emit(ExecutionEvent(event_type=ExecutionEventType.EXECUTION_SUCCESS))

        assert len(received) == 0

    def test_subscriber_exception_does_not_break_bus(self):
        bus = EventBus()
        received: list[ExecutionEvent] = []

        def bad_cb(e): raise RuntimeError("oops")
        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, bad_cb)
        bus.subscribe(ExecutionEventType.EXECUTION_SUCCESS, received.append)

        event = ExecutionEvent(event_type=ExecutionEventType.EXECUTION_SUCCESS)
        bus.emit(event)

        assert len(received) == 1

    def test_get_events_by_type(self):
        bus = EventBus()
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS, action_id="a1")
        bus.emit_typed(ExecutionEventType.EXECUTION_FAILED, action_id="a2")
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS, action_id="a3")

        success_events = bus.get_events(ExecutionEventType.EXECUTION_SUCCESS)
        assert len(success_events) == 2
        assert all(e.event_type == ExecutionEventType.EXECUTION_SUCCESS for e in success_events)

    def test_get_events_by_action_id(self):
        bus = EventBus()
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS, action_id="a1")
        bus.emit_typed(ExecutionEventType.EXECUTION_FAILED, action_id="a1")
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS, action_id="a2")

        a1_events = bus.get_events(action_id="a1")
        assert len(a1_events) == 2

    def test_get_action_timeline(self):
        bus = EventBus()
        bus.emit_typed(ExecutionEventType.ACTION_CREATED, action_id="a1")
        bus.emit_typed(ExecutionEventType.EXECUTION_STARTED, action_id="a1")
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS, action_id="a1")

        timeline = bus.get_action_timeline("a1")
        assert len(timeline) == 3
        assert timeline[0].event_type == ExecutionEventType.ACTION_CREATED
        assert timeline[2].event_type == ExecutionEventType.EXECUTION_SUCCESS

    def test_event_log_limit(self):
        bus = EventBus()
        bus._max_log_size = 10
        for i in range(15):
            bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS, action_id=f"a{i}")
        assert len(bus._event_log) <= 10

    def test_stats(self):
        bus = EventBus()
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS)
        bus.emit_typed(ExecutionEventType.EXECUTION_FAILED)
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS)

        stats = bus.stats()
        assert stats["total_events"] == 3
        assert stats["emit_count"] == 3
        assert stats["by_type"]["execution_success"] == 2
        assert stats["by_type"]["execution_failed"] == 1

    def test_clear(self):
        bus = EventBus()
        bus.emit_typed(ExecutionEventType.EXECUTION_SUCCESS)
        bus.clear()
        assert bus.stats()["total_events"] == 0
        assert bus.stats()["emit_count"] == 0

    def test_all_event_types_emittable(self):
        """验证所有 18 种事件类型都能正常发布."""
        bus = EventBus()
        received: list[ExecutionEvent] = []
        bus.subscribe_all(received.append)

        for et in ExecutionEventType:
            bus.emit_typed(et, action_id="test")

        assert len(received) == len(ExecutionEventType)
        emitted_types = {e.event_type for e in received}
        assert emitted_types == set(ExecutionEventType)