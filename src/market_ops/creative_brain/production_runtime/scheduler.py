"""V4.4 Scheduler — Cron/Interval/Event scheduling.

Supports three schedule types:
  - Cron: 0 6 * * * (daily 6am)
  - Interval: every 3600 seconds
  - Event: triggered by external events

Daily schedule:
  06:00 Facebook Sync
  08:00 Knowledge Update
  09:00 Validation + Lifecycle
  10:00 Policy
  11:00 Creative Generation
  12:00 Upload
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .schemas import ScheduleType


class Scheduler:
    """Cron/Interval/Event scheduler for production runtime."""

    def __init__(self, timezone: str = "Asia/Shanghai") -> None:
        self._timezone = timezone
        self._jobs: dict[str, dict[str, Any]] = {}  # job_id → {schedule, fn, ...}
        self._execution_log: list[dict[str, Any]] = []
        self._running = False

    def add_cron(self, job_id: str, cron_expr: str,
                 fn: Callable[[], Any],
                 description: str = "") -> None:
        """Add a cron-scheduled job.

        Args:
            job_id: Unique job identifier.
            cron_expr: 5-field cron expression (minute hour day month weekday).
            fn: Function to execute.
            description: Human-readable description.
        """
        self._jobs[job_id] = {
            "schedule_type": ScheduleType.CRON,
            "schedule": cron_expr,
            "fn": fn,
            "description": description,
            "last_run": 0.0,
            "next_run": self._calculate_next_run(0.0, cron_expr),
            "enabled": True,
            "run_count": 0,
            "error_count": 0,
        }

    def add_interval(self, job_id: str, interval_seconds: float,
                     fn: Callable[[], Any],
                     description: str = "",
                     start_immediately: bool = False) -> None:
        """Add an interval-scheduled job.

        Args:
            job_id: Unique job identifier.
            interval_seconds: Seconds between runs.
            fn: Function to execute.
            description: Human-readable description.
            start_immediately: Whether to run on first tick.
        """
        now = time.time()
        self._jobs[job_id] = {
            "schedule_type": ScheduleType.INTERVAL,
            "schedule": interval_seconds,
            "fn": fn,
            "description": description,
            "last_run": 0.0,
            "next_run": now if start_immediately else now + interval_seconds,
            "enabled": True,
            "run_count": 0,
            "error_count": 0,
        }

    def add_event(self, job_id: str, event_name: str,
                  fn: Callable[[], Any],
                  description: str = "") -> None:
        """Add an event-triggered job.

        Args:
            job_id: Unique job identifier.
            event_name: Event name that triggers this job.
            fn: Function to execute.
            description: Human-readable description.
        """
        self._jobs[job_id] = {
            "schedule_type": ScheduleType.EVENT,
            "schedule": event_name,
            "fn": fn,
            "description": description,
            "last_run": 0.0,
            "next_run": 0.0,  # Event-driven, no next_run
            "enabled": True,
            "run_count": 0,
            "error_count": 0,
        }

    def trigger_event(self, event_name: str) -> list[str]:
        """Trigger all event-scheduled jobs matching the event name.

        Returns:
            List of triggered job IDs.
        """
        triggered = []
        for job_id, job in self._jobs.items():
            if job["schedule_type"] == ScheduleType.EVENT and job["schedule"] == event_name:
                if job["enabled"]:
                    self._run_job(job_id, job)
                    triggered.append(job_id)
        return triggered

    def tick(self) -> list[str]:
        """Check all jobs and run any that are due.

        Returns:
            List of job IDs that were executed.
        """
        executed = []
        now = time.time()

        for job_id, job in self._jobs.items():
            if not job["enabled"]:
                continue
            if job["schedule_type"] == ScheduleType.EVENT:
                continue  # Event jobs are triggered manually
            if now >= job["next_run"]:
                self._run_job(job_id, job)
                executed.append(job_id)
                # Schedule next run
                if job["schedule_type"] == ScheduleType.CRON:
                    job["next_run"] = self._calculate_next_run(now, job["schedule"])
                elif job["schedule_type"] == ScheduleType.INTERVAL:
                    job["next_run"] = now + job["schedule"]

        return executed

    def _run_job(self, job_id: str, job: dict[str, Any]) -> None:
        """Execute a job and log the result."""
        start = time.time()
        try:
            job["fn"]()
            success = True
            error = ""
        except Exception as e:
            success = False
            error = str(e)
            job["error_count"] += 1

        job["last_run"] = start
        job["run_count"] += 1

        self._execution_log.append({
            "job_id": job_id,
            "started_at": start,
            "duration": time.time() - start,
            "success": success,
            "error": error,
        })

    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        job = self._jobs.get(job_id)
        if job:
            job["enabled"] = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        job = self._jobs.get(job_id)
        if job:
            job["enabled"] = False
            return True
        return False

    def remove_job(self, job_id: str) -> bool:
        """Remove a job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job details."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return {
            "job_id": job_id,
            "schedule_type": job["schedule_type"].value,
            "schedule": job["schedule"],
            "description": job["description"],
            "enabled": job["enabled"],
            "last_run": job["last_run"],
            "next_run": job["next_run"],
            "run_count": job["run_count"],
            "error_count": job["error_count"],
        }

    def get_all_jobs(self) -> list[dict[str, Any]]:
        """Get all jobs."""
        return [self.get_job(jid) for jid in self._jobs]

    def get_due_jobs(self) -> list[str]:
        """Get all jobs that are past their next_run time."""
        now = time.time()
        return [
            jid for jid, job in self._jobs.items()
            if job["enabled"]
            and job["schedule_type"] != ScheduleType.EVENT
            and now >= job["next_run"]
        ]

    def get_execution_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent execution log."""
        return self._execution_log[-limit:]

    def get_summary(self) -> dict[str, Any]:
        """Get scheduler summary."""
        enabled = sum(1 for j in self._jobs.values() if j["enabled"])
        return {
            "total_jobs": len(self._jobs),
            "enabled": enabled,
            "disabled": len(self._jobs) - enabled,
            "total_runs": sum(j["run_count"] for j in self._jobs.values()),
            "total_errors": sum(j["error_count"] for j in self._jobs.values()),
            "due_now": self.get_due_jobs(),
        }

    def _calculate_next_run(self, from_time: float,
                            cron_expr: str) -> float:
        """Calculate the next run time from a cron expression.

        Simplified implementation — in production, use croniter or similar.
        """
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return from_time + 3600  # Default: 1 hour

        try:
            minute = int(parts[0])
            hour = int(parts[1])
        except ValueError:
            return from_time + 3600

        # Use a safe timestamp (Windows may reject 0.0)
        safe_time = from_time if from_time > 0 else time.time()

        # Simple: schedule for the next occurrence of hour:minute
        from datetime import datetime
        dt = datetime.fromtimestamp(safe_time)
        target = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target.timestamp() <= from_time:
            # Already passed for today, schedule for tomorrow
            from datetime import timedelta
            target = target + timedelta(days=1)

        # Handle day-of-month and day-of-week
        dom = parts[2]
        dow = parts[4]
        if dom != "*" or dow != "*":
            from datetime import timedelta
            while True:
                if dom != "*" and target.day != int(dom):
                    target = target + timedelta(days=1)
                    continue
                if dow != "*" and target.weekday() != (int(dow) % 7):
                    target = target + timedelta(days=1)
                    continue
                break

        return target.timestamp()

    def set_next_run(self, job_id: str, next_run: float) -> bool:
        """Manually set the next run time for a job."""
        job = self._jobs.get(job_id)
        if job:
            job["next_run"] = next_run
            return True
        return False