from dataclasses import dataclass, field
from typing import List, Dict
import random


@dataclass
class FailureRecord:
    failure_id: str
    description: str
    root_cause: str
    impact: str
    lessons: List[str] = field(default_factory=list)


class FailureMemory:
    """Store and learn from failures."""

    def __init__(self):
        self._failures: List[FailureRecord] = []
        self._counter = 0

    def record_failure(self, failure: FailureRecord) -> str:
        """Record a failure and return its ID."""
        self._counter += 1
        failure.failure_id = f"fail_{self._counter:04d}"
        self._failures.append(failure)
        return failure.failure_id

    def get_failures(self) -> List[FailureRecord]:
        """Return all recorded failures."""
        return self._failures

    def get_lessons(self) -> List[str]:
        """Aggregate lessons from all failures."""
        lessons: List[str] = []
        for f in self._failures:
            lessons.extend(f.lessons)
        if not lessons:
            lessons = [
                "Always validate assumptions before scaling.",
                "Monitor key metrics in real time.",
                "Design for graceful degradation.",
            ]
        return lessons
