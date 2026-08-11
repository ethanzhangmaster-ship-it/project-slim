"""
E14.2 — Validation: Production Runtime Layer
============================================

Proves the GameFactory OS can run as a long-lived, fault-tolerant service
rather than a one-shot script. Four reliability guarantees are exercised
against a 10-game fleet under a 1000-cycle soak:

  Case 1  Agent crash            -> detected, restarted, resumes.
  Case 2  DecisionStore corrupt  -> restored from latest checkpoint.
  Case 3  Consecutive failed exec -> execution disabled + alert sent.
  Case 4  Single game crash-loop -> all other games UNaffected.

Also asserts the soak itself is crash-free (no game ends degraded/crashed
without an injected fault) and that structured events + alerts were emitted.

Lean: pure-Python, stdlib only, no LLM / no external API / no real backend.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.agent.game_config import GameConfig
from monetization.agent.models import Opportunity
from monetization.agent.registry import GameFactoryOS, GameRegistry
from monetization.agent.validate_agent import seed_memory
from monetization.executor.models import EXEC_ROLLED_BACK, ExecutionResult, new_id
from monetization.runtime.alerting import ALERT_CRITICAL, Alert, MockAlertProvider
from monetization.runtime.event_logger import EventLogger
from monetization.runtime.supervisor import (
    RuntimeConfig, RuntimeSupervisor, STATUS_DEGRADED, STATUS_RUNNING,
)

OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
CKPT = OUT / "checkpoints"
CKPT.mkdir(parents=True, exist_ok=True)
EVENTS_PATH = OUT / "runtime_events.jsonl"

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
# Fleet fixtures
# --------------------------------------------------------------------------- #
def seed_fn():
    """Each game gets its OWN copy of the shared synthetic memory."""
    return list(seed_memory().all())


def build_fleet(n_games: int = 10) -> GameFactoryOS:
    reg = GameRegistry()
    for i in range(n_games):
        reg.register(GameConfig(
            slug=f"game_{i:02d}", display_name=f"Game {i:02d}"))
    base = Path(tempfile.mkdtemp(prefix="launchforge_rt_"))
    return GameFactoryOS(reg, str(base), seed_memory_fn=seed_fn)


def make_opps(slug: str, day: int) -> List[Opportunity]:
    """One opportunity per cycle — enough to exercise the loop, fast for soaks."""
    return [Opportunity(
        id=f"{slug}:c{day:04d}", type="ecpm_drop",
        segment={"country": "US", "platform": "android",
                 "ad_format": "reward", "network": "applovin"},
        metrics={"ecpm": 9.0}, severity=0.8)]


class FailingExecutor:
    """Duck-typed executor that ALWAYS rolls back (Case 3 driver)."""
    def execute(self, request) -> ExecutionResult:
        return ExecutionResult(
            execution_id=new_id(),
            status=EXEC_ROLLED_BACK,
            gate_verdict="approved",
            decision_id=getattr(request, "decision_id", ""),
            strategy_type=getattr(request, "strategy_type", ""),
            error="simulated_provider_failure",
            created_at=datetime.now(timezone.utc).isoformat(),
        )


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> int:
    print("E14.2 — Production Runtime Layer validation\n")

    os_ = build_fleet(10)
    check("fleet built (10 isolated agents)",
          len(os_.agents) == 10, f"agents={sorted(os_.agents)[:3]}...")

    alerts = MockAlertProvider()
    events = EventLogger(path=str(EVENTS_PATH))
    config = RuntimeConfig()
    sup = RuntimeSupervisor(
        os_, str(CKPT), alert_provider=alerts, events=events, config=config)
    sup.start()

    # ----------------------------------------------------------------- #
    # Soak: 1000 cycles across the fleet (crash-free baseline)
    # ----------------------------------------------------------------- #
    print("\n=== Soak: 1000 cycles across 10 games ===")
    sup.run_soak(1000, make_opps)
    summary = sup.summary()
    print(f"  summary: {summary['total_cycles']} cycles, "
          f"running={summary['running']}, degraded={summary['degraded']}, "
          f"events={summary['events_logged']}, alerts={summary['alerts_sent']}")
    check("soak completed 1000 cycles", summary["total_cycles"] == 1000,
          f"{summary['total_cycles']}")
    check("no game degraded during clean soak",
          summary["degraded"] == 0)
    check("every game ran cycles during soak",
          all(s["cycles_run"] > 0 for s in summary["status"]))
    check("structured events were emitted", summary["events_logged"] > 0)
    check("checkpoints written (store snapshots exist)",
          any(CKPT.glob("game_00/store_*.jsonl")))

    # ----------------------------------------------------------------- #
    # Case 1: Agent crash -> detect -> restart -> resume
    # ----------------------------------------------------------------- #
    print("\n=== Case 1: transient agent crash (game_00) ===")
    alerts_before = alerts.count()
    rt = sup.runtimes["game_00"]
    cycles_before = rt.cycles_run
    rt.fault_once = True
    res = sup.tick_one("game_00", make_opps("game_00", 9999))
    check("crash detected (tick returned None)", res is None)
    check("alert emitted for crash", alerts.count() > alerts_before)
    check("agent auto-restarted (running)", rt.status == STATUS_RUNNING)
    check("restart attempt recorded", rt.restart_attempts == 1,
          f"attempts={rt.restart_attempts}")
    # resume: next tick must succeed
    res2 = sup.tick_one("game_00", make_opps("game_00", 10000))
    check("agent resumed after restart", res2 is not None)
    check("cycle count advanced after resume",
          rt.cycles_run > cycles_before)

    # ----------------------------------------------------------------- #
    # Case 2: DecisionStore corruption -> restore from checkpoint
    # ----------------------------------------------------------------- #
    print("\n=== Case 2: DecisionStore corruption (game_01) ===")
    rt = sup.runtimes["game_01"]
    store_path = rt.agent.store.path
    records_before = rt.agent.store.count()
    # corrupt the live store file
    store_path.write_text("{ this is : not : valid json ", encoding="utf-8")
    rt.agent.store.load()  # now loads 0 valid records
    check("corruption drops live record count", rt.agent.store.count() == 0,
          f"count={rt.agent.store.count()}")
    recovered = sup.recovery.restore_from_checkpoint("game_01")
    check("store restored from checkpoint", recovered > 0,
          f"recovered={recovered}")
    check("restored record count close to pre-corruption",
          abs(recovered - records_before) <= 5,
          f"recovered={recovered} before={records_before}")
    check("restore event logged",
          any(e.event == "store_restored" for e in events.recent(500)))

    # ----------------------------------------------------------------- #
    # Case 3: consecutive failed executions -> disable + alert
    # ----------------------------------------------------------------- #
    print("\n=== Case 3: consecutive execution failures (game_02) ===")
    rt = sup.runtimes["game_02"]
    rt.agent.executor = FailingExecutor()   # every execute rolls back
    alerts_before = alerts.count()
    disabled_alert = False
    for k in range(config.max_consecutive_rollbacks + 2):
        sup.tick_one("game_02", make_opps("game_02", 20000 + k))
        if rt.execution_disabled:
            disabled_alert = any(
                a.level == ALERT_CRITICAL and "DISABLED" in a.message
                for a in alerts.sent)
            break
    check("execution auto-disabled after consecutive failures",
          rt.execution_disabled is True)
    check("critical alert sent on disable", disabled_alert)
    check("consecutive-rollback counter reached threshold",
          rt.consecutive_rollbacks >= config.max_consecutive_rollbacks,
          f"count={rt.consecutive_rollbacks}")
    # after disable, no execute should actually succeed
    exec_after = sup.tick_one("game_02", make_opps("game_02", 29999))
    if exec_after is not None:
        did_exec = any(a.action == "execute" and a.result_status == "executed"
                       for a in exec_after.actions)
        check("no real execution after disable", not did_exec)
    else:
        check("no real execution after disable", True,
              "cycle skipped (degraded)")

    # ----------------------------------------------------------------- #
    # Case 4: single game crash-loop -> others unaffected
    # ----------------------------------------------------------------- #
    print("\n=== Case 4: single-game crash-loop (game_03) vs rest ===")
    rt = sup.runtimes["game_03"]
    rt.fault_always = True
    others_before = {s: sup.runtimes[s].cycles_run
                     for s in sup.runtimes if s != "game_03"}
    for _ in range(30):
        opps = {s: make_opps(s, 30000 + _) for s in sup.runtimes}
        sup.tick_all(opps, day=30000 + _)
    # game_03 should be degraded (exhausted restart budget)
    check("crash-loop game ended DEGRADED (isolated)",
          rt.status == STATUS_DEGRADED, f"status={rt.status}")
    check("crash-loop game exhausted restart attempts",
          rt.restart_attempts == config.max_restart_attempts,
          f"attempts={rt.restart_attempts}")
    # every OTHER game kept running and kept accumulating cycles
    others_ok = all(
        sup.runtimes[s].status == STATUS_RUNNING
        and sup.runtimes[s].cycles_run > others_before[s]
        for s in sup.runtimes if s != "game_03")
    check("all other 9 games UNaffected (running + progressed)",
          others_ok)
    others_crashed = any(
        sup.runtimes[s].status in ("crashed", "degraded")
        for s in sup.runtimes if s != "game_03")
    check("no other game was dragged into crash/degraded",
          not others_crashed)

    # ----------------------------------------------------------------- #
    # Persist machine-readable report
    # ----------------------------------------------------------------- #
    report = {
        "soak_cycles": summary["total_cycles"],
        "games": summary["games"],
        "degraded_during_clean_soak": summary["degraded"],
        "total_events": events.count(),
        "total_alerts": alerts.count(),
        "critical_alerts": len(alerts.by_level(ALERT_CRITICAL)),
        "case1": {"game_00_status": sup.runtimes["game_00"].status,
                  "restart_attempts": sup.runtimes["game_00"].restart_attempts},
        "case2": {"game_01_recovered": recovered},
        "case3": {"game_02_disabled": sup.runtimes["game_02"].execution_disabled},
        "case4": {"game_03_status": sup.runtimes["game_03"].status,
                  "others_unaffected": others_ok},
    }
    (OUT / "runtime_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== RESULT: {_passed} passed, {_failed} failed ===")
    print(f"Report written to: {OUT / 'runtime_report.json'}")
    print(f"Events written to: {EVENTS_PATH}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
