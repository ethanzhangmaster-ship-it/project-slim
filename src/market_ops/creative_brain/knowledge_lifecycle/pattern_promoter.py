"""V4.3.5 Pattern Promoter — auto-promote candidate patterns to official.

Criteria:
  - Consecutive winner days >= threshold (e.g., 20)
  - ROAS lift >= threshold (e.g., +35%)
  - Confidence >= threshold (e.g., 0.85)
  - Validation accuracy >= threshold (e.g., 0.6)

No manual intervention needed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import PatternLifecycle, PatternStatus


class PatternPromoter:
    """Auto-promote candidate patterns to active status."""

    def __init__(self,
                 min_winner_days: int = 20,
                 min_roas_lift: float = 0.35,
                 min_confidence: float = 0.85,
                 min_validation_accuracy: float = 0.6) -> None:
        self.min_winner_days = min_winner_days
        self.min_roas_lift = min_roas_lift
        self.min_confidence = min_confidence
        self.min_validation_accuracy = min_validation_accuracy
        self._promotion_history: list[dict[str, Any]] = []

    def evaluate(self, pattern: PatternLifecycle) -> tuple[bool, str]:
        """Evaluate if a pattern should be promoted.

        Returns:
            (should_promote, reason)
        """
        if pattern.status != PatternStatus.CANDIDATE:
            return False, f"Pattern is {pattern.status.value}, not candidate"

        failures = []

        if pattern.consecutive_winner_days < self.min_winner_days:
            failures.append(
                f"winner_days {pattern.consecutive_winner_days} < {self.min_winner_days}"
            )

        if pattern.roas_lift < self.min_roas_lift:
            failures.append(
                f"roas_lift {pattern.roas_lift:.0%} < {self.min_roas_lift:.0%}"
            )

        if pattern.confidence < self.min_confidence:
            failures.append(
                f"confidence {pattern.confidence:.0%} < {self.min_confidence:.0%}"
            )

        if pattern.validation_accuracy < self.min_validation_accuracy:
            failures.append(
                f"validation_accuracy {pattern.validation_accuracy:.0%} < {self.min_validation_accuracy:.0%}"
            )

        if failures:
            return False, "; ".join(failures)

        return True, "All criteria met"

    def promote(self, pattern: PatternLifecycle) -> PatternLifecycle:
        """Promote a pattern to active status.

        Returns the updated pattern.
        """
        should_promote, reason = self.evaluate(pattern)

        if should_promote:
            pattern.status = PatternStatus.PROMOTED
            pattern.promoted_at = datetime.now().isoformat()

        self._promotion_history.append({
            "pattern_id": pattern.pattern_id,
            "name": pattern.name,
            "promoted": should_promote,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

        return pattern

    def evaluate_batch(self, patterns: list[PatternLifecycle]
                       ) -> list[PatternLifecycle]:
        """Evaluate and promote a batch of patterns."""
        results = []
        for p in patterns:
            results.append(self.promote(p))
        return results

    def get_promoted(self, patterns: list[PatternLifecycle]
                     ) -> list[PatternLifecycle]:
        """Get only patterns that were promoted."""
        return [p for p in patterns if p.status == PatternStatus.PROMOTED]

    def get_promotion_history(self) -> list[dict[str, Any]]:
        return list(self._promotion_history)