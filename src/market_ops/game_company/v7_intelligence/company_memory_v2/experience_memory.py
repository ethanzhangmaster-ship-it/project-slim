from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random


@dataclass
class ExperienceRecord:
    experience_id: str
    description: str
    outcome: str
    tags: List[str] = field(default_factory=list)
    timestamp: str = ""


class ExperienceMemory:
    """Store and retrieve organizational experiences."""

    def __init__(self):
        self._experiences: List[ExperienceRecord] = []
        self._counter = 0

    def record_experience(self, exp: ExperienceRecord) -> str:
        """Record a new experience and return its ID."""
        self._counter += 1
        exp.experience_id = f"exp_{self._counter:04d}"
        if not exp.timestamp:
            from datetime import datetime
            exp.timestamp = datetime.now().isoformat()
        self._experiences.append(exp)
        return exp.experience_id

    def get_experiences(self, query: Optional[str] = None) -> List[ExperienceRecord]:
        """Retrieve experiences, optionally filtered by query string."""
        if query is None:
            return self._experiences
        query_lower = query.lower()
        return [
            e
            for e in self._experiences
            if query_lower in e.description.lower() or any(query_lower in t.lower() for t in e.tags)
        ]

    def get_success_patterns(self) -> List[ExperienceRecord]:
        """Return experiences with positive outcomes."""
        return [e for e in self._experiences if e.outcome.lower() in {"success", "win", "positive"}]
