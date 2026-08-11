"""E12.7.1 — Growth Kernel Test Suite。

覆盖:
  - TestGrowthState:      状态机测试 (15)
  - TestGrowthEvent:      事件模型测试 (8)
  - TestGrowthAction:     动作模型测试 (8)
  - TestGrowthCycle:      周期模型测试 (10)
  - TestEventBus:         事件总线测试 (20)
  - TestRuntimeManager:   运行时管理器测试 (20)
  - TestCycleScheduler:   调度器测试 (15)

总计: 96 tests
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_os.kernel import (
    ActionStatus,
    ActionType,
    CycleScheduler,
    EventBus,
    EventPriority,
    EventType,
    GrowthAction,
    GrowthCycle,
    GrowthEvent,
    GrowthRuntime,
    GrowthState,
    RuntimeManager,
    can_transition,
    get_next_state,
    get_state_order,
)


# ── Helpers ─────────────────────────────────────────────────


def make_event(
    event_type: EventType = EventType.CUSTOM,
    product_id: str = "p04",
    source: str = "test",
    severity: float = 0.5,
    priority: EventPriority = EventPriority.MEDIUM,
) -> GrowthEvent:
    return GrowthEvent(
        event_type=event_type,
        product_id=product_id,
        source=source,
        severity=severity,
        priority=priority,
    )


# ── TestGrowthState ────────────────────────────────────────


class TestGrowthState:
    """状态机测试。"""

    def test_all_states_defined(self):
        assert len(GrowthState) == 12

    def test_transition_observe_to_analyze(self):
        assert can_transition(GrowthState.OBSERVE, GrowthState.ANALYZE)

    def test_transition_analyze_to_decide(self):
        assert can_transition(GrowthState.ANALYZE, GrowthState.DECIDE)

    def test_transition_decide_to_plan(self):
        assert can_transition(GrowthState.DECIDE, GrowthState.PLAN)

    def test_transition_plan_to_execute(self):
        assert can_transition(GrowthState.PLAN, GrowthState.EXECUTE)

    def test_transition_execute_to_evaluate(self):
        assert can_transition(GrowthState.EXECUTE, GrowthState.EVALUATE)

    def test_transition_evaluate_to_learn(self):
        assert can_transition(GrowthState.EVALUATE, GrowthState.LEARN)

    def test_transition_learn_to_optimize(self):
        assert can_transition(GrowthState.LEARN, GrowthState.OPTIMIZE)

    def test_transition_optimize_to_observe(self):
        assert can_transition(GrowthState.OPTIMIZE, GrowthState.OBSERVE)

    def test_transition_optimize_to_completed(self):
        assert can_transition(GrowthState.OPTIMIZE, GrowthState.COMPLETED)

    def test_transition_to_error(self):
        assert can_transition(GrowthState.EXECUTE, GrowthState.ERROR)
        assert can_transition(GrowthState.OBSERVE, GrowthState.ERROR)

    def test_transition_to_paused(self):
        assert can_transition(GrowthState.EXECUTE, GrowthState.PAUSED)

    def test_transition_paused_to_observe(self):
        assert can_transition(GrowthState.PAUSED, GrowthState.OBSERVE)

    def test_transition_paused_to_execute(self):
        assert can_transition(GrowthState.PAUSED, GrowthState.EXECUTE)

    def test_invalid_transition(self):
        assert not can_transition(GrowthState.OBSERVE, GrowthState.EXECUTE)
        assert not can_transition(GrowthState.IDLE, GrowthState.EXECUTE)
        assert not can_transition(GrowthState.COMPLETED, GrowthState.ANALYZE)

    def test_get_next_state(self):
        assert get_next_state(GrowthState.OBSERVE) == GrowthState.ANALYZE
        assert get_next_state(GrowthState.ANALYZE) == GrowthState.DECIDE
        assert get_next_state(GrowthState.DECIDE) == GrowthState.PLAN
        assert get_next_state(GrowthState.PLAN) == GrowthState.EXECUTE
        assert get_next_state(GrowthState.EXECUTE) == GrowthState.EVALUATE
        assert get_next_state(GrowthState.EVALUATE) == GrowthState.LEARN
        assert get_next_state(GrowthState.LEARN) == GrowthState.OPTIMIZE

    def test_get_next_state_optimize(self):
        next_state = get_next_state(GrowthState.OPTIMIZE)
        assert next_state in (GrowthState.OBSERVE, GrowthState.COMPLETED)

    def test_get_next_state_terminal(self):
        assert get_next_state(GrowthState.COMPLETED) is None

    def test_get_state_order(self):
        assert get_state_order(GrowthState.IDLE) == 0
        assert get_state_order(GrowthState.OBSERVE) == 1
        assert get_state_order(GrowthState.OPTIMIZE) == 8
        assert get_state_order(GrowthState.COMPLETED) == 9


# ── TestGrowthEvent ────────────────────────────────────────


class TestGrowthEvent:
    """事件模型测试。"""

    def test_event_auto_id(self):
        e = GrowthEvent()
        assert e.event_id.startswith("EVT_")

    def test_event_critical(self):
        e = GrowthEvent(priority=EventPriority.CRITICAL)
        assert e.is_critical
        e2 = GrowthEvent(priority=EventPriority.LOW)
        assert not e2.is_critical

    def test_event_high_severity(self):
        e = GrowthEvent(severity=0.85)
        assert e.is_high_severity
        e2 = GrowthEvent(severity=0.30)
        assert not e2.is_high_severity

    def test_event_priority_order(self):
        critical = GrowthEvent(priority=EventPriority.CRITICAL)
        low = GrowthEvent(priority=EventPriority.LOW)
        assert critical.priority_order > low.priority_order

    def test_event_to_dict(self):
        e = make_event(EventType.CREATIVE_FATIGUE, "p04", severity=0.8)
        d = e.to_dict()
        assert d["event_type"] == "creative_fatigue"
        assert d["product_id"] == "p04"
        assert d["is_critical"] is False

    def test_event_repr(self):
        e = make_event(EventType.ROAS_CHANGE, "p05")
        r = repr(e)
        assert "ROAS_CHANGE" in r or "roas_change" in r
        assert "p05" in r

    def test_event_defaults(self):
        e = GrowthEvent()
        assert e.event_type == EventType.CUSTOM
        assert e.product_id == ""
        assert e.priority == EventPriority.MEDIUM
        assert e.severity == 0.0

    def test_event_custom_id(self):
        e = GrowthEvent(event_id="my_custom_id")
        assert e.event_id == "my_custom_id"


# ── TestGrowthAction ───────────────────────────────────────


class TestGrowthAction:
    """动作模型测试。"""

    def test_action_auto_id(self):
        a = GrowthAction()
        assert a.action_id.startswith("ACT_")

    def test_action_initial_status(self):
        a = GrowthAction()
        assert a.status == ActionStatus.PENDING
        assert not a.is_terminal

    def test_action_terminal_statuses(self):
        for status in [ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.CANCELLED]:
            a = GrowthAction(status=status)
            assert a.is_terminal

    def test_action_successful(self):
        a = GrowthAction(status=ActionStatus.COMPLETED)
        assert a.is_successful

    def test_action_duration(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        a = GrowthAction(
            started_at=now,
            completed_at=now + timedelta(seconds=1.5),
        )
        assert a.duration_ms == pytest.approx(1500, abs=50)

    def test_action_no_duration(self):
        a = GrowthAction()
        assert a.duration_ms is None

    def test_action_to_dict(self):
        a = GrowthAction(
            action_type=ActionType.INCREASE_BUDGET,
            product_id="p04",
            status=ActionStatus.COMPLETED,
            result={"roas": 1.5},
        )
        d = a.to_dict()
        assert d["action_type"] == "increase_budget"
        assert d["is_successful"] is True

    def test_action_repr(self):
        a = GrowthAction(action_type=ActionType.MUTATE_DNA, status=ActionStatus.RUNNING)
        r = repr(a)
        assert "mutate_dna" in r
        assert "running" in r


# ── TestGrowthCycle ────────────────────────────────────────


class TestGrowthCycle:
    """周期模型测试。"""

    def test_cycle_auto_id(self):
        c = GrowthCycle()
        assert c.cycle_id.startswith("CYC_")

    def test_cycle_initial_state(self):
        c = GrowthCycle()
        assert c.state == GrowthState.IDLE
        assert c.is_active is False

    def test_cycle_initial_state_history(self):
        c = GrowthCycle()
        assert len(c.state_history) == 1
        assert c.state_history[0][0] == GrowthState.IDLE

    def test_cycle_transition(self):
        c = GrowthCycle()
        assert c.transition_to(GrowthState.OBSERVE)
        assert c.state == GrowthState.OBSERVE
        assert len(c.state_history) == 2

    def test_cycle_invalid_transition(self):
        c = GrowthCycle()
        assert not c.transition_to(GrowthState.EXECUTE)  # 不能从 IDLE 跳到 EXECUTE
        assert c.state == GrowthState.IDLE

    def test_cycle_is_active(self):
        c = GrowthCycle(state=GrowthState.OBSERVE)
        assert c.is_active

    def test_cycle_is_terminal(self):
        c = GrowthCycle(state=GrowthState.COMPLETED)
        assert c.is_terminal
        c2 = GrowthCycle(state=GrowthState.ERROR)
        assert c2.is_terminal

    def test_cycle_add_event(self):
        c = GrowthCycle()
        e = make_event()
        c.add_event(e)
        assert c.event_count == 1

    def test_cycle_add_action(self):
        c = GrowthCycle()
        a = GrowthAction()
        c.add_action(a)
        assert c.action_count == 1

    def test_cycle_complete(self):
        c = GrowthCycle()
        c.complete()
        assert c.state == GrowthState.COMPLETED
        assert c.end_time is not None

    def test_cycle_successful_action_count(self):
        c = GrowthCycle()
        c.add_action(GrowthAction(status=ActionStatus.COMPLETED))
        c.add_action(GrowthAction(status=ActionStatus.FAILED))
        c.add_action(GrowthAction(status=ActionStatus.COMPLETED))
        assert c.successful_action_count == 2

    def test_cycle_to_dict(self):
        c = GrowthCycle(product_id="p04", cycle_number=3)
        d = c.to_dict()
        assert d["product_id"] == "p04"
        assert d["cycle_number"] == 3

    def test_cycle_repr(self):
        c = GrowthCycle(product_id="p04", cycle_number=5)
        r = repr(c)
        assert "p04" in r
        assert "5" in r


# ── TestGrowthRuntime ──────────────────────────────────────


class TestGrowthRuntimeModel:
    def test_runtime_auto_id(self):
        rt = GrowthRuntime()
        assert rt.runtime_id.startswith("RT_")

    def test_runtime_defaults(self):
        rt = GrowthRuntime()
        assert rt.active_cycle_count == 0
        assert rt.total_cycle_count == 0
        assert rt.status == "initialized"

    def test_runtime_to_dict(self):
        rt = GrowthRuntime()
        d = rt.to_dict()
        assert d["status"] == "initialized"
        assert d["active_cycle_count"] == 0

    def test_runtime_repr(self):
        rt = GrowthRuntime()
        r = repr(rt)
        assert "GrowthRuntime" in r


# ── TestEventBus ───────────────────────────────────────────


class TestEventBus:
    """事件总线测试。"""

    def test_bus_creation(self):
        bus = EventBus()
        assert bus.subscriber_count == 0
        assert bus.history_count == 0

    def test_subscribe_by_type(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler, EventType.CREATIVE_FATIGUE)
        assert bus.subscriber_count == 1

    def test_subscribe_global(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler)
        assert bus.subscriber_count == 1

    def test_publish_type_match(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler, EventType.CREATIVE_FATIGUE)
        e = make_event(EventType.CREATIVE_FATIGUE)
        bus.publish(e)
        assert len(received) == 1

    def test_publish_type_no_match(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler, EventType.CREATIVE_FATIGUE)
        e = make_event(EventType.ROAS_CHANGE)
        bus.publish(e)
        assert len(received) == 0

    def test_publish_global_receives_all(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler)
        bus.publish(make_event(EventType.CREATIVE_FATIGUE))
        bus.publish(make_event(EventType.ROAS_CHANGE))
        assert len(received) == 2

    def test_publish_both_type_and_global(self):
        bus = EventBus()
        type_received: list[GrowthEvent] = []
        global_received: list[GrowthEvent] = []

        bus.subscribe(lambda e: type_received.append(e), EventType.CREATIVE_FATIGUE)
        bus.subscribe(lambda e: global_received.append(e))

        bus.publish(make_event(EventType.CREATIVE_FATIGUE))
        assert len(type_received) == 1
        assert len(global_received) == 1

    def test_unsubscribe_type(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler, EventType.CREATIVE_FATIGUE)
        assert bus.unsubscribe(handler, EventType.CREATIVE_FATIGUE)
        assert bus.subscriber_count == 0

    def test_unsubscribe_global(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        def handler(e: GrowthEvent):
            received.append(e)

        bus.subscribe(handler)
        assert bus.unsubscribe(handler)
        assert bus.subscriber_count == 0

    def test_unsubscribe_not_found(self):
        bus = EventBus()

        def handler(e: GrowthEvent):
            pass

        assert not bus.unsubscribe(handler, EventType.CREATIVE_FATIGUE)

    def test_publish_many(self):
        bus = EventBus()
        received: list[GrowthEvent] = []

        bus.subscribe(lambda e: received.append(e))
        events = [make_event() for _ in range(5)]
        bus.publish_many(events)
        assert len(received) == 5

    def test_history_records(self):
        bus = EventBus()
        for i in range(3):
            bus.publish(make_event(product_id=f"p{i:02d}"))
        assert bus.history_count == 3

    def test_history_filter_by_type(self):
        bus = EventBus()
        bus.publish(make_event(EventType.CREATIVE_FATIGUE))
        bus.publish(make_event(EventType.ROAS_CHANGE))
        bus.publish(make_event(EventType.CREATIVE_FATIGUE))
        results = bus.get_history(event_type=EventType.CREATIVE_FATIGUE)
        assert len(results) == 2

    def test_history_filter_by_product(self):
        bus = EventBus()
        bus.publish(make_event(product_id="p04"))
        bus.publish(make_event(product_id="p05"))
        bus.publish(make_event(product_id="p04"))
        results = bus.get_history(product_id="p04")
        assert len(results) == 2

    def test_history_filter_by_priority(self):
        bus = EventBus()
        bus.publish(make_event(priority=EventPriority.CRITICAL))
        bus.publish(make_event(priority=EventPriority.LOW))
        results = bus.get_history(priority=EventPriority.CRITICAL)
        assert len(results) == 1

    def test_history_limit(self):
        bus = EventBus()
        for i in range(5):
            bus.publish(make_event())
        results = bus.get_history(limit=3)
        assert len(results) == 3

    def test_get_latest(self):
        bus = EventBus()
        e1 = make_event(EventType.CREATIVE_FATIGUE)
        e2 = make_event(EventType.ROAS_CHANGE)
        bus.publish(e1)
        bus.publish(e2)
        assert bus.get_latest().event_id == e2.event_id
        assert bus.get_latest(EventType.CREATIVE_FATIGUE).event_id == e1.event_id

    def test_get_latest_empty(self):
        bus = EventBus()
        assert bus.get_latest() is None

    def test_priority_queue(self):
        bus = EventBus()
        bus.publish(make_event(priority=EventPriority.LOW))
        bus.publish(make_event(priority=EventPriority.CRITICAL))
        bus.publish(make_event(priority=EventPriority.HIGH))
        queue = bus.get_priority_queue()
        assert queue[0].priority == EventPriority.CRITICAL
        assert queue[1].priority == EventPriority.HIGH
        assert queue[2].priority == EventPriority.LOW

    def test_clear_history(self):
        bus = EventBus()
        bus.publish(make_event())
        bus.clear_history()
        assert bus.history_count == 0

    def test_get_statistics(self):
        bus = EventBus()
        bus.publish(make_event(EventType.CREATIVE_FATIGUE))
        stats = bus.get_statistics()
        assert stats["history_count"] == 1
        assert "creative_fatigue" in stats["event_type_counts"]

    def test_max_history(self):
        bus = EventBus(max_history=10)
        for i in range(20):
            bus.publish(make_event())
        assert bus.history_count == 10


# ── TestRuntimeManager ─────────────────────────────────────


class TestRuntimeManager:
    """运行时管理器测试。"""

    def test_create_cycle(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        rm.transition_cycle(cycle, GrowthState.OBSERVE)
        assert cycle.product_id == "p04"
        assert cycle.cycle_number == 1
        assert rm.runtime.active_cycle_count == 1

    def test_create_cycle_auto_increment(self):
        rm = RuntimeManager()
        c1 = rm.create_cycle("p04")
        c2 = rm.create_cycle("p04")
        assert c1.cycle_number == 1
        assert c2.cycle_number == 2

    def test_create_cycle_custom_number(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04", cycle_number=10)
        assert cycle.cycle_number == 10

    def test_transition_cycle(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        assert rm.transition_cycle(cycle, GrowthState.OBSERVE)
        assert cycle.state == GrowthState.OBSERVE

    def test_transition_cycle_invalid(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        assert not rm.transition_cycle(cycle, GrowthState.EXECUTE)
        assert cycle.state == GrowthState.IDLE

    def test_advance_cycle(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        rm.transition_cycle(cycle, GrowthState.OBSERVE)
        new_state = rm.advance_cycle(cycle)
        assert new_state == GrowthState.ANALYZE

    def test_advance_cycle_no_next(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        cycle.state = GrowthState.COMPLETED
        assert rm.advance_cycle(cycle) is None

    def test_run_cycle_auto(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        rm.transition_cycle(cycle, GrowthState.OBSERVE)
        states = rm.run_cycle_auto(cycle)
        assert len(states) >= 5  # 至少经过几个状态
        assert cycle.state == GrowthState.COMPLETED

    def test_cycle_complete_archives(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        rm.transition_cycle(cycle, GrowthState.OBSERVE)
        rm.run_cycle_auto(cycle)
        assert rm.runtime.active_cycle_count == 0
        assert rm.runtime.total_cycle_count == 1

    def test_get_cycle(self):
        rm = RuntimeManager()
        cycle = rm.create_cycle("p04")
        found = rm.get_cycle(cycle.cycle_id)
        assert found is not None
        assert found.product_id == "p04"

    def test_get_cycle_not_found(self):
        rm = RuntimeManager()
        assert rm.get_cycle("nonexistent") is None

    def test_get_active_cycles(self):
        rm = RuntimeManager()
        c1 = rm.create_cycle("p04")
        c2 = rm.create_cycle("p05")
        rm.transition_cycle(c1, GrowthState.OBSERVE)
        rm.transition_cycle(c2, GrowthState.OBSERVE)
        active = rm.get_active_cycles()
        assert len(active) == 2

    def test_create_action(self):
        rm = RuntimeManager()
        action = rm.create_action(
            ActionType.INCREASE_BUDGET,
            product_id="p04",
            target="budget",
            params={"amount": 5000},
        )
        assert action.action_type == ActionType.INCREASE_BUDGET
        assert action.product_id == "p04"

    def test_start_action(self):
        rm = RuntimeManager()
        action = rm.create_action(ActionType.INCREASE_BUDGET)
        rm.start_action(action)
        assert action.status == ActionStatus.RUNNING
        assert action.started_at is not None

    def test_complete_action(self):
        rm = RuntimeManager()
        action = rm.create_action(ActionType.INCREASE_BUDGET)
        rm.start_action(action)
        rm.complete_action(action, result={"roas": 1.3})
        assert action.status == ActionStatus.COMPLETED
        assert action.result == {"roas": 1.3}

    def test_fail_action(self):
        rm = RuntimeManager()
        action = rm.create_action(ActionType.INCREASE_BUDGET)
        rm.fail_action(action, "budget exceeded")
        assert action.status == ActionStatus.FAILED
        assert action.error == "budget exceeded"

    def test_cancel_action(self):
        rm = RuntimeManager()
        action = rm.create_action(ActionType.INCREASE_BUDGET)
        rm.cancel_action(action)
        assert action.status == ActionStatus.CANCELLED

    def test_get_pending_actions(self):
        rm = RuntimeManager()
        rm.create_action(ActionType.INCREASE_BUDGET, priority=EventPriority.LOW)
        rm.create_action(ActionType.MUTATE_DNA, priority=EventPriority.CRITICAL)
        pending = rm.get_pending_actions()
        assert len(pending) == 2
        # Critical 应该排在前面
        assert pending[0].priority == EventPriority.CRITICAL

    def test_get_pending_actions_by_product(self):
        rm = RuntimeManager()
        rm.create_action(ActionType.INCREASE_BUDGET, product_id="p04")
        rm.create_action(ActionType.MUTATE_DNA, product_id="p05")
        pending = rm.get_pending_actions(product_id="p04")
        assert len(pending) == 1
        assert pending[0].product_id == "p04"

    def test_emit_event(self):
        rm = RuntimeManager()
        event = rm.emit_event(
            EventType.CREATIVE_FATIGUE,
            product_id="p04",
            source="test",
            severity=0.8,
        )
        assert event.event_type == EventType.CREATIVE_FATIGUE
        assert rm.runtime.total_event_count == 1

    def test_start_pause_resume_stop(self):
        rm = RuntimeManager()
        rm.start()
        assert rm.is_running
        rm.pause()
        assert rm.runtime.status == "paused"
        rm.resume()
        assert rm.is_running
        rm.stop()
        assert rm.runtime.status == "stopped"

    def test_get_status(self):
        rm = RuntimeManager()
        status = rm.get_status()
        assert status["status"] == "initialized"
        assert "event_bus_stats" in status

    def test_repr(self):
        rm = RuntimeManager()
        r = repr(rm)
        assert "RuntimeManager" in r


# ── TestCycleScheduler ─────────────────────────────────────


class TestCycleScheduler:
    """调度器测试。"""

    def test_schedule_product_cycle(self):
        s = CycleScheduler()
        cycle = s.schedule_product_cycle("p04", interval_minutes=30)
        assert cycle.product_id == "p04"
        assert s.scheduled_product_count == 1

    def test_schedule_product_auto_advance(self):
        s = CycleScheduler()
        cycle = s.schedule_product_cycle("p04", auto_advance=True)
        assert cycle.state == GrowthState.COMPLETED

    def test_schedule_multiple_products(self):
        s = CycleScheduler()
        s.schedule_product_cycle("p04")
        s.schedule_product_cycle("p05")
        s.schedule_product_cycle("p06")
        assert s.scheduled_product_count == 3

    def test_trigger_cycle(self):
        s = CycleScheduler()
        cycle = s.trigger_cycle("p04", reason="manual")
        assert cycle is not None
        assert cycle.product_id == "p04"

    def test_trigger_cycle_no_duplicate(self):
        s = CycleScheduler()
        first = s.trigger_cycle("p04")
        # Transition first cycle to active state
        s._runtime.transition_cycle(first, GrowthState.OBSERVE)
        result = s.trigger_cycle("p04")
        assert result is None  # 已有活跃周期

    def test_trigger_on_event(self):
        s = CycleScheduler()
        event = make_event(EventType.CREATIVE_FATIGUE, "p04", severity=0.85)
        cycle = s.trigger_on_event(event)
        assert cycle is not None
        assert cycle.event_count == 1

    def test_trigger_on_event_no_product(self):
        s = CycleScheduler()
        event = make_event(product_id="")
        assert s.trigger_on_event(event) is None

    def test_trigger_on_event_force(self):
        s = CycleScheduler()
        s.trigger_cycle("p04")
        event = make_event(product_id="p04")
        cycle = s.trigger_on_event(event, force=True)
        assert cycle is not None

    def test_advance_all_cycles(self):
        s = CycleScheduler()
        cycle = s.schedule_product_cycle("p04")
        s._runtime.transition_cycle(cycle, GrowthState.OBSERVE)
        results = s.advance_all_cycles()
        assert len(results) >= 1

    def test_get_product_schedule(self):
        s = CycleScheduler()
        s.schedule_product_cycle("p04", interval_minutes=45)
        schedule = s.get_product_schedule("p04")
        assert schedule is not None
        assert schedule["interval_minutes"] == 45

    def test_get_product_schedule_not_found(self):
        s = CycleScheduler()
        assert s.get_product_schedule("p99") is None

    def test_update_schedule(self):
        s = CycleScheduler()
        s.schedule_product_cycle("p04", interval_minutes=30)
        assert s.update_schedule("p04", interval_minutes=60)
        schedule = s.get_product_schedule("p04")
        assert schedule["interval_minutes"] == 60

    def test_remove_schedule(self):
        s = CycleScheduler()
        s.schedule_product_cycle("p04")
        assert s.remove_schedule("p04")
        assert s.scheduled_product_count == 0

    def test_get_statistics(self):
        s = CycleScheduler()
        s.schedule_product_cycle("p04", interval_minutes=30)
        stats = s.get_statistics()
        assert stats["scheduled_products"] == 1
        assert "p04" in stats["schedules"]

    def test_scheduler_repr(self):
        s = CycleScheduler()
        s.schedule_product_cycle("p04")
        r = repr(s)
        assert "CycleScheduler" in r
        assert "1" in r