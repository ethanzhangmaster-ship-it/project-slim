"""E13.5 — Health Agent CLI (Vitals monitor entry point).

Lean: argparse only, no server. Real Vitals reads are READ-only and need no
unlock. The only real WRITE this agent can trigger is a rollout halt
(RELEASE radius), which requires BOTH:
  * LAUNCHFORGE_AUTO_PUBLISH=1  (the auto-pilot gate)
  * an explicit --apply flag      (RELEASE radius is hard-gated; --apply
                                   alone is refused unless unlock_release)

Typical daily use (safe, reads only):
    python -m operation.publishing_factory.play_runtime.health_cli run

Actually halt a bad rollout (needs unlock + real SA + proxy):
    python -m operation.publishing_factory.play_runtime.health_cli \
        halt com.x.app --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.health_agent import (
    HealthAgent, HealthPolicy,
)
from monetization.providers.models import SandboxMode


def _build_agent():
    conn = PlayConnector(sandbox=SandboxMode.PRODUCTION)
    agent = HealthAgent(conn, policy=HealthPolicy())
    return agent, conn


def _print_json(d):
    import json
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


def cmd_evaluate(args):
    agent, _ = _build_agent()
    r = agent.evaluate(args.package)
    _print_json(r.to_dict())


def cmd_run(args):
    agent, _ = _build_agent()
    pkgs = args.packages or []
    out = agent.run_daily(pkgs, apply=args.apply,
                          window_days=args.window)
    for row in out:
        print(f"{row['package_name']:32} {row['recommendation']:10} "
              f"crash={row.get('crash_rate')} anr={row.get('anr_rate')} "
              f"-> {row['action_taken']}")


def cmd_halt(args):
    agent, conn = _build_agent()
    if args.apply:
        conn.unlock_release(
            args.package,
            token=os.environ.get("LAUNCHFORGE_RELEASE_UNLOCK"))
    res = agent.halt_if_critical(args.package, apply=args.apply)
    _print_json(res.to_dict())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="health_cli", description="E13.5 Health Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("evaluate", help="evaluate one package (read only)")
    p.add_argument("package")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("run", help="evaluate across packages; halt critical")
    p.add_argument("packages", nargs="*")
    p.add_argument("--window", type=int, default=7)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("halt", help="halt rollout if vitals violate a gate")
    p.add_argument("package")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_halt)

    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
