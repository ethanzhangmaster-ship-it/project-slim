from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict
import uuid


class DecisionOutcomeStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    PENDING = "pending"


@dataclass
class DecisionRecord:
    record_id: str
    decision_name: str
    context: str
    decision_maker: str
    decided_at: datetime = field(default_factory=datetime.now)
    expected_outcome: str = ""

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "decision_name": self.decision_name,
            "context": self.context,
            "decision_maker": self.decision_maker,
            "decided_at": self.decided_at.isoformat(),
            "expected_outcome": self.expected_outcome,
        }


@dataclass
class DecisionOutcome:
    outcome_id: str
    decision_id: str
    status: DecisionOutcomeStatus
    actual_result: str
    evaluated_at: datetime = field(default_factory=datetime.now)
    deviation_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "outcome_id": self.outcome_id,
            "decision_id": self.decision_id,
            "status": self.status.value,
            "actual_result": self.actual_result,
            "evaluated_at": self.evaluated_at.isoformat(),
            "deviation_reason": self.deviation_reason,
        }


@dataclass
class DecisionPattern:
    pattern_id: str
    pattern_name: str
    decision_count: int
    success_rate: float
    common_contexts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "decision_count": self.decision_count,
            "success_rate": self.success_rate,
            "common_contexts": self.common_contexts,
        }


class DecisionHistory:
    def __init__(self):
        self._decisions: Dict[str, DecisionRecord] = {}
        self._outcomes: Dict[str, DecisionOutcome] = {}

    def record_decision(self, decision: DecisionRecord) -> DecisionRecord:
        self._decisions[decision.record_id] = decision
        return decision

    def get_decisions(self, filter_status: Optional[DecisionOutcomeStatus] = None) -> List[DecisionRecord]:
        if filter_status is None:
            return list(self._decisions.values())
        matched: List[DecisionRecord] = []
        for d in self._decisions.values():
            outcome = self._outcomes.get(d.record_id)
            if outcome and outcome.status == filter_status:
                matched.append(d)
        return matched

    def get_decision_outcomes(self) -> List[DecisionOutcome]:
        return list(self._outcomes.values())

    def analyze_decision_quality(self) -> Dict:
        total = len(self._outcomes)
        if total == 0:
            return {"total_evaluated": 0, "success_rate": 0.0, "partial_rate": 0.0, "failure_rate": 0.0}
        success = sum(1 for o in self._outcomes.values() if o.status == DecisionOutcomeStatus.SUCCESS)
        partial = sum(1 for o in self._outcomes.values() if o.status == DecisionOutcomeStatus.PARTIAL)
        failure = sum(1 for o in self._outcomes.values() if o.status == DecisionOutcomeStatus.FAILURE)
        return {
            "total_evaluated": total,
            "success_rate": round(success / total, 2),
            "partial_rate": round(partial / total, 2),
            "failure_rate": round(failure / total, 2),
        }

    def get_decision_patterns(self) -> List[DecisionPattern]:
        maker_map: Dict[str, List[DecisionOutcomeStatus]] = {}
        for d in self._decisions.values():
            outcome = self._outcomes.get(d.record_id)
            if outcome:
                maker_map.setdefault(d.decision_maker, []).append(outcome.status)
        patterns: List[DecisionPattern] = []
        for maker, statuses in maker_map.items():
            success_count = sum(1 for s in statuses if s == DecisionOutcomeStatus.SUCCESS)
            patterns.append(
                DecisionPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_name=f"{maker}_decisions",
                    decision_count=len(statuses),
                    success_rate=round(success_count / len(statuses), 2),
                )
            )
        return patterns

    def get_stats(self) -> Dict:
        total_decisions = len(self._decisions)
        total_outcomes = len(self._outcomes)
        quality = self.analyze_decision_quality()
        return {
            "total_decisions": total_decisions,
            "total_outcomes": total_outcomes,
            "evaluation_coverage": round(total_outcomes / total_decisions, 2) if total_decisions else 0.0,
            **quality,
        }
