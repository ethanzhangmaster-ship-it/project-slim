from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class DecisionRecord:
    decision_id: str
    strategy_id: str
    action_type: str
    outcome: str = "pending"
    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)
    success: Optional[bool] = None
    lessons_learned: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class DecisionMemory:
    def __init__(self):
        self.records: Dict[str, DecisionRecord] = {}
        self.success_patterns: Dict[str, int] = {}
        self.failure_patterns: Dict[str, int] = {}

    def add(self, record: DecisionRecord) -> None:
        self.records[record.decision_id] = record

    def get(self, decision_id: str) -> Optional[DecisionRecord]:
        return self.records.get(decision_id)

    def update_outcome(self, decision_id: str, outcome: str, metrics_after: Dict[str, Any], success: bool, lessons: List[str] = None) -> None:
        record = self.records.get(decision_id)
        if not record:
            return

        record.outcome = outcome
        record.metrics_after = metrics_after
        record.success = success
        if lessons:
            record.lessons_learned.extend(lessons)

        pattern_key = f"{record.action_type}_{'success' if success else 'failure'}"
        if success:
            self.success_patterns[pattern_key] = self.success_patterns.get(pattern_key, 0) + 1
        else:
            self.failure_patterns[pattern_key] = self.failure_patterns.get(pattern_key, 0) + 1

    def get_success_rate(self, action_type: str) -> float:
        success_key = f"{action_type}_success"
        failure_key = f"{action_type}_failure"
        
        successes = self.success_patterns.get(success_key, 0)
        failures = self.failure_patterns.get(failure_key, 0)
        total = successes + failures
        
        if total == 0:
            return 0.5
        
        return successes / total

    def get_patterns(self) -> Dict[str, Any]:
        return {
            "success_patterns": dict(sorted(self.success_patterns.items(), key=lambda x: x[1], reverse=True)),
            "failure_patterns": dict(sorted(self.failure_patterns.items(), key=lambda x: x[1], reverse=True)),
        }

    def get_history(self) -> List[DecisionRecord]:
        return list(self.records.values())

    def record(self, data: Dict[str, Any]) -> DecisionRecord:
        record = DecisionRecord(
            decision_id=f"dec_{hash(str(data)) % 10000:04d}",
            strategy_id=data.get("strategy_id", "unknown"),
            action_type=data.get("decision", "unknown"),
            outcome=data.get("outcome", "pending"),
        )
        self.add(record)
        return record

    def get_lessons(self) -> List[str]:
        lessons = []
        for record in self.records.values():
            if record.success is not None:
                lessons.extend(record.lessons_learned)
        return lessons[:20]

    def add_demo(self) -> DecisionRecord:
        record = DecisionRecord(
            decision_id="decision_0001",
            strategy_id="strategy_0001",
            action_type="scale_up",
            metrics_before={"roas": 2.5, "budget": 500},
        )
        self.add(record)
        self.update_outcome(
            "decision_0001",
            outcome="completed",
            metrics_after={"roas": 2.3, "budget": 650, "revenue": "+28%"},
            success=True,
            lessons=["Scale up works best when confidence > 0.85"],
        )
        return record
