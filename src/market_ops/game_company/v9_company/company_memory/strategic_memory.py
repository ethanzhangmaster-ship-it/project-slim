from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
import uuid


@dataclass
class StrategicRecord:
    record_id: str
    strategy_name: str
    description: str
    outcome: str
    success_score: float
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "strategy_name": self.strategy_name,
            "description": self.description,
            "outcome": self.outcome,
            "success_score": self.success_score,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }


@dataclass
class StrategicPattern:
    pattern_id: str
    pattern_name: str
    occurrence_count: int
    avg_success_score: float
    related_strategies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "occurrence_count": self.occurrence_count,
            "avg_success_score": self.avg_success_score,
            "related_strategies": self.related_strategies,
        }


@dataclass
class StrategicLesson:
    lesson_id: str
    category: str
    lesson: str
    source_strategy_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "lesson_id": self.lesson_id,
            "category": self.category,
            "lesson": self.lesson,
            "source_strategy_id": self.source_strategy_id,
            "created_at": self.created_at.isoformat(),
        }


class StrategicMemory:
    def __init__(self):
        self._strategies: Dict[str, StrategicRecord] = {}
        self._lessons: Dict[str, StrategicLesson] = {}

    def record_strategy(self, strategy: StrategicRecord) -> StrategicRecord:
        self._strategies[strategy.record_id] = strategy
        return strategy

    def get_strategies(self) -> List[StrategicRecord]:
        return list(self._strategies.values())

    def get_successful_strategies(self, threshold: float = 0.7) -> List[StrategicRecord]:
        return [s for s in self._strategies.values() if s.success_score >= threshold]

    def get_lessons(self, category: Optional[str] = None) -> List[StrategicLesson]:
        if category is None:
            return list(self._lessons.values())
        return [l for l in self._lessons.values() if l.category == category]

    def get_strategic_patterns(self) -> List[StrategicPattern]:
        tags_map: Dict[str, List[float]] = {}
        for s in self._strategies.values():
            for tag in s.tags:
                tags_map.setdefault(tag, []).append(s.success_score)
        patterns: List[StrategicPattern] = []
        for tag, scores in tags_map.items():
            patterns.append(
                StrategicPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_name=tag,
                    occurrence_count=len(scores),
                    avg_success_score=round(sum(scores) / len(scores), 2),
                )
            )
        return patterns

    def get_stats(self) -> Dict:
        total = len(self._strategies)
        successful = len(self.get_successful_strategies())
        return {
            "total_strategies": total,
            "successful_strategies": successful,
            "success_rate": round(successful / total, 2) if total else 0.0,
            "total_lessons": len(self._lessons),
            "avg_success_score": round(
                sum(s.success_score for s in self._strategies.values()) / total, 2
            ) if total else 0.0,
        }
