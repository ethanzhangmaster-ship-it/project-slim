"""
E15.3 — Graduated traffic rollout with automatic gating.

Replaces "one-shot full rollout" with a 3-phase safety-gated process:
  Phase 1:  5% users,  24h → advance if ARPDAU ≥ +2% AND retention ≥ -2%
  Phase 2: 25% users,  48h → same gate
  Phase 3: 100% users,  complete → monitor guardrail

Auto-ROLLBACK if: ARPDAU drops >5% OR retention drops >2% at any phase.
This is the key piece that makes the operator autonomous — it doesn't need
a human to decide whether to expand or roll back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RolloutPhase:
    phase: int
    traffic_pct: float
    min_hours: int
    gate: Dict[str, float]  # arpdau_pct min, retention_pct min


@dataclass
class RolloutState:
    experiment_id: str
    current_phase: int = 1
    traffic: float = 0.05
    started_at: str = ""
    last_checked_at: str = ""
    verdict: str = "advancing"   # advancing | paused | rollback | complete
    metrics: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "current_phase": self.current_phase,
            "traffic": self.traffic,
            "started_at": self.started_at,
            "last_checked_at": self.last_checked_at,
            "verdict": self.verdict,
            "metrics": self.metrics,
            "history": self.history,
        }


class GraduatedRollout:
    PHASES = [
        RolloutPhase(1, 0.05, 24,
                     {"arpdau_pct": 2.0, "retention_pct": -2.0}),
        RolloutPhase(2, 0.25, 48,
                     {"arpdau_pct": 2.0, "retention_pct": -2.0}),
        RolloutPhase(3, 1.0, 0,
                     {"arpdau_pct": 0.0, "retention_pct": -3.0}),
    ]
    ROLLBACK_ARPDAU = -5.0
    ROLLBACK_RETENTION = -2.0

    def init(self, experiment_id: str) -> RolloutState:
        now = datetime.now(timezone.utc).isoformat()
        return RolloutState(
            experiment_id=experiment_id,
            current_phase=1, traffic=self.PHASES[0].traffic_pct,
            started_at=now, verdict="advancing")

    def evaluate(self, state: RolloutState,
                 metrics: Dict[str, Any]) -> RolloutState:
        arpdau = metrics.get("arpdau_delta_pct", 0.0)
        ret = metrics.get("retention_delta_pct", 0.0)
        state.last_checked_at = datetime.now(timezone.utc).isoformat()
        state.metrics = {"arpdau_delta_pct": arpdau, "retention_delta_pct": ret}
        state.history.append(dict(state.metrics, checked_at=state.last_checked_at))

        # --- auto-ROLLBACK ---
        if arpdau < self.ROLLBACK_ARPDAU or ret < self.ROLLBACK_RETENTION:
            state.verdict = "rollback"
            state.traffic = 0.0
            return state

        if state.current_phase > len(self.PHASES):
            state.verdict = "complete"
            return state

        phase = self.PHASES[state.current_phase - 1]
        gate = phase.gate

        # --- advance gate ---
        can_advance = (arpdau >= gate["arpdau_pct"]
                       and ret >= gate["retention_pct"])
        if not can_advance:
            state.verdict = "paused"
            return state

        # check if enough time has elapsed
        if phase.min_hours > 0 and state.started_at:
            try:
                elapsed = (datetime.now(timezone.utc)
                           - datetime.fromisoformat(state.started_at))
                if elapsed.total_seconds() < phase.min_hours * 3600:
                    state.verdict = "advancing"  # still in window
                    return state
            except (ValueError, TypeError):
                pass

        # advance to next phase
        if state.current_phase < len(self.PHASES):
            state.current_phase += 1
            new_phase = self.PHASES[state.current_phase - 1]
            state.traffic = new_phase.traffic_pct
            state.verdict = "advancing"
        else:
            state.verdict = "complete"
        return state

    def current_phase_spec(self, state: RolloutState) -> Optional[RolloutPhase]:
        if 1 <= state.current_phase <= len(self.PHASES):
            return self.PHASES[state.current_phase - 1]
        return None
