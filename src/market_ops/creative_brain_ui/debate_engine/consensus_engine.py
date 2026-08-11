"""E5.2 Real Debate Engine — Consensus Engine.

Orchestrates multi-round debate and builds final consensus.

Instead of a single vote, this runs:
  Round 1: Each agent presents initial position
  Round 2: Agents respond to each other (counter-arguments)
  Round 3: Rebuttals and refinements
  Final:    Consensus calculation with argument graph traversal
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_brain_ui.debate_engine.agent_base import DebateAgent
from market_ops.creative_brain_ui.debate_engine.argument_graph import (
    Argument, ArgumentGraph, ArgumentRelation, ArgumentState,
)
from market_ops.creative_brain_ui.debate_engine.debate_memory import DebateMemory


class ConsensusEngine:
    """Orchestrates debate rounds to build consensus.

    Multi-round protocol:
      Round 1: Position → initial arguments
      Round 2: Counter → agents respond to each other
      Round 3: Rebuttal → refine positions
      Final:    Vote → weighted consensus by accuracy

    Output: ConsensusResult with vote, strength, dissenting views.
    """

    MAX_ROUNDS = 3

    def __init__(self, memory: DebateMemory | None = None) -> None:
        self._memory = memory or DebateMemory()
        self._graph = ArgumentGraph()

    def run_debate(
        self, agents: list[DebateAgent], evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """Run full debate and produce consensus.

        Args:
            agents: List of debate agents
            evidence: {genes, market_data, trends, competitor_data}

        Returns:
            {final_vote, consensus_strength, dissenting, round_history, argument_count}
        """
        self._graph = ArgumentGraph()

        # Round 1: Initial positions
        round_1_args = self._run_round_1(agents, evidence)

        # Round 2: Counter-arguments
        if round_1_args:
            self._run_round_2(agents, evidence, round_1_args)

        # Round 3: Rebuttals
        self._run_round_3(agents, evidence)

        # Final vote with weighted accuracy
        return self._compute_final_consensus(agents)

    # ── Round Logic ─────────────────────────────────────────

    def _run_round_1(
        self, agents: list[DebateAgent], evidence: dict[str, Any],
    ) -> list[Argument]:
        """Each agent presents initial analysis."""
        all_args = []
        for agent in agents:
            args = agent.analyze(evidence)
            for a in args:
                a.round_number = 1
                self._graph.add_argument(a)
                all_args.append(a)
        return all_args

    def _run_round_2(
        self, agents: list[DebateAgent], evidence: dict[str, Any],
        round_1_args: list[Argument],
    ) -> None:
        """Each agent responds to others' arguments."""
        for agent in agents:
            # Get arguments NOT from this agent
            other_args = [a for a in round_1_args if a.author != agent.name]
            if other_args:
                counter_args = agent.respond_to(other_args, evidence)
                for ca in counter_args:
                    ca.round_number = 2
                    self._graph.add_argument(ca)

                    # Link to original argument
                    for orig in other_args:
                        if orig.dimension == ca.dimension:
                            self._graph.relate(ca.argument_id, orig.argument_id, ArgumentRelation.OPPOSES)

    def _run_round_3(
        self, agents: list[DebateAgent], evidence: dict[str, Any],
    ) -> None:
        """Final rebuttal round."""
        for agent in agents:
            # Get counter-arguments from round 2
            round_2_args = [a for a in self._graph.get_round_arguments(2)
                            if a.author == agent.name and a.state == ArgumentState.ACTIVE]
            if round_2_args:
                rebuttals = agent.respond_to(round_2_args, evidence)
                for rb in rebuttals:
                    rb.round_number = 3
                    self._graph.add_argument(rb)

    # ── Consensus ───────────────────────────────────────────

    def _compute_final_consensus(self, agents: list[DebateAgent]) -> dict[str, Any]:
        """Compute final consensus from all rounds.

        Uses weighted voting where:
          - Historical accuracy of agent → vote weight
          - Confidence calibration → weight multiplier
          - Argument graph support → position strength
        """
        votes: dict[str, float] = {}  # position → accumulated weight
        vote_details: list[dict[str, Any]] = []

        for agent in agents:
            position, confidence, summary = agent.cast_vote()

            # Weight by agent's historical accuracy
            accuracy = self._memory.get_agent_accuracy(agent.name)
            calibration = self._memory.get_agent_calibration(agent.name)
            weight = confidence * accuracy * calibration

            votes[position] = votes.get(position, 0) + weight
            vote_details.append({
                "agent": agent.name,
                "position": position,
                "confidence": round(confidence, 2),
                "weight": round(weight, 3),
                "accuracy": round(accuracy, 2),
                "summary": summary,
            })

        # Determine winner
        if not votes:
            return {"final_vote": "watch", "consensus_strength": 0.0}

        best_position = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        consensus_strength = votes[best_position] / total_weight if total_weight > 0 else 0.0

        # Identify dissenting agents
        dissenting = [d for d in vote_details if d["position"] != best_position]

        # Find strongest argument for winning position
        supporting_args = [a for a in self._graph._nodes.values()
                           if a.position and best_position in a.position]
        strongest = max(supporting_args, key=lambda a: a.confidence).claim if supporting_args else ""

        return {
            "final_vote": best_position,
            "consensus_strength": round(consensus_strength, 2),
            "vote_details": vote_details,
            "dissenting": dissenting,
            "strongest_argument": strongest,
            "total_rounds": self._graph._rounds and max(self._graph._rounds.keys()) or 1,
            "total_arguments": len(self._graph._nodes),
            "most_debated_dimension": self._find_hot_dimension(),
        }

    def _find_hot_dimension(self) -> str:
        """Find the dimension with most arguments (controversial topic)."""
        counts: dict[str, int] = {}
        for a in self._graph._nodes.values():
            counts[a.dimension] = counts.get(a.dimension, 0) + 1
        if not counts:
            return "unknown"
        return max(counts, key=counts.get)
