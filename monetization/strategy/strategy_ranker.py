"""
E13.3.2 — Module 4: Strategy Ranker
====================================

Takes the scored candidates for one Opportunity and sorts them best-first,
attaching a 1-based rank. Produces a RankedStrategy (the canonical output of
the Strategy Engine for a single Opportunity) and a `top_n` helper.

No execution. Pure ordering.
"""
from __future__ import annotations

from typing import List, Optional

from monetization.strategy.models import RankedStrategy, ScoredCandidate


def rank_candidates(opportunity, scored: List[ScoredCandidate]) -> RankedStrategy:
    """Sort scored candidates by score descending and assign ranks."""
    ordered = sorted(scored, key=lambda s: s.score, reverse=True)
    for i, s in enumerate(ordered, 1):
        s.rank = i
    top = ordered[0] if ordered else None
    return RankedStrategy(
        opportunity_id=opportunity.id,
        opportunity_type=opportunity.type,
        target_segment=opportunity.segment,
        strategies=ordered,
        top=top,
    )


def top_n(ranked: RankedStrategy, n: int = 3) -> List[dict]:
    """Return the top-N strategies as plain dicts (for the decision interface)."""
    return [s.to_dict() for s in ranked.strategies[:n]]
