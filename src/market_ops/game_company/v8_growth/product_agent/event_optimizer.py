from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class EventType(Enum):
    LIMITED_TIME = "limited_time"
    RECURRING = "recurring"
    MILESTONE = "milestone"
    SEASONAL = "seasonal"
    PROMOTIONAL = "promotional"
    COMMUNITY = "community"


class EventStatus(Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class GameEvent:
    event_id: str
    name: str
    type: EventType
    status: EventStatus = EventStatus.PLANNED
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    participants: int = 0
    revenue: float = 0.0
    engagement_score: float = 0.0
    conversion_rate: float = 0.0
    retention_impact: float = 0.0
    rewards_offered: List[str] = field(default_factory=list)
    special_offers: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "participants": self.participants,
            "revenue": self.revenue,
            "engagement_score": self.engagement_score,
            "conversion_rate": self.conversion_rate,
            "retention_impact": self.retention_impact,
            "rewards_offered": self.rewards_offered,
            "special_offers": self.special_offers,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EventPerformance:
    event_id: str
    participant_count: int = 0
    completion_rate: float = 0.0
    revenue_per_participant: float = 0.0
    engagement_lift: float = 0.0
    retention_lift: float = 0.0
    dau_increase: float = 0.0
    player_feedback_score: float = 0.0
    viral_coefficient: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "participant_count": self.participant_count,
            "completion_rate": self.completion_rate,
            "revenue_per_participant": self.revenue_per_participant,
            "engagement_lift": self.engagement_lift,
            "retention_lift": self.retention_lift,
            "dau_increase": self.dau_increase,
            "player_feedback_score": self.player_feedback_score,
            "viral_coefficient": self.viral_coefficient,
        }


@dataclass
class EventRecommendation:
    recommendation_id: str
    event_type: EventType
    suggestion: str
    expected_impact: float = 0.0
    confidence: float = 0.0
    priority: int = 5
    timing: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "event_type": self.event_type.value,
            "suggestion": self.suggestion,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "priority": self.priority,
            "timing": self.timing,
            "description": self.description,
        }


class EventOptimizer:
    def __init__(self):
        self._events: Dict[str, GameEvent] = {}
        self._performance: Dict[str, EventPerformance] = {}
        self._recommendations: List[EventRecommendation] = []
        self._historical_data: List[Dict[str, Any]] = []
        self._event_calendar: Dict[str, List[str]] = {}

    def create_event(
        self,
        name: str,
        type: EventType,
        start_date: str = None,
        end_date: str = None,
        rewards: List[str] = None
    ) -> GameEvent:
        event_id = f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        event = GameEvent(
            event_id=event_id,
            name=name,
            type=type,
            start_date=start_date,
            end_date=end_date,
            rewards_offered=rewards or ["coins", "gems", "items"],
        )
        self._events[event_id] = event
        return event

    def activate_event(self, event_id: str) -> Optional[GameEvent]:
        event = self._events.get(event_id)
        if event and event.status == EventStatus.PLANNED:
            event.status = EventStatus.ACTIVE
        return event

    def complete_event(self, event_id: str, performance_data: Dict[str, Any] = None) -> Optional[GameEvent]:
        event = self._events.get(event_id)
        if not event or event.status != EventStatus.ACTIVE:
            return None

        event.status = EventStatus.COMPLETED

        perf = self._record_performance(event_id, performance_data)
        event.participants = perf.participant_count
        event.revenue = perf.revenue_per_participant * perf.participant_count
        event.engagement_score = perf.engagement_lift
        event.conversion_rate = perf.completion_rate
        event.retention_impact = perf.retention_lift

        self._historical_data.append({
            "event_id": event_id,
            "type": event.type.value,
            "performance": perf.to_dict(),
            "timestamp": datetime.now().isoformat(),
        })
        return event

    def _record_performance(self, event_id: str, data: Dict[str, Any] = None) -> EventPerformance:
        perf = EventPerformance(
            event_id=event_id,
            participant_count=data.get("participant_count", random.randint(1000, 50000)) if data else random.randint(1000, 50000),
            completion_rate=data.get("completion_rate", random.uniform(0.3, 0.8)) if data else random.uniform(0.3, 0.8),
            revenue_per_participant=data.get("revenue_per_participant", random.uniform(1.0, 10.0)) if data else random.uniform(1.0, 10.0),
            engagement_lift=data.get("engagement_lift", random.uniform(0.1, 0.5)) if data else random.uniform(0.1, 0.5),
            retention_lift=data.get("retention_lift", random.uniform(0.05, 0.15)) if data else random.uniform(0.05, 0.15),
            dau_increase=data.get("dau_increase", random.uniform(0.1, 0.4)) if data else random.uniform(0.1, 0.4),
            player_feedback_score=data.get("player_feedback_score", random.uniform(3.0, 5.0)) if data else random.uniform(3.0, 5.0),
            viral_coefficient=data.get("viral_coefficient", random.uniform(0.5, 2.0)) if data else random.uniform(0.5, 2.0),
        )
        self._performance[event_id] = perf
        return perf

    def optimize_events(self) -> List[EventRecommendation]:
        recommendations = []

        type_performance = self._analyze_type_performance()
        for event_type, perf in type_performance.items():
            if perf["avg_engagement"] < 0.2:
                rec = EventRecommendation(
                    recommendation_id=f"rec_{event_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    event_type=event_type,
                    suggestion="improve_engagement",
                    expected_impact=0.2,
                    confidence=0.75,
                    priority=2,
                    description=f"{event_type.value} events have low engagement - consider more rewards",
                )
                recommendations.append(rec)

            if perf["avg_retention_lift"] > 0.1:
                rec = EventRecommendation(
                    recommendation_id=f"rec_retention_{event_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    event_type=event_type,
                    suggestion="increase_frequency",
                    expected_impact=perf["avg_retention_lift"] * 0.5,
                    confidence=0.85,
                    priority=1,
                    description=f"{event_type.value} events improve retention - schedule more",
                )
                recommendations.append(rec)

        rec = EventRecommendation(
            recommendation_id=f"rec_calendar_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            event_type=EventType.SEASONAL,
            suggestion="plan_calendar",
            expected_impact=0.1,
            confidence=0.9,
            priority=3,
            timing="next_quarter",
            description="Plan seasonal events calendar for next quarter",
        )
        recommendations.append(rec)

        self._recommendations.extend(recommendations)
        return recommendations

    def _analyze_type_performance(self) -> Dict[EventType, Dict[str, Any]]:
        analysis = {}
        for event_type in EventType:
            type_events = [e for e in self._events.values() if e.type == event_type and e.status == EventStatus.COMPLETED]
            if type_events:
                perfs = [self._performance.get(e.event_id) for e in type_events]
                perfs = [p for p in perfs if p]
                if perfs:
                    analysis[event_type] = {
                        "count": len(type_events),
                        "avg_engagement": sum(p.engagement_lift for p in perfs) / len(perfs),
                        "avg_retention_lift": sum(p.retention_lift for p in perfs) / len(perfs),
                        "avg_revenue": sum(p.revenue_per_participant for p in perfs) / len(perfs),
                    }
            else:
                analysis[event_type] = {"count": 0, "avg_engagement": 0, "avg_retention_lift": 0, "avg_revenue": 0}
        return analysis

    def get_event(self, event_id: str) -> Optional[GameEvent]:
        return self._events.get(event_id)

    def get_active_events(self) -> List[GameEvent]:
        return [e for e in self._events.values() if e.status == EventStatus.ACTIVE]

    def get_completed_events(self) -> List[GameEvent]:
        return [e for e in self._events.values() if e.status == EventStatus.COMPLETED]

    def get_performance(self, event_id: str) -> Optional[EventPerformance]:
        return self._performance.get(event_id)

    def get_historical_data(self) -> List[Dict[str, Any]]:
        return list(self._historical_data)

    def get_recommendations(self) -> List[EventRecommendation]:
        return list(self._recommendations)

    def get_event_calendar(self) -> Dict[str, List[str]]:
        return dict(self._event_calendar)

    def add_to_calendar(self, date: str, event_id: str):
        if date not in self._event_calendar:
            self._event_calendar[date] = []
        self._event_calendar[date].append(event_id)

    def get_stats(self) -> Dict[str, Any]:
        events = list(self._events.values())
        return {
            "total_events": len(events),
            "events_by_status": {
                status.value: sum(1 for e in events if e.status == status)
                for status in EventStatus
            },
            "events_by_type": {
                type.value: sum(1 for e in events if e.type == type)
                for type in EventType
            },
            "total_performance_records": len(self._performance),
            "total_recommendations": len(self._recommendations),
            "historical_events_count": len(self._historical_data),
        }