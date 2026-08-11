"""E12.7.4 Execution Monitor — 实时监控执行过程.

检测: 超时、ROI下降、风险增加、Safety Governor触发.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import ExecutionPlan, ExecutionTask, MonitorEvent, TaskStatus


class ExecutionMonitor:
    """执行监控器 — 实时观察任务执行状态并生成告警事件."""

    # 默认阈值
    DEFAULT_TIMEOUT_SECONDS = 300.0
    DEFAULT_ROAS_DROP_THRESHOLD = -0.20
    DEFAULT_RISK_THRESHOLD = 0.80
    DEFAULT_PROGRESS_STALL_SECONDS = 120.0

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        roas_drop_threshold: float = DEFAULT_ROAS_DROP_THRESHOLD,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        progress_stall_seconds: float = DEFAULT_PROGRESS_STALL_SECONDS,
    ):
        self.timeout_seconds = timeout_seconds
        self.roas_drop_threshold = roas_drop_threshold
        self.risk_threshold = risk_threshold
        self.progress_stall_seconds = progress_stall_seconds
        self._events: list[MonitorEvent] = []
        self._alerts: list[MonitorEvent] = []

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def alert_count(self) -> int:
        return len(self._alerts)

    # ── Event Recording ───────────────────────────────────────

    def _record_event(
        self,
        task_id: str,
        event_type: str,
        severity: str,
        message: str,
        plan_id: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> MonitorEvent:
        event = MonitorEvent(
            task_id=task_id,
            plan_id=plan_id,
            event_type=event_type,
            severity=severity,
            message=message,
            metrics=metrics or {},
        )
        self._events.append(event)
        if severity in {"warning", "critical", "fatal"}:
            self._alerts.append(event)
        return event

    # ── Task Monitoring ───────────────────────────────────────

    def watch_task(self, task: ExecutionTask) -> MonitorEvent | None:
        """监控单个任务."""
        now = datetime.now(timezone.utc)

        # Check timeout
        if task.is_running and task.started_at:
            elapsed = (now - task.started_at).total_seconds()
            if elapsed > self.timeout_seconds:
                return self._record_event(
                    task.task_id,
                    "timeout",
                    "critical",
                    f"Task {task.task_id} timed out after {elapsed:.0f}s",
                    metrics={"elapsed_seconds": elapsed},
                )

        # Check failure
        if task.status == TaskStatus.FAILED:
            return self._record_event(
                task.task_id,
                "task_failed",
                "warning",
                f"Task {task.task_id} failed: {task.error_message}",
            )

        # Check success
        if task.status == TaskStatus.SUCCESS:
            return self._record_event(
                task.task_id,
                "task_completed",
                "info",
                f"Task {task.task_id} completed successfully",
                metrics={"execution_time_ms": task.execution_time_ms},
            )

        return None

    def watch_tasks(self, tasks: list[ExecutionTask]) -> list[MonitorEvent]:
        """监控一组任务."""
        events: list[MonitorEvent] = []
        for task in tasks:
            event = self.watch_task(task)
            if event:
                events.append(event)
        return events

    # ── Plan Monitoring ───────────────────────────────────────

    def watch_plan(self, plan: ExecutionPlan) -> list[MonitorEvent]:
        """监控整个执行计划."""
        events: list[MonitorEvent] = []

        # Check each task
        for task in plan.tasks:
            event = self.watch_task(task)
            if event:
                event.plan_id = plan.plan_id
                events.append(event)

        # Check plan completion
        if plan.is_complete:
            if plan.has_failures:
                events.append(self._record_event(
                    "",
                    "plan_completed_with_failures",
                    "warning",
                    f"Plan {plan.plan_id} completed with {len(plan.failed_tasks)} failures",
                    plan_id=plan.plan_id,
                ))
            else:
                events.append(self._record_event(
                    "",
                    "plan_completed_success",
                    "info",
                    f"Plan {plan.plan_id} completed successfully",
                    plan_id=plan.plan_id,
                    metrics={"total_tasks": plan.task_count},
                ))

        return events

    # ── Metric Alerts ─────────────────────────────────────────

    def detect_roas_drop(self, current_roas: float, previous_roas: float) -> MonitorEvent | None:
        """检测ROAS下降."""
        if previous_roas == 0:
            return None

        change = (current_roas - previous_roas) / previous_roas
        if change < self.roas_drop_threshold:
            severity = "critical" if change < -0.50 else "warning"
            return self._record_event(
                "",
                "roas_drop",
                severity,
                f"ROAS dropped {change:.1%}: {previous_roas:.2f} → {current_roas:.2f}",
                metrics={
                    "current_roas": current_roas,
                    "previous_roas": previous_roas,
                    "change_pct": change,
                },
            )
        return None

    def detect_risk_increase(self, current_risk: float) -> MonitorEvent | None:
        """检测风险超过阈值."""
        if current_risk > self.risk_threshold:
            return self._record_event(
                "",
                "risk_threshold_exceeded",
                "critical",
                f"Risk score {current_risk:.2f} exceeds threshold {self.risk_threshold}",
                metrics={"current_risk": current_risk},
            )
        return None

    def detect_progress_stall(
        self, plan: ExecutionPlan, last_progress: float, stall_duration: float,
    ) -> MonitorEvent | None:
        """检测进度停滞."""
        if stall_duration > self.progress_stall_seconds:
            return self._record_event(
                "",
                "progress_stalled",
                "warning",
                f"Plan {plan.plan_id} progress stalled at {plan.completion_pct:.1%}",
                plan_id=plan.plan_id,
                metrics={
                    "completion_pct": plan.completion_pct,
                    "stall_seconds": stall_duration,
                },
            )
        return None

    # ── Query ─────────────────────────────────────────────────

    def get_alerts(self, severity: str | None = None) -> list[MonitorEvent]:
        """获取告警事件."""
        if severity:
            return [e for e in self._alerts if e.severity == severity]
        return list(self._alerts)

    def get_events(self, event_type: str | None = None) -> list[MonitorEvent]:
        """获取事件列表."""
        if event_type:
            return [e for e in self._events if e.event_type == event_type]
        return list(self._events)

    def get_task_events(self, task_id: str) -> list[MonitorEvent]:
        """获取特定任务的事件."""
        return [e for e in self._events if e.task_id == task_id]

    def clear(self) -> None:
        """清除所有事件."""
        self._events.clear()
        self._alerts.clear()

    def get_summary(self) -> dict[str, Any]:
        """获取监控摘要."""
        return {
            "total_events": len(self._events),
            "total_alerts": len(self._alerts),
            "alerts_by_severity": {
                "warning": len([e for e in self._alerts if e.severity == "warning"]),
                "critical": len([e for e in self._alerts if e.severity == "critical"]),
                "fatal": len([e for e in self._alerts if e.severity == "fatal"]),
            },
        }