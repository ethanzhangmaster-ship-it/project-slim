"""
E14.2 — Module 1: Runtime Supervisor
=====================================

The fleet process-manager. It owns ONE isolated runtime per game and drives
the long-running service loop. Think of it as the `systemd` of the
GameFactory OS:

    RuntimeSupervisor
        |
        +-- Game A Runtime  (agent + checkpoint + health + recovery flags)
        +-- Game B Runtime
        +-- ...
        +-- Game N Runtime
        |
        +-- shared: EventLogger, AlertProvider, RecoveryManager

Public API (per spec):
    supervisor.start()        -> bring all games online
    supervisor.stop()         -> take all games offline
    supervisor.restart(game)  -> rebuild a single game's agent from its store
    supervisor.status()       -> per-game health/status snapshot

Plus the operational tick methods used by the service loop:
    supervisor.tick_one(game, opps, day)
    supervisor.tick_all({game: opps}, day)
    supervisor.run_soak(total_cycles, make_opps)

Reliability guarantees enforced here:
  * A crash in ONE game is caught and never propagates to the others
    (per-game try/except + isolated recovery)  -> Case 4.
  * A crash triggers automatic restart (bounded) or safe degradation -> Case 1.
  * Every cycle writes a stage checkpoint + a rolling store snapshot so a
    corrupted store can be restored                              -> Case 2.
  * Consecutive failed executions disable execution + alert       -> Case 3.

Pure-Python, stdlib only. No LLM, no external API, no shared mutable state
across games (isolation inherited from E14.1).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from monetization.agent.controller import MonetizationAgent
from monetization.agent.registry import GameFactoryOS, build_game_agent
from monetization.runtime.alerting import (
    ALERT_CRITICAL, ALERT_WARNING, Alert, MockAlertProvider,
)
from monetization.runtime.checkpoint import (
    STAGE_AFTER_EXECUTION, STAGE_BEFORE_DECISION, CheckpointManager,
)
from monetization.runtime.event_logger import (
    EVENT_CYCLE_DONE, EVENT_CYCLE_START, EVENT_STRATEGY_BLOCKED,
    EVENT_STRATEGY_EXECUTED, EVENT_STRATEGY_EXPERIMENTED, EventLogger,
)
from monetization.runtime.health import HealthMonitor
from monetization.runtime.recovery import RecoveryManager
from monetization.providers.credential_resolver import (
    CredentialContext, CredentialResolver,
)


# Runtime status vocabulary
STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"
STATUS_CRASHED = "crashed"
STATUS_DEGRADED = "degraded"
RUNTIME_STATUSES = (STATUS_RUNNING, STATUS_STOPPED, STATUS_CRASHED, STATUS_DEGRADED)


@dataclass
class RuntimeConfig:
    """Tunable reliability knobs for the supervisor."""
    stall_timeout_hours: float = 24.0
    failure_rate_threshold: float = 0.20
    max_consecutive_rollbacks: int = 3
    max_restart_attempts: int = 3
    max_store_snapshots: int = 5
    checkpoint_enabled: bool = True
    health_window: int = 50


@dataclass
class GameRuntime:
    """Everything the supervisor tracks for ONE game tenant."""
    slug: str
    agent: MonetizationAgent
    checkpoint: CheckpointManager
    health: HealthMonitor
    status: str = STATUS_RUNNING
    execution_disabled: bool = False
    consecutive_rollbacks: int = 0
    restart_attempts: int = 0
    cycles_run: int = 0
    last_cycle_meta: dict = field(default_factory=dict)
    # ---- test hooks (production never sets these) ----
    fault_once: bool = False
    fault_always: bool = False
    fault_cb: Optional[Callable[[], None]] = None
    # ---- E14.3.5: per-game credential view (None when supervisor is
    #      started without a CredentialResolver — fully backward compatible)
    credential_context: Optional["CredentialContext"] = None


class RuntimeSupervisor:
    """Fleet supervisor / process-manager for the GameFactory OS."""

    def __init__(self, game_factory_os: GameFactoryOS, checkpoint_root: str,
                 alert_provider=None, events: Optional[EventLogger] = None,
                 config: Optional[RuntimeConfig] = None,
                 credential_resolver: Optional[CredentialResolver] = None):
        self.os = game_factory_os
        self.config = config or RuntimeConfig()
        self.alerts = alert_provider or MockAlertProvider()
        self.events = events or EventLogger()
        self.checkpoint_root = Path(checkpoint_root)
        # E14.3.5: optional credential resolver. When None (default) the
        # supervisor behaves exactly as before E14.3.5 — no per-game creds.
        self.credential_resolver = credential_resolver
        self.runtimes: Dict[str, GameRuntime] = {}
        self._build_runtimes()
        self.recovery = RecoveryManager(self, self.alerts, self.events, self.config)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def _build_runtimes(self) -> None:
        for slug, agent in self.os.agents.items():
            ckpt = CheckpointManager(
                str(self.checkpoint_root), slug, self.config.max_store_snapshots)
            hm = HealthMonitor(
                slug, self.config.stall_timeout_hours,
                self.config.failure_rate_threshold, self.config.health_window)
            rt = GameRuntime(slug, agent, ckpt, hm)
            # E14.3.5: attach a game-scoped credential view so that when the
            # supervisor starts N games, each runtime carries agent + providers
            # + credentials that are all naturally isolated. Unsafe slugs or
            # resolver-less startups simply get None (no behaviour change).
            if self.credential_resolver is not None:
                try:
                    rt.credential_context = self.credential_resolver.context(slug)
                except Exception:
                    rt.credential_context = None
            self.runtimes[slug] = rt

    # ------------------------------------------------------------------ #
    # Public lifecycle API
    # ------------------------------------------------------------------ #
    def start(self) -> list:
        for rt in self.runtimes.values():
            if rt.status != STATUS_DEGRADED:
                rt.status = STATUS_RUNNING
        self.events.log("supervisor_start", level="info")
        return self.status()

    def stop(self) -> list:
        for rt in self.runtimes.values():
            rt.status = STATUS_STOPPED
        self.events.log("supervisor_stop", level="info")
        return self.status()

    def restart(self, slug: str) -> Optional[GameRuntime]:
        cfg = self.os.registry.get(slug)
        if cfg is None:
            return None
        agent = build_game_agent(
            cfg, str(self.os.base_store_dir), self.os.seed_memory_fn)
        self.os.agents[slug] = agent
        rt = self.runtimes[slug]
        rt.agent = agent
        rt.consecutive_rollbacks = 0
        rt.execution_disabled = False
        rt.status = STATUS_RUNNING
        rt.health.mark_cycle()
        return rt

    def status(self) -> list:
        out = []
        for slug, rt in sorted(self.runtimes.items()):
            hs = rt.health.check()
            out.append({
                "game": slug,
                "status": rt.status,
                "last_cycle": hs.last_cycle_time,
                "health": "ok" if hs.ok else "unhealthy",
                "cycles_run": rt.cycles_run,
                "execution_disabled": rt.execution_disabled,
                "consecutive_rollbacks": rt.consecutive_rollbacks,
                "restart_attempts": rt.restart_attempts,
            })
        return out

    # ------------------------------------------------------------------ #
    # Operational tick (the service loop calls this)
    # ------------------------------------------------------------------ #
    def tick_one(self, slug: str, opportunities: list, day: int = 0):
        rt = self.runtimes.get(slug)
        if rt is None or rt.status in (STATUS_STOPPED, STATUS_DEGRADED):
            return None
        try:
            # ---- fault injection hooks (test only) ----
            if rt.fault_always:
                raise RuntimeError(f"injected persistent crash in {slug}")
            if rt.fault_once:
                rt.fault_once = False
                raise RuntimeError(f"injected transient crash in {slug}")
            if rt.fault_cb is not None:
                rt.fault_cb()

            # ---- checkpoint: BEFORE ----
            if self.config.checkpoint_enabled:
                rt.checkpoint.save_stage(
                    f"d{day}", STAGE_BEFORE_DECISION, self._state_hash(rt),
                    {"day": day})

            self.events.log(EVENT_CYCLE_START, game=slug, day=day)
            cycle = rt.agent.run_cycle(opportunities, day=day)

            # ---- checkpoint: AFTER (store snapshot + stage meta) ----
            if self.config.checkpoint_enabled:
                rt.checkpoint.snapshot_store(str(rt.agent.store.path))
                rt.checkpoint.save_stage(
                    f"d{day}", STAGE_AFTER_EXECUTION, self._state_hash(rt),
                    {"day": day, "exec": cycle.n_execute,
                     "exp": cycle.n_experiment, "block": cycle.n_block})

            # ---- success bookkeeping ----
            rt.cycles_run += 1
            rt.health.mark_cycle()
            self._feed_health(rt, cycle)
            self._record_action_events(rt, cycle)
            self.events.log(EVENT_CYCLE_DONE, game=slug, day=day,
                            exec=cycle.n_execute, exp=cycle.n_experiment,
                            block=cycle.n_block)

            # ---- recovery: bad decision loop check ----
            self.recovery.on_cycle(slug)
            return cycle

        except Exception as e:  # crash -> isolated recovery (never leaks out)
            self.recovery.on_crash(slug, e)
            return None

    def tick_all(self, opportunities_by_game: Dict[str, list], day: int = 0) -> dict:
        return {slug: self.tick_one(slug, opps, day=day)
                for slug, opps in opportunities_by_game.items()}

    def run_soak(self, total_cycles: int,
                 make_opps: Callable[[str, int], list],
                 day_start: int = 0) -> list:
        slugs = list(self.runtimes.keys())
        for i in range(total_cycles):
            slug = slugs[i % len(slugs)]
            self.tick_one(slug, make_opps(slug, day_start + i), day=day_start + i)
        return self.status()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _state_hash(self, rt: GameRuntime) -> str:
        payload = (f"{rt.agent.store.count()}|{rt.agent.state.day}|"
                   f"{rt.cycles_run}|{rt.execution_disabled}")
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _feed_health(self, rt: GameRuntime, cycle) -> None:
        executed_any = False
        failed = 0
        for a in cycle.actions:
            if a.action != "execute":
                continue
            ok = (a.result_status == "executed")
            rt.health.record_execution(ok)
            if ok:
                executed_any = True
            else:
                failed += 1
        # consecutive-failure tracking for the bad-decision-loop policy
        if executed_any:
            rt.consecutive_rollbacks = 0
        else:
            rt.consecutive_rollbacks += failed

    def _record_action_events(self, rt: GameRuntime, cycle) -> None:
        for a in cycle.actions:
            if a.action == "execute" and a.result_status == "executed":
                self.events.log(EVENT_STRATEGY_EXECUTED, game=rt.slug,
                                strategy=a.strategy_type,
                                result=a.result_status)
            elif a.action == "experiment":
                self.events.log(EVENT_STRATEGY_EXPERIMENTED, game=rt.slug,
                                strategy=a.strategy_type)
            elif a.action == "block":
                self.events.log(EVENT_STRATEGY_BLOCKED, game=rt.slug,
                                strategy=a.strategy_type, level="warning")

    # ------------------------------------------------------------------ #
    def summary(self) -> dict:
        st = self.status()
        return {
            "games": len(self.runtimes),
            "running": sum(1 for s in st if s["status"] == STATUS_RUNNING),
            "stopped": sum(1 for s in st if s["status"] == STATUS_STOPPED),
            "crashed": sum(1 for s in st if s["status"] == STATUS_CRASHED),
            "degraded": sum(1 for s in st if s["status"] == STATUS_DEGRADED),
            "total_cycles": sum(s["cycles_run"] for s in st),
            "alerts_sent": self.alerts.count(),
            "events_logged": self.events.count(),
            "status": st,
        }


__all__ = [
    "RuntimeSupervisor", "RuntimeConfig", "GameRuntime",
    "STATUS_RUNNING", "STATUS_STOPPED", "STATUS_CRASHED", "STATUS_DEGRADED",
]
