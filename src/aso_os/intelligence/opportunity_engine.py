"""
E16.6.14 — ASO Intelligence: Opportunity Engine & Priority Engine.

Unified opportunity detection and scoring across all ASO modules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_os.kernel.models import (
    ASOEvent,
    ASOEventType,
    ASOGrowthScore,
)


class OpportunityEngine:
    """Aggregate signals from all ASO modules → unified opportunities."""

    def process_event(self, event: ASOEvent) -> Optional[ASOGrowthScore]:
        """Convert an ASO event into a scored opportunity."""
        et = event.event_type
        game_id = event.game_id
        market = event.market
        payload = event.payload

        if et == ASOEventType.CVR_DROP:
            severity = abs(payload.get("cvr_change", 0))
            return ASOGrowthScore(
                opportunity_id=str(uuid4()),
                revenue_impact=min(1.0, severity * 2),
                confidence=0.8,
                strategic_fit=0.7,
                execution_speed=0.5,
                risk=0.3,
                source=event.source,
                game_id=game_id, market=market,
            )
        elif et == ASOEventType.COMPETITOR_CHANGE:
            return ASOGrowthScore(
                opportunity_id=str(uuid4()),
                revenue_impact=0.6,
                confidence=0.7,
                strategic_fit=0.8,
                execution_speed=0.6,
                risk=0.4,
                source=event.source,
                game_id=game_id, market=market,
            )
        elif et == ASOEventType.KEYWORD_OPPORTUNITY:
            return ASOGrowthScore(
                opportunity_id=str(uuid4()),
                revenue_impact=payload.get("revenue_impact", 0.3),
                confidence=payload.get("confidence", 0.6),
                strategic_fit=0.6,
                execution_speed=0.8,
                risk=0.2,
                source=event.source,
                game_id=game_id, market=market,
            )
        elif et == ASOEventType.SCREENSHOT_WEAK:
            weakness = 1.0 - payload.get("hook_score", 0.5)
            return ASOGrowthScore(
                opportunity_id=str(uuid4()),
                revenue_impact=min(1.0, weakness * 1.5),
                confidence=0.75,
                strategic_fit=0.7,
                execution_speed=0.6,
                risk=0.3,
                source=event.source,
                game_id=game_id, market=market,
            )
        elif et == ASOEventType.LOCALIZATION_OPPORTUNITY:
            return ASOGrowthScore(
                opportunity_id=str(uuid4()),
                revenue_impact=payload.get("revenue_impact", 0.5),
                confidence=0.7,
                strategic_fit=0.8,
                execution_speed=0.4,
                risk=0.4,
                source=event.source,
                game_id=game_id, market=market,
            )
        return None

    def process_events(
        self, events: List[ASOEvent]
    ) -> List[ASOGrowthScore]:
        scores = []
        for event in events:
            score = self.process_event(event)
            if score:
                score.compute()
                scores.append(score)
        return scores


class PriorityEngine:
    """Resolve conflicts, rank by Growth Score, select top opportunities."""

    def rank(self, scores: List[ASOGrowthScore]) -> List[ASOGrowthScore]:
        return sorted(scores, key=lambda s: s.score, reverse=True)

    def top_k(self, scores: List[ASOGrowthScore], k: int = 5) -> List[ASOGrowthScore]:
        return self.rank(scores)[:k]

    def resolve_conflicts(self, scores: List[ASOGrowthScore]) -> List[ASOGrowthScore]:
        """When multiple opportunities target the same game+market, keep the best."""
        seen: Dict[str, ASOGrowthScore] = {}
        for s in self.rank(scores):
            key = f"{s.game_id}:{s.market}"
            if key not in seen:
                seen[key] = s
        return list(seen.values())


__all__ = ["OpportunityEngine", "PriorityEngine"]
