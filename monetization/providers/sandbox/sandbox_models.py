"""
E14.3.4 — Provider Sandbox Models
==================================

Data contracts for upgrading the three sandbox modes from "the enum exists"
into a complete OPERATING POLICY:

    * ShadowRecord   — one shadow proposal: prediction now, reality later
    * CanaryStage /
      CanaryRun      — staged production rollout (10% -> 50% -> 100%)
    * GateDecision   — verdict of the auto-rollback gate after execution
    * SandboxPolicy  — per (game_id, provider kind) mode + promotion state

Everything here is pure stdlib + E14.3.1 frozen contract types. Nothing in
this module talks to a provider directly — that is the SandboxManager's job.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from monetization.providers.models import Change, SandboxMode


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Shadow: prediction vs reality
# --------------------------------------------------------------------------- #
SHADOW_OPEN = "open"          # proposal recorded, reality not yet observed
SHADOW_CLOSED = "closed"      # reality ingested, error computed


@dataclass
class ShadowRecord:
    """One shadow-mode proposal.

    In SHADOW mode the provider READS the current value but never writes.
    We store what the agent WOULD have done (`proposed`) plus its predicted
    metric impact. Later, when reality arrives (from the Reality Engine /
    revenue read), we close the record and compute the prediction error.
    """
    game_id: str
    provider: str                     # provider kind (max / remote_config / ...)
    change_id: str
    change_type: str
    target: str
    current: Any = None               # real value read in shadow mode
    proposed: Any = None              # value the agent wanted to write
    predicted_metric: float = 0.0     # e.g. predicted eCPM / revenue delta %
    actual_metric: Optional[float] = None
    error_pct: Optional[float] = None # |predicted - actual| / max(|actual|, eps)
    status: str = SHADOW_OPEN
    created_at: str = field(default_factory=_now)
    closed_at: str = ""
    record_id: str = field(default_factory=lambda: f"sh_{uuid.uuid4().hex[:8]}")

    def close(self, actual_metric: float) -> None:
        self.actual_metric = actual_metric
        denom = max(abs(actual_metric), 1e-9)
        self.error_pct = abs(self.predicted_metric - actual_metric) / denom * 100.0
        self.status = SHADOW_CLOSED
        self.closed_at = _now()

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Canary: staged production rollout
# --------------------------------------------------------------------------- #
CANARY_PENDING = "pending"
CANARY_RUNNING = "running"
CANARY_PASSED = "passed"
CANARY_FAILED = "failed"
CANARY_ROLLED_BACK = "rolled_back"

DEFAULT_CANARY_STAGES = (10, 50, 100)   # percent of traffic / scope per stage


@dataclass
class CanaryStage:
    """One rollout stage. `percent` is the scope of the change (the adapter
    decides how percent maps onto the platform: geo subset, ad-unit subset,
    RC conditional audience, ...)."""
    percent: int
    status: str = CANARY_PENDING
    result_success: Optional[bool] = None
    observed_metric: Optional[float] = None   # metric measured at this stage
    gate_passed: Optional[bool] = None
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanaryRun:
    """A staged production rollout of ONE Change."""
    game_id: str
    provider: str
    change_id: str
    stages: List[CanaryStage] = field(default_factory=lambda: [
        CanaryStage(p) for p in DEFAULT_CANARY_STAGES])
    status: str = CANARY_PENDING
    rolled_back: bool = False
    created_at: str = field(default_factory=_now)
    run_id: str = field(default_factory=lambda: f"cn_{uuid.uuid4().hex[:8]}")

    def current_stage(self) -> Optional[CanaryStage]:
        for s in self.stages:
            if s.status in (CANARY_PENDING, CANARY_RUNNING):
                return s
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stages"] = [s.to_dict() for s in self.stages]
        return d


# --------------------------------------------------------------------------- #
# Auto-rollback gate
# --------------------------------------------------------------------------- #
GATE_HOLD = "hold"            # keep the change, metrics healthy
GATE_ROLLBACK = "rollback"    # metrics breached — reverse the change NOW


@dataclass
class GateDecision:
    """Verdict of the rollback gate for one guarded change."""
    change_id: str
    verdict: str                       # GATE_HOLD | GATE_ROLLBACK
    reason: str = ""
    metric_name: str = ""
    baseline: float = 0.0
    observed: float = 0.0
    drop_pct: float = 0.0
    decided_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Per game+provider sandbox policy (the promotion ladder)
# --------------------------------------------------------------------------- #
# Promotion ladder: simulation -> shadow -> production. Demotion can jump
# straight back to simulation (safety first).
PROMOTION_LADDER = (SandboxMode.SIMULATION, SandboxMode.SHADOW, SandboxMode.PRODUCTION)


@dataclass
class SandboxPolicy:
    """The complete operating policy for one (game_id, provider kind) pair.

    Promotion gates (all must hold to climb one rung):
      sim -> shadow:  min_sim_success simulated applies, all successful
      shadow -> prod: min_shadow_closed closed shadow records AND
                      mean prediction error <= max_shadow_error_pct AND
                      health score >= min_health_score
    Demotion (automatic, any time):
      health score < demote_below_score  OR  rollback-gate fired
      -> drop to SIMULATION and alert.
    """
    game_id: str
    provider: str
    mode: SandboxMode = SandboxMode.SIMULATION
    # promotion thresholds
    min_sim_success: int = 3
    min_shadow_closed: int = 3
    max_shadow_error_pct: float = 25.0
    min_health_score: float = 70.0
    demote_below_score: float = 40.0
    # counters
    sim_success_count: int = 0
    demotions: int = 0
    promotions: int = 0
    history: List[str] = field(default_factory=list)   # audit trail

    def record_event(self, event: str) -> None:
        self.history.append(f"{_now()} {event}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


__all__ = [
    "ShadowRecord", "SHADOW_OPEN", "SHADOW_CLOSED",
    "CanaryStage", "CanaryRun", "DEFAULT_CANARY_STAGES",
    "CANARY_PENDING", "CANARY_RUNNING", "CANARY_PASSED",
    "CANARY_FAILED", "CANARY_ROLLED_BACK",
    "GateDecision", "GATE_HOLD", "GATE_ROLLBACK",
    "SandboxPolicy", "PROMOTION_LADDER",
]
