from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class StopStatus(Enum):
    ACTIVE = "active"
    RELEASED = "released"


@dataclass
class EmergencyEvent:
    event_id: str
    trigger_reason: str
    released_reason: Optional[str] = None
    status: StopStatus = StopStatus.ACTIVE
    triggered_by: str = "system"
    triggered_at: datetime = field(default_factory=datetime.now)
    released_by: Optional[str] = None
    released_at: Optional[datetime] = None
    affected_systems: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger_reason": self.trigger_reason,
            "released_reason": self.released_reason,
            "status": self.status.value,
            "triggered_by": self.triggered_by,
            "triggered_at": self.triggered_at.isoformat(),
            "released_by": self.released_by,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "affected_systems": self.affected_systems,
        }


class EmergencyStop:
    def __init__(self):
        self._current_event: Optional[EmergencyEvent] = None
        self._history: List[EmergencyEvent] = []

    def trigger(self, reason: str, affected_systems: List[str] = None) -> EmergencyEvent:
        event = EmergencyEvent(
            event_id=f"emergency_{datetime.now().timestamp()}",
            trigger_reason=reason,
            affected_systems=affected_systems or [],
        )
        self._current_event = event
        self._history.append(event)
        return event

    def release(self, reason: str) -> bool:
        if not self._current_event or self._current_event.status != StopStatus.ACTIVE:
            return False
        self._current_event.status = StopStatus.RELEASED
        self._current_event.released_reason = reason
        self._current_event.released_by = "system_admin"
        self._current_event.released_at = datetime.now()
        return True

    def get_status(self) -> StopStatus:
        if self._current_event and self._current_event.status == StopStatus.ACTIVE:
            return StopStatus.ACTIVE
        return StopStatus.RELEASED

    def get_trigger_history(self) -> List[EmergencyEvent]:
        return sorted(
            self._history,
            key=lambda e: e.triggered_at,
            reverse=True
        )

    def is_active(self) -> bool:
        return self.get_status() == StopStatus.ACTIVE

    def get_current_event(self) -> Optional[EmergencyEvent]:
        return self._current_event

    def get_stats(self) -> Dict[str, Any]:
        total_triggers = len(self._history)
        active_triggers = sum(1 for e in self._history if e.status == StopStatus.ACTIVE)
        released_triggers = sum(1 for e in self._history if e.status == StopStatus.RELEASED)
        return {
            "is_active": self.is_active(),
            "total_triggers": total_triggers,
            "active_triggers": active_triggers,
            "released_triggers": released_triggers,
        }