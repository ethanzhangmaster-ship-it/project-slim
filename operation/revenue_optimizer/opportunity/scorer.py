"""
E15.2.6 §4 — Opportunity Scoring.

Score = expected_lift * confidence * (1 - risk).

Higher score = bigger, more certain, safer upside. This is the single number
the autopilot uses to decide what to work on first.
"""
from __future__ import annotations

from typing import List, Tuple

from operation.revenue_optimizer.models import RevenueOpportunity


class OpportunityScorer:
    def score(self, opp: RevenueOpportunity) -> float:
        lift = max(opp.expected_lift, 0.0)
        conf = min(max(opp.confidence, 0.0), 1.0)
        risk = min(max(opp.risk, 0.0), 1.0)
        return round(lift * conf * (1.0 - risk), 6)

    def score_all(self, opps: List[RevenueOpportunity]) -> List[float]:
        return [self.score(o) for o in opps]
