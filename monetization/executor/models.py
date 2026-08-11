"""
E13.3.3 — Module 1: Executor Models
====================================

Data contracts for the *Controlled Execution Layer*. This is the only component
in the entire E13.3 chain that is allowed to turn a Decision into a concrete
config change — and it is deliberately gated:

    Decision (simulated)
        |
        |  Approval Gate        (reject / manual_review / approved)
        v
    Config Mutator          (generate Change records, no side effects)
        |
        |  Provider apply()     (mock in v1 — NO real MAX / LevelPlay / RC call)
        v
    ExecutionResult         (status: executed | rolled_back | failed | rejected)
        |
        |  Rollback            (on any provider failure)

Hard constraints (per E13.3.3 scope):
  * NO real ad-platform API call. Providers are MOCK and self-certify
    `real_api_called: false`.
  * A Decision is NEVER executed directly from an Opportunity. It must pass the
    Approval Gate first. `Opportunity -> MAX API` is forbidden.
  * Rollback is mandatory: if any provider apply() fails, every already-applied
    change is rolled back before the result is returned.

Status flow (Decision -> Execution):
    candidate -> simulated -> [Approval Gate] -> approved -> executed (mock)
                                          |
                                          +-> manual_review (pending, human)
                                          +-> rejected (never executed)

ExecutionResult.status enum:
    rejected       gate rejected, nothing executed
    pending        awaiting human approval (manual_review)
    approved       gate approved, execution in progress (transient)
    executed       all changes applied (mock) successfully
    failed         a change failed and rollback could NOT complete
    rolled_back    a change failed but all prior changes rolled back OK
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Status vocabulary
# --------------------------------------------------------------------------- #
# Gate verdicts (what the Approval Gate decided)
GATE_REJECTED = "rejected"
GATE_APPROVED = "approved"
GATE_MANUAL_REVIEW = "manual_review"
GATE_VERDICTS = (GATE_APPROVED, GATE_MANUAL_REVIEW, GATE_REJECTED)

# Execution statuses (what the orchestrator produced)
EXEC_REJECTED = "rejected"
EXEC_PENDING = "pending"
EXEC_APPROVED = "approved"
EXEC_EXECUTED = "executed"
EXEC_FAILED = "failed"
EXEC_ROLLED_BACK = "rolled_back"
EXECUTION_STATUSES = (
    EXEC_REJECTED, EXEC_PENDING, EXEC_APPROVED, EXEC_EXECUTED,
    EXEC_FAILED, EXEC_ROLLED_BACK,
)

# Provider labels
PROVIDER_MAX = "MAX"
PROVIDER_LEVELPLAY = "LevelPlay"
PROVIDER_REMOTE_CONFIG = "RemoteConfig"
PROVIDERS = (PROVIDER_MAX, PROVIDER_LEVELPLAY, PROVIDER_REMOTE_CONFIG)


# --------------------------------------------------------------------------- #
# Atomic config change (mirrors E12 Mutation Operation record)
# --------------------------------------------------------------------------- #
@dataclass
class Change:
    """One concrete config mutation, provider-tagged, before/after values.

    This is the unit a provider applies/rolls back. It carries enough context
    to be reversible (old/new) and auditable (target/provider/change_type).
    """
    target: str                 # e.g. "US_android_reward_applovin_floor"
    provider: str               # PROVIDER_MAX / LEVELPLAY / REMOTE_CONFIG
    change_type: str            # bid_floor | waterfall_priority | reward_frequency | backup_network
    old: Any = None
    new: Any = None
    # optional free-form note (e.g. waterfall reorder description)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_yaml_block(self) -> str:
        """Minimal dependency-free YAML rendering for audit logs."""
        def fmt(v) -> str:
            if isinstance(v, (list, dict)):
                return str(v)
            return str(v)
        lines = [
            f"- target: {self.target}",
            f"  provider: {self.provider}",
            f"  change_type: {self.change_type}",
            f"  old: {fmt(self.old)}",
            f"  new: {fmt(self.new)}",
        ]
        if self.note:
            lines.append(f"  note: \"{self.note}\"")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Execution request
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionRequest:
    """The gated, executable form of a StrategyDecision.

    `approved` is set by the Approval Gate before execution. All scoring
    context (score/confidence/risk/simulation_positive) is carried so the gate
    and the report can reason about it without re-deriving from the Decision.
    """
    decision_id: str
    strategy_type: str
    target_segment: dict
    mutation: dict
    simulation_score: float
    # gate inputs (filled by the builder / caller)
    confidence: float = 0.0
    risk: str = "low"                       # low | medium | high
    simulation_positive: bool = True
    repeat_count: int = 0                   # how many times this strategy+segment ran OK before
    approved: bool = False                  # set True only by Approval Gate
    # test-only: force the next provider apply() to fail (drives Case 3 rollback)
    simulate_fail: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Execution result
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionResult:
    """Outcome of executing (or refusing to execute) a Decision."""
    execution_id: str
    status: str                             # EXECUTION_STATUSES
    gate_verdict: str                       # GATE_VERDICTS
    decision_id: str
    strategy_type: str
    changes: List[Change] = field(default_factory=list)
    rollback_available: bool = False
    provider_response: dict = field(default_factory=dict)
    error: Optional[str] = None
    # snapshot of the gate inputs for the report
    score: float = 0.0
    confidence: float = 0.0
    risk: str = "low"
    simulation_positive: bool = True
    repeat_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["changes"] = [c.to_dict() for c in self.changes]
        return d


# --------------------------------------------------------------------------- #
# Rollback record
# --------------------------------------------------------------------------- #
@dataclass
class RollbackOperation:
    """Audit record of a rollback: which changes were reverted and how."""
    execution_id: str
    reverted_changes: List[Change] = field(default_factory=list)
    provider_responses: List[dict] = field(default_factory=list)
    status: str = EXEC_ROLLED_BACK
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reverted_changes"] = [c.to_dict() for c in self.reverted_changes]
        return d


def new_id(prefix: str = "exec") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
