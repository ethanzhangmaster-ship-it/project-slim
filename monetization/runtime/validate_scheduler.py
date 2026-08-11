"""
E14.4.2 — Validation: Lean Scheduler (Game Runtime Pool)
=========================================================

Proves the orchestration layer drives the existing RuntimeSupervisor as a
service without re-implementing reliability:

  * daily cycle      — every managed game runs its decision loop
  * resource limit   — games processed in POOLS of max_concurrent_games
  * retry            — transient tick failure is retried (bounded)
  * restart          — a DEGRADED game is escalated to a full agent rebuild
  * shard            — scheduler manages only a SUBSET of slugs

Lean: pure-Python, stdlib only, reuses E14.2 supervisor + JSONL store.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.agent.game_config import GameConfig
from monetization.agent.registry import GameFactoryOS, GameRegistry
from monetization.runtime.scheduler import (
    SchedulerConfig, GameScheduler, default_make_opps,
)
from monetization.runtime.supervisor import (
    RuntimeConfig, RuntimeSupervisor, STATUS_DEGRADED, STATUS_RUNNING,
)

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


def build_fleet(n_games: int, base: str) -> GameFactoryOS:
    reg = GameRegistry()
    for i in range(n_games):
        reg.register(GameConfig(slug=f"game_{i:02d}",
                                display_name=f"Game {i:02d}"))
    # seed_memory_fn=None -> empty memory (a fresh game has no history)
    return GameFactoryOS(reg, base, seed_memory_fn=None)


def make_sup(n_games: int):
    base = Path(tempfile.mkdtemp(prefix="launchforge_sched_"))
    ckpt = base / "ckpt"
    os_ = build_fleet(n_games, str(base / "stores"))
    sup = RuntimeSupervisor(os_, str(ckpt), config=RuntimeConfig())
    sup.start()
    return sup


def main() -> int:
    print("E14.4.2 — Lean Scheduler validation\n")

    # ----------------------------------------------------------------- #
    # 1. Daily cycle: every managed game runs its loop
    # ----------------------------------------------------------------- #
    print("=== 1. Daily cycle (12 games) ===")
    sup = make_sup(12)
    sched = GameScheduler(sup, config=SchedulerConfig(
        max_concurrent_games=8, daily_cycles=1), make_opps=default_make_opps)
    rep = sched.run_daily(0)
    check("all 12 games managed", rep.total_games == 12,
          f"total={rep.total_games}")
    check("every game succeeded its daily tick",
          rep.ok == 12, f"ok={rep.ok}")
    check("no game failed", rep.failed == 0)
    check("every game advanced >=1 cycle",
          all(r.cycles_run >= 1 for r in rep.results))
    summ = sched.summary()
    check("scheduler summary: 12 running", summ["running"] == 12,
          f"running={summ['running']}")

    # ----------------------------------------------------------------- #
    # 2. Resource limit: games batched into POOLS of max_concurrent
    # ----------------------------------------------------------------- #
    print("\n=== 2. Resource limit (pool sizing, 12 games / pool=4) ===")
    sup2 = make_sup(12)
    sched2 = GameScheduler(sup2, config=SchedulerConfig(
        max_concurrent_games=4, daily_cycles=1), make_opps=default_make_opps)
    rep2 = sched2.run_daily(0)
    check("pools_used == ceil(12/4) == 3", rep2.pools_used == 3,
          f"pools={rep2.pools_used}")
    check("all 12 processed despite pool cap", rep2.ok == 12)
    check("managed summary reflects pool cap is a batch, not a cap on total",
          sched2.summary()["managed_games"] == 12)

    # ----------------------------------------------------------------- #
    # 3. Retry: transient tick failure is retried and recovers
    # ----------------------------------------------------------------- #
    print("\n=== 3. Retry on transient crash (game_00) ===")
    sup3 = make_sup(12)
    sched3 = GameScheduler(sup3, config=SchedulerConfig(
        max_concurrent_games=12, retry_attempts=3,
        retry_backoff_seconds=0.0), make_opps=default_make_opps)
    rt = sup3.runtimes["game_00"]
    cycles_before = rt.cycles_run
    rt.fault_once = True          # one injected crash, supervisor auto-restarts
    ok, retries, restarted = sched3._tick_with_retry("game_00", 1)
    check("transient failure retried to success", ok is True)
    check("retry counter incremented (>=1)", retries >= 1, f"retries={retries}")
    check("no full rebuild needed for transient fault",
          restarted is False)
    check("cycle advanced after retry",
          sup3.runtimes["game_00"].cycles_run > cycles_before)

    # ----------------------------------------------------------------- #
    # 4. Restart: a DEGRADED game is escalated to a full agent rebuild
    # ----------------------------------------------------------------- #
    print("\n=== 4. Restart escalation (simulated DEGRADED game_05) ===")
    sup4 = make_sup(12)
    sched4 = GameScheduler(sup4, config=SchedulerConfig(
        max_concurrent_games=12, retry_attempts=3),
        make_opps=default_make_opps)
    rt4 = sup4.runtimes["game_05"]
    rt4.status = STATUS_DEGRADED     # simulate exhausted supervisor budget
    rt4.cycles_run = 0
    ok4, retries4, restarted4 = sched4._tick_with_retry("game_05", 2)
    check("DEGRADED game escalated to full rebuild", restarted4 is True)
    check("rebuilt game tick succeeded", ok4 is True)
    check("rebuilt game is RUNNING again",
          sup4.runtimes["game_05"].status == STATUS_RUNNING)
    check("rebuilt game resumed cycles",
          sup4.runtimes["game_05"].cycles_run >= 1)

    # ----------------------------------------------------------------- #
    # 5. Shard: scheduler manages only a SUBSET of slugs
    # ----------------------------------------------------------------- #
    print("\n=== 5. Shard (only game_00 + game_03) ===")
    sup5 = make_sup(12)
    sched5 = GameScheduler(sup5, config=SchedulerConfig(
        max_concurrent_games=8), make_opps=default_make_opps,
        slugs=["game_00", "game_03"])
    before_other = sup5.runtimes["game_01"].cycles_run
    rep5 = sched5.run_daily(0)
    check("shard manages exactly 2 games", rep5.total_games == 2,
          f"total={rep5.total_games}")
    check("both sharded games ran", rep5.ok == 2)
    check("unmanaged game_01 untouched (cycle count unchanged)",
          sup5.runtimes["game_01"].cycles_run == before_other,
          f"before={before_other} after={sup5.runtimes['game_01'].cycles_run}")
    check("shard summary reports 2 managed", sched5.summary()["managed_games"] == 2)

    print(f"\n=== RESULT: {_passed} passed, {_failed} failed ===")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
