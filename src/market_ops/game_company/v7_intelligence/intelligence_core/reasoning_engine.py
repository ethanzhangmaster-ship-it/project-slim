from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class Observation:
    text: str = ""
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
        }


@dataclass
class Hypothesis:
    text: str = ""
    confidence: float = 0.0
    supporting_evidence: List[str] = field(default_factory=list)
    expected_outcome: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "supporting_evidence": self.supporting_evidence,
            "expected_outcome": self.expected_outcome,
        }


@dataclass
class ReasoningChain:
    observations: List[Observation] = field(default_factory=list)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    expected_results: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observations": [o.to_dict() for o in self.observations],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "decisions": self.decisions,
            "expected_results": self.expected_results,
        }


class ReasoningEngine:
    def __init__(self):
        self._chains: List[ReasoningChain] = []

    def reason(self, data: Dict[str, Any]) -> ReasoningChain:
        observation = self.observe(data)
        hypothesis = self.hypothesize(observation)
        chain = ReasoningChain(
            observations=[observation],
            hypotheses=[hypothesis],
        )
        self._chains.append(chain)
        return chain

    def observe(self, data: Dict[str, Any]) -> Observation:
        return Observation(
            text=str(data.get("text", "")),
            source=data.get("source", "unknown"),
            confidence=data.get("confidence", 0.5),
        )

    def hypothesize(self, observation: Observation) -> Hypothesis:
        return Hypothesis(
            text=f"Based on observation: {observation.text}",
            confidence=observation.confidence * 0.9,
            supporting_evidence=[observation.text],
            expected_outcome="pending evaluation",
        )
