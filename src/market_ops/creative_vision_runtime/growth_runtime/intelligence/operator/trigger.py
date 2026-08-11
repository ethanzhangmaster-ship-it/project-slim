"""E15.3.1 Trigger Engine — 触发器引擎.

管理并评估触发器，决定何时触发 Operator 运行周期。

触发类型:
  - TIME:           定时触发 (interval_seconds)
  - EVENT:          事件触发 (metric + threshold)
  - GOAL_PROGRESS:  目标进度触发 (goal_id + progress_threshold)
  - ANOMALY:        异常触发 (metric + deviation_threshold)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    OperatorObservation,
    OperatorTrigger,
    TriggerType,
)


# ═══════════════════════════════════════════════════════════════
# Trigger Engine
# ═══════════════════════════════════════════════════════════════


class TriggerEngine:
    """E15.3.1 触发器引擎.

    评估各类触发器，返回触发原因。

    用法:
        engine = TriggerEngine()
        engine.add_trigger(trigger)
        fired = engine.evaluate(observation, last_trigger_time)
    """

    def __init__(self):
        self._triggers: dict[str, OperatorTrigger] = {}

    # ── CRUD ────────────────────────────────────────────────────

    def add_trigger(self, trigger: OperatorTrigger) -> None:
        """添加触发器."""
        self._triggers[trigger.trigger_id] = trigger

    def remove_trigger(self, trigger_id: str) -> bool:
        """删除触发器."""
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]
            return True
        return False

    def get_trigger(self, trigger_id: str) -> OperatorTrigger | None:
        """获取触发器."""
        return self._triggers.get(trigger_id)

    def get_all_triggers(self) -> list[OperatorTrigger]:
        """获取所有触发器."""
        return list(self._triggers.values())

    def enable_trigger(self, trigger_id: str) -> bool:
        """启用触发器."""
        t = self._triggers.get(trigger_id)
        if t:
            t.enabled = True
            return True
        return False

    def disable_trigger(self, trigger_id: str) -> bool:
        """禁用触发器."""
        t = self._triggers.get(trigger_id)
        if t:
            t.enabled = False
            return True
        return False

    # ── Evaluation ──────────────────────────────────────────────

    def evaluate(
        self,
        observation: OperatorObservation | None = None,
        last_triggered_at: str | None = None,
    ) -> list[OperatorTrigger]:
        """评估所有触发器，返回已触发的列表.

        Args:
            observation:       当前观察
            last_triggered_at: 上次触发时间

        Returns:
            list[OperatorTrigger]: 触发的触发器 (按优先级排序)
        """
        fired: list[OperatorTrigger] = []

        for trigger in self._triggers.values():
            if not trigger.enabled:
                continue

            if self._is_on_cooldown(trigger):
                continue

            if self._evaluate_trigger(trigger, observation, last_triggered_at):
                trigger.last_triggered = datetime.now(timezone.utc).isoformat()
                fired.append(trigger)

        return fired

    def should_trigger(
        self,
        trigger_id: str,
        observation: OperatorObservation | None = None,
        last_triggered_at: str | None = None,
    ) -> bool:
        """检查特定触发器是否应触发.

        Args:
            trigger_id:        触发器 ID
            observation:       当前观察
            last_triggered_at: 上次触发时间

        Returns:
            bool
        """
        trigger = self._triggers.get(trigger_id)
        if trigger is None:
            return False
        if not trigger.enabled:
            return False
        if self._is_on_cooldown(trigger):
            return False
        return self._evaluate_trigger(trigger, observation, last_triggered_at)

    # ── Internal Evaluation ─────────────────────────────────────

    def _evaluate_trigger(
        self,
        trigger: OperatorTrigger,
        observation: OperatorObservation | None,
        last_triggered_at: str | None,
    ) -> bool:
        """评估单个触发器."""
        if trigger.type == TriggerType.TIME:
            return self._evaluate_time(trigger, last_triggered_at)
        elif trigger.type == TriggerType.EVENT:
            return self._evaluate_event(trigger, observation)
        elif trigger.type == TriggerType.ANOMALY:
            return self._evaluate_anomaly(trigger, observation)
        elif trigger.type == TriggerType.GOAL_PROGRESS:
            return self._evaluate_goal_progress(trigger, observation)
        return False

    def _evaluate_time(
        self,
        trigger: OperatorTrigger,
        last_triggered_at: str | None,
    ) -> bool:
        """评估定时触发."""
        interval = trigger.condition.get("interval_seconds", 3600)
        if last_triggered_at is None:
            return True

        try:
            last_time = datetime.fromisoformat(last_triggered_at)
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            return elapsed >= interval
        except (ValueError, TypeError):
            return True

    def _evaluate_event(
        self,
        trigger: OperatorTrigger,
        observation: OperatorObservation | None,
    ) -> bool:
        """评估事件触发.

        condition 格式:
          {"metric": "roas", "operator": "lt", "threshold": 0.8}
        """
        if observation is None:
            return False

        cond = trigger.condition
        metric = cond.get("metric", "")
        op = cond.get("operator", "lt")
        threshold = cond.get("threshold", 0)

        value = observation.get_metric(metric)
        if value is None:
            return False

        return self._compare(value, op, threshold)

    def _evaluate_anomaly(
        self,
        trigger: OperatorTrigger,
        observation: OperatorObservation | None,
    ) -> bool:
        """评估异常触发.

        condition 格式:
          {"metric": "roas", "deviation_threshold": 0.2, "baseline": 1.0}
        """
        if observation is None:
            return False

        cond = trigger.condition
        metric = cond.get("metric", "")
        baseline = cond.get("baseline", 0)
        deviation_threshold = cond.get("deviation_threshold", 0.2)

        value = observation.get_metric(metric)
        if value is None or baseline == 0:
            return False

        deviation = abs(value - baseline) / abs(baseline)
        return deviation >= deviation_threshold

    def _evaluate_goal_progress(
        self,
        trigger: OperatorTrigger,
        observation: OperatorObservation | None,
    ) -> bool:
        """评估目标进度触发.

        condition 格式:
          {"goal_id": "...", "progress_threshold": 0.5}
        """
        # 目标进度触发依赖外部 GoalManager 传入检查
        # 此处仅检查 condition 完整性
        if observation is None:
            return False
        cond = trigger.condition
        return "goal_id" in cond and "progress_threshold" in cond

    # ── Helpers ─────────────────────────────────────────────────

    def _compare(self, value: float, op: str, threshold: float) -> bool:
        """比较操作."""
        ops = {
            "lt": lambda v, t: v < t,
            "lte": lambda v, t: v <= t,
            "gt": lambda v, t: v > t,
            "gte": lambda v, t: v >= t,
            "eq": lambda v, t: v == t,
        }
        return ops.get(op, lambda v, t: False)(value, threshold)

    def _is_on_cooldown(self, trigger: OperatorTrigger) -> bool:
        """检查是否在冷却期."""
        if trigger.cooldown_seconds <= 0:
            return False
        if trigger.last_triggered is None:
            return False

        try:
            last_time = datetime.fromisoformat(trigger.last_triggered)
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            return elapsed < trigger.cooldown_seconds
        except (ValueError, TypeError):
            return False


__all__ = ["TriggerEngine"]