"""
E13.4.4 — Module 6: Guardrails
================================

The hard safety layer. Automation's biggest risk is a mistaken action; the
guardrails are the last line of defence and can NEVER be bypassed by the
Policy or Planner.

Enforced limits (per GuardrailConfig):
  * max_bid_change_pct      — a single action may not move a parameter beyond X%
  * max_executions_per_day  — daily execution cap (per game)
  * max_experiments_per_day — daily experiment cap (per game)
  * retention_drop_block_pct— if a strategy would drop D1 retention <= -X%, BLOCK
  * allow_high_risk_execute — high-retention-risk actions are NEVER executed

`enforce()` takes the Policy's *intended* action and returns the *actual*
action the agent is permitted to take, plus the reason if it was downgraded.
This keeps the Policy optimistic and the Guardrails conservative.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from monetization.agent.models import (
    ACTION_BLOCK, ACTION_EXECUTE, ACTION_EXPERIMENT, ACTION_OBSERVE, GuardrailConfig,
)


def bid_change_pct(mutation: Optional[dict]) -> float:
    """Extract the magnitude (in %) a mutation would change a parameter by."""
    m = mutation or {}
    params = m.get("params", {}) or {}
    at = m.get("action_type") or ""
    if at == "review_bidding" and m.get("increase_bid_floor"):
        return float(params.get("bid_floor_pct", 0.0) or 0.0)
    if at in ("change_waterfall", "review_bidding", "adjust_ad_frequency"):
        return float(params.get("magnitude_pct", 0.0) or 0.0)
    return 0.0


class Guardrails:
    """Stateful per-day limit tracker + hard limit enforcer."""

    def __init__(self, config: Optional[GuardrailConfig] = None):
        self.config = config or GuardrailConfig()
        self.executions_today: int = 0
        self.experiments_today: int = 0
        self._day: int = -1
        # audit log of every downgrade the guardrails performed
        self.violations: list = []

    # ------------------------------------------------------------------ #
    def _rollover(self, day: int) -> None:
        if day != self._day:
            self._day = day
            self.executions_today = 0
            self.experiments_today = 0

    # ------------------------------------------------------------------ #
    def check_retention(self, retention_delta_pct: float) -> bool:
        """True if this retention delta would trip the protection block."""
        return retention_delta_pct <= -self.config.retention_drop_block_pct

    def can_execute(self) -> bool:
        return self.executions_today < self.config.max_executions_per_day

    def can_experiment(self) -> bool:
        return self.experiments_today < self.config.max_experiments_per_day

    # ------------------------------------------------------------------ #
    def enforce(self, intended: str, *, risk: str, retention_delta: float,
                bid_change: float, day: int) -> Tuple[str, str]:
        """Return (actual_action, downgrade_reason).

        `intended` is the Policy's preferred move. The guardrails may only
        *restrict* it (execute -> experiment/observe/block), never loosen it.
        """
        self._rollover(day)

        # 1) high retention risk is never executed
        if intended == ACTION_EXECUTE and (
                risk == "high" or (not self.config.allow_high_risk_execute
                                   and risk == "high")):
            self._log(day, "execute", ACTION_BLOCK, "high_risk")
            return ACTION_BLOCK, "high_risk"

        # 2) retention protection block
        if intended in (ACTION_EXECUTE, ACTION_EXPERIMENT) and \
                self.check_retention(retention_delta):
            self._log(day, intended, ACTION_BLOCK, "retention_protection")
            return ACTION_BLOCK, "retention_protection"

        # 3) parameter-change ceiling
        if intended == ACTION_EXECUTE and bid_change > self.config.max_bid_change_pct:
            self._log(day, intended, ACTION_BLOCK, "max_bid_change_exceeded")
            return ACTION_BLOCK, "max_bid_change_exceeded"

        # 4) daily execution cap -> fall back to experiment/observe
        if intended == ACTION_EXECUTE and not self.can_execute():
            fallback = ACTION_EXPERIMENT if self.can_experiment() else ACTION_OBSERVE
            self._log(day, intended, fallback, "daily_exec_cap")
            return fallback, "daily_exec_cap"

        # 5) daily experiment cap -> observe
        if intended == ACTION_EXPERIMENT and not self.can_experiment():
            self._log(day, intended, ACTION_OBSERVE, "daily_exp_cap")
            return ACTION_OBSERVE, "daily_exp_cap"

        return intended, ""

    # ------------------------------------------------------------------ #
    def record_execution(self) -> None:
        self.executions_today += 1

    def record_experiment(self) -> None:
        self.experiments_today += 1

    def _log(self, day, wanted, got, reason) -> None:
        self.violations.append({
            "day": day, "wanted": wanted, "enforced": got, "reason": reason,
        })
