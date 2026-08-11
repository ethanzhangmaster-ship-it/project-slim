"""
E16.6.14 — ASO OS Kernel: state management, event bus, and scheduler.

The Kernel is the core scheduler/dispatcher — like an operating system kernel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.aso_os.kernel.models import (
    ASOEvent,
    ASOEventType,
    ASOOSState,
)


SubscriberFn = Callable[[ASOEvent], None]


class ASOOSKernel:
    """Core OS Kernel — state, events, and health."""

    def __init__(self):
        self.state = ASOOSState()
        self._subscribers: Dict[ASOEventType, List[SubscriberFn]] = {}

    # ------------------------------------------------------------------ #
    # Event bus
    # ------------------------------------------------------------------ #
    def publish(self, event: ASOEvent) -> None:
        """Publish an event to all subscribers of its type."""
        for sub in self._subscribers.get(event.event_type, []):
            sub(event)

    def subscribe(self, event_type: ASOEventType, handler: SubscriberFn) -> None:
        """Subscribe a handler to an event type."""
        self._subscribers.setdefault(event_type, []).append(handler)

    def subscribe_many(self, handlers: Dict[ASOEventType, SubscriberFn]) -> None:
        for et, h in handlers.items():
            self.subscribe(et, h)

    # ------------------------------------------------------------------ #
    # State management
    # ------------------------------------------------------------------ #
    def update_state(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self.state, k):
                setattr(self.state, k, v)
        self.state.updated_at = datetime.now(timezone.utc).isoformat()

    def get_state(self) -> ASOOSState:
        return self.state

    # ------------------------------------------------------------------ #
    # Health
    # ------------------------------------------------------------------ #
    def health_check(self) -> str:
        return self.state.health


class DailyScheduler:
    """Daily ASO OS schedule — coordinates when agents run."""

    SCHEDULE = {
        "08:00": "Scan all games — collect reality data",
        "09:00": "Analyze — detect signals, create opportunities",
        "10:00": "Plan & approve — priority engine + approval gateway",
        "14:00": "Execute — auto-actions + prepare human tasks",
        "20:00": "Review — collect results, learn patterns, update knowledge",
    }

    def get_schedule(self) -> Dict[str, str]:
        return dict(self.SCHEDULE)

    def phase_for_hour(self, hour: int) -> str:
        if hour < 9:
            return "SCAN"
        elif hour < 10:
            return "ANALYZE"
        elif hour < 14:
            return "PLAN_APPROVE"
        elif hour < 20:
            return "EXECUTE"
        else:
            return "REVIEW_LEARN"


__all__ = ["ASOOSKernel", "DailyScheduler"]
