"""
E13.3.2 — Module 1: Strategy Models
====================================

Data contracts for the Strategy Engine. This layer sits *between* the
E13.3.1 Reality Engine (Opportunity) and the E13.2.9 Simulator, and is the
"Hypothesis / Mutation" half of the E12 Autonomous Growth Loop:

    Observation  -> (Reality Engine, E13.3.1)
    Hypothesis   -> Opportunity            (E13.3.1 detect)
    Mutation     -> StrategyCandidate      (THIS MODULE)
    Simulation   -> StrategyPrediction     (E13.2.9)
    Decision     -> StrategyDecision       (THIS MODULE, status<=simulated)

Hard constraints (per E13.3.2 scope):
  * No MAX API call. No RemoteConfig write. No execution of any mutation.
  * Every StrategyCandidate / StrategyDecision stays at status
    'candidate' or 'simulated'. 'approved' / 'executed' are reserved for
    the future E13.3.3 Autonomous Executor only.
  * This module is rule-based, NOT an AI agent. No autonomy here.

Connection to E12 (Mutation Operation):
  * Each candidate's `mutation` dict carries a `mutation_type` + `gene`
    so it can later be handed to an E12 Mutation Planner / Genome without
    re-design. See `strategy_rules.py` for the mapping table.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


# Status flow (see PRD): candidate -> simulated -> approved -> executed.
# E13.3.2 only ever emits the first two.
CANDIDATE = "candidate"
SIMULATED = "simulated"
APPROVED = "approved"
EXECUTED = "executed"

# Statuses that are legal to emit from THIS module.
ALLOWED_STRATEGY_STATUS = (CANDIDATE, SIMULATED)


@dataclass
class StrategyCandidate:
    """A concrete, simulatable response to an Opportunity.

    Maps 1:1 to the PRD `StrategyCandidate` contract.
    """
    id: str
    opportunity_id: str
    strategy_type: str
    target_segment: dict
    mutation: dict            # {action_type, params, description, mutation_type, gene}
    expected_impact: dict     # rule-based prior expectation (pre-simulation)
    confidence: float         # rule prior confidence [0,1]
    status: str = CANDIDATE   # always starts 'candidate'

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoredCandidate:
    """A candidate once it has been run through the E13.2.9 Simulator.

    Carries the simulation result + the composite score. The simulator's
    prediction is attached verbatim (status always 'simulated').
    """
    candidate: StrategyCandidate
    prediction: Optional[dict]   # StrategyPrediction.to_dict() or neutral synth
    revenue_component: float
    retention_component: float
    confidence_component: float
    score: float
    rank: Optional[int] = None
    status: str = SIMULATED      # set after simulation; never 'executed'

    def to_dict(self) -> dict:
        return {
            "candidate": self.candidate.to_dict(),
            "prediction": self.prediction,
            "score_breakdown": {
                "revenue_component": round(self.revenue_component, 4),
                "retention_component": round(self.retention_component, 4),
                "confidence_component": round(self.confidence_component, 4),
                "weights": {"revenue": 0.4, "retention": 0.3, "confidence": 0.3},
            },
            "score": round(self.score, 4),
            "rank": self.rank,
            "status": self.status,
        }


@dataclass
class RankedStrategy:
    """All scored candidates for one Opportunity, sorted best-first."""
    opportunity_id: str
    opportunity_type: str
    target_segment: dict
    strategies: List[ScoredCandidate]   # sorted by score desc
    top: Optional[ScoredCandidate] = None

    def to_dict(self) -> dict:
        ranked = [s.to_dict() for s in self.strategies]
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "target_segment": self.target_segment,
            "strategies": ranked,
            "top": self.top.to_dict() if self.top else None,
        }


@dataclass
class StrategyDecision:
    """The recommended strategy for an Opportunity, wrapped as a decision.

    This is the seam that feeds E13.3.3 (Autonomous Executor). It is produced
    in status 'simulated' (we ran the simulator) and is NEVER executed here.

    Mirrors the E12 Decision Layer shape: decision_type + status + payload,
    so the Executor can consume it without re-design.
    """
    decision_type: str                 # constant "monetization_strategy"
    opportunity_id: str
    strategy: dict                     # {type, score, mutation, prediction}
    status: str = SIMULATED           # candidate | simulated (never executed)
    rationale: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def new_id(prefix: str = "st") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
