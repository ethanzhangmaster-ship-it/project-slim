"""
E16.2 — Economy Memory: the closed-loop "did it work?" store.

Composes the two E16.1 JSONL stores (one-way dependency, shared formats):

* ``JsonlRevenueExperienceStore`` — outcome records with reward/success
  (economy actions serialize via their str-Enum values thanks to the
  E16.1 tolerance layer)
* ``JsonlPatternMemory``          — reusable patterns for future decisions

``record_outcome`` double-writes: the raw experience AND a distilled
pattern, so the next Economy Intelligence run can both calibrate its
simulator confidence (experience stats) and surface historical precedent
(pattern search).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from src.revenue_intelligence.experience import (
    JsonlRevenueExperienceStore,
    RevenueExperience,
    RevenuePoint,
)
from src.revenue_intelligence.models import PatternMatch
from src.revenue_intelligence.pattern_memory import JsonlPatternMemory

from .models import EconomyAction


class EconomyMemory:
    """Double-write outcome memory for economy decisions."""

    def __init__(self, experience_path: str, pattern_path: str):
        self.experience_store = JsonlRevenueExperienceStore(experience_path)
        self.pattern_memory = JsonlPatternMemory(pattern_path)

    # ------------------------------------------------------------------ #
    def record_outcome(
        self,
        game_id: str,
        action: EconomyAction,
        reason: str,
        before_revenue: float,
        after_revenue: float,
    ) -> RevenueExperience:
        """Record one decision outcome; returns the scored experience."""
        exp = RevenueExperience(
            game_id=game_id,
            action=action,
            reason=reason,
            before=RevenuePoint(revenue_total=before_revenue),
            after=RevenuePoint(revenue_total=after_revenue),
        )
        # store computes reward & success (revenue-lift fallback path)
        self.experience_store.add(exp)

        outcome = "worked" if exp.success else "failed"
        pattern = PatternMatch(
            pattern_id=f"eco_{uuid.uuid4().hex[:10]}",
            description=(
                f"{action.value} {outcome} for {game_id}: {reason} "
                f"(reward {exp.reward:+.2%})"
            ),
            confidence=min(0.9, 0.5 + abs(exp.reward)),
            similar_case=f"{game_id}:{action.value}",
            recommended_action=action if exp.success else None,
            recommended_strategy=reason if exp.success else f"avoid: {reason}",
            source="economy_intelligence",
        )
        self.pattern_memory.add(pattern, game_id=game_id)
        return exp

    # ------------------------------------------------------------------ #
    def stats(self, game_id: str, action: EconomyAction) -> Dict[str, Any]:
        return self.experience_store.stats(game_id, action)

    def search_similar(
        self, game_id: str, signal: Dict[str, Any], limit: int = 3
    ) -> List[PatternMatch]:
        return self.pattern_memory.search_similar(game_id, signal, limit)


__all__ = ["EconomyMemory"]
