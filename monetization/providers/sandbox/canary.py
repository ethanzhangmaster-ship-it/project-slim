"""
E14.3.4 — Canary Controller (staged production rollout)
========================================================

Production writes never go 0 -> 100%. A CanaryRun walks the stages
(default 10% -> 50% -> 100%); each stage:

    1. apply the stage-scoped Change through the frozen contract
    2. observe the stage metric (fed by the caller / Reality Engine)
    3. stage gate: metric must not drop more than `max_drop_pct` vs baseline
    4. pass  -> next stage
       fail  -> STOP + rollback EVERY applied stage (reverse order) + alert

How "percent" maps to platform scope is the ADAPTER's business (geo subset,
ad-unit subset, RC conditional audience). The controller only sequences and
guards. Contract surface used: apply_change / rollback_change. Nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from monetization.providers.base import MonetizationProvider
from monetization.providers.models import Change, ProviderResult
from monetization.providers.sandbox.sandbox_models import (
    CANARY_FAILED, CANARY_PASSED, CANARY_PENDING, CANARY_ROLLED_BACK,
    CANARY_RUNNING, CanaryRun, CanaryStage,
)

try:
    from monetization.runtime.alerting import Alert, ALERT_CRITICAL, ALERT_INFO
except Exception:  # pragma: no cover
    Alert = None  # type: ignore
    ALERT_CRITICAL = "critical"
    ALERT_INFO = "info"


def _stage_change(change: Change, percent: int) -> Change:
    """Derive the stage-scoped Change (same mutation, annotated scope)."""
    staged = Change(
        target=change.target,
        change_type=change.change_type,
        old=change.old, new=change.new,
        provider=change.provider, game_id=change.game_id,
        note=(change.note + f" [canary {percent}%]").strip(),
        sandbox=change.sandbox,
        credential_ref=change.credential_ref)
    # keep traceability back to the parent change
    staged.change_id = f"{change.change_id}_p{percent}"
    return staged


class CanaryController:
    """Sequences staged rollouts; hard-stops + rolls back on stage failure."""

    def __init__(self, alert_provider=None, max_drop_pct: float = 10.0):
        self._alerts = alert_provider
        self._max_drop_pct = max_drop_pct
        self._runs: Dict[str, CanaryRun] = {}
        # per run: stage changes actually applied (for reverse rollback)
        self._applied: Dict[str, List[Change]] = {}
        self._providers: Dict[str, MonetizationProvider] = {}
        self._baselines: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    def start(self, change: Change, provider: MonetizationProvider, *,
              baseline_metric: float,
              stages: Optional[List[int]] = None) -> CanaryRun:
        run = CanaryRun(game_id=change.game_id,
                        provider=change.provider or provider.name,
                        change_id=change.change_id)
        if stages:
            run.stages = [CanaryStage(p) for p in stages]
        run.status = CANARY_RUNNING
        self._runs[run.run_id] = run
        self._applied[run.run_id] = []
        self._providers[run.run_id] = provider
        self._baselines[run.run_id] = baseline_metric
        self._parent_changes = getattr(self, "_parent_changes", {})
        self._parent_changes[run.run_id] = change
        return run

    # ------------------------------------------------------------------ #
    def advance(self, run_id: str, observed_metric: float) -> CanaryRun:
        """Apply the next pending stage, then gate it on `observed_metric`.

        The caller supplies the metric observed AFTER the stage soak window
        (in tests this is synchronous; in production the Runtime feeds it).
        """
        run = self._runs[run_id]
        if run.status != CANARY_RUNNING:
            return run
        stage = run.current_stage()
        if stage is None:
            run.status = CANARY_PASSED
            return run

        provider = self._providers[run_id]
        parent = self._parent_changes[run_id]
        baseline = self._baselines[run_id]

        # 1. apply stage-scoped change
        stage.status = CANARY_RUNNING
        staged = _stage_change(parent, stage.percent)
        result: ProviderResult = provider.apply_change(staged)
        stage.result_success = result.success
        if not result.success:
            stage.status = CANARY_FAILED
            stage.detail = f"apply failed: {result.error}"
            self._fail(run, stage)
            return run
        self._applied[run_id].append(staged)

        # 2+3. gate on observed metric
        stage.observed_metric = observed_metric
        drop_pct = ((baseline - observed_metric) /
                    max(abs(baseline), 1e-9)) * 100.0
        stage.gate_passed = drop_pct <= self._max_drop_pct
        if not stage.gate_passed:
            stage.status = CANARY_FAILED
            stage.detail = (f"stage gate breach: metric dropped "
                            f"{drop_pct:.1f}% (limit {self._max_drop_pct}%)")
            self._fail(run, stage)
            return run

        # 4. pass
        stage.status = CANARY_PASSED
        stage.detail = f"gate ok (drop {drop_pct:.1f}%)"
        if run.current_stage() is None:
            run.status = CANARY_PASSED
            self._alert(ALERT_INFO,
                        f"canary {run.change_id} fully rolled out "
                        f"({len(run.stages)} stages)", run)
        return run

    # ------------------------------------------------------------------ #
    def _fail(self, run: CanaryRun, stage: CanaryStage) -> None:
        """Stage failed: stop the run and reverse everything applied so far."""
        run.status = CANARY_FAILED
        provider = self._providers[run.run_id]
        for applied in reversed(self._applied[run.run_id]):
            provider.rollback_change(applied)
        if self._applied[run.run_id]:
            run.rolled_back = True
            run.status = CANARY_ROLLED_BACK
        self._alert(ALERT_CRITICAL,
                    f"canary {run.change_id} FAILED at {stage.percent}%: "
                    f"{stage.detail}; rolled back "
                    f"{len(self._applied[run.run_id])} stage(s)", run)

    def _alert(self, level: str, message: str, run: CanaryRun) -> None:
        if self._alerts is not None and Alert is not None:
            self._alerts.send(Alert(level=level, message=message,
                                    game=run.game_id, source="canary",
                                    meta={"run": run.to_dict()}))

    # ------------------------------------------------------------------ #
    def run(self, run_id: str) -> Optional[CanaryRun]:
        return self._runs.get(run_id)

    def applied_stages(self, run_id: str) -> List[Change]:
        return list(self._applied.get(run_id, ()))


__all__ = ["CanaryController"]
