"""
E15.2.5 — Monetization scoring layer.

Splits the single misleading "health 36/100" number into THREE
independent, orthogonal scores so the agent can reason about
*current state* vs *upside* vs *fragility* separately:

    HealthScorer      -> is the account monetizing efficiently RIGHT NOW?
    OpportunityScorer -> how much recoverable value is on the table?
    RiskScorer        -> how fragile is the revenue (single points of failure)?

Rationale (user calibration): a low health score alone is misleading.
An account can score Health 36 / Opportunity 82 — meaning it is *not*
broken, it simply has huge headroom. Health must NOT be dragged down by
"opportunity" signals, and opportunity must NOT be hidden inside health.

All scorers are deterministic (no LLM). Scores are 0-100.
"""
from operation.optimizer.scoring.score_models import ScoreResult, Dimension
from operation.optimizer.scoring.health_score import HealthScorer
from operation.optimizer.scoring.opportunity_score import OpportunityScorer
from operation.optimizer.scoring.risk_score import RiskScorer

__all__ = [
    "ScoreResult", "Dimension",
    "HealthScorer", "OpportunityScorer", "RiskScorer",
]
