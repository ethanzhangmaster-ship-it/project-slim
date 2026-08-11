"""
E14.4.2 — Lean Scheduler (Game Runtime Pool)
=============================================

Orchestration layer that runs the GameFactory OS as a *service* across 10–50
games, sitting ON TOP of the existing ``RuntimeSupervisor`` (E14.2). It adds
the cloud-ops behaviours the OS needs without touching the reliability core
(E14.2 crash-restart-degrade logic stays authoritative):

    * daily cycle      — drive every (sharded) game's decision loop on a cadence
    * resource limit   — cap concurrent games into pools (bound memory/CPU)
    * retry            — bounded retry + backoff on a transient tick failure
    * restart          — escalate a DEGRADED game to a full agent rebuild
    * shard            — manage a SUBSET of slugs so a container handles 1/N games

Lean: pure-Python, stdlib only. Reuses RuntimeSupervisor.tick_all / the
RecoveryManager / the JSONL DecisionStore. No new backend, no Postgres/Redis/
S3. The container (E14.4.1) just invokes ``GameScheduler.run_daily``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from monetization.agent.models import Opportunity
from monetization.runtime.supervisor import (
    STATUS_CRASHED, STATUS_DEGRADED, STATUS_RUNNING, STATUS_STOPPED,
    RuntimeSupervisor,
)


def default_make_opps(slug: str, day: int) -> List[Opportunity]:
    """One synthetic monetization opportunity per game per cycle.

    Production feeds real Reality-Engine opportunities here; this is the
    smoke/default so the scheduler is runnable with zero external wiring.
    """
    return [Opportunity(
        id=f"{slug}:c{day:05d}",
        type="ecpm_drop",
        segment={"country": "US", "platform": "android",
                 "ad_format": "reward", "network": "applovin"},
        metrics={"ecpm": 9.0},
        severity=0.8,
    )]


@dataclass
class SchedulerConfig:
    """Tunable knobs for the Lean scheduler."""
    daily_cycles: int = 1                 # decision cycles driven per game / day
    max_concurrent_games: int = 8         # POOL SIZE == resource limit
    retry_attempts: int = 3               # bounded retry on transient tick failure
    retry_backoff_seconds: float = 0.0    # 0 = no sleep (fast tests)
    between_pool_sleep_seconds: float = 0.0


@dataclass
class GameCycleResult:
    slug: str
    day: int
    success: bool
    cycles_run: int
    status: str
    restarted: bool = False
    retries: int = 0

    def to_dict(self) -> dict:
        return {
            "slug": self.slug, "day": self.day, "success": self.success,
            "cycles_run": self.cycles_run, "status": self.status,
            "restarted": self.restarted, "retries": self.retries,
        }


@dataclass
class DailyReport:
    day: int
    total_games: int
    ok: int = 0
    failed: int = 0
    restarted: int = 0
    pools_used: int = 0
    results: List[GameCycleResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "total_games": self.total_games,
            "ok": self.ok,
            "failed": self.failed,
            "restarted": self.restarted,
            "pools_used": self.pools_used,
            "per_game": [r.to_dict() for r in self.results],
        }


class GameScheduler:
    """Drives a (sharded) fleet of game runtimes on a daily cadence.

    Never re-implements crash handling — it delegates every tick to
    ``RuntimeSupervisor.tick_one`` and only adds retry/restart/resource-limit
    *orchestration* around it.
    """

    def __init__(self, supervisor: RuntimeSupervisor,
                 config: Optional[SchedulerConfig] = None,
                 make_opps: Optional[Callable[[str, int], List[Opportunity]]] = None,
                 slugs: Optional[List[str]] = None):
        self.sup = supervisor
        self.cfg = config or SchedulerConfig()
        self.make_opps = make_opps or default_make_opps
        # shard: None -> all games known to the supervisor
        if slugs is None:
            self.slugs = list(supervisor.runtimes.keys())
        else:
            self.slugs = [s for s in slugs if s in supervisor.runtimes]

    # ------------------------------------------------------------------ #
    def _pools(self) -> List[List[str]]:
        size = max(1, self.cfg.max_concurrent_games)
        return [self.slugs[i:i + size]
                for i in range(0, len(self.slugs), size)]

    def _tick_with_retry(self, slug: str, day: int):
        """Bounded retry + escalation for ONE game's tick.

        Returns (ok, retries_used, restarted). The supervisor already isolates
        per-game crashes internally; this adds the *orchestration* safety net:
        retry a transient failure, and rebuild the agent if it is DEGRADED.
        """
        attempts = 0
        restarted = False
        while attempts < self.cfg.retry_attempts:
            res = self.sup.tick_one(
                slug, self.make_opps(slug, day), day=day)
            if res is not None:
                return True, attempts, restarted
            rt = self.sup.runtimes[slug]
            attempts += 1
            # escalate a degraded game to a full agent rebuild (once)
            if rt.status == STATUS_DEGRADED and not restarted:
                self.sup.restart(slug)
                restarted = True
                continue
            if self.cfg.retry_backoff_seconds > 0:
                time.sleep(self.cfg.retry_backoff_seconds)
        # final shot whatever the state
        res = self.sup.tick_one(slug, self.make_opps(slug, day), day=day)
        return res is not None, attempts, restarted

    # ------------------------------------------------------------------ #
    def run_daily(self, day: int = 0) -> DailyReport:
        """Run one daily cycle across the managed (sharded) fleet.

        Games are processed in POOLS of ``max_concurrent_games`` — that pool
        size IS the resource limit (a container never holds all 50 agents'
        heavy state in one hot batch at once, and a fault in one pool is
        isolated from the others).
        """
        pools = self._pools()
        results: List[GameCycleResult] = []
        for pool in pools:
            for _ in range(self.cfg.daily_cycles):
                for slug in pool:
                    ok, retries, restarted = self._tick_with_retry(slug, day)
                    rt = self.sup.runtimes[slug]
                    results.append(GameCycleResult(
                        slug, day, ok, rt.cycles_run, rt.status,
                        restarted, retries))
            if self.cfg.between_pool_sleep_seconds > 0:
                time.sleep(self.cfg.between_pool_sleep_seconds)

        ok = sum(1 for r in results if r.success)
        restarted = sum(1 for r in results if r.restarted)
        return DailyReport(
            day=day,
            total_games=len(self.slugs),
            ok=ok,
            failed=len(results) - ok,
            restarted=restarted,
            pools_used=len(pools),
            results=results,
        )

    # ------------------------------------------------------------------ #
    def run_forever(self, interval_seconds: int = 86400, start_day: int = 0,
                    stop_flag=None) -> int:
        """Long-running service loop (container entrypoint mode).

        ``stop_flag`` is a callable returning True to halt (e.g. set by a
        SIGTERM handler). Returns the number of daily cycles completed.
        """
        day = start_day
        cycles = 0
        while True:
            if stop_flag is not None and stop_flag():
                break
            self.run_daily(day)
            day += 1
            cycles += 1
            if stop_flag is not None and stop_flag():
                break
            # sleep in 1s slices so SIGTERM is honoured promptly
            for _ in range(max(0, interval_seconds)):
                if stop_flag is not None and stop_flag():
                    break
                time.sleep(1)
        return cycles

    # ------------------------------------------------------------------ #
    def summary(self) -> dict:
        st = self.sup.status()
        managed = {s["game"]: s for s in st if s["game"] in set(self.slugs)}
        return {
            "managed_games": len(managed),
            "running": sum(1 for s in managed.values()
                           if s["status"] == STATUS_RUNNING),
            "degraded": sum(1 for s in managed.values()
                            if s["status"] == STATUS_DEGRADED),
            "crashed": sum(1 for s in managed.values()
                           if s["status"] == STATUS_CRASHED),
            "total_cycles": sum(s["cycles_run"] for s in managed.values()),
        }


__all__ = [
    "SchedulerConfig", "GameCycleResult", "DailyReport", "GameScheduler",
    "default_make_opps",
]
