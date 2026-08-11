"""E12.7.1 — Growth Runtime。

Growth OS 运行时管理器。

功能:
  - 全局状态管理
  - 周期生命周期管理
  - 任务队列管理
  - 运行时恢复
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .event_bus import EventBus
from .models import (
    ActionStatus,
    ActionType,
    EventPriority,
    EventType,
    GrowthAction,
    GrowthCycle,
    GrowthEvent,
    GrowthRuntime,
    GrowthState,
    _gen_id,
    _now,
    can_transition,
    get_next_state,
)


class RuntimeManager:
    """Growth OS 运行时管理器。

    管理整个 Growth OS 的生命周期和状态。
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        max_cycles: int = 100,
    ) -> None:
        self._runtime = GrowthRuntime()
        self._event_bus = event_bus or EventBus()
        self._max_cycles = max_cycles
        self._cycle_counter: dict[str, int] = {}

    # ── Cycle Management ───────────────────────────────────

    def create_cycle(
        self,
        product_id: str,
        cycle_number: int | None = None,
    ) -> GrowthCycle:
        """创建新的增长周期。

        Args:
            product_id:   产品 ID
            cycle_number: 周期编号（None 则自动递增）

        Returns:
            GrowthCycle
        """
        if cycle_number is None:
            self._cycle_counter[product_id] = self._cycle_counter.get(product_id, 0) + 1
            cycle_number = self._cycle_counter[product_id]

        cycle = GrowthCycle(
            product_id=product_id,
            cycle_number=cycle_number,
        )

        # 注册到运行时
        self._runtime.cycles[cycle.cycle_id] = cycle

        # 发布周期开始事件
        self._event_bus.publish(
            GrowthEvent(
                event_type=EventType.CYCLE_START,
                product_id=product_id,
                source="growth_runtime",
                priority=EventPriority.MEDIUM,
                data={"cycle_id": cycle.cycle_id, "cycle_number": cycle_number},
            )
        )

        return cycle

    def transition_cycle(
        self, cycle: GrowthCycle, new_state: GrowthState
    ) -> bool:
        """执行周期状态转移。

        Args:
            cycle:     目标周期
            new_state: 目标状态

        Returns:
            True 如果转移成功
        """
        if not cycle.transition_to(new_state):
            return False

        # 发布状态变更事件
        self._event_bus.publish(
            GrowthEvent(
                event_type=EventType.STATE_CHANGE,
                product_id=cycle.product_id,
                source="growth_runtime",
                priority=EventPriority.LOW,
                data={
                    "cycle_id": cycle.cycle_id,
                    "from_state": cycle.state_history[-2][0].value if len(cycle.state_history) >= 2 else "idle",
                    "to_state": new_state.value,
                },
            )
        )

        # 检查是否完成
        if new_state == GrowthState.COMPLETED:
            cycle.complete()
            self._archive_cycle(cycle)
            self._event_bus.publish(
                GrowthEvent(
                    event_type=EventType.CYCLE_COMPLETE,
                    product_id=cycle.product_id,
                    source="growth_runtime",
                    priority=EventPriority.MEDIUM,
                    data={"cycle_id": cycle.cycle_id},
                )
            )

        return True

    def advance_cycle(self, cycle: GrowthCycle) -> GrowthState | None:
        """推进周期到下一个状态。

        Args:
            cycle: 目标周期

        Returns:
            新状态，如果无法推进则返回 None
        """
        next_state = get_next_state(cycle.state)
        if next_state is None:
            return None
        if self.transition_cycle(cycle, next_state):
            return next_state
        return None

    def run_cycle_auto(self, cycle: GrowthCycle) -> list[GrowthState]:
        """自动推进周期走完所有状态。

        Returns:
            经过的状态列表
        """
        states: list[GrowthState] = [cycle.state]
        while True:
            next_state = get_next_state(cycle.state)
            if next_state is None:
                break
            if not self.transition_cycle(cycle, next_state):
                break
            states.append(next_state)
            if next_state == GrowthState.COMPLETED or next_state == GrowthState.ERROR:
                break
        return states

    def get_cycle(self, cycle_id: str) -> GrowthCycle | None:
        """获取周期。"""
        return self._runtime.cycles.get(cycle_id)

    def get_active_cycles(self) -> list[GrowthCycle]:
        """获取所有活跃周期。"""
        return [c for c in self._runtime.cycles.values() if c.is_active]

    def _archive_cycle(self, cycle: GrowthCycle) -> None:
        """归档完成的周期。"""
        if cycle.cycle_id in self._runtime.cycles:
            del self._runtime.cycles[cycle.cycle_id]
        self._runtime.cycle_history.append(cycle)

        # 限制历史长度
        if len(self._runtime.cycle_history) > self._max_cycles:
            self._runtime.cycle_history = self._runtime.cycle_history[-self._max_cycles:]

    # ── Action Management ──────────────────────────────────

    def create_action(
        self,
        action_type: ActionType,
        product_id: str = "",
        target: str = "",
        params: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.MEDIUM,
    ) -> GrowthAction:
        """创建增长动作。

        Args:
            action_type: 动作类型
            product_id:  产品 ID
            target:      动作目标
            params:      动作参数
            priority:    优先级

        Returns:
            GrowthAction
        """
        action = GrowthAction(
            action_type=action_type,
            product_id=product_id,
            target=target,
            params=params or {},
            priority=priority,
        )
        self._runtime.actions.append(action)
        return action

    def start_action(self, action: GrowthAction) -> None:
        """开始执行动作。"""
        action.status = ActionStatus.RUNNING
        action.started_at = _now()

    def complete_action(
        self,
        action: GrowthAction,
        result: dict[str, Any] | None = None,
    ) -> None:
        """标记动作完成。"""
        action.status = ActionStatus.COMPLETED
        action.completed_at = _now()
        if result:
            action.result = result

    def fail_action(self, action: GrowthAction, error: str) -> None:
        """标记动作失败。"""
        action.status = ActionStatus.FAILED
        action.completed_at = _now()
        action.error = error

    def cancel_action(self, action: GrowthAction) -> None:
        """取消动作。"""
        action.status = ActionStatus.CANCELLED
        action.completed_at = _now()

    def get_pending_actions(
        self, product_id: str | None = None
    ) -> list[GrowthAction]:
        """获取待处理动作。"""
        actions = [
            a for a in self._runtime.actions
            if a.status == ActionStatus.PENDING
        ]
        if product_id:
            actions = [a for a in actions if a.product_id == product_id]
        actions.sort(key=lambda a: a.priority_order, reverse=True)
        return actions

    # ── Event Management ───────────────────────────────────

    def emit_event(
        self,
        event_type: EventType,
        product_id: str = "",
        source: str = "",
        severity: float = 0.0,
        data: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.MEDIUM,
    ) -> GrowthEvent:
        """发出事件。

        Args:
            event_type: 事件类型
            product_id: 产品 ID
            source:     事件来源
            severity:   严重程度
            data:       事件数据
            priority:   优先级

        Returns:
            GrowthEvent
        """
        event = GrowthEvent(
            event_type=event_type,
            product_id=product_id,
            source=source,
            severity=severity,
            data=data or {},
            priority=priority,
        )
        self._event_bus.publish(event)
        self._runtime.events.append(event)
        return event

    # ── Runtime Status ─────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """获取运行时状态。"""
        return {
            "runtime_id": self._runtime.runtime_id,
            "status": self._runtime.status,
            "active_cycles": self._runtime.active_cycle_count,
            "total_cycles": self._runtime.total_cycle_count,
            "total_events": self._runtime.total_event_count,
            "total_actions": self._runtime.total_action_count,
            "pending_actions": len(self.get_pending_actions()),
            "event_bus_stats": self._event_bus.get_statistics(),
        }

    def start(self) -> None:
        """启动运行时。"""
        self._runtime.status = "running"
        self._runtime.started_at = _now()

    def pause(self) -> None:
        """暂停运行时。"""
        self._runtime.status = "paused"

    def resume(self) -> None:
        """恢复运行时。"""
        self._runtime.status = "running"

    def stop(self) -> None:
        """停止运行时。"""
        self._runtime.status = "stopped"

    @property
    def is_running(self) -> bool:
        return self._runtime.status == "running"

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def runtime(self) -> GrowthRuntime:
        return self._runtime

    def __repr__(self) -> str:
        return (
            f"RuntimeManager(status={self._runtime.status}, "
            f"cycles={self._runtime.active_cycle_count})"
        )