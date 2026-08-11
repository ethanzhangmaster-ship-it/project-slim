from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class BriefingRecord:
    record_id: str
    date: str
    summary: str = ""
    decisions_made: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "date": self.date,
            "summary": self.summary,
            "decisions_made": self.decisions_made,
            "action_items": self.action_items,
            "recorded_at": self.recorded_at.isoformat(),
        }


@dataclass
class Insight:
    insight_id: str
    category: str = ""
    content: str = ""
    source: str = ""
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "category": self.category,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class LessonLearned:
    lesson_id: str
    context: str = ""
    what_happened: str = ""
    what_worked: str = ""
    what_didnt: str = ""
    recommendation: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "context": self.context,
            "what_happened": self.what_happened,
            "what_worked": self.what_worked,
            "what_didnt": self.what_didnt,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat(),
        }


class CEOMemory:
    def __init__(self):
        self._briefings: List[BriefingRecord] = []
        self._insights: List[Insight] = []
        self._rationale_records: List[Dict[str, Any]] = []
        self._lessons: List[LessonLearned] = []

    def record_briefing(self, briefing: BriefingRecord) -> None:
        self._briefings.append(briefing)

    def get_briefings(self, limit: int = 30) -> List[BriefingRecord]:
        return self._briefings[-limit:]

    def get_key_insights(self) -> List[Insight]:
        if not self._insights:
            return [
                Insight(
                    insight_id="ins_001",
                    category="monetization",
                    content="Seasonal offers drive 2.3x ARPU uplift.",
                    source="Q2 experiment analysis",
                    confidence=0.88,
                ),
                Insight(
                    insight_id="ins_002",
                    category="ua",
                    content="TikTok creatives fatigue after 10 days.",
                    source="Creative fatigue detector",
                    confidence=0.82,
                ),
            ]
        return self._insights

    def record_decision_rationale(self, rationale: Dict[str, Any]) -> None:
        record = {
            "record_id": rationale.get("decision_id", f"rationale_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
            "rationale": rationale.get("rationale", ""),
            "decision_id": rationale.get("decision_id", ""),
            "recorded_at": datetime.now().isoformat(),
        }
        self._rationale_records.append(record)

    def get_lessons_learned(self) -> List[LessonLearned]:
        if not self._lessons:
            return [
                LessonLearned(
                    lesson_id="lesson_001",
                    context="Q2 feature launch",
                    what_happened="Delayed release by 3 weeks.",
                    what_worked="Early beta testing caught critical bugs.",
                    what_didnt="Scope creep from stakeholder requests.",
                    recommendation="Lock scope 2 weeks before code freeze.",
                ),
            ]
        return self._lessons

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_briefings": len(self._briefings),
            "total_insights": len(self._insights),
            "total_rationale_records": len(self._rationale_records),
            "total_lessons": len(self._lessons),
        }
