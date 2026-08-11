"""E5.2 Real Debate Engine — Base Agent with personality, memory, and reasoning.

Each agent has:
  - Personality: values, risk tolerance, expertise weights
  - Memory: past arguments, counter-arguments, confidence calibration
  - Decision function: analyze evidence → produce position → respond to counter
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from market_ops.creative_brain_ui.debate_engine.argument_graph import Argument, ArgumentGraph
from market_ops.creative_brain_ui.debate_engine.debate_memory import DebateMemory, AgentMemory


class RiskTolerance(Enum):
    CONSERVATIVE = "conservative"   # Prefers proven patterns
    MODERATE = "moderate"          # Balances risk/reward
    AGGRESSIVE = "aggressive"      # Favors innovation over safety


@dataclass
class AgentPersonality:
    """Defines an agent's decision-making character."""
    role: str = ""
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    expertise_weights: dict[str, float] = field(default_factory=dict)
    # Core beliefs that influence decisions
    beliefs: list[str] = field(default_factory=list)
    # What this agent values most
    priority_factors: list[str] = field(default_factory=list)


class DebateAgent:
    """A reasoning agent in the debate.

    Each agent:
      1. Receives the idea/opportunity
      2. Analyzes with its domain expertise
      3. Produces an initial position with supporting arguments
      4. Listens to other agents' arguments
      5. Produces counter-arguments
      6. Updates position if persuaded
      7. Casts final vote with confidence
    """

    def __init__(
        self,
        name: str,
        persona: AgentPersonality,
        memory: DebateMemory | None = None,
    ) -> None:
        self.name = name
        self.persona = persona
        self._memory = memory or DebateMemory()
        self._round_arguments: list[Argument] = []
        self._position_strength: float = 0.5  # 0-1, how convinced of own position

    # ── Lifecycle ───────────────────────────────────────────

    def analyze(self, evidence: dict[str, Any]) -> list[Argument]:
        """Analyze evidence and produce initial arguments.

        Args:
            evidence: {genes, market_data, competitor_data, performance_history}
        """
        # Reset for new debate
        self._round_arguments = []

        arguments = self._produce_arguments(evidence)
        self._round_arguments = arguments
        self._position_strength = self._calculate_initial_confidence(arguments, evidence)
        return arguments

    def respond_to(self, opponent_arguments: list[Argument], evidence: dict[str, Any]) -> list[Argument]:
        """Generate counter-arguments responding to other agents.

        Returns: counter-arguments targeting opponent claims.
        """
        counter_args = []
        for opp_arg in opponent_arguments:
            counter = self._generate_counter(opp_arg, evidence)
            if counter:
                counter_args.append(counter)
                self._round_arguments.append(counter)

        # Re-evaluate position
        self._position_strength = self._update_confidence(counter_args)
        return counter_args

    def cast_vote(self) -> tuple[str, float, str]:
        """Cast final vote: (position, confidence, reasoning summary).

        Returns:
            vote: "build", "prototype", "watch", "skip"
            confidence: 0-1
            summary: one-line reasoning
        """
        vote, confidence = self._decide_vote()
        summary = self._summarize_position()
        return vote, confidence, summary

    # ── Override points for specific agents ─────────────────

    def _produce_arguments(self, evidence: dict[str, Any]) -> list[Argument]:
        """Override: produce domain-specific arguments."""
        raise NotImplementedError("Subclasses must implement _produce_arguments")

    def _generate_counter(self, opponent_arg: Argument, evidence: dict[str, Any]) -> Argument | None:
        """Override: generate counter-argument to opponent's claim."""
        # Default: check if disagreement, then counter
        if opponent_arg.position in self._disagree_positions(evidence):
            return Argument(
                author=self.name,
                dimension=opponent_arg.dimension,
                position="counter",
                claim=f"Counter to [{opponent_arg.author}]: {opponent_arg.claim}",
                evidence=["Disagree based on domain expertise"],
                confidence=max(0.3, self._position_strength - 0.2),
            )
        return None

    def _disagree_positions(self, evidence: dict[str, Any]) -> list[str]:
        """Override: positions this agent disagrees with."""
        return []

    def _decide_vote(self) -> tuple[str, float]:
        """Override: decide final vote based on position strength."""
        if self._position_strength >= 0.7:
            return "build", self._position_strength
        if self._position_strength >= 0.5:
            return "prototype", self._position_strength
        if self._position_strength >= 0.3:
            return "watch", self._position_strength
        return "skip", self._position_strength

    def _summarize_position(self) -> str:
        args = self._round_arguments[-3:] if self._round_arguments else []
        claims = "; ".join(a.claim[:60] for a in args)
        return f"[{self.name}] {claims}" if claims else f"[{self.name}] No strong position"

    # ── Confidence tracking ─────────────────────────────────

    def _calculate_initial_confidence(
        self, arguments: list[Argument], evidence: dict[str, Any]
    ) -> float:
        if not arguments:
            return 0.3
        avg_confidence = sum(a.confidence for a in arguments) / len(arguments)
        return min(0.9, avg_confidence * 0.8 + evidence.get("base_confidence", 0.3) * 0.2)

    def _update_confidence(self, counter_args: list[Argument]) -> float:
        """Update confidence after hearing counter-arguments."""
        effective_counters = [c for c in counter_args if c.confidence > self._position_strength]
        if effective_counters:
            # Being countered by strong arguments reduces confidence
            penalty = len(effective_counters) * 0.05
            self._position_strength = max(0.1, self._position_strength - penalty)
        return self._position_strength
