"""
E15.2.2 — Action Safety Agent

Gate that all monetization operations must pass through before execution.
Integrates with memory layer for past-evidence checks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import SafetyCheck, SafetyResult
from .rules import SafetyRuleEngine


class SafetyAgent:
    """Pre-execution safety gate for monetization operations."""

    def __init__(
        self,
        engine: Optional[SafetyRuleEngine] = None,
        memory_agent=None,  # Optional MemoryAgent for past-evidence lookups
    ):
        self._engine = engine or SafetyRuleEngine()
        self._memory = memory_agent

    def check(
        self,
        game_id: str,
        operation: str,
        provider: str,
        changes: Optional[Dict[str, Any]] = None,
        current_metrics: Optional[Dict[str, Any]] = None,
        expected_impact: Optional[Dict[str, Any]] = None,
        has_rollback: bool = False,
        rollback_snapshot_id: Optional[str] = None,
    ) -> SafetyResult:
        """Run safety checks on a proposed operation."""

        # Auto-enrich with past evidence from memory
        past_evidence: List[Dict[str, Any]] = []
        if self._memory:
            context = changes or {}
            similar = self._memory.recall_similar(game_id, operation, context, limit=5)
            past_evidence = [
                {
                    "success": r.result_success,
                    "revenue_impact": r.revenue_impact,
                    "confidence": r.confidence,
                    "timestamp": r.timestamp,
                }
                for r in similar
            ]

        sc = SafetyCheck(
            game_id=game_id,
            operation=operation,
            provider=provider,
            changes=changes or {},
            current_metrics=current_metrics or {},
            expected_impact=expected_impact or {},
            past_evidence=past_evidence,
            has_rollback=has_rollback,
            rollback_snapshot_id=rollback_snapshot_id,
        )

        return self._engine.evaluate(sc)

    def is_safe(self, result: SafetyResult) -> bool:
        """Convenience: is the operation safe to proceed?"""
        return result.status == "allowed"

    def should_warn(self, result: SafetyResult) -> bool:
        """Convenience: does the operation need confirmation?"""
        return result.status in ("require_confirmation", "blocked")
