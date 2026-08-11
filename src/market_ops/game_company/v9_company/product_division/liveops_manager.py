from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(Enum):
    SEASONAL = "seasonal"
    WEEKLY = "weekly"
    DAILY = "daily"
    SPECIAL = "special"
    COLLABORATION = "collaboration"


@dataclass
class LiveEvent:
    event_id: str
    title: str
    event_type: EventType
    start_time: datetime
    end_time: datetime
    rewards_pool: float
    target_segment: str = "all"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "event_type": self.event_type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "rewards_pool": self.rewards_pool,
            "target_segment": self.target_segment,
        }


@dataclass
class EventCalendar:
    month: int
    year: int
    events: List[LiveEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "month": self.month,
            "year": self.year,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class EventEvaluation:
    event_id: str
    participation_rate: float
    revenue_uplift: float
    retention_uplift: float
    player_satisfaction: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "participation_rate": self.participation_rate,
            "revenue_uplift": self.revenue_uplift,
            "retention_uplift": self.retention_uplift,
            "player_satisfaction": self.player_satisfaction,
        }


class LiveOpsManager:
    def __init__(self):
        self._events: Dict[str, LiveEvent] = {}
        self._evaluations: Dict[str, EventEvaluation] = {}

    def plan_events(self) -> EventCalendar:
        now = datetime.now()
        events = [
            LiveEvent(
                "e1",
                "Summer Festival",
                EventType.SEASONAL,
                now,
                now + timedelta(days=14),
                50000.0,
                "all",
            ),
            LiveEvent(
                "e2",
                "Weekend Rush",
                EventType.WEEKLY,
                now,
                now + timedelta(days=2),
                5000.0,
                "retained",
            ),
            LiveEvent(
                "e3",
                "Daily Login Bonus",
                EventType.DAILY,
                now,
                now + timedelta(days=1),
                1000.0,
                "lapsed",
            ),
            LiveEvent(
                "e4",
                "Crossover Event",
                EventType.COLLABORATION,
                now + timedelta(days=30),
                now + timedelta(days=45),
                100000.0,
                "whales",
            ),
        ]
        for e in events:
            self._events[e.event_id] = e
        return EventCalendar(now.month, now.year, events)

    def get_event_calendar(self) -> EventCalendar:
        return self.plan_events()

    def create_event(self, event: LiveEvent) -> str:
        self._events[event.event_id] = event
        return event.event_id

    def evaluate_event(self, event_id: str) -> Optional[EventEvaluation]:
        if event_id in self._evaluations:
            return self._evaluations[event_id]
        evaluation = EventEvaluation(
            event_id=event_id,
            participation_rate=0.35,
            revenue_uplift=0.18,
            retention_uplift=0.08,
            player_satisfaction=4.2,
        )
        self._evaluations[event_id] = evaluation
        return evaluation

    def get_event_recommendations(self) -> List[Dict[str, Any]]:
        return [
            {
                "event_type": EventType.SEASONAL.value,
                "recommendation": "Launch summer-themed event with limited skins",
                "expected_revenue_uplift": 0.22,
                "priority": "high",
            },
            {
                "event_type": EventType.SPECIAL.value,
                "recommendation": "Anniversary event with 2x rewards",
                "expected_revenue_uplift": 0.30,
                "priority": "critical",
            },
            {
                "event_type": EventType.WEEKLY.value,
                "recommendation": "Weekend tournament with leaderboard",
                "expected_revenue_uplift": 0.10,
                "priority": "medium",
            },
        ]

    def get_stats(self) -> Dict[str, Any]:
        events = list(self._events.values())
        type_counts = {t.value: 0 for t in EventType}
        for e in events:
            type_counts[e.event_type.value] += 1
        return {
            "total_events": len(events),
            "evaluated_events": len(self._evaluations),
            "type_distribution": type_counts,
            "upcoming_events": sum(1 for e in events if e.start_time > datetime.now()),
        }