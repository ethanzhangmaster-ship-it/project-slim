from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class DecisionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


@dataclass
class DecisionOption:
    option_id: str
    label: str
    description: str = ""
    probability: float = 0.5
    payoff: float = 0.0
    cost: float = 0.0
    risks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "label": self.label,
            "description": self.description,
            "probability": self.probability,
            "payoff": self.payoff,
            "cost": self.cost,
            "risks": self.risks,
        }


@dataclass
class ExpectedValue:
    option_id: str
    ev: float = 0.0
    best_case: float = 0.0
    worst_case: float = 0.0
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "ev": self.ev,
            "best_case": self.best_case,
            "worst_case": self.worst_case,
            "confidence": self.confidence.value,
        }


@dataclass
class Decision:
    decision_id: str
    context: str = ""
    chosen_option_id: Optional[str] = None
    options: List[DecisionOption] = field(default_factory=list)
    expected_values: List[ExpectedValue] = field(default_factory=list)
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM
    rationale: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "context": self.context,
            "chosen_option_id": self.chosen_option_id,
            "options": [o.to_dict() for o in self.options],
            "expected_values": [e.to_dict() for e in self.expected_values],
            "confidence": self.confidence.value,
            "rationale": self.rationale,
            "created_at": self.created_at.isoformat(),
        }


class DecisionFramework:
    def __init__(self):
        self._decisions: List[Decision] = []
        self._rationale_map: Dict[str, str] = {}

    def make_decision(self, context: str) -> Decision:
        decision_id = f"decision_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        options = [
            DecisionOption(
                option_id=f"{decision_id}_opt_a",
                label="Aggressive expansion",
                description="Double UA spend and enter new markets.",
                probability=0.35,
                payoff=2000000.0,
                cost=800000.0,
                risks=["High burn", "Market uncertainty"],
            ),
            DecisionOption(
                option_id=f"{decision_id}_opt_b",
                label="Steady optimization",
                description="Improve LTV/CAC in existing markets.",
                probability=0.65,
                payoff=1200000.0,
                cost=400000.0,
                risks=["Slower growth"],
            ),
        ]

        expected_values = self._calculate_evs(options)
        chosen = max(expected_values, key=lambda ev: ev.ev)

        decision = Decision(
            decision_id=decision_id,
            context=context,
            chosen_option_id=chosen.option_id,
            options=options,
            expected_values=expected_values,
            confidence=chosen.confidence,
            rationale=f"Selected {chosen.option_id} with highest EV.",
        )

        self._decisions.append(decision)
        self._rationale_map[decision_id] = decision.rationale
        return decision

    def evaluate_options(self, options: List[DecisionOption]) -> List[ExpectedValue]:
        return self._calculate_evs(options)

    def _calculate_evs(self, options: List[DecisionOption]) -> List[ExpectedValue]:
        results = []
        for opt in options:
            ev = (opt.probability * opt.payoff) - opt.cost
            best = opt.payoff - opt.cost
            worst = -opt.cost
            confidence = (
                DecisionConfidence.HIGH if opt.probability >= 0.7
                else DecisionConfidence.MEDIUM if opt.probability >= 0.4
                else DecisionConfidence.LOW
            )
            results.append(
                ExpectedValue(
                    option_id=opt.option_id,
                    ev=ev,
                    best_case=best,
                    worst_case=worst,
                    confidence=confidence,
                )
            )
        return results

    def calculate_expected_value(self, decision: Decision) -> Dict[str, Any]:
        evs = self._calculate_evs(decision.options)
        total_ev = sum(e.ev for e in evs)
        return {
            "decision_id": decision.decision_id,
            "total_expected_value": total_ev,
            "option_evs": [e.to_dict() for e in evs],
            "timestamp": datetime.now().isoformat(),
        }

    def get_decision_rationale(self, decision_id: str) -> Optional[str]:
        return self._rationale_map.get(decision_id)

    def get_decision_history(self) -> List[Decision]:
        return list(self._decisions)

    def get_stats(self) -> Dict[str, Any]:
        if not self._decisions:
            return {"total_decisions": 0, "high_confidence_rate": 0.0}

        high_confidence = sum(
            1 for d in self._decisions if d.confidence == DecisionConfidence.HIGH
        )
        return {
            "total_decisions": len(self._decisions),
            "high_confidence_rate": high_confidence / len(self._decisions),
            "avg_options_per_decision": sum(len(d.options) for d in self._decisions) / len(self._decisions),
        }
