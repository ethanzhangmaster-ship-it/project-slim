"""V4.3.5 Pattern Retirer — auto-deprecate declining patterns.

Criteria:
  - ROAS dropped below threshold
  - Consecutive decline days >= threshold (e.g., 90)
  - NOT deleted — marked as DEPRECATED, history preserved

Keeps historical knowledge for future reference.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import PatternLifecycle, PatternStatus


class PatternRetirer:
    """Auto-deprecate patterns that have declined.

    Never deletes — only marks as DEPRECATED or RETIRED.
    """

    def __init__(self,
                 roas_decline_threshold: float = 0.5,
                 min_decline_days: int = 90,
                 peak_decline_ratio: float = 0.4) -> None:
        self.roas_decline_threshold = roas_decline_threshold
        self.min_decline_days = min_decline_days
        self.peak_decline_ratio = peak_decline_ratio  # current / peak < this → retire
        self._retirement_history: list[dict[str, Any]] = []

    def evaluate(self, pattern: PatternLifecycle) -> tuple[bool, str]:
        """Evaluate if a pattern should be retired.

        Returns:
            (should_retire, reason)
        """
        if pattern.status in (PatternStatus.DEPRECATED, PatternStatus.RETIRED):
            return False, f"Already {pattern.status.value}"

        reasons = []

        # Check ROAS decline
        if pattern.current_roas < self.roas_decline_threshold:
            reasons.append(
                f"ROAS {pattern.current_roas:.2f} < threshold {self.roas_decline_threshold}"
            )

        # Check peak decline ratio
        if pattern.peak_roas > 0:
            ratio = pattern.current_roas / pattern.peak_roas
            if ratio < self.peak_decline_ratio:
                reasons.append(
                    f"Current/peak ratio {ratio:.0%} < {self.peak_decline_ratio:.0%}"
                )

        # Check consecutive decline days
        if pattern.consecutive_decline_days >= self.min_decline_days:
            reasons.append(
                f"Decline days {pattern.consecutive_decline_days} >= {self.min_decline_days}"
            )

        if reasons:
            return True, "; ".join(reasons)

        return False, "Pattern still healthy"

    def retire(self, pattern: PatternLifecycle) -> PatternLifecycle:
        """Retire a pattern (mark as DEPRECATED).

        Returns the updated pattern.
        """
        should_retire, reason = self.evaluate(pattern)

        if should_retire:
            pattern.status = PatternStatus.DEPRECATED
            pattern.deprecated_at = datetime.now().isoformat()

        self._retirement_history.append({
            "pattern_id": pattern.pattern_id,
            "name": pattern.name,
            "retired": should_retire,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

        return pattern

    def evaluate_batch(self, patterns: list[PatternLifecycle]
                       ) -> list[PatternLifecycle]:
        """Evaluate and retire a batch of patterns."""
        return [self.retire(p) for p in patterns]

    def get_retired(self, patterns: list[PatternLifecycle]
                    ) -> list[PatternLifecycle]:
        """Get only patterns that were retired."""
        return [p for p in patterns if p.status == PatternStatus.DEPRECATED]

    def get_active(self, patterns: list[PatternLifecycle]
                   ) -> list[PatternLifecycle]:
        """Get only active patterns."""
        return [p for p in patterns if p.status == PatternStatus.ACTIVE]

    def get_retirement_history(self) -> list[dict[str, Any]]:
        return list(self._retirement_history)