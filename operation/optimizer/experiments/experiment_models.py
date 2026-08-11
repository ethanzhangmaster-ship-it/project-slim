"""
E15.2.5+ — Monetization Experiment & Verification Layer models.

An *experiment* is a formally-tracked, manually-applied monetization change
(e.g. raise a hidden-winner network's bid opportunity, or lift a bid
constraint on a backfill network). The operator applies it in the MAX
dashboard; this layer only *verifies* whether the predicted outcome
happened — and whether it hurt users (ARPDAU guardrail).

Phase 1 contract holds: this layer NEVER writes to MAX. It proposes and
verifies; the operator executes in the dashboard.

Deterministic — no LLM.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, Dict, Optional

# statuses an experiment moves through
# Full lifecycle: PROPOSED → APPLIED → (OBSERVING) → WINNER | ROLLBACK
#                 → MEMORIZED (OptimizationMemory row written)
PROPOSED = "PROPOSED"        # recommended, not yet watched long enough
ACTIVE = "ACTIVE"            # watching; within min horizon
SUCCESS = "SUCCESS"          # predicted signal resolved + guardrail ok/pending
FAIL = "FAIL"                # signal persisted past horizon, or guardrail regressed
INCONCLUSIVE = "INCONCLUSIVE"
ARCHIVED = "ARCHIVED"
APPLIED = "APPLIED"          # operator confirmed the change is live in MAX
WINNER = "WINNER"            # measured net revenue impact positive, guardrail held
ROLLBACK = "ROLLBACK"        # measured impact negative or guardrail regressed
MEMORIZED = "MEMORIZED"      # outcome persisted to OptimizationMemory

# actions that are Experiment-layer (real revenue/fill impact, A/B first)
EXPERIMENT_ACTIONS = {
    "increase_bid_opportunity",
    "adjust_bid_constraint",
}

# E15.2.6.1 — A/B-eligible actions: every monetization lever that can be
# expressed as a formal A/B variable experiment (A=current / B=variant)
# with Revenue/DAU as the single expected metric. Superset of
# EXPERIMENT_ACTIONS (adds the approval-tier revenue levers so the 6 intel
# rules all surface as A/B opportunities, not just the 2 core ones).
AB_ELIGIBLE_ACTIONS = {
    "increase_bid_opportunity",   # hidden_winner  -> AUTO / experiment
    "adjust_bid_constraint",      # bid_floor      -> AUTO / experiment
    "disable_network",            # zombie         -> AUTO (safe, trackable)
    "quarantine_network",         # zombie(protected) -> APPROVAL
    "diversify",                  # concentration  -> APPROVAL (risk hedge)
}

# which IntelSignal.rule each A/B action expects to clear (for verify signal)
_EXPECTED_SIGNAL_RULE = {
    "increase_bid_opportunity": "hidden_winner",
    "adjust_bid_constraint": "bid_floor",
    "disable_network": "zombie_network",
    "quarantine_network": "zombie_network",
    "diversify": "",             # no revenue signal to clear (guardrail-only)
}

_HYPOTHESIS = {
    "increase_bid_opportunity":
        "Raising auction exposure captures the network's eCPM-implied "
        "potential; the hidden_winner signal should clear without ARPDAU "
        "regression.",
    "adjust_bid_constraint":
        "Lifting the bid constraint cuts lowest-value backfill; the "
        "bid_floor signal should clear with fill-rate guarded.",
    "disable_network":
        "Removing the zombie frees waterfall slots for higher-eCPM networks; "
        "the zombie_network signal clears (network exits the report).",
    "quarantine_network":
        "If the protected network is truly zombie, 7d isolation confirms it; "
        "the zombie_network signal clears on disable.",
    "diversify":
        "Introducing a candidate network reduces single-point revenue risk; "
        "this is a guardrail hedge, not a direct Revenue/DAU lift.",
}


# MAX report network naming drifts between pulls/accounts (e.g. "CHARTBOOST"
# vs "CHARTBOOST_NETWORK" vs "CHARTBOOST_BIDDING" are the same network). The
# experiment identity (exp_id) must be stable across that drift so the store
# de-duplicates and outcome-learning tracks one experiment per network — not a
# new one every time the suffix changes. The *display/target* field stays the
# real name (ImpactMeasurer matches raw rows), only the id is canonicalized.
_SUFFIXES = ("_BIDDING_NETWORK", "_NETWORK", "_BIDDING")


def canon_target(net: str) -> str:
    """Canonical network key: upper-cased, redundant suffix stripped."""
    s = (net or "").upper().strip()
    for suf in _SUFFIXES:
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def exp_id(account: str, action_type: str, target: str, tag: str = "") -> str:
    """Stable id shared across store / ledger / card.

    The target is canonicalized (suffix-stripped) so the same network keeps
    the same id even when MAX renames it across pulls.
    """
    return hashlib.sha1(
        f"{account}|{action_type}|{canon_target(target)}|{tag}".encode()
    ).hexdigest()[:12]


@dataclass
class ExperimentDefinition:
    exp_id: str
    account: str
    title: str
    hypothesis: str
    action_type: str              # increase_bid_opportunity | adjust_bid_constraint
    target: str                   # network / app / segment key
    source_rule: str              # IntelSignal rule that spawned it
    params: Dict[str, Any] = field(default_factory=dict)
    expected_signal: Dict[str, str] = field(default_factory=dict)  # {rule,target}
    guardrail: str = "arpdau"     # user-impact guardrail kind
    min_days: int = 3             # min days before a verdict is allowed
    max_days: int = 14            # give up / mark FAIL after this if signal persists
    status: str = PROPOSED
    created_at: str = ""
    launched_at: Optional[str] = None   # when first observed as actionable
    resolved_at: Optional[str] = None   # when verdict reached
    result_note: str = ""
    # latest verification snapshot (for rendering)
    last_arpdau_guardrail: str = ""     # pass | regression | pending | n/a
    last_arpdau_delta_pct: Optional[float] = None
    # snapshot of user metrics at creation (may be PENDING) for guardrail compare
    baseline_user_metrics: Dict[str, Any] = field(default_factory=dict)
    # ---- outcome learning (E15.2.5 increment 4) ----------------------- #
    applied_at: Optional[str] = None    # operator marked change live in MAX
    impact: Dict[str, Any] = field(default_factory=dict)   # ImpactMeasurement
    decision: str = ""                  # KEEP | ROLLBACK | "" (undecided)
    memorized_at: Optional[str] = None  # OptimizationMemory row written
    # ---- A/B variable experiment (E15.2.6.1 increment) ---------------- #
    # Every monetization opportunity is expressed as a formal A/B test:
    #   A (control)  = current state, measured today
    #   B (variant)  = the proposed change, measured after human apply
    # The single expected metric is Revenue/DAU (the operator's North Star);
    # expected_lift_pct is the *hypothesized* lift, confirmed by post-apply
    # diff-in-diff impact measurement (WinnerSelector).
    variant_a: str = ""            # control description (current state)
    variant_b: str = ""            # treatment description (proposed change)
    expected_metric: str = "revenue_per_dau"   # single North Star KPI
    expected_lift_pct: Optional[float] = None   # hypothesized lift on metric
    metric_baseline: Optional[float] = None     # current metric value (proxy)
    ab_design: str = ""            # assignment / measurement plan
    ab_kind: str = "revenue"       # revenue | risk_hedge
    verify_mode: str = "signal"    # signal | guardrail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exp_id": self.exp_id, "account": self.account, "title": self.title,
            "hypothesis": self.hypothesis, "action_type": self.action_type,
            "target": self.target, "source_rule": self.source_rule,
            "params": self.params, "expected_signal": self.expected_signal,
            "guardrail": self.guardrail, "min_days": self.min_days,
            "max_days": self.max_days, "status": self.status,
            "created_at": self.created_at, "launched_at": self.launched_at,
            "resolved_at": self.resolved_at, "result_note": self.result_note,
            "last_arpdau_guardrail": self.last_arpdau_guardrail,
            "last_arpdau_delta_pct": self.last_arpdau_delta_pct,
            "baseline_user_metrics": self.baseline_user_metrics,
            "applied_at": self.applied_at, "impact": self.impact,
            "decision": self.decision, "memorized_at": self.memorized_at,
            "variant_a": self.variant_a, "variant_b": self.variant_b,
            "expected_metric": self.expected_metric,
            "expected_lift_pct": self.expected_lift_pct,
            "metric_baseline": self.metric_baseline,
            "ab_design": self.ab_design, "ab_kind": self.ab_kind,
            "verify_mode": self.verify_mode,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExperimentDefinition":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class ExperimentVerification:
    exp_id: str
    account: str
    status: str                   # resulting status after this check
    checked_at: str
    signal_still_firing: bool
    signal_resolved: Optional[bool]   # None while inside min horizon
    arpdau_guardrail: str         # pass | regression | pending | n/a
    arpdau_delta_pct: Optional[float]
    days_watched: int
    verdict_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exp_id": self.exp_id, "account": self.account, "status": self.status,
            "checked_at": self.checked_at, "signal_still_firing": self.signal_still_firing,
            "signal_resolved": self.signal_resolved,
            "arpdau_guardrail": self.arpdau_guardrail,
            "arpdau_delta_pct": self.arpdau_delta_pct,
            "days_watched": self.days_watched, "verdict_note": self.verdict_note,
        }
