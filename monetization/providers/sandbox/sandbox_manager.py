"""
E14.3.4 — Sandbox Manager (the operating policy)
=================================================

Upgrades simulation / shadow / production from "an enum value" into a
complete PER-GAME, PER-PROVIDER operating strategy:

    * every (game_id, provider kind) pair owns a SandboxPolicy
    * the promotion ladder is gated:
          simulation --(N clean simulated applies)--> shadow
          shadow --(N closed records, error <= X%, health >= Y)--> production
    * production writes go through the CanaryController (staged rollout)
      and every executed change is armed on the RollbackGate
    * demotion is AUTOMATIC and one-way-fast: unhealthy score or a fired
      rollback gate drops the pair straight back to SIMULATION + alert

The manager only ever touches providers through the frozen E14.3.1 contract
(apply_change / rollback_change / health_check). It never imports MAX or
Remote Config modules — routing stays in the ProviderRegistry.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from monetization.providers.base import MonetizationProvider
from monetization.providers.models import Change, ProviderResult, SandboxMode
from monetization.providers.registry import ProviderRegistry
from monetization.providers.sandbox.canary import CanaryController
from monetization.providers.sandbox.health_score import HealthScorer, HealthSnapshot
from monetization.providers.sandbox.rollback_gate import RollbackGate
from monetization.providers.sandbox.sandbox_models import (
    GATE_ROLLBACK, GateDecision, SandboxPolicy, ShadowRecord,
)
from monetization.providers.sandbox.shadow_tracker import ShadowTracker

try:
    from monetization.runtime.alerting import (
        Alert, ALERT_CRITICAL, ALERT_INFO, ALERT_WARNING,
    )
except Exception:  # pragma: no cover
    Alert = None  # type: ignore
    ALERT_CRITICAL, ALERT_INFO, ALERT_WARNING = "critical", "info", "warning"


class SandboxManager:
    """Per game+provider sandbox policy, promotion ladder, and guarded
    execution. One instance can serve the whole fleet (state is keyed by
    (game_id, kind) so isolation mirrors the ProviderRegistry)."""

    def __init__(self, registry: Optional[ProviderRegistry] = None,
                 alert_provider=None,
                 shadow_persist_path: Optional[str] = None):
        self.registry = registry or ProviderRegistry()
        self._alerts = alert_provider
        self.shadow = ShadowTracker(persist_path=shadow_persist_path)
        self.scorer = HealthScorer()
        self.gate = RollbackGate(alert_provider=alert_provider,
                                 on_rollback=self._on_gate_rollback)
        self.canary = CanaryController(alert_provider=alert_provider)
        self._policies: Dict[Tuple[str, str], SandboxPolicy] = {}
        # change_id -> (game_id, kind), so a gate rollback can demote the pair
        self._change_owner: Dict[str, Tuple[str, str]] = {}

    # ------------------------------------------------------------------ #
    # policy access
    # ------------------------------------------------------------------ #
    def policy(self, game_id: str, kind: str) -> SandboxPolicy:
        key = (game_id, kind)
        if key not in self._policies:
            self._policies[key] = SandboxPolicy(game_id=game_id, provider=kind)
        return self._policies[key]

    def mode(self, game_id: str, kind: str) -> SandboxMode:
        return self.policy(game_id, kind).mode

    def set_mode(self, game_id: str, kind: str, mode: SandboxMode,
                 reason: str = "manual") -> None:
        pol = self.policy(game_id, kind)
        old = pol.mode
        pol.mode = mode
        pol.record_event(f"mode {old.value} -> {mode.value} ({reason})")

    # ------------------------------------------------------------------ #
    # guarded execution — the single entry point
    # ------------------------------------------------------------------ #
    def execute(self, change: Change, *,
                predicted_metric: float = 0.0,
                baseline_metric: float = 0.0,
                metric_name: str = "revenue",
                max_drop_pct: float = 15.0) -> ProviderResult:
        """Execute one Change under the CURRENT policy mode for its
        (game, provider) pair. The change's own sandbox field is OVERRIDDEN
        by policy — the policy is the source of truth, not the caller."""
        provider = self.registry.provider_for(change.game_id, change)
        kind = change.provider
        pol = self.policy(change.game_id, kind)

        # policy overrides the change + instance sandbox
        change.sandbox = pol.mode
        provider.sandbox = pol.mode

        result = provider.apply_change(change)
        self.scorer.observe(change.game_id, result)
        self._change_owner[change.change_id] = (change.game_id, kind)

        if pol.mode == SandboxMode.SIMULATION:
            if result.success:
                pol.sim_success_count += 1
        elif pol.mode == SandboxMode.SHADOW:
            if result.success:
                self.shadow.record_proposal(change, result, predicted_metric)
        elif pol.mode == SandboxMode.PRODUCTION:
            if result.success:
                self.gate.arm(change, provider,
                              metric_name=metric_name,
                              baseline=baseline_metric,
                              max_drop_pct=max_drop_pct)

        self._maybe_demote(change.game_id, kind)
        return result

    def execute_canary(self, change: Change, *,
                       baseline_metric: float,
                       stages: Optional[List[int]] = None):
        """Start a staged production rollout for a change. Only legal when
        the pair's policy is PRODUCTION. Returns the CanaryRun."""
        provider = self.registry.provider_for(change.game_id, change)
        kind = change.provider
        pol = self.policy(change.game_id, kind)
        if pol.mode != SandboxMode.PRODUCTION:
            raise PermissionError(
                f"canary rollout requires PRODUCTION policy for "
                f"({change.game_id},{kind}); current={pol.mode.value}")
        change.sandbox = pol.mode
        provider.sandbox = pol.mode
        return self.canary.start(change, provider,
                                 baseline_metric=baseline_metric,
                                 stages=stages)

    # ------------------------------------------------------------------ #
    # reality feedback
    # ------------------------------------------------------------------ #
    def ingest_reality(self, change_id: str, actual_metric: float) -> dict:
        """Feed one observed metric for a change. Routes to BOTH the shadow
        tracker (closes prediction records) and the rollback gate (guard
        check). Returns a small report of what happened."""
        report: dict = {"change_id": change_id}
        rec = self.shadow.ingest_reality(change_id, actual_metric)
        if rec is not None:
            report["shadow_closed"] = True
            report["shadow_error_pct"] = rec.error_pct
        decision = self.gate.observe(change_id, actual_metric)
        if decision is not None:
            report["gate_verdict"] = decision.verdict
            report["gate_reason"] = decision.reason
        return report

    # ------------------------------------------------------------------ #
    # promotion ladder
    # ------------------------------------------------------------------ #
    def try_promote(self, game_id: str, kind: str) -> Tuple[bool, str]:
        """Attempt to climb ONE rung. Returns (promoted?, reason)."""
        pol = self.policy(game_id, kind)

        if pol.mode == SandboxMode.SIMULATION:
            if pol.sim_success_count < pol.min_sim_success:
                return False, (f"need {pol.min_sim_success} clean simulated "
                               f"applies, have {pol.sim_success_count}")
            self._promote(pol, SandboxMode.SHADOW,
                          f"{pol.sim_success_count} clean simulated applies")
            return True, "promoted simulation -> shadow"

        if pol.mode == SandboxMode.SHADOW:
            closed = self.shadow.closed_count(game_id, kind)
            if closed < pol.min_shadow_closed:
                return False, (f"need {pol.min_shadow_closed} closed shadow "
                               f"records, have {closed}")
            err = self.shadow.mean_error_pct(game_id, kind)
            if err is None or err > pol.max_shadow_error_pct:
                return False, (f"mean shadow error {err if err is None else round(err, 1)}% "
                               f"exceeds {pol.max_shadow_error_pct}%")
            snap = self.scorer.score(game_id, kind)
            if snap.score < pol.min_health_score:
                return False, (f"health score {snap.score:.0f} below "
                               f"{pol.min_health_score:.0f}")
            self._promote(pol, SandboxMode.PRODUCTION,
                          f"{closed} closed shadows, err {err:.1f}%, "
                          f"health {snap.score:.0f}")
            return True, "promoted shadow -> production"

        return False, "already at production"

    def _promote(self, pol: SandboxPolicy, to: SandboxMode, why: str) -> None:
        old = pol.mode
        pol.mode = to
        pol.promotions += 1
        pol.record_event(f"PROMOTE {old.value} -> {to.value}: {why}")
        self._send_alert(ALERT_INFO,
                         f"({pol.game_id},{pol.provider}) promoted "
                         f"{old.value} -> {to.value}: {why}", pol.game_id)

    # ------------------------------------------------------------------ #
    # demotion (automatic safety)
    # ------------------------------------------------------------------ #
    def _maybe_demote(self, game_id: str, kind: str) -> None:
        pol = self.policy(game_id, kind)
        if pol.mode == SandboxMode.SIMULATION:
            return
        snap = self.scorer.score(game_id, kind)
        if snap.score < pol.demote_below_score:
            self._demote(pol, f"health score {snap.score:.0f} < "
                              f"{pol.demote_below_score:.0f}")

    def _on_gate_rollback(self, change: Change, decision: GateDecision) -> None:
        owner = self._change_owner.get(change.change_id)
        if owner is None:
            return
        pol = self.policy(*owner)
        self._demote(pol, f"rollback gate fired: {decision.reason}")

    def _demote(self, pol: SandboxPolicy, why: str) -> None:
        if pol.mode == SandboxMode.SIMULATION:
            return
        old = pol.mode
        pol.mode = SandboxMode.SIMULATION
        pol.demotions += 1
        pol.sim_success_count = 0          # must re-earn the ladder
        pol.record_event(f"DEMOTE {old.value} -> simulation: {why}")
        self._send_alert(ALERT_WARNING,
                         f"({pol.game_id},{pol.provider}) DEMOTED "
                         f"{old.value} -> simulation: {why}", pol.game_id)

    # ------------------------------------------------------------------ #
    # fleet views (Runtime / Dashboard)
    # ------------------------------------------------------------------ #
    def health_report(self, game_id: str) -> List[HealthSnapshot]:
        return self.scorer.scores_for_game(game_id)

    def status(self, game_id: str) -> dict:
        pols = [p.to_dict() for (g, _), p in self._policies.items()
                if g == game_id]
        return {
            "game_id": game_id,
            "policies": pols,
            "health": [s.to_dict() for s in self.health_report(game_id)],
            "shadow_open": self.shadow.open_count(game_id),
            "shadow_closed": self.shadow.closed_count(game_id),
            "guarded_active": self.gate.active_count(),
            "rollbacks_fired": self.gate.rollbacks_fired,
        }

    def _send_alert(self, level: str, message: str, game_id: str) -> None:
        if self._alerts is not None and Alert is not None:
            self._alerts.send(Alert(level=level, message=message,
                                    game=game_id, source="sandbox_manager"))


__all__ = ["SandboxManager"]
