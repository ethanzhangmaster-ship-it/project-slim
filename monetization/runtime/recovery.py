"""
E14.2 — Module 5: Recovery Manager
===================================

Turns health/crash signals into *safe* automatic recovery actions. It never
makes business decisions (that's the Agent's job); it only protects the
runtime from getting stuck or doing harm.

Three recovery policies (per the spec):

  1. AGENT CRASH        -> restart the game's agent from its store, up to
                          `max_restart_attempts` times; beyond that the game
                          is marked DEGRADED (isolated) so the rest of the
                          fleet keeps running.
  2. BAD DECISION LOOP  -> consecutive `rolled_back` executions reaching
                          `max_consecutive_rollbacks` => DISABLE execution for
                          that game + send a critical alert. (No config change
                          will be attempted until a human re-enables it.)
  3. DATA CORRUPTION    -> restore the agent's DecisionStore from the latest
                          good checkpoint snapshot, then reload.

The Recovery Manager holds a reference to the RuntimeSupervisor (injected at
construction) but does NOT import it, so there is no module cycle.
"""
from __future__ import annotations

from typing import Optional

from monetization.executor.models import (
    EXEC_REJECTED, GATE_REJECTED, ExecutionResult, new_id,
)
from monetization.runtime.alerting import ALERT_CRITICAL, ALERT_WARNING, Alert
from monetization.runtime.event_logger import (
    EVENT_AGENT_CRASH, EVENT_AGENT_DEGRADED, EVENT_AGENT_RESTART,
    EVENT_EXECUTION_DISABLED, EVENT_STORE_CORRUPTED, EVENT_STORE_RESTORED,
    EventLogger,
)
from monetization.runtime.health import HealthMonitor


class DisabledExecutor:
    """Drop-in replacement for the real executor once execution is disabled.

    It refuses every request (no config change, no real API call) so a
    game stuck in a bad loop cannot keep mutating live config.
    """

    def execute(self, request) -> ExecutionResult:
        return ExecutionResult(
            execution_id=new_id(),
            status=EXEC_REJECTED,
            gate_verdict=GATE_REJECTED,
            decision_id=getattr(request, "decision_id", ""),
            strategy_type=getattr(request, "strategy_type", ""),
            error="execution_disabled_by_recovery",
            created_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
        )


class RecoveryManager:
    """Owns the automated recovery policies for the whole fleet."""

    def __init__(self, supervisor, alerts, events: EventLogger, config):
        self.supervisor = supervisor          # injected; not imported (no cycle)
        self.alerts = alerts
        self.events = events
        self.config = config

    # ------------------------------------------------------------------ #
    # Policy 1: Agent crash -> restart (bounded) -> else degrade
    # ------------------------------------------------------------------ #
    def on_crash(self, slug: str, error: BaseException) -> None:
        rt = self.supervisor.runtimes.get(slug)
        if rt is None:
            return
        rt.status = "crashed"
        self.events.log(EVENT_AGENT_CRASH, game=slug, level="critical",
                        error=str(error))
        self.alerts.send(Alert(ALERT_CRITICAL,
                               f"{slug} agent crashed: {error}", game=slug,
                               source="recovery"))

        if rt.restart_attempts < self.config.max_restart_attempts:
            rt.restart_attempts += 1
            self.supervisor.restart(slug)
            rt.status = "running"
            self.events.log(EVENT_AGENT_RESTART, game=slug, level="info",
                            attempt=rt.restart_attempts)
            self.alerts.send(Alert(ALERT_WARNING,
                                   f"{slug} agent restarted (attempt "
                                   f"{rt.restart_attempts})", game=slug,
                                   source="recovery"))
        else:
            rt.status = "degraded"
            self.events.log(EVENT_AGENT_DEGRADED, game=slug, level="critical",
                            attempts=rt.restart_attempts)
            self.alerts.send(Alert(ALERT_CRITICAL,
                                   f"{slug} agent DEGRADED after "
                                   f"{rt.restart_attempts} restart attempts; "
                                   f"isolated from fleet", game=slug,
                                   source="recovery"))

    # ------------------------------------------------------------------ #
    # Policy 2: Bad decision loop -> disable execution
    # ------------------------------------------------------------------ #
    def on_cycle(self, slug: str) -> None:
        rt = self.supervisor.runtimes.get(slug)
        if rt is None:
            return
        if rt.consecutive_rollbacks >= self.config.max_consecutive_rollbacks:
            if not rt.execution_disabled:
                self.disable_execution(slug)

    def disable_execution(self, slug: str) -> None:
        rt = self.supervisor.runtimes.get(slug)
        if rt is None:
            return
        rt.execution_disabled = True
        rt.agent.executor = DisabledExecutor()
        self.events.log(EVENT_EXECUTION_DISABLED, game=slug, level="critical",
                        consecutive_rollbacks=rt.consecutive_rollbacks)
        self.alerts.send(Alert(ALERT_CRITICAL,
                               f"{slug} execution DISABLED after "
                               f"{rt.consecutive_rollbacks} consecutive "
                               f"rollbacks", game=slug, source="recovery"))

    # ------------------------------------------------------------------ #
    # Policy 3: Data corruption -> restore store from checkpoint
    # ------------------------------------------------------------------ #
    def restore_from_checkpoint(self, slug: str) -> int:
        rt = self.supervisor.runtimes.get(slug)
        if rt is None:
            return 0
        self.events.log(EVENT_STORE_CORRUPTED, game=slug, level="critical")
        recovered = rt.checkpoint.restore_store(rt.agent)
        self.events.log(EVENT_STORE_RESTORED, game=slug, level="info",
                        records=recovered)
        self.alerts.send(Alert(ALERT_WARNING,
                               f"{slug} store restored from checkpoint "
                               f"({recovered} records)", game=slug,
                               source="recovery"))
        return recovered


__all__ = ["RecoveryManager", "DisabledExecutor"]
