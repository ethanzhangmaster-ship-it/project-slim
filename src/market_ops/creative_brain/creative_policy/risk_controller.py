"""V4.3 Risk Controller — safety constraints for autonomous decisions.

Controls:
  - Consecutive failures per creative/country/trend
  - Budget limits per creative
  - Daily budget cap
  - Trend dead → halt generation
  - Country-level risk tracking

Any decision can be overridden by Risk Controller.
"""

from __future__ import annotations

from typing import Any

from .schemas import DecisionPolicy, PolicyAction, RiskScore, RiskLevel


class RiskController:
    """Risk management layer for autonomous decision policy.

    Tracks failures, enforces limits, and can override policy decisions
    when risk thresholds are exceeded.
    """

    def __init__(self) -> None:
        # Failure tracking: {target_id: consecutive_failures}
        self._creative_failures: dict[str, int] = {}
        self._country_failures: dict[str, int] = {}
        self._trend_failures: dict[str, int] = {}
        # Total tracking
        self._total_failures: int = 0
        self._total_attempts: int = 0
        # Daily budget tracking
        self._daily_spend: float = 0.0
        # Halted targets
        self._halted: set[str] = set()

    def assess_risk(self, creative_id: str, country: str,
                    trend: str, budget: float,
                    policy: DecisionPolicy) -> RiskScore:
        """Assess risk for a single creative.

        Returns RiskScore with level and should_halt flag.
        """
        reasons = []
        level = RiskLevel.SAFE

        creative_fails = self._creative_failures.get(creative_id, 0)
        country_fails = self._country_failures.get(country, 0)
        trend_fails = self._trend_failures.get(trend, 0)

        # Check consecutive failures
        if creative_fails >= policy.max_consecutive_failures:
            level = RiskLevel.CRITICAL
            reasons.append(
                f"Creative {creative_id}: {creative_fails} consecutive failures"
            )
        elif creative_fails >= policy.max_consecutive_failures - 2:
            level = RiskLevel.WARNING
            reasons.append(f"Creative approaching failure limit")

        if country_fails >= policy.max_consecutive_failures:
            level = RiskLevel.CRITICAL
            reasons.append(f"Country {country}: {country_fails} consecutive failures")

        if trend_fails >= policy.max_consecutive_failures:
            level = RiskLevel.CRITICAL
            reasons.append(f"Trend {trend}: {trend_fails} consecutive failures")

        # Budget check
        if budget > policy.max_budget_per_creative:
            level = RiskLevel.WARNING
            reasons.append(f"Budget {budget} exceeds per-creative limit")

        if self._daily_spend + budget > policy.max_daily_budget:
            level = RiskLevel.CRITICAL
            reasons.append(f"Daily budget would be exceeded")

        # Overall failure rate
        if self._total_attempts > 10:
            failure_rate = self._total_failures / self._total_attempts
            if failure_rate > policy.max_failure_rate:
                level = max(level, RiskLevel.WARNING)
                reasons.append(f"Failure rate {failure_rate:.0%} exceeds limit")

        # Halted check
        should_halt = (
            level == RiskLevel.CRITICAL or
            creative_id in self._halted or
            country in self._halted or
            trend in self._halted
        )

        return RiskScore(
            target_id=creative_id,
            target_type="creative",
            level=level,
            consecutive_failures=creative_fails,
            failure_rate=(self._total_failures / max(self._total_attempts, 1)),
            budget_consumed=self._daily_spend,
            budget_limit=policy.max_daily_budget,
            should_halt=should_halt,
            reason="; ".join(reasons) if reasons else "No risk detected",
        )

    def override_decision(self, action: PolicyAction,
                          risk: RiskScore) -> tuple[PolicyAction, bool, str]:
        """Override a policy decision based on risk assessment.

        Returns:
            (final_action, was_overridden, reason)
        """
        if risk.should_halt:
            return PolicyAction.KILL, True, f"Risk override: {risk.reason}"

        if risk.level == RiskLevel.WARNING:
            # Downgrade: GENERATE → RETEST, ADAPT → RETEST
            if action == PolicyAction.GENERATE:
                return PolicyAction.RETEST, True, "Downgraded due to risk warning"
            if action == PolicyAction.ADAPT:
                return PolicyAction.RETEST, True, "Downgraded due to risk warning"

        return action, False, ""

    def record_failure(self, creative_id: str, country: str = "",
                       trend: str = "") -> None:
        """Record a failure for tracking."""
        self._creative_failures[creative_id] = \
            self._creative_failures.get(creative_id, 0) + 1
        if country:
            self._country_failures[country] = \
                self._country_failures.get(country, 0) + 1
        if trend:
            self._trend_failures[trend] = \
                self._trend_failures.get(trend, 0) + 1
        self._total_failures += 1
        self._total_attempts += 1

    def record_success(self, creative_id: str, country: str = "",
                       trend: str = "") -> None:
        """Record a success (resets consecutive failure counter)."""
        self._creative_failures[creative_id] = 0
        if country:
            self._country_failures[country] = 0
        if trend:
            self._trend_failures[trend] = 0
        self._total_attempts += 1

    def record_spend(self, amount: float) -> None:
        """Record daily spend."""
        self._daily_spend += amount

    def halt_target(self, target_id: str) -> None:
        """Halt a specific target (creative/country/trend)."""
        self._halted.add(target_id)

    def unhalt_target(self, target_id: str) -> None:
        """Resume a halted target."""
        self._halted.discard(target_id)

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self._daily_spend = 0.0

    def get_risk_summary(self) -> dict[str, Any]:
        """Get current risk state summary."""
        return {
            "total_failures": self._total_failures,
            "total_attempts": self._total_attempts,
            "failure_rate": round(
                self._total_failures / max(self._total_attempts, 1), 3
            ),
            "daily_spend": round(self._daily_spend, 2),
            "halted_targets": list(self._halted),
            "top_failing_creatives": sorted(
                self._creative_failures.items(), key=lambda x: -x[1]
            )[:5],
            "top_failing_countries": sorted(
                self._country_failures.items(), key=lambda x: -x[1]
            )[:5],
        }