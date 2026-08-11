from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class LearningType(Enum):
    PREDICTION_ERROR = "prediction_error"
    STRATEGY_ADAPTATION = "strategy_adaptation"
    BIAS_CORRECTION = "bias_correction"
    CALIBRATION_LESSON = "calibration_lesson"
    DATA_QUALITY = "data_quality"
    PERFORMANCE_INSIGHT = "performance_insight"


class LearningStatus(Enum):
    STORED = "stored"
    APPLIED = "applied"
    ARCHIVED = "archived"


@dataclass
class LearningInsight:
    insight_id: str
    title: str
    description: str
    confidence: float
    impact: float
    source: str
    tags: List[str] = field(default_factory=list)
    related_learnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "impact": self.impact,
            "source": self.source,
            "tags": self.tags,
            "related_learnings": self.related_learnings,
        }


@dataclass
class LearningRecord:
    learning_id: str
    learning_type: LearningType
    content: Dict[str, Any]
    insight: Optional[LearningInsight] = None
    status: LearningStatus = LearningStatus.STORED
    timestamp: datetime = field(default_factory=datetime.now)
    applied_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "learning_id": self.learning_id,
            "learning_type": self.learning_type.value,
            "content": self.content,
            "insight": self.insight.to_dict() if self.insight else None,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "applied_timestamp": self.applied_timestamp.isoformat() if self.applied_timestamp else None,
            "metadata": self.metadata,
        }


class LearningMemory:
    def __init__(self):
        self._learnings: Dict[str, LearningRecord] = {}
        self._insights: Dict[str, LearningInsight] = {}
        self._learning_index: Dict[str, List[str]] = {}

    def store_learning(self, learning: LearningRecord) -> LearningRecord:
        self._learnings[learning.learning_id] = learning

        if learning.insight:
            self._insights[learning.insight.insight_id] = learning.insight

        for tag in (learning.insight.tags if learning.insight else []):
            if tag not in self._learning_index:
                self._learning_index[tag] = []
            self._learning_index[tag].append(learning.learning_id)

        return learning

    def retrieve_learnings(self, query: Dict[str, Any]) -> List[LearningRecord]:
        results = list(self._learnings.values())

        if "learning_type" in query:
            results = [l for l in results if l.learning_type.value == query["learning_type"]]

        if "status" in query:
            results = [l for l in results if l.status.value == query["status"]]

        if "tags" in query:
            tags = query["tags"]
            if isinstance(tags, list):
                results = [
                    l for l in results
                    if l.insight and any(tag in l.insight.tags for tag in tags)
                ]
            else:
                results = [
                    l for l in results
                    if l.insight and tags in l.insight.tags
                ]

        if "start_time" in query:
            start_time = datetime.fromisoformat(query["start_time"])
            results = [l for l in results if l.timestamp >= start_time]

        if "end_time" in query:
            end_time = datetime.fromisoformat(query["end_time"])
            results = [l for l in results if l.timestamp <= end_time]

        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def get_key_learnings(self, limit: int = 10) -> List[LearningInsight]:
        insights = sorted(
            self._insights.values(),
            key=lambda x: x.confidence * x.impact,
            reverse=True,
        )
        return insights[:limit]

    def apply_learning(self, learning_id: str) -> bool:
        if learning_id not in self._learnings:
            return False

        learning = self._learnings[learning_id]
        learning.status = LearningStatus.APPLIED
        learning.applied_timestamp = datetime.now()
        return True

    def get_learning_stats(self) -> Dict[str, Any]:
        total = len(self._learnings)
        applied = sum(1 for l in self._learnings.values() if l.status == LearningStatus.APPLIED)
        stored = sum(1 for l in self._learnings.values() if l.status == LearningStatus.STORED)
        archived = sum(1 for l in self._learnings.values() if l.status == LearningStatus.ARCHIVED)

        by_type = {}
        for learning in self._learnings.values():
            by_type[learning.learning_type.value] = by_type.get(learning.learning_type.value, 0) + 1

        avg_confidence = (
            sum(l.insight.confidence for l in self._learnings.values() if l.insight)
            / len([l for l in self._learnings.values() if l.insight])
            if any(l.insight for l in self._learnings.values())
            else 0.0
        )

        avg_impact = (
            sum(l.insight.impact for l in self._learnings.values() if l.insight)
            / len([l for l in self._learnings.values() if l.insight])
            if any(l.insight for l in self._learnings.values())
            else 0.0
        )

        return {
            "total_learnings": total,
            "applied_learnings": applied,
            "stored_learnings": stored,
            "archived_learnings": archived,
            "learnings_by_type": by_type,
            "average_confidence": avg_confidence,
            "average_impact": avg_impact,
            "total_insights": len(self._insights),
            "record_count": len(self._learning_index),
            "stats_timestamp": datetime.now().isoformat(),
        }