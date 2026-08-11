from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class CalendarEventType(Enum):
    DAILY_ROUTINE = "daily_routine"
    WEEKLY_REVIEW = "weekly_review"
    MONTHLY_STRATEGY = "monthly_strategy"
    MARKET_SCAN = "market_scan"
    UA_OPTIMIZATION = "ua_optimization"
    CREATIVE_BATCH = "creative_batch"
    LAUNCH = "launch"
    EXPERIMENT = "experiment"
    MILESTONE = "milestone"


@dataclass
class CalendarEvent:
    event_id: str
    event_type: CalendarEventType
    title: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    recurring: bool = False
    recurrence_pattern: str = ""
    status: str = "scheduled"
    related_workflow: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class CompanyCalendar:
    def __init__(self):
        self._events: Dict[str, CalendarEvent] = {}
        self._by_date: Dict[str, List[str]] = {}
        self._by_type: Dict[str, List[str]] = {}

    def add_event(
        self,
        event_type: CalendarEventType,
        title: str,
        start_time: datetime,
        end_time: datetime = None,
        description: str = "",
        recurring: bool = False,
        recurrence_pattern: str = "",
        related_workflow: str = "",
        metadata: Dict[str, Any] = None,
    ) -> CalendarEvent:
        if end_time is None:
            end_time = start_time + timedelta(hours=1)

        event_id = f"evt_{hash(title + str(start_time)) % 100000:05d}"

        event = CalendarEvent(
            event_id=event_id,
            event_type=event_type,
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            recurring=recurring,
            recurrence_pattern=recurrence_pattern,
            related_workflow=related_workflow,
            metadata=metadata or {},
        )

        self._events[event_id] = event

        date_key = start_time.strftime("%Y-%m-%d")
        if date_key not in self._by_date:
            self._by_date[date_key] = []
        self._by_date[date_key].append(event_id)

        type_key = event_type.value
        if type_key not in self._by_type:
            self._by_type[type_key] = []
        self._by_type[type_key].append(event_id)

        return event

    def initialize_default_schedule(self):
        now = datetime.now()

        for day_offset in range(7):
            day = now + timedelta(days=day_offset)
            
            times = [
                (8, 0, CalendarEventType.MARKET_SCAN, "Morning Market Scan", "Scan market trends and competitors"),
                (9, 0, CalendarEventType.UA_OPTIMIZATION, "UA Optimization", "Optimize ad campaigns"),
                (12, 0, CalendarEventType.CREATIVE_BATCH, "Creative Batch", "Generate and rotate creatives"),
            ]
            
            for hour, minute, etype, title, desc in times:
                start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                self.add_event(
                    event_type=etype,
                    title=title,
                    start_time=start,
                    description=desc,
                    recurring=True,
                    recurrence_pattern="daily",
                )

        for week_offset in range(4):
            friday = now + timedelta(days=(4 - now.weekday()) + week_offset * 7)
            if friday < now:
                friday += timedelta(days=7)
            start = friday.replace(hour=16, minute=0, second=0, microsecond=0)
            self.add_event(
                event_type=CalendarEventType.WEEKLY_REVIEW,
                title="Weekly Review",
                start_time=start,
                end_time=start + timedelta(hours=2),
                description="Weekly performance review and planning",
                recurring=True,
                recurrence_pattern="weekly",
            )

        return self

    def get_events_for_date(self, date_str: str) -> List[CalendarEvent]:
        ids = self._by_date.get(date_str, [])
        events = [self._events[eid] for eid in ids if eid in self._events]
        return sorted(events, key=lambda e: e.start_time)

    def get_events_for_week(self, start_date: str = None) -> List[CalendarEvent]:
        if start_date is None:
            today = datetime.now()
            start = today - timedelta(days=today.weekday())
        else:
            start = datetime.strptime(start_date, "%Y-%m-%d")

        events = []
        for i in range(7):
            date = start + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            events.extend(self.get_events_for_date(date_str))

        return sorted(events, key=lambda e: e.start_time)

    def get_events_by_type(self, event_type: CalendarEventType) -> List[CalendarEvent]:
        ids = self._by_type.get(event_type.value, [])
        return [self._events[eid] for eid in ids if eid in self._events]

    def get_upcoming_events(self, hours: int = 24) -> List[CalendarEvent]:
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)
        upcoming = [
            e for e in self._events.values()
            if now <= e.start_time <= cutoff
        ]
        return sorted(upcoming, key=lambda e: e.start_time)

    def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        return self._events.get(event_id)

    def complete_event(self, event_id: str) -> bool:
        event = self._events.get(event_id)
        if event:
            event.status = "completed"
            return True
        return False

    def cancel_event(self, event_id: str) -> bool:
        event = self._events.get(event_id)
        if event:
            event.status = "cancelled"
            return True
        return False

    def get_day_view(self, date_str: str = None) -> Dict[str, Any]:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        events = self.get_events_for_date(date_str)
        completed = sum(1 for e in events if e.status == "completed")
        upcoming = sum(1 for e in events if e.status == "scheduled")

        return {
            "date": date_str,
            "total_events": len(events),
            "completed": completed,
            "upcoming": upcoming,
            "events": [
                {
                    "id": e.event_id,
                    "title": e.title,
                    "type": e.event_type.value,
                    "time": e.start_time.strftime("%H:%M"),
                    "status": e.status,
                }
                for e in events
            ],
        }

    def get_week_view(self, start_date: str = None) -> Dict[str, Any]:
        events = self.get_events_for_week(start_date)
        by_day: Dict[str, List] = {}

        for event in events:
            day = event.start_time.strftime("%Y-%m-%d")
            if day not in by_day:
                by_day[day] = []
            by_day[day].append({
                "id": event.event_id,
                "title": event.title,
                "type": event.event_type.value,
                "time": event.start_time.strftime("%H:%M"),
                "status": event.status,
            })

        return {
            "start_date": start_date or (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d"),
            "total_events": len(events),
            "by_day": by_day,
        }

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._events)
        completed = sum(1 for e in self._events.values() if e.status == "completed")
        recurring = sum(1 for e in self._events.values() if e.recurring)

        by_type_counts = {k: len(v) for k, v in self._by_type.items()}

        return {
            "total_events": total,
            "completed_events": completed,
            "recurring_events": recurring,
            "events_by_type": by_type_counts,
            "dates_tracked": len(self._by_date),
        }
