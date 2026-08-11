#!/usr/bin/env python3
"""
E14.4.1 — Lean Container Worker entrypoint
===========================================

Wires the GameFactory OS into a runnable service and drives it via the
Lean Scheduler (E14.4.2). Runs identically:

    * inside the Docker container (ENTRYPOINT), and
    * directly on the host with plain `python deploy/worker.py` (so it is
      verifiable without Docker in this sandbox).

Design (Lean, per the E13.x->E14.3 architecture principle):
    * pure-Python orchestrator, NO FastAPI / Postgres / Redis / S3
    * JSONL DecisionStore on a mounted volume = the only state
    * credentials mounted read-only from a secret volume; per-game isolation
      is enforced by CredentialResolver (E14.3.5)
    * a container handles a SHARD of games (GAMES=...) so 50 games scale
      horizontally across N workers, each still isolated

Env / CLI (both accepted):
    GAMES_DIR / --games-dir        dir of game_*.json configs (else synthetic)
    N_GAMES / --n-games            synthetic game count when no config dir
    STORE_DIR / --store-dir        JSONL store root (volume)
    CHECKPOINT_DIR / --checkpoint-dir
    CREDENTIALS_DIR / --credentials-dir   secret volume (optional)
    GAMES / --games                shard: comma list of slugs (optional)
    MAX_CONCURRENT / --max-concurrent   scheduler pool size (resource limit)
    DAILY_CYCLES / --daily-cycles      cycles per game per day
    ONCE / --once                  run ONE daily cycle then exit (smoke/test)
    INTERVAL_SECONDS / --interval  seconds between daily cycles (forever mode)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

# launchforge/ is the import root for `monetization`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.agent.game_config import GameConfig  # noqa: E402
from monetization.agent.registry import GameFactoryOS, GameRegistry  # noqa: E402
from monetization.providers.credential_resolver import (  # noqa: E402
    CredentialResolver,
)
from monetization.runtime.alerting import MockAlertProvider  # noqa: E402
from monetization.runtime.event_logger import EventLogger  # noqa: E402
from monetization.runtime.scheduler import (  # noqa: E402
    SchedulerConfig, GameScheduler, default_make_opps,
)
from monetization.runtime.supervisor import (  # noqa: E402
    RuntimeConfig, RuntimeSupervisor,
)


def build_os(games_dir: str, n_games: int, base_store_dir: str) -> GameFactoryOS:
    """Build the fleet. Prefer a mounted games/ config dir; else synthetic."""
    reg = GameRegistry()
    loaded = 0
    if games_dir and Path(games_dir).is_dir():
        loaded = reg.load_from_dir(games_dir)
    if loaded == 0:
        for i in range(n_games):
            reg.register(GameConfig(slug=f"game_{i:02d}",
                                    display_name=f"Game {i:02d}"))
    # seed_memory_fn=None -> a fresh game starts with no history (real state)
    return GameFactoryOS(reg, base_store_dir, seed_memory_fn=None)


def parse_args() -> argparse.Namespace:
    def env(name, default):
        v = os.environ.get(name, "")
        return v if v != "" else default

    ap = argparse.ArgumentParser(description="LaunchForge Lean Worker")
    ap.add_argument("--games-dir", default=env("GAMES_DIR", ""))
    ap.add_argument("--n-games", type=int, default=int(env("N_GAMES", "12")))
    ap.add_argument("--store-dir",
                    default=env("STORE_DIR", "/app/data/stores"))
    ap.add_argument("--checkpoint-dir",
                    default=env("CHECKPOINT_DIR", "/app/data/checkpoints"))
    ap.add_argument("--credentials-dir", default=env("CREDENTIALS_DIR", ""))
    ap.add_argument("--games", default=env("GAMES", ""))
    ap.add_argument("--max-concurrent", type=int,
                    default=int(env("MAX_CONCURRENT", "8")))
    ap.add_argument("--daily-cycles", type=int,
                    default=int(env("DAILY_CYCLES", "1")))
    ap.add_argument("--once", action="store_true",
                    default=bool(env("ONCE", "")))
    ap.add_argument("--interval", type=int,
                    default=int(env("INTERVAL_SECONDS", "86400")))
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    os_ = build_os(args.games_dir, args.n_games, args.store_dir)

    # ---- shard selection (horizontal scaling across workers) ----
    slugs: list = None
    if args.games:
        wanted = [s.strip() for s in args.games.split(",") if s.strip()]
        slugs = [s for s in wanted if s in os_.agents]
        if not slugs:
            print(f"[warn] GAMES={args.games} matched no known game; "
                  f"running all {len(os_.agents)}", file=sys.stderr)
            slugs = None

    # ---- optional per-game credential isolation (E14.3.5) ----
    cred_resolver = None
    if args.credentials_dir and Path(args.credentials_dir).is_dir():
        cred_resolver = CredentialResolver(args.credentials_dir)

    sup = RuntimeSupervisor(
        os_, args.checkpoint_dir, config=RuntimeConfig(),
        credential_resolver=cred_resolver)
    sup.start()

    sched = GameScheduler(
        sup,
        config=SchedulerConfig(
            max_concurrent_games=args.max_concurrent,
            daily_cycles=args.daily_cycles),
        make_opps=default_make_opps,
        slugs=slugs,
    )

    print(f"[worker] fleet={len(os_.agents)} managed={len(sched.slugs)} "
          f"pool={args.max_concurrent} creds={'on' if cred_resolver else 'off'} "
          f"mode={'once' if args.once else 'forever'}", flush=True)

    # ---- graceful shutdown ----
    stop = {"flag": False}

    def _handler(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

    try:
        if args.once:
            rep = sched.run_daily(0)
            print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2),
                  flush=True)
            return 0
        cycles = sched.run_forever(
            interval_seconds=args.interval, start_day=0, stop_flag=lambda: stop["flag"])
        print(f"[worker] stopped cleanly after {cycles} daily cycle(s)",
              flush=True)
        return 0
    except Exception as e:  # never crash the container silently
        print(f"[worker] FATAL: {e}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
