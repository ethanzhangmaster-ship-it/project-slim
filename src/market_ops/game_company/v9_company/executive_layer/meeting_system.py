from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class MeetingType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    AD_HOC = "ad_hoc"


@dataclass
class ActionItem:
    action_id: str
    description: str = ""
    owner: str = ""
    due_date: str = ""
    status: str = "open"
    priority: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "owner": self.owner,
            "due_date": self.due_date,
            "status": self.status,
            "priority": self.priority,
        }


@dataclass
class MeetingMinutes:
    minutes_id: str
    meeting_id: str
    attendees: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minutes_id": self.minutes_id,
            "meeting_id": self.meeting_id,
            "attendees": self.attendees,
            "notes": self.notes,
            "decisions": self.decisions,
            "action_items": [a.to_dict() for a in self.action_items],
            "recorded_at": self.recorded_at.isoformat(),
        }


@dataclass
class Meeting:
    meeting_id: str
    title: str
    meeting_type: MeetingType
    scheduled_at: datetime = field(default_factory=datetime.now)
    duration_minutes: int = 30
    attendees: List[str] = field(default_factory=list)
    agenda: List[str] = field(default_factory=list)
    status: str = "scheduled"
    minutes: Optional[MeetingMinutes] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "meeting_type": self.meeting_type.value,
            "scheduled_at": self.scheduled_at.isoformat(),
            "duration_minutes": self.duration_minutes,
            "attendees": self.attendees,
            "agenda": self.agenda,
            "status": self.status,
            "minutes": self.minutes.to_dict() if self.minutes else None,
        }


class MeetingSystem:
    def __init__(self):
        self._meetings: Dict[str, Meeting] = {}
        self._minutes: Dict[str, MeetingMinutes] = {}

    def schedule_meeting(self, meeting: Meeting) -> Meeting:
        self._meetings[meeting.meeting_id] = meeting
        return meeting

    def get_meetings(self) -> List[Meeting]:
        return list(self._meetings.values())

    def get_meeting(self, meeting_id: str) -> Optional[Meeting]:
        return self._meetings.get(meeting_id)

    def record_minutes(self, meeting_id: str, minutes: MeetingMinutes) -> bool:
        meeting = self._meetings.get(meeting_id)
        if not meeting:
            return False

        meeting.minutes = minutes
        meeting.status = "completed"
        self._minutes[minutes.minutes_id] = minutes
        return True

    def get_action_items(self, meeting_id: str) -> List[ActionItem]:
        meeting = self._meetings.get(meeting_id)
        if not meeting or not meeting.minutes:
            return []
        return meeting.minutes.action_items

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._meetings)
        completed = sum(1 for m in self._meetings.values() if m.status == "completed")
        by_type = {}
        for m in self._meetings.values():
            t = m.meeting_type.value
            by_type[t] = by_type.get(t, 0) + 1

        total_actions = sum(
            len(m.minutes.action_items)
            for m in self._meetings.values()
            if m.minutes
        )
        open_actions = sum(
            sum(1 for a in m.minutes.action_items if a.status == "open")
            for m in self._meetings.values()
            if m.minutes
        )

        return {
            "total_meetings": total,
            "completed_meetings": completed,
            "meetings_by_type": by_type,
            "total_action_items": total_actions,
            "open_action_items": open_actions,
        }
