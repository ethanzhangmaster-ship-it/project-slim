"""E12.7.6 Adaptive Scheduler — 智能决定何时启动下一轮循环."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class SchedulePolicy(str, Enum):
    """调度策略."""
    FIXED_INTERVAL = "fixed_interval"
    DATA_DRIVEN = "data_driven"
    OPPORTUNITY = "opportunity"
    CONTINUOUS = "continuous"
    HYBRID = "hybrid"


class TriggerReason(str, Enum):
    """触发原因."""
    TIME_ELAPSED = "time_elapsed"
    ROAS_DROP = "roas_drop"
    CTR_DROP = "ctr_drop"
    FATIGUE_HIGH = "fatigue_high"
    NEW_OPPORTUNITY = "new_opportunity"
    COMPETITOR_CHANGE = "competitor_change"
    MANUAL = "manual"


class AdaptiveScheduler:
    """自适应调度器 — 根据时间、数据和机会决定何时启动下一轮循环.

    触发条件:
      - 时间: 每天/每周/每N小时
      - 数据: ROAS下降 / CTR下降 / Creative疲劳
      - 机会: 新趋势 / 竞争变化
    """

    def __init__(
        self,
        policy: SchedulePolicy = SchedulePolicy.HYBRID,
        fixed_interval_hours: float = 24.0,
        roas_drop_threshold: float = -0.15,
        ctr_drop_threshold: float = -0.10,
        fatigue_threshold: float = 0.7,
        cooldown_hours: float = 1.0,
    ):
        self._policy = policy
        self._fixed_interval_hours = fixed_interval_hours
        self._roas_drop_threshold = roas_drop_threshold
        self._ctr_drop_threshold = ctr_drop_threshold
        self._fatigue_threshold = fatigue_threshold
        self._cooldown_hours = cooldown_hours

        self._last_triggered: dict[str, datetime] = {}
        self._schedule_count: int = 0

    @property
    def schedule_count(self) -> int:
        return self._schedule_count

    @property
    def policy(self) -> SchedulePolicy:
        return self._policy

    # ── Should Trigger ────────────────────────────────────────

    def should_trigger(
        self,
        product_id: str,
        current_metrics: dict[str, Any] | None = None,
        previous_metrics: dict[str, Any] | None = None,
    ) -> tuple[bool, list[TriggerReason]]:
        """判断是否应该触发下一轮循环."""
        self._schedule_count += 1
        reasons: list[TriggerReason] = []

        # Check cooldown
        if not self._check_cooldown(product_id):
            return False, reasons

        # Continuous policy: always trigger after cooldown
        if self._policy == SchedulePolicy.CONTINUOUS:
            return True, [TriggerReason.MANUAL]

        # Time-based trigger
        if self._policy in {SchedulePolicy.FIXED_INTERVAL, SchedulePolicy.HYBRID}:
            if self._is_time_trigger(product_id):
                reasons.append(TriggerReason.TIME_ELAPSED)

        # Data-driven trigger
        if self._policy in {SchedulePolicy.DATA_DRIVEN, SchedulePolicy.HYBRID}:
            if current_metrics and previous_metrics:
                data_reasons = self._check_data_triggers(current_metrics, previous_metrics)
                reasons.extend(data_reasons)

        # Opportunity trigger
        if self._policy in {SchedulePolicy.OPPORTUNITY, SchedulePolicy.HYBRID}:
            if current_metrics:
                opp_reasons = self._check_opportunity_triggers(current_metrics)
                reasons.extend(opp_reasons)

        if reasons:
            self._last_triggered[product_id] = datetime.now(timezone.utc)
            return True, reasons

        return False, reasons

    # ── Time Check ────────────────────────────────────────────

    def _is_time_trigger(self, product_id: str) -> bool:
        """检查是否到了定时触发时间."""
        last = self._last_triggered.get(product_id)
        if last is None:
            return True  # Never triggered before
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
        return elapsed >= self._fixed_interval_hours

    def _check_cooldown(self, product_id: str) -> bool:
        """检查冷却时间."""
        last = self._last_triggered.get(product_id)
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
        return elapsed >= self._cooldown_hours

    # ── Data Triggers ─────────────────────────────────────────

    def _check_data_triggers(
        self, current: dict[str, Any], previous: dict[str, Any],
    ) -> list[TriggerReason]:
        """检查数据驱动的触发条件."""
        reasons: list[TriggerReason] = []

        cur_roas = current.get("roas", 0.0)
        prev_roas = previous.get("roas", 0.0)
        if prev_roas > 0:
            roas_change = (cur_roas - prev_roas) / prev_roas
            if roas_change <= self._roas_drop_threshold:
                reasons.append(TriggerReason.ROAS_DROP)

        cur_ctr = current.get("ctr", 0.0)
        prev_ctr = previous.get("ctr", 0.0)
        if prev_ctr > 0:
            ctr_change = (cur_ctr - prev_ctr) / prev_ctr
            if ctr_change <= self._ctr_drop_threshold:
                reasons.append(TriggerReason.CTR_DROP)

        fatigue = current.get("fatigue_score", 0.0)
        if fatigue >= self._fatigue_threshold:
            reasons.append(TriggerReason.FATIGUE_HIGH)

        return reasons

    def _check_opportunity_triggers(
        self, current: dict[str, Any],
    ) -> list[TriggerReason]:
        """检查机会驱动的触发条件."""
        reasons: list[TriggerReason] = []

        roas = current.get("roas", 0.0)
        if roas > 2.0:
            reasons.append(TriggerReason.NEW_OPPORTUNITY)

        return reasons

    # ── Next Schedule ─────────────────────────────────────────

    def get_next_schedule_time(self, product_id: str) -> datetime:
        """获取下次计划触发时间."""
        last = self._last_triggered.get(product_id, datetime.now(timezone.utc))
        return last + timedelta(hours=self._fixed_interval_hours)

    def get_time_until_next(self, product_id: str) -> float:
        """获取距离下次触发还有多少小时."""
        next_time = self.get_next_schedule_time(product_id)
        delta = next_time - datetime.now(timezone.utc)
        return max(0.0, delta.total_seconds() / 3600.0)

    # ── Reset ─────────────────────────────────────────────────

    def reset(self, product_id: str) -> None:
        """重置产品调度状态."""
        self._last_triggered.pop(product_id, None)

    def reset_all(self) -> None:
        """重置所有调度状态."""
        self._last_triggered.clear()

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "policy": self._policy.value,
            "fixed_interval_hours": self._fixed_interval_hours,
            "roas_drop_threshold": self._roas_drop_threshold,
            "ctr_drop_threshold": self._ctr_drop_threshold,
            "fatigue_threshold": self._fatigue_threshold,
            "cooldown_hours": self._cooldown_hours,
            "schedule_count": self._schedule_count,
            "tracked_products": list(self._last_triggered.keys()),
        }