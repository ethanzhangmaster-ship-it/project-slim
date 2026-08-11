"""
E13.4.4 — Module 4: Scheduler
=============================

Decides *when* the agent runs. In production this maps to:
    * 00:00  daily Reality Scan       -> one full cycle
    * hourly Monetization Health Check -> lightweight observation only
    * event-triggered (ROAS crash, retention alert) -> immediate cycle

For the acceptance simulation we run one full cycle per day (the daily scan)
and support an event queue so an urgent signal can force an extra immediate
cycle. The scheduler is intentionally simple and side-effect free — it only
answers "should I run now?" and tracks pending events.
"""
from __future__ import annotations

from typing import List


class Scheduler:
    def __init__(self):
        self._events: List[str] = []
        self.daily_hour = 0            # daily reality scan at midnight
        self.health_hour = 12          # mid-day health check
        self._last_daily_day: int = -1

    # ------------------------------------------------------------------ #
    def trigger_event(self, name: str) -> None:
        """Queue an urgent event (e.g. 'roas_crash') for an immediate cycle."""
        self._events.append(name)

    def pending_events(self) -> List[str]:
        return list(self._events)

    def consume_events(self) -> List[str]:
        ev = list(self._events)
        self._events.clear()
        return ev

    # ------------------------------------------------------------------ #
    def should_run_daily(self, day: int) -> bool:
        """One full cycle per day (the daily reality scan)."""
        if day != self._last_daily_day:
            self._last_daily_day = day
            return True
        return False

    def should_run_health(self, hour: int) -> bool:
        """Lightweight observation-only check (no execution)."""
        return hour == self.health_hour
