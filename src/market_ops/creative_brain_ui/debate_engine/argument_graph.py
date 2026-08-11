"""E5.2 Real Debate Engine — Argument Graph.

Tracks arguments and their relationships:
  - Supporting arguments (strengthen a position)
  - Counter-arguments (oppose a position)
  - Evidence chains (argument → data → conclusion)
  - Resolution state

Forms a DAG that the ConsensusEngine traverses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ArgumentRelation(Enum):
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    QUALIFIES = "qualifies"  # partially supports with conditions
    UNRELATED = "unrelated"


class ArgumentState(Enum):
    ACTIVE = "active"      # Under debate
    ACCEPTED = "accepted"   # Consensus reached
    REJECTED = "rejected"   # Countered successfully
    WITHDRAWN = "withdrawn"  # Author retracted


@dataclass
class Argument:
    """A single argument in the debate graph."""
    argument_id: str = ""
    author: str = ""           # Agent name
    round_number: int = 0      # Which debate round
    dimension: str = ""        # "market", "gameplay", "ua", "production", "investment"
    position: str = ""         # "for_build", "for_prototype", "against_build", "neutral"
    claim: str = ""            # The actual argument
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5
    references: list[str] = field(default_factory=list)  # IDs of referenced arguments
    state: ArgumentState = ArgumentState.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.argument_id:
            import uuid
            self.argument_id = f"arg_{str(uuid.uuid4())[:8]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "argument_id": self.argument_id,
            "author": self.author,
            "round": self.round_number,
            "dimension": self.dimension,
            "position": self.position,
            "claim": self.claim,
            "evidence_count": len(self.evidence),
            "confidence": round(self.confidence, 2),
            "state": self.state.value,
        }


@dataclass
class Edge:
    """Relationship between two arguments."""
    source_id: str
    target_id: str
    relation: ArgumentRelation = ArgumentRelation.UNRELATED
    weight: float = 1.0  # strength of relation

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relation": self.relation.value,
            "weight": self.weight,
        }


class ArgumentGraph:
    """Directed acyclic graph of debate arguments.

    Nodes: Arguments
    Edges: Support/Oppose/Qualify relationships

    Usage:
        graph = ArgumentGraph()
        graph.add_argument(arg1)
        graph.add_argument(arg2)
        graph.relate(arg1.id, arg2.id, ArgumentRelation.OPPOSES)
        consensus = graph.compute_consensus()
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Argument] = {}
        self._edges: list[Edge] = []
        self._rounds: dict[int, list[str]] = {}  # round → argument_ids

    # ── CRUD ────────────────────────────────────────────────

    def add_argument(self, arg: Argument) -> str:
        self._nodes[arg.argument_id] = arg
        self._rounds.setdefault(arg.round_number, []).append(arg.argument_id)
        return arg.argument_id

    def relate(self, source_id: str, target_id: str, relation: ArgumentRelation = ArgumentRelation.UNRELATED) -> None:
        if source_id in self._nodes and target_id in self._nodes:
            self._edges.append(Edge(source_id, target_id, relation))

    def get_argument(self, arg_id: str) -> Argument | None:
        return self._nodes.get(arg_id)

    def get_round_arguments(self, round_number: int) -> list[Argument]:
        ids = self._rounds.get(round_number, [])
        return [self._nodes[i] for i in ids if i in self._nodes]

    def get_author_arguments(self, author: str) -> list[Argument]:
        return [a for a in self._nodes.values() if a.author == author]

    def get_opposing_to(self, arg_id: str) -> list[Argument]:
        """Find arguments that oppose this one."""
        opp_ids = [e.source_id for e in self._edges
                   if e.target_id == arg_id and e.relation == ArgumentRelation.OPPOSES]
        return [self._nodes[i] for i in opp_ids if i in self._nodes]

    # ── Analysis ────────────────────────────────────────────

    def compute_position_strength(self, position: str) -> float:
        """How strong is a position based on argument graph?

        Considers:
          - Number of supporting arguments
          - Confidence of supporters
          - Strength of counter-arguments
          - Resolution state of each argument
        """
        supporting = [a for a in self._nodes.values()
                      if a.position == position and a.state == ArgumentState.ACTIVE]
        opposing = self._get_opposing_arguments(position)

        support_strength = sum(a.confidence for a in supporting) / max(1, len(supporting))
        opposition_strength = sum(a.confidence for a in opposing) / max(1, len(opposing))

        # Normalize to 0-1
        total = support_strength + opposition_strength
        if total == 0:
            return 0.5
        return support_strength / total

    def _get_opposing_arguments(self, position: str) -> list[Argument]:
        """Get all arguments opposing a position."""
        # Map position to its opposite
        position_pairs = {
            "for_build": "against_build",
            "for_prototype": "against_build",
            "against_build": "for_build",
            "watch": "for_build",
            "skip": "for_build",
        }
        opposing_position = position_pairs.get(position, "against_build")
        return [a for a in self._nodes.values()
                if a.position == opposing_position and a.state == ArgumentState.ACTIVE]

    def get_unresolved_arguments(self) -> list[Argument]:
        """Get arguments still under debate."""
        return [a for a in self._nodes.values() if a.state == ArgumentState.ACTIVE]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_arguments": len(self._nodes),
            "total_edges": len(self._edges),
            "rounds": len(self._rounds),
            "nodes": [a.to_dict() for a in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
        }
