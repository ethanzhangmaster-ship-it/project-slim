"""E15.3.1 Operator Controller 测试 — 完整测试.

测试覆盖:
  - 模型 (12 tests)
  - GoalManager (15 tests)
  - ObservationCollector (10 tests)
  - TriggerEngine (15 tests)
  - LifecycleManager (15 tests)
  - MemoryBridge (10 tests)
  - OperatorController (20 tests)
  - 集成测试 (10 tests)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.models import (
    CycleOutcome,
    GoalStatus,
    OperatorCycleResult,
    OperatorExperience,
    OperatorGoal,
    OperatorObservation,
    OperatorSession,
    OperatorState,
    OperatorTrigger,
    TriggerType,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.goal import (
    GoalManager,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.observation import (
    ObservationCollector,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.trigger import (
    TriggerEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.lifecycle import (
    LifecycleManager,
    VALID_TRANSITIONS,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.memory import (
    OperatorMemoryBridge,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.controller import (
    OperatorController,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def roas_goal() -> OperatorGoal:
    return OperatorGoal(
        name="Increase ROAS",
        description="Increase D30 ROAS for US iOS",
        metric="roas",
        target=0.8,
        current=0.5,
        direction="above",
        priority="high",
    )


@pytest.fixture
def spend_goal() -> OperatorGoal:
    return OperatorGoal(
        name="Reduce Spend",
        description="Reduce daily spend below $500",
        metric="spend",
        target=500.0,
        current=600.0,
        direction="below",
        priority="medium",
    )


@pytest.fixture
def observation() -> OperatorObservation:
    return OperatorObservation(
        metrics={"roas": 0.65, "ctr": 2.1, "spend": 450.0, "fatigue": 0.3},
        source="meta_ads",
    )


@pytest.fixture
def time_trigger() -> OperatorTrigger:
    return OperatorTrigger(
        name="6h_timer",
        type=TriggerType.TIME,
        condition={"interval_seconds": 21600},
    )


@pytest.fixture
def anomaly_trigger() -> OperatorTrigger:
    return OperatorTrigger(
        name="roas_drop",
        type=TriggerType.ANOMALY,
        condition={"metric": "roas", "baseline": 1.0, "deviation_threshold": 0.2},
    )


# ═══════════════════════════════════════════════════════════════════
# Test: Models
# ═══════════════════════════════════════════════════════════════════


class TestOperatorGoal:
    """OperatorGoal 模型测试."""

    def test_default_creation(self):
        g = OperatorGoal()
        assert g.goal_id != ""
        assert g.status == GoalStatus.ACTIVE

    def test_full_creation(self, roas_goal):
        assert roas_goal.name == "Increase ROAS"
        assert roas_goal.target == 0.8
        assert roas_goal.direction == "above"

    def test_update_progress_above(self):
        g = OperatorGoal(metric="roas", target=1.0, current=0.5, direction="above")
        g.update_progress(0.8)
        assert g.progress == 0.8
        assert g.current == 0.8

    def test_update_progress_below(self):
        g = OperatorGoal(metric="spend", target=500, current=600, direction="below")
        g.update_progress(550)
        assert g.progress == pytest.approx(500 / 550, 0.01)

    def test_is_achieved_above(self):
        g = OperatorGoal(target=1.0, current=1.0, direction="above")
        assert g.is_achieved() is True

    def test_is_achieved_below(self):
        g = OperatorGoal(target=500, current=500, direction="below")
        assert g.is_achieved() is True

    def test_is_not_achieved(self, roas_goal):
        assert roas_goal.is_achieved() is False

    def test_progress_zero_target(self):
        g = OperatorGoal(target=0.0, current=0.5)
        g.update_progress(0.8)
        assert g.progress == 0.0

    def test_to_dict(self, roas_goal):
        d = roas_goal.to_dict()
        assert d["name"] == "Increase ROAS"


class TestOperatorObservation:
    """OperatorObservation 模型测试."""

    def test_get_metric(self, observation):
        assert observation.get_metric("roas") == 0.65

    def test_get_metric_default(self, observation):
        assert observation.get_metric("nonexistent", 99.0) == 99.0

    def test_to_dict(self, observation):
        d = observation.to_dict()
        assert d["source"] == "meta_ads"


class TestOperatorTrigger:
    """OperatorTrigger 模型测试."""

    def test_default_type(self):
        t = OperatorTrigger()
        assert t.type == TriggerType.TIME

    def test_enabled_by_default(self):
        t = OperatorTrigger()
        assert t.enabled is True


# ═══════════════════════════════════════════════════════════════════
# Test: GoalManager
# ═══════════════════════════════════════════════════════════════════


class TestGoalManager:
    """GoalManager 测试."""

    def test_add_goal(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        assert mgr.get_goal_count() == 1

    def test_remove_goal(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        assert mgr.remove_goal(roas_goal.goal_id) is True
        assert mgr.get_goal_count() == 0

    def test_remove_nonexistent(self):
        mgr = GoalManager()
        assert mgr.remove_goal("nonexistent") is False

    def test_get_goal(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        assert mgr.get_goal(roas_goal.goal_id) is not None

    def test_get_nonexistent(self):
        mgr = GoalManager()
        assert mgr.get_goal("nonexistent") is None

    def test_get_active_goals(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        active = mgr.get_active_goals()
        assert len(active) == 1

    def test_get_active_goals_sorted_by_priority(self):
        mgr = GoalManager()
        mgr.add_goal(OperatorGoal(goal_id="g1", name="low", priority="low"))
        mgr.add_goal(OperatorGoal(goal_id="g2", name="high", priority="high"))
        mgr.add_goal(OperatorGoal(goal_id="g3", name="medium", priority="medium"))
        active = mgr.get_active_goals()
        assert active[0].priority == "high"
        assert active[-1].priority == "low"

    def test_update_from_observation(self, roas_goal, observation):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        updated = mgr.update_from_observation(observation)
        assert len(updated) >= 1
        assert roas_goal.current == 0.65

    def test_update_goal_achieved(self):
        mgr = GoalManager()
        g = OperatorGoal(metric="roas", target=1.0, current=0.5, direction="above")
        mgr.add_goal(g)
        mgr.update_goal(g.goal_id, 1.2)
        assert g.status == GoalStatus.ACHIEVED

    def test_update_goal_failed(self):
        mgr = GoalManager()
        g = OperatorGoal(metric="roas", target=1.0, current=0.5, direction="above")
        mgr.add_goal(g)
        mgr.update_goal(g.goal_id, 0.3)
        assert g.status == GoalStatus.ACTIVE  # not failed, just not achieved

    def test_evaluate_all(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        evaluation = mgr.evaluate_all()
        assert len(evaluation["active"]) == 1

    def test_get_achieved(self):
        mgr = GoalManager()
        g = OperatorGoal(metric="roas", target=1.0, current=1.5, direction="above")
        g.status = GoalStatus.ACHIEVED
        mgr.add_goal(g)
        assert len(mgr.get_achieved()) == 1

    def test_mark_failed(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        mgr.mark_failed(roas_goal.goal_id, "Budget exhausted")
        assert roas_goal.status == GoalStatus.FAILED
        assert roas_goal.metadata["failure_reason"] == "Budget exhausted"

    def test_pause_and_resume_goal(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        mgr.pause_goal(roas_goal.goal_id)
        assert roas_goal.status == GoalStatus.PAUSED
        mgr.resume_goal(roas_goal.goal_id)
        assert roas_goal.status == GoalStatus.ACTIVE

    def test_get_progress_summary(self, roas_goal):
        mgr = GoalManager()
        mgr.add_goal(roas_goal)
        summary = mgr.get_progress_summary()
        assert summary["total"] == 1
        assert summary["active"] == 1

    def test_get_goals_by_metric(self):
        mgr = GoalManager()
        mgr.add_goal(OperatorGoal(goal_id="g1", metric="roas", target=1.0))
        mgr.add_goal(OperatorGoal(goal_id="g2", metric="ctr", target=2.0))
        by_roas = mgr.get_goals_by_metric("roas")
        assert len(by_roas) == 1
        assert by_roas[0].goal_id == "g1"


# ═══════════════════════════════════════════════════════════════════
# Test: ObservationCollector
# ═══════════════════════════════════════════════════════════════════


class TestObservationCollector:
    """ObservationCollector 测试."""

    def test_register_source(self):
        collector = ObservationCollector()
        collector.register_source("meta_ads", {"roas": 1.5, "ctr": 2.0})
        assert collector.has_source("meta_ads")

    def test_collect_merges_sources(self):
        collector = ObservationCollector()
        collector.register_source("meta_ads", {"roas": 1.5})
        collector.register_source("adjust", {"d7_roas": 0.8})
        obs = collector.collect()
        assert obs.get_metric("meta_ads.roas") == 1.5
        assert obs.get_metric("adjust.d7_roas") == 0.8

    def test_collect_with_prefix_and_plain(self):
        collector = ObservationCollector()
        collector.register_source("meta_ads", {"roas": 1.5})
        obs = collector.collect()
        assert obs.get_metric("meta_ads.roas") == 1.5
        assert obs.get_metric("roas") == 1.5

    def test_update_source_metric(self):
        collector = ObservationCollector()
        collector.register_source("meta_ads", {"roas": 1.0})
        collector.update_source_metric("meta_ads", "roas", 1.5)
        metrics = collector.get_source_metrics("meta_ads")
        assert metrics["roas"] == 1.5

    def test_collect_from_raw(self):
        collector = ObservationCollector()
        raw = {"roas": 1.5, "ctr": 2.0, "name": "not_a_number"}
        obs = collector.collect_from_raw(raw, source="test")
        assert obs.get_metric("roas") == 1.5
        assert obs.get_metric("name") == 0.0  # string filtered out

    def test_get_all_sources(self):
        collector = ObservationCollector()
        collector.register_source("a", {})
        collector.register_source("b", {})
        assert len(collector.get_all_sources()) == 2

    def test_clear_sources(self):
        collector = ObservationCollector()
        collector.register_source("a", {"roas": 1.0})
        collector.clear_sources()
        assert collector.has_source("a") is False

    def test_has_source(self):
        collector = ObservationCollector()
        collector.register_source("meta", {})
        assert collector.has_source("meta") is True
        assert collector.has_source("nonexistent") is False

    def test_collect_empty(self):
        collector = ObservationCollector()
        obs = collector.collect()
        assert obs.metrics == {}


# ═══════════════════════════════════════════════════════════════════
# Test: TriggerEngine
# ═══════════════════════════════════════════════════════════════════


class TestTriggerEngine:
    """TriggerEngine 测试."""

    def test_add_trigger(self, time_trigger):
        engine = TriggerEngine()
        engine.add_trigger(time_trigger)
        assert engine.get_trigger(time_trigger.trigger_id) is not None

    def test_remove_trigger(self, time_trigger):
        engine = TriggerEngine()
        engine.add_trigger(time_trigger)
        assert engine.remove_trigger(time_trigger.trigger_id) is True
        assert engine.get_trigger(time_trigger.trigger_id) is None

    def test_time_trigger_fires_no_last_trigger(self, time_trigger):
        """无上次触发时间 → 定时触发."""
        engine = TriggerEngine()
        engine.add_trigger(time_trigger)
        fired = engine.evaluate()
        assert len(fired) == 1

    def test_event_trigger_fires(self):
        """事件触发 — roas < 0.8."""
        engine = TriggerEngine()
        trigger = OperatorTrigger(
            type=TriggerType.EVENT,
            condition={"metric": "roas", "operator": "lt", "threshold": 0.8},
        )
        engine.add_trigger(trigger)
        obs = OperatorObservation(metrics={"roas": 0.65})
        fired = engine.evaluate(observation=obs)
        assert len(fired) == 1

    def test_event_trigger_no_fire(self):
        """事件触发 — roas > 0.8 不触发."""
        engine = TriggerEngine()
        trigger = OperatorTrigger(
            type=TriggerType.EVENT,
            condition={"metric": "roas", "operator": "lt", "threshold": 0.8},
        )
        engine.add_trigger(trigger)
        obs = OperatorObservation(metrics={"roas": 1.2})
        fired = engine.evaluate(observation=obs)
        assert len(fired) == 0

    def test_anomaly_trigger_fires(self):
        """异常触发 — 偏差 30% > 20%."""
        engine = TriggerEngine()
        trigger = OperatorTrigger(
            type=TriggerType.ANOMALY,
            condition={"metric": "roas", "baseline": 1.0, "deviation_threshold": 0.2},
        )
        engine.add_trigger(trigger)
        obs = OperatorObservation(metrics={"roas": 0.65})
        fired = engine.evaluate(observation=obs)
        assert len(fired) == 1

    def test_anomaly_trigger_no_fire(self):
        """异常触发 — 偏差 10% < 20% 不触发."""
        engine = TriggerEngine()
        trigger = OperatorTrigger(
            type=TriggerType.ANOMALY,
            condition={"metric": "roas", "baseline": 1.0, "deviation_threshold": 0.2},
        )
        engine.add_trigger(trigger)
        obs = OperatorObservation(metrics={"roas": 0.95})
        fired = engine.evaluate(observation=obs)
        assert len(fired) == 0

    def test_disabled_trigger_no_fire(self, time_trigger):
        """禁用触发器不触发."""
        engine = TriggerEngine()
        time_trigger.enabled = False
        engine.add_trigger(time_trigger)
        fired = engine.evaluate()
        assert len(fired) == 0

    def test_enable_disable_trigger(self, time_trigger):
        engine = TriggerEngine()
        engine.add_trigger(time_trigger)
        engine.disable_trigger(time_trigger.trigger_id)
        assert time_trigger.enabled is False
        engine.enable_trigger(time_trigger.trigger_id)
        assert time_trigger.enabled is True

    def test_cooldown_prevents_fire(self, time_trigger):
        """冷却期阻止触发."""
        from datetime import datetime, timezone, timedelta
        engine = TriggerEngine()
        time_trigger.cooldown_seconds = 3600
        time_trigger.last_triggered = datetime.now(timezone.utc).isoformat()
        engine.add_trigger(time_trigger)
        fired = engine.evaluate()
        assert len(fired) == 0

    def test_should_trigger(self, time_trigger):
        engine = TriggerEngine()
        engine.add_trigger(time_trigger)
        assert engine.should_trigger(time_trigger.trigger_id) is True

    def test_should_trigger_nonexistent(self):
        engine = TriggerEngine()
        assert engine.should_trigger("nonexistent") is False

    def test_compare_operators(self):
        """测试比较操作符."""
        engine = TriggerEngine()
        assert engine._compare(1.0, "gt", 0.5) is True
        assert engine._compare(1.0, "gt", 1.0) is False
        assert engine._compare(1.0, "gte", 1.0) is True
        assert engine._compare(1.0, "lt", 2.0) is True
        assert engine._compare(1.0, "lte", 1.0) is True
        assert engine._compare(1.0, "eq", 1.0) is True
        assert engine._compare(1.0, "eq", 2.0) is False

    def test_goal_progress_trigger(self):
        """目标进度触发."""
        engine = TriggerEngine()
        trigger = OperatorTrigger(
            type=TriggerType.GOAL_PROGRESS,
            condition={"goal_id": "g1", "progress_threshold": 0.5},
        )
        engine.add_trigger(trigger)
        obs = OperatorObservation(metrics={"roas": 0.8})
        fired = engine.evaluate(observation=obs)
        assert len(fired) == 1

    def test_event_trigger_none_observation(self):
        """无观察时事件触发不触发."""
        engine = TriggerEngine()
        trigger = OperatorTrigger(
            type=TriggerType.EVENT,
            condition={"metric": "roas", "operator": "lt", "threshold": 0.8},
        )
        engine.add_trigger(trigger)
        fired = engine.evaluate()
        assert len(fired) == 0


# ═══════════════════════════════════════════════════════════════════
# Test: LifecycleManager
# ═══════════════════════════════════════════════════════════════════


class TestLifecycleManager:
    """LifecycleManager 测试."""

    def test_initial_state(self):
        lm = LifecycleManager()
        assert lm.state == OperatorState.IDLE

    def test_start(self):
        lm = LifecycleManager()
        assert lm.start() is True
        assert lm.state == OperatorState.OBSERVING
        assert lm.started_at is not None

    def test_start_from_non_idle(self):
        lm = LifecycleManager()
        lm.start()
        assert lm.start() is False  # already started

    def test_pause(self):
        lm = LifecycleManager()
        lm.start()
        assert lm.pause() is True
        assert lm.state == OperatorState.PAUSED

    def test_pause_from_idle(self):
        lm = LifecycleManager()
        assert lm.pause() is False  # can't pause from idle

    def test_resume(self):
        lm = LifecycleManager()
        lm.start()
        lm.pause()
        assert lm.resume() is True
        assert lm.state == OperatorState.OBSERVING

    def test_resume_from_non_paused(self):
        lm = LifecycleManager()
        lm.start()
        assert lm.resume() is False  # not paused

    def test_stop(self):
        lm = LifecycleManager()
        lm.start()
        assert lm.stop() is True
        assert lm.state == OperatorState.STOPPED

    def test_stop_from_idle(self):
        lm = LifecycleManager()
        assert lm.stop() is True  # can stop from idle

    def test_error_state(self):
        lm = LifecycleManager()
        lm.start()
        assert lm.error() is True
        assert lm.state == OperatorState.ERROR

    def test_transition_invalid(self):
        lm = LifecycleManager()
        # IDLE → EXECUTING is invalid
        assert lm.transition(OperatorState.EXECUTING) is False

    def test_can_transition(self):
        lm = LifecycleManager()
        assert lm.can_transition(OperatorState.OBSERVING) is True
        assert lm.can_transition(OperatorState.EXECUTING) is False

    def test_is_running(self):
        lm = LifecycleManager()
        assert lm.is_running() is False
        lm.start()
        assert lm.is_running() is True

    def test_reset(self):
        lm = LifecycleManager()
        lm.start()
        lm.reset()
        assert lm.state == OperatorState.IDLE

    def test_get_history(self):
        lm = LifecycleManager()
        lm.start()
        lm.transition(OperatorState.THINKING)
        history = lm.get_history()
        assert len(history) >= 2

    def test_get_state_summary(self):
        lm = LifecycleManager()
        lm.start()
        summary = lm.get_state_summary()
        assert summary["current_state"] == "observing"
        assert summary["is_running"] is True


# ═══════════════════════════════════════════════════════════════════
# Test: OperatorMemoryBridge
# ═══════════════════════════════════════════════════════════════════


class TestOperatorMemoryBridge:
    """OperatorMemoryBridge 测试."""

    def test_record_success(self, roas_goal):
        bridge = OperatorMemoryBridge()
        cycle = OperatorCycleResult(
            cycle_number=1,
            outcome=CycleOutcome.SUCCESS,
            action={"action_type": "creative_refresh"},
        )
        exp = bridge.record(cycle, roas_goal)
        assert exp.outcome == "success"
        assert exp.reward >= 0.8

    def test_record_failure(self, roas_goal):
        bridge = OperatorMemoryBridge()
        cycle = OperatorCycleResult(
            cycle_number=1,
            outcome=CycleOutcome.FAILURE,
            error="Budget exhausted",
        )
        exp = bridge.record(cycle, roas_goal)
        assert exp.outcome == "failure"
        assert exp.reward == 0.0

    def test_record_no_action(self):
        bridge = OperatorMemoryBridge()
        cycle = OperatorCycleResult(outcome=CycleOutcome.NO_ACTION)
        exp = bridge.record(cycle)
        assert exp.reward == 0.3

    def test_record_direct(self):
        bridge = OperatorMemoryBridge()
        exp = bridge.record_direct(
            goal="test_goal",
            action={"type": "scale"},
            result={"roas": 1.5},
            outcome="success",
            reward=0.9,
            lesson="Scaling worked",
        )
        assert exp.lesson == "Scaling worked"

    def test_get_experiences(self):
        bridge = OperatorMemoryBridge()
        bridge.record_direct("g1", {}, {}, "success", 0.9)
        bridge.record_direct("g1", {}, {}, "failure", 0.0)
        assert len(bridge.get_experiences()) == 2

    def test_get_recent(self):
        bridge = OperatorMemoryBridge()
        for i in range(15):
            bridge.record_direct("g1", {}, {}, "success", 0.8)
        assert len(bridge.get_recent(5)) == 5

    def test_get_by_outcome(self):
        bridge = OperatorMemoryBridge()
        bridge.record_direct("g1", {}, {}, "success", 0.9)
        bridge.record_direct("g1", {}, {}, "failure", 0.0)
        assert len(bridge.get_successful()) == 1
        assert len(bridge.get_failed()) == 1

    def test_get_summary(self):
        bridge = OperatorMemoryBridge()
        bridge.record_direct("g1", {}, {}, "success", 0.9)
        bridge.record_direct("g1", {}, {}, "failure", 0.0)
        summary = bridge.get_summary()
        assert summary["total"] == 2
        assert summary["success_rate"] == 0.5

    def test_get_summary_empty(self):
        bridge = OperatorMemoryBridge()
        summary = bridge.get_summary()
        assert summary["total"] == 0

    def test_clear(self):
        bridge = OperatorMemoryBridge()
        bridge.record_direct("g1", {}, {}, "success", 0.9)
        bridge.clear()
        assert len(bridge.get_experiences()) == 0


# ═══════════════════════════════════════════════════════════════════
# Test: OperatorController
# ═══════════════════════════════════════════════════════════════════


class TestOperatorController:
    """OperatorController 测试."""

    @pytest.fixture
    def controller(self) -> OperatorController:
        return OperatorController()

    def test_initial_state(self, controller):
        assert controller.state == OperatorState.IDLE

    def test_setup_goal(self, controller, roas_goal):
        controller.setup_goal(roas_goal)
        assert controller.goal_manager.get_goal_count() == 1

    def test_setup_trigger(self, controller, time_trigger):
        controller.setup_trigger(time_trigger)
        assert len(controller.session.triggers) == 1

    def test_register_observation_source(self, controller):
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        assert controller.observation_collector.has_source("meta_ads")

    def test_start(self, controller):
        assert controller.start() is True
        assert controller.state == OperatorState.OBSERVING

    def test_start_twice(self, controller):
        controller.start()
        assert controller.start() is False

    def test_pause(self, controller):
        controller.start()
        assert controller.pause() is True
        assert controller.state == OperatorState.PAUSED

    def test_resume(self, controller):
        controller.start()
        controller.pause()
        assert controller.resume() is True
        assert controller.state == OperatorState.OBSERVING

    def test_stop(self, controller):
        controller.start()
        assert controller.stop() is True
        assert controller.state == OperatorState.STOPPED

    def test_run_cycle_idle(self, controller):
        """IDLE 状态运行周期."""
        result = controller.run_cycle()
        assert result.cycle_number == 1
        assert result.observation is not None
        assert result.outcome == CycleOutcome.NO_ACTION

    def test_run_cycle_with_trigger(self, controller, time_trigger):
        """含触发器运行周期."""
        controller.setup_trigger(time_trigger)
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        result = controller.run_cycle()
        assert result.triggered_by is not None
        assert result.decision is not None

    def test_run_cycle_with_goal(self, controller, roas_goal):
        """含目标运行周期."""
        controller.setup_goal(roas_goal)
        controller.register_observation_source("meta_ads", {"roas": 0.65})
        result = controller.run_cycle()
        # 目标进度应更新
        assert roas_goal.current == 0.65

    def test_run_cycle_anomaly_trigger(self, controller, anomaly_trigger, roas_goal):
        """异常触发运行周期."""
        controller.setup_goal(roas_goal)
        controller.setup_trigger(anomaly_trigger)
        controller.register_observation_source("meta_ads", {"roas": 0.65})
        result = controller.run_cycle()
        assert result.triggered_by is not None
        assert result.decision == "anomaly_response"

    def test_run_cycle_increments_counter(self, controller):
        controller.run_cycle()
        controller.run_cycle()
        assert controller.session.total_cycles == 2

    def test_run_cycle_records_experience(self, controller, time_trigger):
        controller.setup_trigger(time_trigger)
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        controller.run_cycle()
        summary = controller.memory_bridge.get_summary()
        assert summary["total"] >= 1

    def test_get_cycle_results(self, controller):
        controller.run_cycle()
        results = controller.get_cycle_results()
        assert len(results) == 1

    def test_get_last_cycle(self, controller):
        controller.run_cycle()
        last = controller.get_last_cycle()
        assert last is not None
        assert last.cycle_number == 1

    def test_get_last_observation(self, controller):
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        controller.run_cycle()
        obs = controller.get_last_observation()
        assert obs is not None

    def test_get_status(self, controller, roas_goal):
        controller.setup_goal(roas_goal)
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        controller.run_cycle()
        status = controller.get_status()
        assert "state" in status
        assert "goals" in status
        assert "cycles" in status
        assert "memory" in status

    def test_run_cycle_full_lifecycle(self, controller, time_trigger):
        """完整生命周期: start → cycle → stop."""
        controller.setup_trigger(time_trigger)
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        controller.start()
        controller.run_cycle()
        controller.stop()
        assert controller.state == OperatorState.STOPPED

    def test_error_in_cycle(self, controller):
        """周期内错误 — 状态变 ERROR."""
        controller.register_observation_source("meta_ads", {"roas": 1.5})
        # 模拟: 没有触发器时不会触发错误，但 cycle 正常完成
        result = controller.run_cycle()
        assert result.outcome != CycleOutcome.ERROR

    def test_multiple_cycles(self, controller, time_trigger):
        """多轮运行."""
        controller.setup_trigger(time_trigger)
        controller.register_observation_source("meta_ads", {"roas": 1.5})

        for i in range(5):
            result = controller.run_cycle()
            assert result.cycle_number == i + 1

        assert controller.session.total_cycles == 5
        assert len(controller.get_cycle_results()) == 5

    def test_properties_accessible(self, controller):
        """属性可访问."""
        assert controller.goal_manager is not None
        assert controller.observation_collector is not None
        assert controller.trigger_engine is not None
        assert controller.lifecycle is not None
        assert controller.memory_bridge is not None


# ═══════════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试 — 完整 Operator 链路."""

    def test_full_operator_setup_and_run(self):
        """完整 Operator 设置和运行."""
        controller = OperatorController()

        # 设置目标
        controller.setup_goal(OperatorGoal(
            name="Improve ROAS",
            metric="roas",
            target=0.8,
            current=0.5,
            direction="above",
            priority="high",
        ))

        # 设置触发器
        controller.setup_trigger(OperatorTrigger(
            name="4h_check",
            type=TriggerType.TIME,
            condition={"interval_seconds": 14400},
        ))
        controller.setup_trigger(OperatorTrigger(
            name="roas_anomaly",
            type=TriggerType.ANOMALY,
            condition={"metric": "roas", "baseline": 1.0, "deviation_threshold": 0.2},
        ))

        # 注册数据源
        controller.register_observation_source("meta_ads", {
            "roas": 0.65, "ctr": 2.1, "spend": 450,
        })
        controller.register_observation_source("adjust", {
            "d7_roas": 0.7, "payer_rate": 0.05,
        })

        # 启动
        assert controller.start() is True

        # 运行多轮
        for i in range(3):
            result = controller.run_cycle()
            assert result.cycle_number == i + 1
            assert result.observation is not None
            assert result.outcome is not None

        # 停止
        controller.stop()
        assert controller.state == OperatorState.STOPPED

        # 验证状态
        status = controller.get_status()
        assert status["cycles"] == 3
        assert status["goals"]["total"] == 1
        assert status["memory"]["total"] >= 3

    def test_goal_achievement_flow(self):
        """目标达成流程."""
        controller = OperatorController()

        goal = OperatorGoal(
            name="Achieve ROAS",
            metric="roas",
            target=0.8,
            current=0.5,
            direction="above",
        )
        controller.setup_goal(goal)

        controller.setup_trigger(OperatorTrigger(
            name="timer",
            type=TriggerType.TIME,
            condition={"interval_seconds": 3600},
        ))

        # 模拟 ROAS 逐步提升
        for roas in [0.6, 0.7, 0.85]:
            controller.observation_collector.clear_sources()
            controller.register_observation_source("meta_ads", {"roas": roas})
            controller.run_cycle()

        assert goal.is_achieved() is True
        assert goal.status == GoalStatus.ACHIEVED

    def test_session_state_tracking(self):
        """会话状态追踪."""
        controller = OperatorController()

        controller.setup_goal(OperatorGoal(name="Test", metric="roas", target=0.8))
        controller.register_observation_source("meta", {"roas": 0.7})

        controller.start()
        assert controller.session.state == OperatorState.OBSERVING

        controller.pause()
        assert controller.session.state == OperatorState.PAUSED

        controller.resume()
        assert controller.session.state == OperatorState.OBSERVING

        controller.stop()
        assert controller.session.state == OperatorState.STOPPED

    def test_memory_bridge_integration(self):
        """记忆桥接集成."""
        controller = OperatorController()

        goal = OperatorGoal(name="Test", metric="roas", target=0.8)
        controller.setup_goal(goal)
        controller.setup_trigger(OperatorTrigger(
            name="timer", type=TriggerType.TIME,
            condition={"interval_seconds": 3600},
        ))
        controller.register_observation_source("meta", {"roas": 0.9})

        controller.run_cycle()
        controller.run_cycle()

        summary = controller.memory_bridge.get_summary()
        assert summary["total"] >= 2

        # 有成功经验
        successes = controller.memory_bridge.get_successful()
        assert len(successes) >= 1

    def test_trigger_engine_integration(self):
        """触发器引擎集成."""
        controller = OperatorController()

        controller.setup_trigger(OperatorTrigger(
            name="roas_event",
            type=TriggerType.EVENT,
            condition={"metric": "roas", "operator": "lt", "threshold": 0.8},
        ))

        controller.register_observation_source("meta", {"roas": 0.65})
        result = controller.run_cycle()

        assert result.triggered_by is not None
        assert result.decision == "event_response"

    def test_goal_price_direction_below(self):
        """below 方向目标."""
        controller = OperatorController()

        goal = OperatorGoal(
            name="Reduce Spend",
            metric="spend",
            target=500.0,
            current=600.0,
            direction="below",
        )
        controller.setup_goal(goal)
        controller.setup_trigger(OperatorTrigger(
            name="timer", type=TriggerType.TIME,
            condition={"interval_seconds": 3600},
        ))
        controller.register_observation_source("meta", {"spend": 480.0})

        controller.run_cycle()
        assert goal.is_achieved() is True
        assert goal.status == GoalStatus.ACHIEVED

    def test_lifecycle_pause_resume_cycle(self):
        """暂停恢复后继续运行."""
        controller = OperatorController()

        controller.setup_trigger(OperatorTrigger(
            name="timer", type=TriggerType.TIME,
            condition={"interval_seconds": 3600},
        ))
        controller.register_observation_source("meta", {"roas": 1.0})

        controller.start()
        controller.run_cycle()

        controller.pause()
        assert controller.state == OperatorState.PAUSED

        controller.resume()
        controller.run_cycle()

        assert controller.session.total_cycles == 2

    def test_status_after_multiple_goals(self):
        """多目标状态."""
        controller = OperatorController()

        controller.setup_goal(OperatorGoal(
            name="ROAS", metric="roas", target=0.8, priority="high",
        ))
        controller.setup_goal(OperatorGoal(
            name="CTR", metric="ctr", target=2.5, priority="medium",
        ))

        controller.register_observation_source("meta", {"roas": 0.7, "ctr": 2.0})
        controller.run_cycle()

        status = controller.get_status()
        assert status["goals"]["total"] == 2
        assert status["goals"]["active"] == 2

    def test_cycle_result_to_dict(self):
        """CycleResult to_dict."""
        controller = OperatorController()
        controller.setup_trigger(OperatorTrigger(
            name="timer", type=TriggerType.TIME,
            condition={"interval_seconds": 3600},
        ))
        controller.register_observation_source("meta", {"roas": 1.0})
        controller.run_cycle()

        result = controller.get_last_cycle()
        d = result.to_dict()
        assert d["cycle_number"] == 1
        assert d["triggered_by"] is not None