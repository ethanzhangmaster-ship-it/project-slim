"""
E14.5.1 — System Health Aggregator
====================================

Consumes the RuntimeSupervisor (E14.2) and produces ONE HealthSnapshot per
game. The snapshot is the single thing a human operator reads to know
"is this game healthy, and why not".

It deliberately avoids introducing any new backend: it only *reads* state
already owned by the supervisor (HealthMonitor, GameRuntime flags, the
per-game DecisionStore) and an OPTIONAL provider-health source (e.g. a
SandboxManager.health_report score) if one is injected.

Scoring (simple + explainable, no ML):

    score = 0.4 * (100 - failure_rate*100)
          + 0.3 * (100 - rollback_rate*100)
          + 0.3 * provider_health

Status bands:   >= 70 healthy | 40..70 degraded | < 40 unhealthy
                runtime isolated (degraded/crashed) -> "isolated" (capped)
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from monetization.observability.models import (
    RISK_HIGH, RISK_LOW, RISK_MEDIUM, HealthSnapshot, FleetHealthReport,
    HEALTH_DEGRADED, HEALTH_HEALTHY, HEALTH_ISOLATED, HEALTH_UNHEALTHY,
)
from monetization.runtime.supervisor import STATUS_CRASHED, STATUS_DEGRADED

# execution_status vocabulary (learning/models.py)
_EXEC_ATTEMPT = ("executed", "rolled_back", "failed")
_EXEC_ROLLBACK = ("rolled_back", "failed")


class SystemHealthAggregator:
    """Turns raw runtime state into operator-readable health."""

    def __init__(self, supervisor,
                 provider_health_sources: Optional[Dict[str, Callable[[str], float]]] = None):
        """
        Args:
            supervisor:              a RuntimeSupervisor instance.
            provider_health_sources: optional {provider_kind: fn(game_id)->0..100}.
                                     When given, provider_health is the mean of
                                     the sourced scores; otherwise it is derived
                                     from runtime signals (failure rate, flags).
        """
        self.sup = supervisor
        self.provider_health_sources = provider_health_sources or {}

    # ------------------------------------------------------------------ #
    def _exec_status(self, rec) -> str:
        for attr in ("execution_status", "status", "result_status"):
            v = getattr(rec, attr, None)
            if isinstance(v, str) and v:
                return v
        return ""

    def _rollback_rate(self, rt) -> float:
        recs = rt.agent.store.all()
        attempts = [r for r in recs if self._exec_status(r) in _EXEC_ATTEMPT]
        if not attempts:
            return 0.0
        rb = [r for r in attempts if self._exec_status(r) in _EXEC_ROLLBACK]
        return len(rb) / len(attempts)

    def _provider_health(self, rt) -> float:
        src = self.provider_health_sources
        if src:
            scores = []
            for fn in src.values():
                try:
                    scores.append(float(fn(rt.slug)))
                except Exception:
                    pass
            if scores:
                return max(0.0, min(100.0, sum(scores) / len(scores)))
        # derived fallback from runtime signals
        hs = rt.health.check()
        score = 100.0 - hs.failure_rate * 100.0
        if rt.execution_disabled:
            score -= 40.0
        score -= min(rt.consecutive_rollbacks * 8.0, 40.0)
        if rt.status == STATUS_DEGRADED:
            score -= 50.0
        elif rt.status == STATUS_CRASHED:
            score -= 60.0
        return max(0.0, min(100.0, score))

    # ------------------------------------------------------------------ #
    def snapshot(self) -> FleetHealthReport:
        out: List[HealthSnapshot] = []
        for slug, rt in sorted(self.sup.runtimes.items()):
            hs = rt.health.check()
            fr = hs.failure_rate
            success_rate = (1.0 - fr) if hs.recent_executions else 1.0
            rb_rate = self._rollback_rate(rt)
            prov = self._provider_health(rt)
            latency_ms = hs.max_event_delay_s * 1000.0

            score = (0.4 * (100.0 - fr * 100.0)
                     + 0.3 * (100.0 - rb_rate * 100.0)
                     + 0.3 * prov)
            score = max(0.0, min(100.0, score))

            isolated = rt.status in (STATUS_DEGRADED, STATUS_CRASHED)
            if isolated:
                status = HEALTH_ISOLATED
                score = min(score, 30.0)
                risk = RISK_HIGH
            elif score >= 70.0:
                status = HEALTH_HEALTHY
                risk = RISK_LOW
            elif score >= 40.0:
                status = HEALTH_DEGRADED
                risk = RISK_MEDIUM
            else:
                status = HEALTH_UNHEALTHY
                risk = RISK_HIGH

            # execution disabled => at least degraded + high risk
            if rt.execution_disabled and status == HEALTH_HEALTHY:
                status = HEALTH_DEGRADED
                risk = RISK_HIGH

            out.append(HealthSnapshot(
                game_id=slug, status=status, risk=risk, score=score,
                cycle_success_rate=success_rate, failure_rate=fr,
                rollback_rate=rb_rate, latency_ms=latency_ms,
                provider_health=prov, execution_disabled=rt.execution_disabled,
                consecutive_rollbacks=rt.consecutive_rollbacks,
                cycles_run=rt.cycles_run, issues=list(hs.issues)))
        return FleetHealthReport(games=out)


__all__ = ["SystemHealthAggregator"]
