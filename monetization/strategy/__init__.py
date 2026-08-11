"""
E13.3.2 — Monetization Strategy Engine (public API)
====================================================

Converts E13.3.1 Reality Engine Opportunities into ranked Strategy Candidates
via the E13.2.9 Simulator. Rule-based, lean, no autonomy, no execution.

    Reality Engine (E13.3.1)
          |  Opportunity
          v
    Strategy Engine (this package)
          |  Candidate Strategies
          v
    E13.2.9 Simulator
          |  Prediction
          v
    Ranked Strategy + simulated StrategyDecision

Usage:
    from monetization.strategy import StrategyEngine
    engine = StrategyEngine(facts)
    ranked = engine.process_all(opportunities)
    decision = engine.decide(ranked[0])   # status == 'simulated'
"""
from monetization.strategy.models import (
    SIMULATED, CANDIDATE, RankedStrategy, ScoredCandidate,
    StrategyCandidate, StrategyDecision, new_id,
)
from monetization.strategy.strategy_rules import (
    EXPECTED_IMPACT, RULES, RULE_CONFIDENCE, candidate_specs, has_rule,
)
from monetization.strategy.strategy_generator import (
    StrategyEngine, generate_candidates, to_e12_mutation,
)
from monetization.strategy.strategy_evaluator import (
    evaluate_candidate, NO_ACTION_CONFIDENCE,
)
from monetization.strategy.strategy_ranker import rank_candidates, top_n

__all__ = [
    "SIMULATED", "CANDIDATE", "RankedStrategy", "ScoredCandidate",
    "StrategyCandidate", "StrategyDecision", "new_id",
    "EXPECTED_IMPACT", "RULES", "RULE_CONFIDENCE", "candidate_specs", "has_rule",
    "StrategyEngine", "generate_candidates", "to_e12_mutation",
    "evaluate_candidate", "NO_ACTION_CONFIDENCE",
    "rank_candidates", "top_n",
]
