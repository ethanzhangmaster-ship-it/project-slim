from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class StrategyRecord:
    strategy_id: str = ""
    name: str = ""
    outcome: str = ""
    reason: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "outcome": self.outcome,
            "reason": self.reason,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StrategicInsight:
    insight_id: str = ""
    topic: str = ""
    insight_text: str = ""
    confidence: float = 0.0
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "topic": self.topic,
            "insight_text": self.insight_text,
            "confidence": self.confidence,
            "source": self.source,
        }


class StrategicMemory:
    def __init__(self):
        self._records: List[StrategyRecord] = []
        self._insights: List[StrategicInsight] = []

    def record_strategy(self, record: StrategyRecord) -> StrategyRecord:
        self._records.append(record)
        return record

    def get_successful_strategies(self) -> List[StrategyRecord]:
        return [r for r in self._records if r.outcome == "success"]

    def get_failed_strategies(self) -> List[StrategyRecord]:
        return [r for r in self._records if r.outcome == "failure"]

    def search(self, query: str) -> List[StrategyRecord]:
        query_lower = query.lower()
        results = []
        for record in self._records:
            if (query_lower in record.name.lower() or
                query_lower in record.reason.lower() or
                any(query_lower in tag.lower() for tag in record.tags)):
                results.append(record)
        return results

    def add_insight(self, insight: StrategicInsight) -> StrategicInsight:
        self._insights.append(insight)
        return insight
