"""E6.2: Decision Memory — Self-Calibrating Agents.

Tracks agent prediction accuracy over time and auto-adjusts weights.
This turns the debate from "one-time vote" into "learning committee".

Key capabilities:
  - Record decision history (idea genome + agent votes + actual outcome)
  - Calibrate agent confidence against reality
  - Auto-adjust agent weight based on prediction accuracy
  - Identify which debate dimensions each agent is best at
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PredictedDecision:
    """A single agent's prediction for an opportunity."""
    agent_name: str
    vote: str               # "build", "prototype", "watch", "skip"
    confidence: float        # 0-1
    reasoning_summary: str
    dimension_accuracies: dict[str, float] = field(default_factory=dict)


@dataclass
class DecisionRecord:
    """Full record of one debate + its real-world outcome."""
    record_id: str = ""
    opportunity_name: str = ""
    genome_signature: dict[str, str] = field(default_factory=dict)  # snapshot of genome genes
    debate_date: str = field(default_factory=lambda: datetime.now().isoformat())
    # Agent predictions
    predictions: list[PredictedDecision] = field(default_factory=list)
    consensus_vote: str = ""
    consensus_strength: float = 0.0
    # Real-world outcome
    was_released: bool = False
    actual_roas: float = 0.0
    actual_ctr: float = 0.0
    actual_installs: int = 0
    actual_outcome: str = ""  # "winner", "failure", "inconclusive"
    outcome_confidence: float = 0.0
    # Learning
    lessons_learned: list[str] = field(default_factory=list)
    was_consensus_correct: bool = False

    def __post_init__(self) -> None:
        if not self.record_id:
            import uuid
            self.record_id = f"dec_{str(uuid.uuid4())[:8]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "opportunity": self.opportunity_name,
            "consensus_vote": self.consensus_vote,
            "actual_outcome": self.actual_outcome,
            "was_correct": self.was_consensus_correct,
            "lessons": self.lessons_learned,
        }


class DecisionHistory:
    """Complete history of all debate decisions and their outcomes.

    Learns: which agents are accurate, when consensus is reliable,
    and which debate patterns precede success.

    Usage:
        history = DecisionHistory()
        history.record_decision(record)
        # After 50+ records:
        calibration = history.calibrate()
        # → agent weights auto-adjusted
    """

    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []
        self._agent_accuracy: dict[str, dict[str, Any]] = {}  # agent → {correct, total, weight}
        self._dimension_accuracy: dict[str, dict[str, dict[str, Any]]] = {}
        self._consensus_accuracy: dict[str, list[bool]] = {"build": [], "prototype": [], "watch": [], "skip": []}

    # ── Recording ───────────────────────────────────────────

    def record_decision(self, record: DecisionRecord) -> None:
        """Record a debate outcome."""
        self._records.append(record)

        # Update agent accuracy
        for pred in record.predictions:
            self._update_agent_accuracy(pred.agent_name, pred.vote, record)

        # Update consensus accuracy
        self._consensus_accuracy.setdefault(record.consensus_vote, []).append(
            record.was_consensus_correct
        )

    def record_batch(self, records: list[DecisionRecord]) -> None:
        for r in records:
            self.record_decision(r)

    # ── Agent Calibration ───────────────────────────────────

    def calibrate(self) -> dict[str, Any]:
        """Run full calibration and return updated weights.

        For each agent:
          1. Calculate overall accuracy (correct / total)
          2. Calculate confidence calibration (how well confidence matches reality)
          3. Calculate dimension-specific accuracy
          4. Compute new weight
        """
        calibration = {}

        for agent_name, acc_info in self._agent_accuracy.items():
            total = acc_info.get("total", 0)
            correct = acc_info.get("correct", 0)
            accuracy = correct / max(1, total)

            # Confidence calibration
            calibration_score = self._calculate_calibration_score(agent_name)

            # New weight: blend accuracy (70%) + calibration (30%)
            new_weight = accuracy * 0.7 + calibration_score * 0.3

            calibration[agent_name] = {
                "total_predictions": total,
                "correct": correct,
                "accuracy": round(accuracy, 3),
                "calibration": round(calibration_score, 3),
                "weight": round(new_weight, 3),
                "weight_change": round(new_weight - acc_info.get("weight", 0.5), 3),
            }

        # Update stored weights
        for agent_name, cal in calibration.items():
            self._agent_accuracy[agent_name]["weight"] = cal["weight"]

        return calibration

    def get_agent_ranking(self) -> list[dict[str, Any]]:
        """Get agents ranked by accuracy."""
        ranking = []
        for name, info in self._agent_accuracy.items():
            total = info.get("total", 0)
            if total >= 3:  # minimum sample
                ranking.append({
                    "agent": name,
                    "accuracy": round(info.get("correct", 0) / total, 2),
                    "samples": total,
                    "weight": info.get("weight", 0.5),
                })
        return sorted(ranking, key=lambda r: r["accuracy"], reverse=True)

    def get_dimension_expertise(self) -> dict[str, dict[str, float]]:
        """Which agent is best at which dimension?"""
        expertise: dict[str, dict[str, float]] = {}
        for dim, agents in self._dimension_accuracy.items():
            expertise[dim] = {}
            for agent_name, stats in agents.items():
                total = stats.get("total", 0)
                if total >= 2:
                    expertise[dim][agent_name] = stats.get("correct", 0) / total
        return expertise

    def should_trust_consensus(self, consensus_vote: str) -> dict[str, Any]:
        """Should we trust the consensus based on historical accuracy?"""
        outcomes = self._consensus_accuracy.get(consensus_vote, [])
        if len(outcomes) < 5:
            return {"trust": "insufficient_data", "accuracy": None, "samples": len(outcomes)}

        accuracy = sum(1 for o in outcomes if o) / len(outcomes)
        trust = "high" if accuracy >= 0.7 else ("medium" if accuracy >= 0.5 else "low")
        return {"trust": trust, "accuracy": round(accuracy, 2), "samples": len(outcomes)}

    def get_learning_summary(self) -> dict[str, Any]:
        """What has the system learned?"""
        winners = [r for r in self._records if r.actual_outcome == "winner"]
        failures = [r for r in self._records if r.actual_outcome == "failure"]

        # Extract common patterns from winners
        winner_genes: dict[str, dict[str, int]] = {}
        for w in winners:
            for key, value in w.genome_signature.items():
                winner_genes.setdefault(key, {}).setdefault(value, 0)
                winner_genes[key][value] += 1

        # Top performing genes
        top_genes = {}
        for key, values in winner_genes.items():
            if values:
                top_genes[key] = max(values, key=values.get)

        return {
            "total_decisions": len(self._records),
            "outcome_breakdown": {
                "winner": len(winners),
                "failure": len(failures),
                "inconclusive": len(self._records) - len(winners) - len(failures),
            },
            "top_winning_genes": top_genes,
            "calibration": self.calibrate(),
        }

    # ── Internal ────────────────────────────────────────────

    def _update_agent_accuracy(self, agent_name: str, vote: str, record: DecisionRecord) -> None:
        """Update agent accuracy based on outcome."""
        if agent_name not in self._agent_accuracy:
            self._agent_accuracy[agent_name] = {"correct": 0, "total": 0, "weight": 0.5}

        info = self._agent_accuracy[agent_name]
        info["total"] += 1

        # Was the prediction correct? (predicted vote matches "build"/"skip" relative to outcome)
        predicted_build = vote in ("build", "prototype")
        was_winner = record.actual_outcome == "winner"

        if (predicted_build and was_winner) or (not predicted_build and not was_winner):
            info["correct"] += 1

    def _calculate_calibration_score(self, agent_name: str) -> float:
        """Calculate how well agent confidence correlates with reality.

        Returns 0-1: 1.0 = perfectly calibrated, 0.0 = overconfident/underconfident.
        """
        relevant_records = [r for r in self._records
                            if any(p.agent_name == agent_name for p in r.predictions)]

        if len(relevant_records) < 3:
            return 0.5  # default calibration

        deviations = []
        for record in relevant_records:
            for pred in record.predictions:
                if pred.agent_name == agent_name:
                    expected = 1.0 if record.was_consensus_correct else 0.0
                    deviations.append(abs(pred.confidence - expected))

        avg_deviation = sum(deviations) / len(deviations)
        return max(0.0, 1.0 - avg_deviation * 2)  # Scale: perfect=1.0, worst=0.0
