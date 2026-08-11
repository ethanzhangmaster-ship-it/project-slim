"""E12.7.1 — Cycle Scheduler。

增长周期调度器。

功能:
  - 基于时间触发周期
  - 基于事件触发周期
  - 多产品周期编排
  - 周期优先级管理
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .event_bus import EventBus
from .models import (
    EventPriority,
    EventType,
    GrowthCycle,
    GrowthEvent,
    GrowthState,
    _now,
)
from .runtime import RuntimeManager


class CycleScheduler:
    """增长周期调度器。

    管理多个产品增长周期的调度和执行。
    """

    def __init__(
        self,
        runtime: RuntimeManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._runtime = runtime or RuntimeManager()
        self._event_bus = event_bus or self._runtime.event_bus
        self._scheduled_cycles: dict[str, dict[str, Any]] = {}
        self._last_cycle_time: dict[str, datetime] = {}

    def schedule_product_cycle(
        self,
        product_id: str,
        interval_minutes: int = 60,
        auto_advance: bool = False,
    ) -> GrowthCycle:
        """为产品调度增长周期。

        Args:
            product_id:        产品 ID
            interval_minutes:  周期间隔（分钟）
            auto_advance:      是否自动推进所有状态

        Returns:
            GrowthCycle
        """
        cycle = self._runtime.create_cycle(product_id)
        self._scheduled_cycles[product_id] = {
            "cycle_id": cycle.cycle_id,
            "interval_minutes": interval_minutes,
            "auto_advance": auto_advance,
            "created_at": _now(),
        }
        self._last_cycle_time[product_id] = _now()

        if auto_advance:
            self._runtime.run_cycle_auto(cycle)

        return cycle

    def trigger_cycle(
        self,
        product_id: str,
        reason: str = "manual",
    ) -> GrowthCycle | None:
        """触发产品的新周期。

        Args:
            product_id: 产品 ID
            reason:     触发原因

        Returns:
            GrowthCycle 或 None（如果已有活跃周期）
        """
        # 检查是否有活跃周期
        active = self._runtime.get_active_cycles()
        for c in active:
            if c.product_id == product_id:
                return None  # 已有活跃周期，不重复创建

        cycle = self._runtime.create_cycle(product_id)
        self._last_cycle_time[product_id] = _now()

        self._event_bus.publish(
            GrowthEvent(
                event_type=EventType.CUSTOM,
                product_id=product_id,
                source="cycle_scheduler",
                priority=EventPriority.MEDIUM,
                data={"reason": reason, "cycle_id": cycle.cycle_id},
            )
        )

        return cycle

    def trigger_on_event(
        self,
        event: GrowthEvent,
        force: bool = False,
    ) -> GrowthCycle | None:
        """基于事件触发周期。

        Args:
            event: 触发事件
            force: 是否强制创建（即使有活跃周期）

        Returns:
            GrowthCycle 或 None
        """
        product_id = event.product_id
        if not product_id:
            return None

        if not force:
            active = self._runtime.get_active_cycles()
            for c in active:
                if c.product_id == product_id:
                    return None

        cycle = self._runtime.create_cycle(product_id)
        cycle.add_event(event)
        self._last_cycle_time[product_id] = _now()

        return cycle

    def should_trigger(self, product_id: str) -> bool:
        """检查是否应该触发新周期（基于间隔时间）。

        Args:
            product_id: 产品 ID

        Returns:
            True 如果应该触发
        """
        schedule = self._scheduled_cycles.get(product_id)
        if not schedule:
            return False

        # 检查是否有活跃周期
        active = self._runtime.get_active_cycles()
        for c in active:
            if c.product_id == product_id:
                return False

        # 检查间隔时间
        last_time = self._last_cycle_time.get(product_id)
        if last_time is None:
            return True

        interval = schedule.get("interval_minutes", 60)
        elapsed = _now() - last_time
        return elapsed.total_seconds() >= interval * 60

    def tick(self) -> list[GrowthCycle]:
        """执行一次调度 tick。

        检查所有调度产品，触发应启动的周期。

        Returns:
            新启动的周期列表
        """
        new_cycles: list[GrowthCycle] = []
        for product_id in list(self._scheduled_cycles.keys()):
            if self.should_trigger(product_id):
                cycle = self.trigger_cycle(product_id, reason="scheduled")
                if cycle:
                    new_cycles.append(cycle)
        return new_cycles

    def advance_all_cycles(self) -> list[tuple[str, GrowthState]]:
        """推进所有周期到下一个状态。

        Returns:
            [(cycle_id, new_state), ...]
        """
        results: list[tuple[str, GrowthState]] = []
        for cycle in self._runtime.get_active_cycles():
            new_state = self._runtime.advance_cycle(cycle)
            if new_state:
                results.append((cycle.cycle_id, new_state))
        return results

    def get_product_schedule(self, product_id: str) -> dict[str, Any] | None:
        """获取产品调度信息。"""
        return self._scheduled_cycles.get(product_id)

    def get_all_schedules(self) -> dict[str, dict[str, Any]]:
        """获取所有调度信息。"""
        return dict(self._scheduled_cycles)

    def update_schedule(
        self, product_id: str, interval_minutes: int | None = None
    ) -> bool:
        """更新调度配置。"""
        schedule = self._scheduled_cycles.get(product_id)
        if not schedule:
            return False
        if interval_minutes is not None:
            schedule["interval_minutes"] = interval_minutes
        return True

    def remove_schedule(self, product_id: str) -> bool:
        """移除调度配置。"""
        if product_id in self._scheduled_cycles:
            del self._scheduled_cycles[product_id]
            return True
        return False

    @property
    def scheduled_product_count(self) -> int:
        return len(self._scheduled_cycles)

    def get_statistics(self) -> dict[str, Any]:
        """获取调度统计。"""
        return {
            "scheduled_products": self.scheduled_product_count,
            "active_cycles": self._runtime.runtime.active_cycle_count,
            "total_cycles": self._runtime.runtime.total_cycle_count,
            "schedules": {
                pid: {
                    "interval_minutes": s["interval_minutes"],
                    "auto_advance": s["auto_advance"],
                }
                for pid, s in self._scheduled_cycles.items()
            },
        }

    def __repr__(self) -> str:
        return (
            f"CycleScheduler(products={self.scheduled_product_count}, "
            f"active={self._runtime.runtime.active_cycle_count})"
        )