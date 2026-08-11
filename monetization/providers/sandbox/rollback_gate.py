"""
E14.3.4 — Auto Rollback Gate
=============================

After a change is EXECUTED (production or canary stage), it is not "done" —
it is GUARDED. The gate watches the post-execution metric and, on breach,
automatically reverses the change through the SAME frozen contract surface
(`provider.rollback_change`) and raises a CRITICAL alert.

Guard rule (explainable, mirrors E13.4.4 guardrails):

    drop_pct = (baseline - observed) / max(|baseline|, eps) * 100
    breach   = drop_pct > max_drop_pct           (metric collapsed)
               OR observed < hard_floor          (absolute disaster line)

The gate NEVER blocks the executor thread: `observe()` is fed by the caller
(Reality Engine / canary controller) whenever fresh metrics arrive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from monetization.providers.base import MonetizationProvider
from monetization.providers.models import Change, ProviderResult
from monetization.providers.sandbox.sandbox_models import (
    GATE_HOLD, GATE_ROLLBACK, GateDecision,
)

try:  # alerting is optional at import time (sandbox layer stays standalone)
    from monetization.runtime.alerting import (
        Alert, AlertProvider, ALERT_CRITICAL,
    )
except Exception:  # pragma: no cover
    Alert = None          # type: ignore
    AlertProvider = None  # type: ignore
    ALERT_CRITICAL = "critical"


@dataclass
class GuardedChange:
    """One executed change under guard."""
    change: Change
    provider: MonetizationProvider
    metric_name: str
    baseline: float
    max_drop_pct: float = 15.0
    hard_floor: Optional[float] = None
    active: bool = True
    decisions: List[GateDecision] = field(default_factory=list)


class RollbackGate:
    """Guards executed changes; auto-rolls-back on metric breach."""

    def __init__(self, alert_provider=None,
                 on_rollback: Optional[Callable[[Change, GateDecision], None]] = None):
        self._guarded: Dict[str, GuardedChange] = {}
        self._alerts = alert_provider
        self._on_rollback = on_rollback
        self.rollbacks_fired = 0

    # ------------------------------------------------------------------ #
    def arm(self, change: Change, provider: MonetizationProvider, *,
            metric_name: str, baseline: float,
            max_drop_pct: float = 15.0,
            hard_floor: Optional[float] = None) -> GuardedChange:
        g = GuardedChange(change=change, provider=provider,
                          metric_name=metric_name, baseline=baseline,
                          max_drop_pct=max_drop_pct, hard_floor=hard_floor)
        self._guarded[change.change_id] = g
        return g

    def disarm(self, change_id: str) -> None:
        g = self._guarded.get(change_id)
        if g:
            g.active = False

    # ------------------------------------------------------------------ #
    def observe(self, change_id: str, observed: float) -> Optional[GateDecision]:
        """Feed a fresh metric for a guarded change. Returns the decision, or
        None if the change is unknown / no longer guarded."""
        g = self._guarded.get(change_id)
        if g is None or not g.active:
            return None

        drop_pct = ((g.baseline - observed) /
                    max(abs(g.baseline), 1e-9)) * 100.0
        breached = drop_pct > g.max_drop_pct
        floored = g.hard_floor is not None and observed < g.hard_floor

        if breached or floored:
            reason = (f"{g.metric_name} dropped {drop_pct:.1f}% "
                      f"(limit {g.max_drop_pct}%)" if breached else
                      f"{g.metric_name}={observed} below hard floor {g.hard_floor}")
            decision = GateDecision(
                change_id=change_id, verdict=GATE_ROLLBACK, reason=reason,
                metric_name=g.metric_name, baseline=g.baseline,
                observed=observed, drop_pct=drop_pct)
            g.decisions.append(decision)
            self._fire_rollback(g, decision)
            return decision

        decision = GateDecision(
            change_id=change_id, verdict=GATE_HOLD,
            reason=f"{g.metric_name} within bounds (drop {drop_pct:.1f}%)",
            metric_name=g.metric_name, baseline=g.baseline,
            observed=observed, drop_pct=drop_pct)
        g.decisions.append(decision)
        return decision

    # ------------------------------------------------------------------ #
    def _fire_rollback(self, g: GuardedChange, decision: GateDecision) -> None:
        """Reverse via the frozen contract; alert; notify listener."""
        result: ProviderResult = g.provider.rollback_change(g.change)
        g.active = False
        self.rollbacks_fired += 1
        if self._alerts is not None and Alert is not None:
            self._alerts.send(Alert(
                level=ALERT_CRITICAL,
                message=f"AUTO-ROLLBACK {g.change.change_id}: {decision.reason}",
                game=g.change.game_id, source="rollback_gate",
                meta={"decision": decision.to_dict(),
                      "rollback_success": result.success,
                      "real_api_called": result.real_api_called}))
        if self._on_rollback:
            self._on_rollback(g.change, decision)

    # ------------------------------------------------------------------ #
    def guarded(self, change_id: str) -> Optional[GuardedChange]:
        return self._guarded.get(change_id)

    def active_count(self) -> int:
        return sum(1 for g in self._guarded.values() if g.active)

    def decisions(self, change_id: str) -> List[GateDecision]:
        g = self._guarded.get(change_id)
        return list(g.decisions) if g else []


__all__ = ["RollbackGate", "GuardedChange"]
