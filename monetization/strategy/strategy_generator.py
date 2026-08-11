"""
E13.3.2 — Module 1+5 glue: Strategy Candidate Generator + Engine
=================================================================

generate_candidates(opportunity)
    Turns an E13.3.1 Opportunity into a list of StrategyCandidates using the
    rule engine (Module 2). This is the "Hypothesis -> Mutation" step.

StrategyEngine
    Orchestrates the full per-opportunity loop (no autonomy, no execution):

        Opportunity
            -> generate_candidates        (rules)
            -> evaluate_candidate         (E13.2.9 simulator + score)
            -> rank_candidates            (Module 4)
            -> decide                     (Module 5: StrategyDecision, simulated)

Module 5 — Decision Interface
    Produces a StrategyDecision (decision_type="monetization_strategy") for the
    top-ranked strategy. Status is ALWAYS 'simulated' here — 'approved' /
    'executed' are reserved for the future E13.3.3 Autonomous Executor.

E12 connection point: `to_e12_mutation(candidate)` projects a candidate's
mutation into the E12 Mutation Operation shape (mutation_type + gene) so the
Executor can consume it without re-design.
"""
from __future__ import annotations

from typing import List, Optional

from monetization.strategy.models import (
    SIMULATED, StrategyCandidate, StrategyDecision, new_id,
)
from monetization.strategy.strategy_evaluator import (
    _baseline_for_opportunity, evaluate_candidate,
)
from monetization.strategy.strategy_ranker import rank_candidates
from monetization.strategy.strategy_rules import (
    EXPECTED_IMPACT, RULE_CONFIDENCE, candidate_specs,
)


def generate_candidates(opportunity) -> List[StrategyCandidate]:
    """Convert one Opportunity into >=1 StrategyCandidate via the rule engine."""
    specs = candidate_specs(opportunity.type)

    # Fallback: unknown opportunity type -> safe no_action candidate.
    if not specs:
        specs = [{
            "strategy_type": "no_action",
            "mutation": {
                "action_type": "", "params": {},
                "description": "No rule mapped to this opportunity type; "
                               "default to monitoring (no_action).",
                "mutation_type": "none", "gene": {},
            },
        }]

    candidates: List[StrategyCandidate] = []
    for spec in specs:
        stype = spec["strategy_type"]
        mut = spec["mutation"]
        candidates.append(StrategyCandidate(
            id=new_id("st"),
            opportunity_id=opportunity.id,
            strategy_type=stype,
            target_segment=dict(opportunity.segment or {}),
            mutation=mut,
            expected_impact=EXPECTED_IMPACT.get(stype, {"intent": "unknown"}),
            confidence=RULE_CONFIDENCE.get(stype, 0.5),
            status="candidate",
        ))
    return candidates


def to_e12_mutation(candidate: StrategyCandidate) -> dict:
    """Project a candidate's mutation into the E12 Mutation Operation shape."""
    mut = candidate.mutation or {}
    return {
        "mutation_type": mut.get("mutation_type", "none"),
        "gene": mut.get("gene", {}),
        "source": "E13.3.2_strategy_engine",
        "strategy_type": candidate.strategy_type,
        "opportunity_id": candidate.opportunity_id,
    }


class StrategyEngine:
    """Lean, rule-based orchestrator. No AI agent, no external calls."""

    def __init__(self, facts: Optional[List] = None):
        self.facts = list(facts or [])

    def set_facts(self, facts) -> None:
        self.facts = list(facts or [])

    def process_opportunity(self, opportunity) -> RankedStrategy:
        candidates = generate_candidates(opportunity)
        scored = []
        for c in candidates:
            baseline = _baseline_for_opportunity(opportunity, self.facts)
            scored.append(evaluate_candidate(c, baseline))
        return rank_candidates(opportunity, scored)

    def process_all(self, opportunities) -> List[RankedStrategy]:
        return [self.process_opportunity(o) for o in opportunities]

    def decide(self, ranked: RankedStrategy) -> Optional[StrategyDecision]:
        """Wrap the top-ranked strategy as a simulated StrategyDecision.

        Status is 'simulated' (we ran the simulator). Never 'executed'.
        """
        if ranked.top is None:
            return None
        top = ranked.top
        cand = top.candidate
        mut = cand.mutation or {}
        strategy_payload = {
            "type": cand.strategy_type,
            "score": round(top.score, 4),
            "mutation": mut,
            "prediction": top.prediction,
            "e12_mutation": to_e12_mutation(cand),
        }
        rationale = (f"Top strategy for {ranked.opportunity_type} on "
                     f"{'_'.join(str(v) for v in ranked.target_segment.values()) or 'global'}: "
                     f"{cand.strategy_type} (score {top.score:.3f}). "
                     f"{mut.get('description', '')}")
        return StrategyDecision(
            decision_type="monetization_strategy",
            opportunity_id=ranked.opportunity_id,
            strategy=strategy_payload,
            status=SIMULATED,
            rationale=rationale,
        )


# Re-export RankedStrategy for callers that build it directly.
from monetization.strategy.models import RankedStrategy  # noqa: E402,F401
