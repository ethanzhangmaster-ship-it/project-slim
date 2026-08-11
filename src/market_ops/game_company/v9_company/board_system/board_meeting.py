from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import List, Optional, Dict
import uuid


class MeetingFrequency(Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    AD_HOC = "ad_hoc"


@dataclass
class MeetingAgenda:
    agenda_id: str
    title: str
    description: str
    estimated_duration_minutes: int
    presenter: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "agenda_id": self.agenda_id,
            "title": self.title,
            "description": self.description,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "presenter": self.presenter,
        }


@dataclass
class BoardMeetingRecord:
    meeting_id: str
    title: str
    scheduled_at: datetime
    frequency: MeetingFrequency
    attendees: List[str] = field(default_factory=list)
    agendas: List[MeetingAgenda] = field(default_factory=list)
    status: str = "scheduled"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "scheduled_at": self.scheduled_at.isoformat(),
            "frequency": self.frequency.value,
            "attendees": self.attendees,
            "agendas": [a.to_dict() for a in self.agendas],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BoardDecision:
    decision_id: str
    meeting_id: str
    title: str
    description: str
    approved_by: List[str] = field(default_factory=list)
    decided_at: datetime = field(default_factory=datetime.now)
    status: str = "passed"

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "meeting_id": self.meeting_id,
            "title": self.title,
            "description": self.description,
            "approved_by": self.approved_by,
            "decided_at": self.decided_at.isoformat(),
            "status": self.status,
        }


class BoardMeeting:
    def __init__(self):
        self._meetings: Dict[str, BoardMeetingRecord] = {}
        self._decisions: Dict[str, BoardDecision] = {}

    def schedule_meeting(
        self,
        title: str,
        frequency: MeetingFrequency = MeetingFrequency.MONTHLY,
        attendees: Optional[List[str]] = None,
        agendas: Optional[List[MeetingAgenda]] = None,
    ) -> BoardMeetingRecord:
        meeting_id = str(uuid.uuid4())
        scheduled_at = datetime.now() + timedelta(days=7)
        record = BoardMeetingRecord(
            meeting_id=meeting_id,
            title=title,
            scheduled_at=scheduled_at,
            frequency=frequency,
            attendees=attendees or ["CEO", "CTO", "CFO", "COO"],
            agendas=agendas or [
                MeetingAgenda(
                    agenda_id=str(uuid.uuid4()),
                    title="季度业务回顾",
                    description="回顾上季度关键业务指标",
                    estimated_duration_minutes=30,
                )
            ],
        )
        self._meetings[meeting_id] = record
        return record

    def get_meetings(self) -> List[BoardMeetingRecord]:
        return list(self._meetings.values())

    def get_meeting(self, meeting_id: str) -> Optional[BoardMeetingRecord]:
        return self._meetings.get(meeting_id)

    def record_decision(self, meeting_id: str, decision: BoardDecision) -> BoardDecision:
        decision.meeting_id = meeting_id
        self._decisions[decision.decision_id] = decision
        return decision

    def get_board_decisions(self) -> List[BoardDecision]:
        return list(self._decisions.values())

    def get_stats(self) -> Dict:
        return {
            "total_meetings": len(self._meetings),
            "total_decisions": len(self._decisions),
            "scheduled_meetings": sum(1 for m in self._meetings.values() if m.status == "scheduled"),
            "completed_meetings": sum(1 for m in self._meetings.values() if m.status == "completed"),
        }
