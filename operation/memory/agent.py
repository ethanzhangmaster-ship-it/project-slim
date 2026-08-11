"""
E15.2.1 — Operation Memory Agent

Wraps monetization operation providers to record every operation:
- Snapshots before/after state
- Records context and results
- Enables query for similar past operations (learning)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import OperationRecord, record_factory
from .store import OperationMemoryStore


class MemoryAgent:
    """Records every monetization operation into the memory store."""

    def __init__(self, store: Optional[OperationMemoryStore] = None):
        self.store = store or OperationMemoryStore()

    def record(
        self,
        game_id: str,
        operation: str,
        provider: str,
        sandbox: str = "SIMULATION",
        context: Optional[Dict[str, Any]] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        result_success: bool = True,
        result_metrics: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        confidence: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> OperationRecord:
        """Record an operation and persist it."""
        rec = record_factory(
            game_id=game_id,
            operation=operation,
            provider=provider,
            sandbox=sandbox,
            context=context,
            before_state=before_state,
            after_state=after_state,
            result_success=result_success,
            result_metrics=result_metrics,
            error=error,
            confidence=confidence,
            tags=tags,
        )
        self.store.append(rec)
        return rec

    def recall_similar(
        self, game_id: str, operation: str, context: Dict[str, Any], limit: int = 10
    ) -> List[OperationRecord]:
        """Find past operations with similar context for learning."""
        return self.store.find_similar(game_id, operation, context, limit=limit)

    def recall_by_game(self, game_id: str) -> List[OperationRecord]:
        """Load all operation history for a game."""
        return self.store.load(game_id)

    def summary(self, game_id: str) -> Dict[str, Any]:
        """Get aggregated operation memory summary."""
        return self.store.summary(game_id)

    def get_operation_effectiveness(
        self, game_id: str, operation: str
    ) -> Dict[str, Any]:
        """Calculate how effective a particular operation type has been."""
        records = self.store.query(game_id=game_id, operation=operation)
        if not records:
            return {"operation": operation, "times_used": 0, "effectiveness": "unknown"}

        successes = [r for r in records if r.result_success]
        revenue_impacts = [r.revenue_impact for r in records if r.revenue_impact is not None]
        avg_confidence = sum(r.confidence for r in records) / len(records)

        return {
            "operation": operation,
            "times_used": len(records),
            "success_rate": round(len(successes) / len(records), 3),
            "avg_revenue_impact_pct": round(sum(revenue_impacts) / len(revenue_impacts), 2) if revenue_impacts else None,
            "avg_confidence": round(avg_confidence, 3),
            "recommendation": _recommendation(records),
        }


def _recommendation(records: List[OperationRecord]) -> str:
    """Heuristic recommendation based on past results."""
    successes = sum(1 for r in records if r.result_success)
    rate = successes / len(records) if records else 0
    impacts = [r.revenue_impact for r in records if r.revenue_impact is not None and r.revenue_impact > 0]

    if rate >= 0.8 and impacts:
        return "highly_effective"
    elif rate >= 0.6:
        return "generally_effective"
    elif rate >= 0.4:
        return "mixed_results"
    else:
        return "mostly_ineffective"
