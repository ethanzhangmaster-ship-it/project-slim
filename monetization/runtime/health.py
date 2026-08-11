"""
E14.2 — Module 4: Health Monitor
=================================

Per-game health. Three classes of check (per the spec):

  * AGENT   — `last_cycle_time` older than `stall_timeout_hours` => alert.
  * DECISION— `execution_failure_rate` over the recent window above
               `failure_rate_threshold` => pause / flag.
  * DATA    — `event_delay` (lag between an event occurring and being
               persisted/observed) above budget => flag. (Modelled as a
               soft metric; the structured EventLogger makes it observable.)

Pure stdlib. No LLM, no external API. The monitor only *reports*; the
Recovery Manager decides what to do.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class HealthStatus:
    game: str
    ok: bool
    last_cycle_time: Optional[str] = None
    stalled_hours: float = 0.0
    failure_rate: float = 0.0
    recent_executions: int = 0
    max_event_delay_s: float = 0.0
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "ok": self.ok,
            "last_cycle_time": self.last_cycle_time,
            "stalled_hours": round(self.stalled_hours, 3),
            "failure_rate": round(self.failure_rate, 3),
            "recent_executions": self.recent_executions,
            "max_event_delay_s": round(self.max_event_delay_s, 3),
            "issues": self.issues,
        }


class HealthMonitor:
    """Tracks health signals for ONE game."""

    def __init__(self, game: str, stall_timeout_hours: float = 24.0,
                 failure_rate_threshold: float = 0.20,
                 window: int = 50):
        self.game = game
        self.stall_timeout_hours = stall_timeout_hours
        self.failure_rate_threshold = failure_rate_threshold
        self.window = window
        self.last_cycle_time: Optional[datetime] = None
        self._exec_outcomes: deque = deque(maxlen=window)
        self.max_event_delay_s: float = 0.0

    # ------------------------------------------------------------------ #
    def mark_cycle(self, now: Optional[datetime] = None) -> None:
        self.last_cycle_time = now or datetime.now(timezone.utc)

    def record_execution(self, success: bool) -> None:
        self._exec_outcomes.append(1 if success else 0)

    def record_event_delay(self, delay_seconds: float) -> None:
        if delay_seconds > self.max_event_delay_s:
            self.max_event_delay_s = delay_seconds

    # ------------------------------------------------------------------ #
    def failure_rate(self) -> float:
        if not self._exec_outcomes:
            return 0.0
        failures = sum(1 for x in self._exec_outcomes if x == 0)
        return failures / len(self._exec_outcomes)

    def stalled_hours(self, now: Optional[datetime] = None) -> float:
        if self.last_cycle_time is None:
            return float("inf")
        now = now or datetime.now(timezone.utc)
        delta = (now - self.last_cycle_time).total_seconds() / 3600.0
        return max(0.0, delta)

    def check(self, now: Optional[datetime] = None) -> HealthStatus:
        now = now or datetime.now(timezone.utc)
        issues: List[str] = []
        stalled = self.stalled_hours(now)
        if self.last_cycle_time is not None and stalled > self.stall_timeout_hours:
            issues.append(
                f"agent stalled {stalled:.1f}h (> {self.stall_timeout_hours}h)")
        fr = self.failure_rate()
        if fr > self.failure_rate_threshold:
            issues.append(
                f"execution failure rate {fr:.0%} (> {self.failure_rate_threshold:.0%})")
        return HealthStatus(
            game=self.game,
            ok=len(issues) == 0,
            last_cycle_time=(
                self.last_cycle_time.isoformat() if self.last_cycle_time else None),
            stalled_hours=stalled,
            failure_rate=fr,
            recent_executions=len(self._exec_outcomes),
            max_event_delay_s=self.max_event_delay_s,
            issues=issues,
        )


__all__ = ["HealthMonitor", "HealthStatus"]
