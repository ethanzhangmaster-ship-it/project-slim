from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum


class DailyPhase(Enum):
    MORNING_MARKET_SCAN = "morning_market_scan"
    MORNING_UA_OPTIMIZATION = "morning_ua_optimization"
    MIDDAY_CREATIVE = "midday_creative"
    AFTERNOON_ANALYTICS = "afternoon_analytics"
    EVENING_FINANCE_REVIEW = "evening_finance_review"
    NIGHT_CEO_REPORT = "night_ceo_report"


@dataclass
class DailySchedule:
    date: str
    phases: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    status: str = "scheduled"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DailyCycle:
    def __init__(self):
        self._schedules: Dict[str, DailySchedule] = {}
        self._current_phase: Optional[DailyPhase] = None
        self._phase_handlers: Dict[str, Callable] = {}
        self._history: List[Dict[str, Any]] = []

        self._phase_times = {
            DailyPhase.MORNING_MARKET_SCAN: "08:00",
            DailyPhase.MORNING_UA_OPTIMIZATION: "09:00",
            DailyPhase.MIDDAY_CREATIVE: "12:00",
            DailyPhase.AFTERNOON_ANALYTICS: "15:00",
            DailyPhase.EVENING_FINANCE_REVIEW: "18:00",
            DailyPhase.NIGHT_CEO_REPORT: "23:00",
        }

    def register_phase_handler(self, phase: DailyPhase, handler: Callable):
        self._phase_handlers[phase.value] = handler

    def get_today_schedule(self) -> DailySchedule:
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self._schedules:
            self._schedules[today] = DailySchedule(date=today)
            for phase, time_str in self._phase_times.items():
                self._schedules[today].phases[phase.value] = {
                    "time": time_str,
                    "status": "scheduled",
                }
        return self._schedules[today]

    def get_current_phase(self) -> Optional[DailyPhase]:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        sorted_phases = sorted(self._phase_times.items(), key=lambda x: x[1])

        current = None
        for phase, time_str in sorted_phases:
            if current_time >= time_str:
                current = phase

        return current

    def execute_phase(self, phase: DailyPhase) -> Dict[str, Any]:
        today = self.get_today_schedule()
        today.phases[phase.value]["status"] = "running"
        today.phases[phase.value]["started_at"] = datetime.now().isoformat()

        handler = self._phase_handlers.get(phase.value)
        result = {"phase": phase.value, "status": "completed"}

        if handler:
            try:
                handler_result = handler()
                result["result"] = handler_result
            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)

        today.phases[phase.value]["status"] = result["status"]
        today.phases[phase.value]["completed_at"] = datetime.now().isoformat()

        return result

    def execute_morning_routine(self) -> Dict[str, Any]:
        results = {}
        for phase in [DailyPhase.MORNING_MARKET_SCAN, DailyPhase.MORNING_UA_OPTIMIZATION]:
            result = self.execute_phase(phase)
            results[phase.value] = result
        return results

    def execute_full_day(self) -> Dict[str, Any]:
        results = {}
        today = self.get_today_schedule()
        today.status = "running"
        today.started_at = datetime.now()

        for phase in DailyPhase:
            result = self.execute_phase(phase)
            results[phase.value] = result

        today.status = "completed"
        today.completed_at = datetime.now()

        self._history.append({
            "date": today.date,
            "status": today.status,
            "duration": (today.completed_at - today.started_at).total_seconds() if today.completed_at and today.started_at else 0,
        })

        return {
            "date": today.date,
            "status": today.status,
            "results": results,
        }

    def get_phase_description(self, phase: DailyPhase) -> str:
        descriptions = {
            DailyPhase.MORNING_MARKET_SCAN: "Scan market trends, competitor data, and keyword performance",
            DailyPhase.MORNING_UA_OPTIMIZATION: "Optimize UA campaigns, adjust bids and budgets",
            DailyPhase.MIDDAY_CREATIVE: "Generate new creatives, analyze performance, rotate ads",
            DailyPhase.AFTERNOON_ANALYTICS: "Review daily metrics, analyze user behavior, detect anomalies",
            DailyPhase.EVENING_FINANCE_REVIEW: "Review daily spend and revenue, check ROI, adjust budgets",
            DailyPhase.NIGHT_CEO_REPORT: "Generate daily summary report, update strategy, plan tomorrow",
        }
        return descriptions.get(phase, "")

    def get_today_progress(self) -> Dict[str, Any]:
        today = self.get_today_schedule()
        completed = sum(1 for p in today.phases.values() if p["status"] == "completed")
        total = len(today.phases)
        return {
            "date": today.date,
            "status": today.status,
            "completed_phases": completed,
            "total_phases": total,
            "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
            "current_phase": self.get_current_phase().value if self.get_current_phase() else None,
            "phases": today.phases,
        }

    def get_history(self, days: int = 30) -> List[Dict[str, Any]]:
        return self._history[-days:]
