from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class FirebaseEvent:
    event_id: str
    event_name: str
    timestamp: datetime
    user_id: str
    event_params: Dict[str, Any] = field(default_factory=dict)
    device_info: Optional[Dict[str, str]] = None
    country: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "event_params": self.event_params,
            "device_info": self.device_info,
            "country": self.country,
        }


@dataclass
class FirebaseAnalytics:
    metric_name: str
    value: float
    period_start: datetime
    period_end: datetime
    dimensions: Dict[str, str] = field(default_factory=dict)
    sample_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "dimensions": self.dimensions,
            "sample_size": self.sample_size,
        }


class FirebaseConnector:
    def __init__(self):
        self._connected = False
        self._project_ids: Dict[str, bool] = {}

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_events(self, project_id: str) -> List[FirebaseEvent]:
        if not self._connected:
            return []

        now = datetime.now()
        event_names = ["screen_view", "user_engagement", "purchase", "add_to_cart", "level_up"]
        events = [
            FirebaseEvent(
                event_id=f"evt_{i}",
                event_name=event_names[i % len(event_names)],
                timestamp=now,
                user_id=f"user_{i}",
                event_params={
                    "screen_name": f"level_{i % 5}",
                    "value": 100 + i * 50,
                },
                device_info={
                    "platform": "iOS" if i % 2 == 0 else "Android",
                    "model": "iPhone 14" if i % 2 == 0 else "Samsung S23",
                },
                country="US" if i % 3 == 0 else "CN" if i % 3 == 1 else "EU",
            )
            for i in range(25)
        ]
        return events

    def get_analytics(self, project_id: str) -> List[FirebaseAnalytics]:
        if not self._connected:
            return []

        now = datetime.now()
        metrics = [
            {"name": "active_users", "value": 12500},
            {"name": "new_users", "value": 1200},
            {"name": "sessions", "value": 45000},
            {"name": "session_duration", "value": 235.5},
            {"name": "conversion_rate", "value": 3.2},
            {"name": "retention_1d", "value": 45.8},
            {"name": "retention_7d", "value": 28.5},
            {"name": "retention_30d", "value": 15.2},
        ]
        analytics = [
            FirebaseAnalytics(
                metric_name=metric["name"],
                value=metric["value"],
                period_start=now.replace(hour=0, minute=0, second=0),
                period_end=now,
                dimensions={"platform": "all"},
                sample_size=10000 + i * 500,
            )
            for i, metric in enumerate(metrics)
        ]
        return analytics

    def get_crashlytics(self, project_id: str) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        now = datetime.now()
        return {
            "success": True,
            "total_crashes": 156,
            "unique_crashes": 23,
            "affected_users": 452,
            "crash_rate": 0.0035,
            "top_issues": [
                {"issue_id": "issue_1", "title": "NullReferenceException in GameManager", "count": 45},
                {"issue_id": "issue_2", "title": "OutOfMemoryException on level load", "count": 32},
                {"issue_id": "issue_3", "title": "NetworkTimeoutException", "count": 28},
            ],
            "period_start": now.replace(hour=0, minute=0, second=0).isoformat(),
            "period_end": now.isoformat(),
        }

    def sync_data(self) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        return {
            "success": True,
            "events_synced": 500,
            "analytics_synced": 50,
            "crashlytics_synced": 1,
            "timestamp": datetime.now().isoformat(),
        }