"""E5.2 Real Debate Engine — Debate Memory.

Remembers past debates to improve future decisions:
  - Which arguments were persuasive
  - Which agents were most accurate
  - Calibration of confidence vs actual outcomes
  - Argument effectiveness over time
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DebateOutcome:
    """Recorded outcome of a debate."""
    debate_id: str = ""
    opportunity_name: str = ""
    debate_winner: str = ""   # Which position won
    debate_date: str = field(default_factory=lambda: datetime.now().isoformat())
    actual_outcome: str = ""  # What really happened (ROAS, installs, etc.)
    was_correct: bool = False
    notes: str = ""


@dataclass
class AgentMemory:
    """An agent's evolving memory from past debates."""
    agent_name: str = ""
    total_participation: int = 0
    correct_predictions: int = 0
    accuracy_rate: float = 0.5  # updated over time
    confidence_accuracy: list[tuple[float, bool]] = field(default_factory=list)
    # Track which argument dimensions the agent is best at
    dimension_accuracy: dict[str, float] = field(default_factory=dict)
    # Track which counter-argument types were effective
    effective_counters: list[str] = field(default_factory=list)


class DebateMemory:
    """Collective memory of all debate sessions.

    Learning: updates agent accuracy, calibrates confidence, tracks argument patterns.
    """

    def __init__(self) -> None:
        self._outcomes: list[DebateOutcome] = []
        self._agent_memory: dict[str, AgentMemory] = {}

    # ── Recording ───────────────────────────────────────────

    def record_outcome(
        self,
        debate_id: str,
        opportunity_name: str,
        winning_position: str,
        actual_outcome: str,
        was_correct: bool,
    ) -> None:
        """Record the outcome of a debate."""
        self._outcomes.append(DebateOutcome(
            debate_id=debate_id,
            opportunity_name=opportunity_name,
            debate_winner=winning_position,
            actual_outcome=actual_outcome,
            was_correct=was_correct,
        ))

    def record_agent_prediction(
        self,
        agent_name: str,
        confidence: float,
        was_correct: bool,
        dimensions: list[str] | None = None,
    ) -> None:
        """Record an agent's prediction accuracy."""
        if agent_name not in self._agent_memory:
            self._agent_memory[agent_name] = AgentMemory(agent_name=agent_name)

        mem = self._agent_memory[agent_name]
        mem.total_participation += 1
        if was_correct:
            mem.correct_predictions += 1
        mem.accuracy_rate = mem.correct_predictions / max(1, mem.total_participation)
        mem.confidence_accuracy.append((confidence, was_correct))

    # ── Query ───────────────────────────────────────────────

    def get_agent_accuracy(self, agent_name: str) -> float:
        mem = self._agent_memory.get(agent_name)
        return mem.accuracy_rate if mem else 0.5

    def get_agent_calibration(self, agent_name: str) -> float:
        """How well-calibrated is the agent's confidence? (0=overconfident, 1=perfect)"""
        mem = self._agent_memory.get(agent_name)
        if not mem or not mem.confidence_accuracy:
            return 0.5
        deviations = []
        for confidence, was_correct in mem.confidence_accuracy:
            expected = 1.0 if was_correct else 0.0
            deviations.append(abs(confidence - expected))
        avg_deviation = sum(deviations) / len(deviations)
        return max(0.0, 1.0 - avg_deviation)

    def get_most_accurate_dimension(self, agent_name: str) -> tuple[str, float]:
        mem = self._agent_memory.get(agent_name)
        if not mem or not mem.dimension_accuracy:
            return ("unknown", 0.5)
        best = max(mem.dimension_accuracy, key=mem.dimension_accuracy.get)
        return best, mem.dimension_accuracy[best]

    def get_overall_accuracy(self) -> float:
        """Collective accuracy of all agents."""
        agents = list(self._agent_memory.values())
        if not agents:
            return 0.5
        return sum(a.accuracy_rate for a in agents) / len(agents)

    def get_accuracy_trend(self) -> str:
        """Is the system getting better at predicting?"""
        if len(self._outcomes) < 5:
            return "insufficient_data"
        recent = self._outcomes[-5:]
        older = self._outcomes[:-5] or self._outcomes[:5]
        recent_accuracy = sum(1 for o in recent if o.was_correct) / len(recent)
        older_accuracy = sum(1 for o in older if o.was_correct) / len(older)
        if recent_accuracy > older_accuracy + 0.1:
            return "improving"
        if recent_accuracy < older_accuracy - 0.1:
            return "declining"
        return "stable"

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_debates": len(self._outcomes),
            "overall_accuracy": round(self.get_overall_accuracy(), 2),
            "accuracy_trend": self.get_accuracy_trend(),
            "agents": {
                name: {
                    "accuracy": round(mem.accuracy_rate, 2),
                    "calibration": round(self.get_agent_calibration(name), 2),
                    "participation": mem.total_participation,
                }
                for name, mem in self._agent_memory.items()
            },
        }
