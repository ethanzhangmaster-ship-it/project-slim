"""
E14.3.4 — Provider Health Scoring
==================================

Turns a rolling window of ProviderResult observations into a single 0-100
score + status label, consumed by:

    * SandboxManager   — promotion / demotion decisions
    * Runtime (E14.2)  — Supervisor degrade / alert
    * Dashboard (E14.5)

Scoring model (deliberately simple + explainable, no ML):

    score = 100
          - failure_rate * W_FAILURE      (failures dominate)
          - latency_penalty               (slow providers are risky providers)
          - health_check_penalty          (failed health checks)

Status bands:  >= 70 healthy | >= 40 degraded | < 40 unhealthy
(the demotion threshold in SandboxPolicy defaults to < 40 -> auto-demote)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from monetization.providers.models import ProviderResult

STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_UNHEALTHY = "unhealthy"

HEALTHY_MIN = 70.0
DEGRADED_MIN = 40.0

# weights
W_FAILURE = 100.0          # failure_rate (0..1) * 100 => a 40% failure rate alone drops to 60
W_HEALTH_FAIL = 15.0       # each failed health check in window
LATENCY_SOFT_MS = 500.0    # no penalty below this
LATENCY_MAX_PENALTY = 20.0


def status_for(score: float) -> str:
    if score >= HEALTHY_MIN:
        return STATUS_HEALTHY
    if score >= DEGRADED_MIN:
        return STATUS_DEGRADED
    return STATUS_UNHEALTHY


@dataclass
class HealthSnapshot:
    provider: str
    game_id: str
    score: float
    status: str
    window: int
    failure_rate: float
    avg_latency_ms: float
    health_fails: int

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "game_id": self.game_id,
            "score": round(self.score, 2),
            "status": self.status,
            "window": self.window,
            "failure_rate": round(self.failure_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "health_fails": self.health_fails,
        }


class HealthScorer:
    """Rolling-window health scorer, isolated per (game_id, provider kind)."""

    def __init__(self, window: int = 50):
        self._window = window
        self._ops: Dict[Tuple[str, str], Deque[ProviderResult]] = {}
        self._health: Dict[Tuple[str, str], Deque[ProviderResult]] = {}

    # ------------------------------------------------------------------ #
    def observe(self, game_id: str, result: ProviderResult) -> None:
        """Feed one ProviderResult (apply / rollback / health_check)."""
        key = (game_id, result.provider)
        if result.operation == "health_check":
            dq = self._health.setdefault(key, deque(maxlen=self._window))
        else:
            dq = self._ops.setdefault(key, deque(maxlen=self._window))
        dq.append(result)

    # ------------------------------------------------------------------ #
    def score(self, game_id: str, provider: str) -> HealthSnapshot:
        key = (game_id, provider)
        ops = list(self._ops.get(key, ()))
        checks = list(self._health.get(key, ()))

        n = len(ops)
        failures = sum(1 for r in ops if not r.success)
        failure_rate = (failures / n) if n else 0.0
        avg_lat = (sum(r.latency_ms for r in ops) / n) if n else 0.0
        health_fails = sum(1 for r in checks if not r.success)

        score = 100.0
        score -= failure_rate * W_FAILURE
        if avg_lat > LATENCY_SOFT_MS:
            over = min((avg_lat - LATENCY_SOFT_MS) / LATENCY_SOFT_MS, 1.0)
            score -= over * LATENCY_MAX_PENALTY
        score -= min(health_fails * W_HEALTH_FAIL, 45.0)
        score = max(0.0, min(100.0, score))

        return HealthSnapshot(
            provider=provider, game_id=game_id, score=score,
            status=status_for(score), window=n,
            failure_rate=failure_rate, avg_latency_ms=avg_lat,
            health_fails=health_fails)

    def scores_for_game(self, game_id: str) -> List[HealthSnapshot]:
        kinds = {k[1] for k in list(self._ops) + list(self._health)
                 if k[0] == game_id}
        return [self.score(game_id, kind) for kind in sorted(kinds)]

    def reset(self, game_id: str, provider: str = "") -> None:
        """Drop history (recovery / restart path)."""
        def keep(k: Tuple[str, str]) -> bool:
            if k[0] != game_id:
                return True
            return bool(provider) and k[1] != provider
        self._ops = {k: v for k, v in self._ops.items() if keep(k)}
        self._health = {k: v for k, v in self._health.items() if keep(k)}


__all__ = [
    "HealthScorer", "HealthSnapshot", "status_for",
    "STATUS_HEALTHY", "STATUS_DEGRADED", "STATUS_UNHEALTHY",
    "HEALTHY_MIN", "DEGRADED_MIN",
]
