"""
E13.3.3 — Module 2: Approval Gate  (the most important module)
===============================================================

The single point that decides whether a simulated Decision is allowed to become
a real (mock) config change. The whole system's safety lives here:

    Decision (simulated)
        |
        |  ApprovalGate.decide(...)
        v
    rejected      -> never executed (hard safety: high risk / negative sim / too unsure)
    manual_review -> not executed, waits for a human  (default for first-time strategies)
    approved      -> allowed to execute (mock)

First-version rules (from the PRD):
  * HARD REJECT if any of:
        - risk == "high"                         (retention would be harmed)
        - simulation_positive is False           (revenue would drop)
        - confidence < REJECT_CONFIDENCE         (too unsure to trust)
  * AUTO-APPROVE only if ALL of:
        - confidence > 0.80
        - risk != "high"
        - simulation_positive is True
        - repeat_count > 3                       (proven safe over >=4 runs)
  * otherwise -> manual_review  (positive but unproven, or moderate confidence)

This deliberately errings toward `manual_review` for anything new. A brand-new
strategy from the simulator defaults to human review; only after it has been
approved + executed + observed OK >=3 times does it auto-approve. That is the
exact accumulation principle the user described for E13.4 (collect 1000+
samples before any RL). No autonomy is granted on day one.

The gate keeps an in-memory `history` of (strategy_type, segment) -> success
count so `repeat_count` can be derived automatically for real pipeline runs.
"""
from __future__ import annotations

from typing import Dict, Tuple

from monetization.executor.models import (
    GATE_APPROVED, GATE_MANUAL_REVIEW, GATE_REJECTED,
)

# Thresholds (tunable; documented for the report)
CONF_APPROVE = 0.80         # auto-approve needs confidence strictly above this
CONF_REJECT = 0.40          # below this we do not even trust a manual review
REPEAT_AUTO = 3             # need strictly more than this many prior OK runs


def _seg_key(segment: dict) -> str:
    return "_".join(str(segment.get(k, "")) for k in
                    ("country", "platform", "ad_format", "network")
                    if segment.get(k))


class ApprovalGate:
    """Decides whether a simulated Decision may be executed."""

    def __init__(self):
        # (strategy_type, segment_key) -> number of prior successful executions
        self.history: Dict[Tuple[str, str], int] = {}

    def record_success(self, strategy_type: str, segment: dict) -> None:
        """Call after a successful (executed) run so future repeats auto-approve."""
        key = (strategy_type, _seg_key(segment))
        self.history[key] = self.history.get(key, 0) + 1

    def repeat_count_for(self, strategy_type: str, segment: dict) -> int:
        return self.history.get((strategy_type, _seg_key(segment)), 0)

    def decide(self, *, score: float, risk: str, confidence: float,
               simulation_positive: bool, repeat_count: int,
               strategy_type: str = "", segment: dict = None) -> str:
        """Return one of GATE_APPROVED / GATE_MANUAL_REVIEW / GATE_REJECTED."""
        segment = segment or {}

        # 1) Hard safety rejections
        if risk == "high":
            return GATE_REJECTED
        if not simulation_positive:
            return GATE_REJECTED
        if confidence < CONF_REJECT:
            return GATE_REJECTED

        # 2) Auto-approve only when fully proven
        if (confidence > CONF_APPROVE
                and risk != "high"
                and simulation_positive
                and repeat_count > REPEAT_AUTO):
            return GATE_APPROVED

        # 3) Everything else -> human review (safe default)
        return GATE_MANUAL_REVIEW
