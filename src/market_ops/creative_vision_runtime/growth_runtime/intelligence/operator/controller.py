"""E15.3.1 Operator Controller — 核心控制器.

Autonomous Operator 的入口层，协调:
  - GoalManager:        目标管理
  - ObservationCollector: 环境观察
  - TriggerEngine:       触发判断
  - LifecycleManager:    生命周期
  - Intelligence Layer:  E15.2 推理决策
  - MemoryBridge:        经验记录

运行循环:
  observe → evaluate_goals → check_triggers → think → act → learn
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .goal import GoalManager
from .lifecycle import LifecycleManager
from .memory import OperatorMemoryBridge
from .models import (
    CycleOutcome,
    GoalStatus,
    OperatorCycleResult,
    OperatorGoal,
    OperatorObservation,
    OperatorSession,
    OperatorState,
    OperatorTrigger,
    TriggerType,
)
from .observation import ObservationCollector
from .trigger import TriggerEngine


# ═══════════════════════════════════════════════════════════════
# Operator Controller
# ═══════════════════════════════════════════════════════════════


class OperatorController:
    """E15.3.1 Operator Controller.

    Autonomous Operator 的核心控制器，管理完整的 observe→think→act→learn 循环。

    用法:
        controller = OperatorController()
        controller.setup_goal(goal)
        controller.start()
        controller.run_cycle()
    """

    def __init__(
        self,
        goal_manager: GoalManager | None = None,
        observation_collector: ObservationCollector | None = None,
        trigger_engine: TriggerEngine | None = None,
        lifecycle: LifecycleManager | None = None,
        memory_bridge: OperatorMemoryBridge | None = None,
    ):
        self._goal_manager = goal_manager or GoalManager()
        self._observation_collector = observation_collector or ObservationCollector()
        self._trigger_engine = trigger_engine or TriggerEngine()
        self._lifecycle = lifecycle or LifecycleManager()
        self._memory_bridge = memory_bridge or OperatorMemoryBridge()

        self._session = OperatorSession()
        self._cycle_results: list[OperatorCycleResult] = []
        self._last_observation: OperatorObservation | None = None
        self._last_triggered_at: str | None = None

    # ── Properties ──────────────────────────────────────────────

    @property
    def goal_manager(self) -> GoalManager:
        return self._goal_manager

    @property
    def observation_collector(self) -> ObservationCollector:
        return self._observation_collector

    @property
    def trigger_engine(self) -> TriggerEngine:
        return self._trigger_engine

    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    @property
    def memory_bridge(self) -> OperatorMemoryBridge:
        return self._memory_bridge

    @property
    def state(self) -> OperatorState:
        return self._lifecycle.state

    @property
    def session(self) -> OperatorSession:
        return self._session

    # ── Setup ───────────────────────────────────────────────────

    def setup_goal(self, goal: OperatorGoal) -> None:
        """设置 Operator 目标."""
        self._goal_manager.add_goal(goal)
        self._session.goals.append(goal)

    def setup_trigger(self, trigger: OperatorTrigger) -> None:
        """设置触发器."""
        self._trigger_engine.add_trigger(trigger)
        self._session.triggers.append(trigger)

    def register_observation_source(self, name: str, metrics: dict[str, float]) -> None:
        """注册观察数据源."""
        self._observation_collector.register_source(name, metrics)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> bool:
        """启动 Operator."""
        if not self._lifecycle.start():
            return False
        self._session.state = self._lifecycle.state
        self._session.started_at = self._lifecycle.started_at
        return True

    def pause(self) -> bool:
        """暂停 Operator."""
        if not self._lifecycle.pause():
            return False
        self._session.state = self._lifecycle.state
        self._session.paused_at = self._lifecycle.paused_at
        return True

    def resume(self) -> bool:
        """恢复 Operator."""
        if not self._lifecycle.resume():
            return False
        self._session.state = self._lifecycle.state
        return True

    def stop(self) -> bool:
        """停止 Operator."""
        if not self._lifecycle.stop():
            return False
        self._session.state = self._lifecycle.state
        self._session.stopped_at = self._lifecycle.stopped_at
        return True

    # ── Core Cycle ──────────────────────────────────────────────

    def run_cycle(self) -> OperatorCycleResult:
        """执行一个完整运行周期.

        流程:
          1. OBSERVE:  收集环境观察
          2. EVALUATE: 更新目标进度
          3. CHECK:    检查触发器
          4. THINK:    推理决策
          5. ACT:      执行动作
          6. LEARN:    记录经验

        Returns:
            OperatorCycleResult
        """
        self._session.current_cycle += 1
        self._session.total_cycles += 1
        cycle_number = self._session.current_cycle

        try:
            # 1. OBSERVE
            self._lifecycle.transition(OperatorState.OBSERVING)
            observation = self._observation_collector.collect()
            self._last_observation = observation

            # 2. EVALUATE GOALS
            updated_goals = self._goal_manager.update_from_observation(observation)
            goals_updated = [g.goal_id for g in updated_goals]

            # 3. CHECK TRIGGERS
            self._lifecycle.transition(OperatorState.THINKING)
            fired = self._trigger_engine.evaluate(observation, self._last_triggered_at)
            triggered_by = None
            if fired:
                triggered_by = fired[0].trigger_id
                self._last_triggered_at = fired[0].last_triggered

            # 4. DECIDE (E15.2 Intelligence)
            self._lifecycle.transition(OperatorState.DECIDING)
            decision, action = self._make_decision(observation, fired)

            # 5. ACT (E15.1 Execution)
            self._lifecycle.transition(OperatorState.EXECUTING)
            result, outcome, error = self._execute_action(action)

            # 6. LEARN
            self._lifecycle.transition(OperatorState.LEARNING)
            self._record_experience(cycle_number, observation, triggered_by,
                                    updated_goals, decision, action, result, outcome, error)

            # 回到观察
            self._lifecycle.transition(OperatorState.OBSERVING)
            self._session.state = self._lifecycle.state

            cycle_result = OperatorCycleResult(
                cycle_number=cycle_number,
                observation=observation,
                triggered_by=triggered_by,
                goals_updated=goals_updated,
                decision=decision,
                action=action,
                result=result,
                outcome=outcome,
                error=error,
            )

        except Exception as e:
            self._lifecycle.error()
            self._session.state = self._lifecycle.state
            cycle_result = OperatorCycleResult(
                cycle_number=cycle_number,
                outcome=CycleOutcome.ERROR,
                error=str(e),
            )

        self._cycle_results.append(cycle_result)
        return cycle_result

    # ── Decision & Execution ────────────────────────────────────

    def _make_decision(
        self,
        observation: OperatorObservation,
        fired_triggers: list[OperatorTrigger],
    ) -> tuple[str | None, dict[str, Any]]:
        """决策 — 连接 E15.2 Intelligence Layer.

        Args:
            observation:    当前观察
            fired_triggers: 触发的触发器

        Returns:
            (decision, action)
        """
        if not fired_triggers:
            return None, {}

        trigger = fired_triggers[0]
        active_goals = self._goal_manager.get_active_goals()

        # 根据触发器类型生成决策
        if trigger.type == TriggerType.ANOMALY:
            metric = trigger.condition.get("metric", "")
            if active_goals:
                goal = active_goals[0]
                return (
                    "anomaly_response",
                    {
                        "action_type": "anomaly_response",
                        "metric": metric,
                        "goal": goal.name,
                        "trigger": trigger.name,
                    },
                )

        if trigger.type == TriggerType.EVENT:
            return (
                "event_response",
                {
                    "action_type": "event_response",
                    "trigger": trigger.name,
                },
            )

        if trigger.type == TriggerType.GOAL_PROGRESS:
            goal_id = trigger.condition.get("goal_id", "")
            goal = self._goal_manager.get_goal(goal_id)
            return (
                "goal_progress_check",
                {
                    "action_type": "goal_progress_check",
                    "goal": goal.name if goal else goal_id,
                    "trigger": trigger.name,
                },
            )

        # TIME trigger
        return (
            "scheduled_check",
            {
                "action_type": "scheduled_check",
                "trigger": trigger.name,
            },
        )

    def _execute_action(
        self, action: dict[str, Any]
    ) -> tuple[dict[str, Any], CycleOutcome, str | None]:
        """执行动作 — 连接 E15.1 Workflow Execution.

        Args:
            action: 动作定义

        Returns:
            (result, outcome, error)
        """
        if not action:
            return {}, CycleOutcome.NO_ACTION, None

        # 模拟执行 (实际连接 E15.1 Workflow)
        action_type = action.get("action_type", "")
        try:
            return {
                "action_type": action_type,
                "status": "executed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, CycleOutcome.SUCCESS, None
        except Exception as e:
            return {}, CycleOutcome.FAILURE, str(e)

    def _record_experience(
        self,
        cycle_number: int,
        observation: OperatorObservation,
        triggered_by: str | None,
        updated_goals: list[str],
        decision: str | None,
        action: dict[str, Any],
        result: dict[str, Any],
        outcome: CycleOutcome,
        error: str | None,
    ) -> None:
        """记录经验."""
        active_goals = self._goal_manager.get_active_goals()
        primary_goal = active_goals[0] if active_goals else None

        cycle_result = OperatorCycleResult(
            cycle_number=cycle_number,
            observation=observation,
            triggered_by=triggered_by,
            goals_updated=updated_goals,
            decision=decision,
            action=action,
            result=result,
            outcome=outcome,
            error=error,
        )

        self._memory_bridge.record(cycle_result, primary_goal)

    # ── Query ───────────────────────────────────────────────────

    def get_cycle_results(self) -> list[OperatorCycleResult]:
        """获取所有周期结果."""
        return list(self._cycle_results)

    def get_last_cycle(self) -> OperatorCycleResult | None:
        """获取最近一次周期结果."""
        if self._cycle_results:
            return self._cycle_results[-1]
        return None

    def get_last_observation(self) -> OperatorObservation | None:
        """获取最近一次观察."""
        return self._last_observation

    def get_status(self) -> dict[str, Any]:
        """获取 Operator 状态摘要."""
        return {
            "state": self._lifecycle.state.value,
            "session": self._session.to_dict(),
            "goals": self._goal_manager.get_progress_summary(),
            "triggers": len(self._trigger_engine.get_all_triggers()),
            "cycles": self._session.total_cycles,
            "memory": self._memory_bridge.get_summary(),
            "last_observation": (
                self._last_observation.to_dict() if self._last_observation else None
            ),
        }


__all__ = ["OperatorController"]