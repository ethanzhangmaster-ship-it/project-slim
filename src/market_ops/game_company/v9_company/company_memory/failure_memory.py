from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict
import uuid


class FailureType(Enum):
    PRODUCT = "product"
    GROWTH = "growth"
    TECH = "tech"
    MARKET = "market"
    TEAM = "team"


@dataclass
class FailureRecord:
    record_id: str
    failure_type: FailureType
    description: str
    impact_score: float
    occurred_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "failure_type": self.failure_type.value,
            "description": self.description,
            "impact_score": self.impact_score,
            "occurred_at": self.occurred_at.isoformat(),
            "resolved": self.resolved,
            "resolution_notes": self.resolution_notes,
        }


@dataclass
class FailurePattern:
    pattern_id: str
    pattern_name: str
    failure_type: FailureType
    occurrence_count: int
    common_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "failure_type": self.failure_type.value,
            "occurrence_count": self.occurrence_count,
            "common_factors": self.common_factors,
        }


@dataclass
class FailureLesson:
    lesson_id: str
    lesson: str
    failure_type: FailureType
    source_record_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "lesson_id": self.lesson_id,
            "lesson": self.lesson,
            "failure_type": self.failure_type.value,
            "source_record_id": self.source_record_id,
            "created_at": self.created_at.isoformat(),
        }


class FailureMemory:
    def __init__(self):
        self._failures: Dict[str, FailureRecord] = {}
        self._lessons: Dict[str, FailureLesson] = {}

    def record_failure(self, failure: FailureRecord) -> FailureRecord:
        self._failures[failure.record_id] = failure
        return failure

    def get_failures(self, failure_type: Optional[FailureType] = None) -> List[FailureRecord]:
        if failure_type is None:
            return list(self._failures.values())
        return [f for f in self._failures.values() if f.failure_type == failure_type]

    def get_failure_patterns(self) -> List[FailurePattern]:
        type_counts: Dict[FailureType, int] = {}
        for f in self._failures.values():
            type_counts[f.failure_type] = type_counts.get(f.failure_type, 0) + 1
        patterns: List[FailurePattern] = []
        for ft, count in type_counts.items():
            patterns.append(
                FailurePattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_name=f"{ft.value}_recurring",
                    failure_type=ft,
                    occurrence_count=count,
                    common_factors=["资源不足", "时间压力", "沟通缺失"],
                )
            )
        return patterns

    def get_lessons_from_failures(self) -> List[FailureLesson]:
        return list(self._lessons.values())

    def get_failure_rate(self) -> float:
        total = len(self._failures)
        if total == 0:
            return 0.0
        unresolved = sum(1 for f in self._failures.values() if not f.resolved)
        return round(unresolved / total, 2)

    def get_stats(self) -> Dict:
        total = len(self._failures)
        unresolved = sum(1 for f in self._failures.values() if not f.resolved)
        return {
            "total_failures": total,
            "unresolved": unresolved,
            "resolved": total - unresolved,
            "failure_rate": self.get_failure_rate(),
            "total_lessons": len(self._lessons),
            "by_type": {ft.value: sum(1 for f in self._failures.values() if f.failure_type == ft) for ft in FailureType},
        }
