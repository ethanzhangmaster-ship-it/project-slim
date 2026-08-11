from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class LearningType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PATTERN = "pattern"
    INSIGHT = "insight"
    CORRECTION = "correction"


@dataclass
class GrowthLearning:
    learning_id: str
    type: LearningType
    category: str
    title: str
    description: str = ""
    confidence: float = 0.0
    applicability: float = 1.0
    source: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    applied_count: int = 0
    last_applied: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "learning_id": self.learning_id,
            "type": self.type.value,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "applicability": self.applicability,
            "source": self.source,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
            "applied_count": self.applied_count,
            "last_applied": self.last_applied.isoformat() if self.last_applied else None,
        }


class GrowthMemory:
    def __init__(self):
        self._learnings: List[GrowthLearning] = []
        self._success_patterns: List[Dict[str, Any]] = []
        self._failed_patterns: List[Dict[str, Any]] = []

    def record_learning(self, learning: GrowthLearning) -> GrowthLearning:
        self._learnings.append(learning)
        if learning.type == LearningType.SUCCESS:
            self._success_patterns.append({
                "pattern": learning.title,
                "evidence": learning.evidence,
                "confidence": learning.confidence,
            })
        elif learning.type == LearningType.FAILURE:
            self._failed_patterns.append({
                "pattern": learning.title,
                "evidence": learning.evidence,
                "confidence": learning.confidence,
            })
        return learning

    def get_learnings(self, query: Dict[str, Any] = None) -> List[GrowthLearning]:
        if not query:
            return list(self._learnings)

        results = []
        for learning in self._learnings:
            match = True
            if "type" in query and learning.type.value != query["type"]:
                match = False
            if "category" in query and learning.category != query["category"]:
                match = False
            if "min_confidence" in query and learning.confidence < query["min_confidence"]:
                match = False
            if match:
                results.append(learning)
        return results

    def get_successful_patterns(self, category: str = None) -> List[Dict[str, Any]]:
        if category:
            learnings = [l for l in self._learnings if l.type == LearningType.SUCCESS and l.category == category]
            return [{"title": l.title, "evidence": l.evidence, "confidence": l.confidence} for l in learnings]
        return list(self._success_patterns)

    def get_failed_patterns(self, category: str = None) -> List[Dict[str, Any]]:
        if category:
            learnings = [l for l in self._learnings if l.type == LearningType.FAILURE and l.category == category]
            return [{"title": l.title, "evidence": l.evidence, "confidence": l.confidence} for l in learnings]
        return list(self._failed_patterns)

    def apply_lessons(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        applicable = []
        for learning in self._learnings:
            if learning.applicability > 0.5:
                applicable.append({
                    "learning_id": learning.learning_id,
                    "title": learning.title,
                    "applicability": learning.applicability,
                    "suggestion": learning.description,
                })
                learning.applied_count += 1
                learning.last_applied = datetime.now()
        return applicable

    def get_learning(self, learning_id: str) -> Optional[GrowthLearning]:
        for learning in self._learnings:
            if learning.learning_id == learning_id:
                return learning
        return None

    def update_confidence(self, learning_id: str, new_confidence: float) -> bool:
        learning = self.get_learning(learning_id)
        if learning:
            learning.confidence = new_confidence
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._learnings)
        by_type = {}
        for learning in self._learnings:
            by_type[learning.type.value] = by_type.get(learning.type.value, 0) + 1

        avg_confidence = sum(l.confidence for l in self._learnings) / total if total > 0 else 0
        total_applications = sum(l.applied_count for l in self._learnings)

        return {
            "total_learnings": total,
            "by_type": by_type,
            "success_patterns": len(self._success_patterns),
            "failed_patterns": len(self._failed_patterns),
            "avg_confidence": avg_confidence,
            "total_applications": total_applications,
        }

    def clear_old_learnings(self, days: int = 90) -> int:
        cutoff = datetime.now() - __import__("datetime").timedelta(days=days)
        original_count = len(self._learnings)
        self._learnings = [l for l in self._learnings if l.created_at >= cutoff]
        return original_count - len(self._learnings)