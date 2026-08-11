"""
E15.2.6 §4 — Opportunity Ranking.

Returns opportunities sorted by score (best first), optionally capped at top_n.
Ties break by confidence then by absolute lift so the output is deterministic.
"""
from __future__ import annotations

from typing import List, Tuple

from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.opportunity.scorer import OpportunityScorer


class OpportunityRanker:
    def __init__(self) -> None:
        self._scorer = OpportunityScorer()

    def rank(self, opps: List[RevenueOpportunity],
             top_n: int = None) -> List[Tuple[RevenueOpportunity, float]]:
        scored = [(o, self._scorer.score(o)) for o in opps]
        scored.sort(key=lambda t: (t[1], t[0].confidence, t[0].expected_lift),
                    reverse=True)
        if top_n is not None:
            scored = scored[:top_n]
        return scored
