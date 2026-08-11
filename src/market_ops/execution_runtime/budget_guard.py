"""E10.2 Phase 3 — Budget Safety Controller.

Prevents dangerous budget scaling operations before they reach
the platform adapter. Acts as a pre-execution safety gate.

Rules:
  1. MAX_SCALE_RATIO: max percentage increase per SCALE operation
  2. Daily Cap: total daily spend limit per campaign
  3. Minimum budget floor

Usage:
    guard = BudgetGuard(max_scale_ratio=0.30, daily_cap=1000.0)
    result = guard.check(budget_before=100.0, budget_after=500.0)
    if not result.allowed:
        raise BudgetGuardError(result.reason)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BudgetGuardResult:
    """Result of a budget safety check.

    Attributes:
        allowed: Whether the budget change is permitted.
        reason: Human-readable reason if not allowed.
        budget_before: Original budget.
        budget_after: Requested budget.
        capped_budget: Suggested safe budget if rejected.
        max_allowed: The maximum budget that would be allowed.
    """
    allowed: bool = True
    reason: str = ""
    budget_before: float = 0.0
    budget_after: float = 0.0
    capped_budget: float = 0.0
    max_allowed: float = 0.0

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "budget_before": round(self.budget_before, 2),
            "budget_after": round(self.budget_after, 2),
            "capped_budget": round(self.capped_budget, 2),
            "max_allowed": round(self.max_allowed, 2),
        }


class BudgetGuardError(Exception):
    """Raised when a budget change violates safety rules."""

    def __init__(self, result: BudgetGuardResult) -> None:
        super().__init__(result.reason)
        self.result = result


class BudgetGuard:
    """Budget safety controller for campaign mutations.

    Prevents:
      - Excessive scale-up (beyond MAX_SCALE_RATIO)
      - Exceeding daily spend cap
      - Budget below minimum floor

    Args:
        max_scale_ratio: Max increase ratio (e.g., 0.30 = 30%).
        daily_cap: Maximum daily budget per campaign.
        min_budget: Minimum allowed daily budget.
    """

    def __init__(
        self,
        max_scale_ratio: float = 0.30,
        daily_cap: float = 1000.0,
        min_budget: float = 1.0,
    ) -> None:
        self._max_scale_ratio = max_scale_ratio
        self._daily_cap = daily_cap
        self._min_budget = min_budget

    def check(self, budget_before: float, budget_after: float, current_spend: float = 0.0) -> BudgetGuardResult:
        """Check if a budget change is safe.

        Args:
            budget_before: Current daily budget.
            budget_after: Proposed new daily budget.
            current_spend: Current daily spend (for cap check).

        Returns:
            BudgetGuardResult with allowed flag and reason.
        """
        # Rule 1: Minimum budget floor
        if budget_after < self._min_budget:
            return BudgetGuardResult(
                allowed=False,
                reason=f"Budget ${budget_after:.2f} below minimum ${self._min_budget:.2f}",
                budget_before=budget_before,
                budget_after=budget_after,
                capped_budget=self._min_budget,
                max_allowed=self._min_budget,
            )

        # Rule 2: Max scale ratio (only for increases)
        if budget_after > budget_before:
            max_allowed = budget_before * (1.0 + self._max_scale_ratio)
            if budget_after > max_allowed:
                return BudgetGuardResult(
                    allowed=False,
                    reason=(
                        f"Scale too aggressive: ${budget_before:.2f} → ${budget_after:.2f} "
                        f"exceeds {self._max_scale_ratio*100:.0f}% limit "
                        f"(max: ${max_allowed:.2f})"
                    ),
                    budget_before=budget_before,
                    budget_after=budget_after,
                    capped_budget=max_allowed,
                    max_allowed=max_allowed,
                )

        # Rule 3: Daily cap
        projected_spend = current_spend + budget_after
        if projected_spend > self._daily_cap:
            remaining = max(0.0, self._daily_cap - current_spend)
            return BudgetGuardResult(
                allowed=False,
                reason=(
                    f"Daily cap exceeded: current spend ${current_spend:.2f} + "
                    f"budget ${budget_after:.2f} = ${projected_spend:.2f} "
                    f"exceeds ${self._daily_cap:.2f}"
                ),
                budget_before=budget_before,
                budget_after=budget_after,
                capped_budget=remaining,
                max_allowed=remaining,
            )

        return BudgetGuardResult(
            allowed=True,
            budget_before=budget_before,
            budget_after=budget_after,
            max_allowed=budget_after,
        )

    def get_safe_budget(self, budget_before: float, budget_after: float) -> float:
        """Get the safe budget value (capped if needed).

        Args:
            budget_before: Current daily budget.
            budget_after: Proposed new daily budget.

        Returns:
            The safe budget value.
        """
        result = self.check(budget_before, budget_after)
        if result.allowed:
            return budget_after
        return result.capped_budget

    # ── Properties ─────────────────────────────────────────

    @property
    def max_scale_ratio(self) -> float:
        return self._max_scale_ratio

    @property
    def daily_cap(self) -> float:
        return self._daily_cap

    @property
    def min_budget(self) -> float:
        return self._min_budget