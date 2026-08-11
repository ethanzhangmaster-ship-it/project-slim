from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from collections import defaultdict


class EventType(Enum):
    INSTALL = "install"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TUTORIAL_COMPLETE = "tutorial_complete"
    LEVEL_COMPLETE = "level_complete"
    PURCHASE = "purchase"
    SUBSCRIPTION = "subscription"
    AD_IMPRESSION = "ad_impression"
    AD_CLICK = "ad_click"
    AD_REVENUE = "ad_revenue"
    CUSTOM = "custom"


@dataclass
class EventRecord:
    event_id: str
    event_type: EventType
    user_id: str
    timestamp: datetime
    properties: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    country: str = "US"
    platform: str = "ios"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "properties": self.properties,
            "source": self.source,
            "country": self.country,
            "platform": self.platform,
        }


class EventCollector:
    def __init__(self):
        self._events: Dict[str, EventRecord] = {}
        self._event_buckets: Dict[str, List[str]] = defaultdict(list)
        self._user_events: Dict[str, List[str]] = defaultdict(list)

    def collect(
        self,
        event_type: EventType,
        user_id: str,
        properties: Dict[str, Any] = None,
        source: str = "unknown",
        country: str = "US",
        platform: str = "ios",
    ) -> EventRecord:
        event_id = f"evt_{hash(event_type.value + user_id + str(datetime.now())) % 1000000:06d}"

        event = EventRecord(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            timestamp=datetime.now(),
            properties=properties or {},
            source=source,
            country=country,
            platform=platform,
        )

        self._events[event_id] = event
        self._event_buckets[event_type.value].append(event_id)
        self._user_events[user_id].append(event_id)

        return event

    def collect_batch(self, events: List[Dict[str, Any]]) -> List[EventRecord]:
        results = []
        for evt in events:
            etype = evt.get("event_type", "custom")
            if isinstance(etype, str):
                try:
                    etype = EventType(etype)
                except ValueError:
                    etype = EventType.CUSTOM

            result = self.collect(
                event_type=etype,
                user_id=evt.get("user_id", "unknown"),
                properties=evt.get("properties", {}),
                source=evt.get("source", "batch"),
                country=evt.get("country", "US"),
                platform=evt.get("platform", "ios"),
            )
            results.append(result)
        return results

    def get_event(self, event_id: str) -> Optional[EventRecord]:
        return self._events.get(event_id)

    def get_events_by_type(self, event_type: EventType, limit: int = 100) -> List[EventRecord]:
        ids = self._event_buckets.get(event_type.value, [])
        return [self._events[eid] for eid in ids[-limit:]]

    def get_user_events(self, user_id: str, limit: int = 100) -> List[EventRecord]:
        ids = self._user_events.get(user_id, [])
        return [self._events[eid] for eid in ids[-limit:]]

    def get_events_by_date(self, date_str: str) -> List[EventRecord]:
        results = []
        for event in self._events.values():
            if event.timestamp.strftime("%Y-%m-%d") == date_str:
                results.append(event)
        return results

    def get_event_count_by_type(self, start_date: str = None, end_date: str = None) -> Dict[str, int]:
        counts = {etype.value: 0 for etype in EventType}
        for event in self._events.values():
            if start_date and event.timestamp.strftime("%Y-%m-%d") < start_date:
                continue
            if end_date and event.timestamp.strftime("%Y-%m-%d") > end_date:
                continue
            counts[event.event_type.value] += 1
        return counts

    def get_dau(self, date_str: str = None) -> int:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        users = set()
        for event in self._events.values():
            if event.timestamp.strftime("%Y-%m-%d") == date_str:
                users.add(event.user_id)
        return len(users)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_events": len(self._events),
            "event_type_counts": {k: len(v) for k, v in self._event_buckets.items()},
            "unique_users": len(self._user_events),
            "events_per_user": round(len(self._events) / len(self._user_events), 2) if self._user_events else 0,
        }
