from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum


class ScheduleType(Enum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"
    INTERVAL = "interval"


@dataclass
class Schedule:
    schedule_id: str
    workflow_name: str
    schedule_type: ScheduleType
    cron_expression: str = ""
    interval_seconds: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    is_active: bool = True
    max_runs: int = 0
    run_count: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduledRun:
    run_id: str
    schedule_id: str
    workflow_name: str
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    parameters: Dict[str, Any] = field(default_factory=dict)


class WorkflowScheduler:
    def __init__(self):
        self.schedules: Dict[str, Schedule] = {}
        self.run_history: List[ScheduledRun] = []
        self.pending_runs: List[ScheduledRun] = []
        self.workflow_creators: Dict[str, Callable] = {}

    def register_workflow_creator(self, workflow_name: str, creator: Callable):
        self.workflow_creators[workflow_name] = creator

    def add_schedule(
        self,
        workflow_name: str,
        schedule_type: ScheduleType,
        parameters: Dict[str, Any] = None,
        start_time: datetime = None,
        end_time: datetime = None,
        interval_seconds: int = 0,
        cron_expression: str = "",
        max_runs: int = 0,
    ) -> Schedule:
        schedule_id = f"sched_{hash(workflow_name + str(datetime.now())) % 100000:05d}"

        if start_time is None:
            start_time = datetime.now()

        next_run = self._calculate_next_run(start_time, schedule_type, interval_seconds)

        schedule = Schedule(
            schedule_id=schedule_id,
            workflow_name=workflow_name,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            start_time=start_time,
            end_time=end_time,
            next_run=next_run,
            is_active=True,
            max_runs=max_runs,
            parameters=parameters or {},
        )

        self.schedules[schedule_id] = schedule
        return schedule

    def _calculate_next_run(
        self,
        from_time: datetime,
        schedule_type: ScheduleType,
        interval_seconds: int = 0,
    ) -> Optional[datetime]:
        if schedule_type == ScheduleType.ONCE:
            return from_time
        elif schedule_type == ScheduleType.INTERVAL and interval_seconds > 0:
            return from_time + timedelta(seconds=interval_seconds)
        elif schedule_type == ScheduleType.HOURLY:
            return from_time + timedelta(hours=1)
        elif schedule_type == ScheduleType.DAILY:
            return from_time + timedelta(days=1)
        elif schedule_type == ScheduleType.WEEKLY:
            return from_time + timedelta(weeks=1)
        elif schedule_type == ScheduleType.MONTHLY:
            month = from_time.month + 1
            year = from_time.year
            if month > 12:
                month = 1
                year += 1
            return from_time.replace(year=year, month=month)
        return None

    def remove_schedule(self, schedule_id: str) -> bool:
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            return True
        return False

    def pause_schedule(self, schedule_id: str) -> bool:
        if schedule_id in self.schedules:
            self.schedules[schedule_id].is_active = False
            return True
        return False

    def resume_schedule(self, schedule_id: str) -> bool:
        if schedule_id in self.schedules:
            self.schedules[schedule_id].is_active = True
            return True
        return False

    def get_due_schedules(self, now: datetime = None) -> List[Schedule]:
        if now is None:
            now = datetime.now()

        due = []
        for schedule in self.schedules.values():
            if not schedule.is_active:
                continue
            if schedule.end_time and now > schedule.end_time:
                schedule.is_active = False
                continue
            if schedule.max_runs > 0 and schedule.run_count >= schedule.max_runs:
                schedule.is_active = False
                continue
            if schedule.next_run and schedule.next_run <= now:
                due.append(schedule)

        return sorted(due, key=lambda s: s.next_run or datetime.min)

    def trigger_schedule(self, schedule_id: str) -> Optional[ScheduledRun]:
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return None
        if not schedule.is_active:
            return None
        if schedule.max_runs > 0 and schedule.run_count >= schedule.max_runs:
            schedule.is_active = False
            return None

        run_id = f"run_{hash(schedule_id + str(datetime.now())) % 100000:05d}"
        run = ScheduledRun(
            run_id=run_id,
            schedule_id=schedule_id,
            workflow_name=schedule.workflow_name,
            scheduled_at=datetime.now(),
            parameters=schedule.parameters.copy(),
        )

        self.pending_runs.append(run)
        schedule.run_count += 1

        if schedule.schedule_type != ScheduleType.ONCE:
            schedule.last_run = datetime.now()
            schedule.next_run = self._calculate_next_run(
                datetime.now(),
                schedule.schedule_type,
                schedule.interval_seconds,
            )

        return run

    def tick(self, now: datetime = None) -> List[ScheduledRun]:
        if now is None:
            now = datetime.now()

        due_schedules = self.get_due_schedules(now)
        triggered_runs = []

        for schedule in due_schedules:
            run = self.trigger_schedule(schedule.schedule_id)
            if run:
                triggered_runs.append(run)

        return triggered_runs

    def get_pending_runs(self) -> List[ScheduledRun]:
        return [r for r in self.pending_runs if r.status == "pending"]

    def mark_run_started(self, run_id: str) -> bool:
        for run in self.pending_runs:
            if run.run_id == run_id:
                run.started_at = datetime.now()
                run.status = "running"
                return True
        return False

    def mark_run_completed(self, run_id: str, status: str = "completed") -> bool:
        for run in self.pending_runs:
            if run.run_id == run_id:
                run.completed_at = datetime.now()
                run.status = status
                self.run_history.append(run)
                self.pending_runs = [r for r in self.pending_runs if r.run_id != run_id]
                return True
        return False

    def get_daily_schedule(self) -> Dict[str, List[Dict[str, Any]]]:
        daily = {}
        for schedule in self.schedules.values():
            if not schedule.is_active:
                continue
            if schedule.next_run:
                day = schedule.next_run.strftime("%Y-%m-%d")
                if day not in daily:
                    daily[day] = []
                daily[day].append({
                    "schedule_id": schedule.schedule_id,
                    "workflow_name": schedule.workflow_name,
                    "next_run": schedule.next_run.isoformat(),
                    "type": schedule.schedule_type.value,
                })
        return daily

    def get_stats(self) -> Dict[str, Any]:
        active = sum(1 for s in self.schedules.values() if s.is_active)
        total_runs = len(self.run_history)
        successful = sum(1 for r in self.run_history if r.status == "completed")
        return {
            "total_schedules": len(self.schedules),
            "active_schedules": active,
            "pending_runs": len(self.get_pending_runs()),
            "total_runs": total_runs,
            "successful_runs": successful,
            "success_rate": round(successful / total_runs * 100, 1) if total_runs > 0 else 0,
        }
