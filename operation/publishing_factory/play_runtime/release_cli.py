"""E13.5 — Release Agent CLI (staged rollout controller entry point).

Lean: argparse only, no server. Real writes require BOTH:
  * LAUNCHFORGE_AUTO_PUBLISH=1  (the auto-pilot gate)
  * an explicit --apply flag      (RELEASE radius is hard-gated; --apply
                                   alone is refused unless unlock_release)

Typical daily use (safe, no write):
    python -m operation.publishing_factory.play_runtime.release_cli daily

Actually advance (needs unlock + real SA + proxy):
    python -m operation.publishing_factory.play_runtime.release_cli \
        advance com.x.app --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.release_agent import (
    ReleaseAgent, ReleasePolicy,
)
from monetization.providers.models import SandboxMode


def _build_agent(packages=None):
    conn = PlayConnector(sandbox=SandboxMode.PRODUCTION)
    # RELEASE radius: require explicit unlock to even consider a write.
    agent = ReleaseAgent(conn, policy=ReleasePolicy())
    return agent, conn


def _print_json(d):
    import json
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


def cmd_evaluate(args):
    agent, _ = _build_agent()
    d = agent.evaluate(args.package)
    _print_json(d)


def cmd_advance(args):
    agent, conn = _build_agent()
    if args.apply:
        conn.unlock_release(
            args.package,
            token=os.environ.get("LAUNCHFORGE_RELEASE_UNLOCK"))
    res = agent.advance(args.package, apply=args.apply)
    _print_json(res.to_dict())


def cmd_halt(args):
    agent, conn = _build_agent()
    if args.apply:
        conn.unlock_release(
            args.package,
            token=os.environ.get("LAUNCHFORGE_RELEASE_UNLOCK"))
    res = agent.halt(args.package, apply=args.apply)
    _print_json(res.to_dict())


def cmd_daily(args):
    agent, conn = _build_agent()
    if args.apply:
        # multi-package sweep: global unlock, still dual-factor via token
        conn.unlock_release(
            token=os.environ.get("LAUNCHFORGE_RELEASE_UNLOCK"))
    pkgs = args.packages or []
    out = agent.run_daily(pkgs, apply=args.apply,
                          now=datetime.now(timezone.utc))
    for row in out:
        print(f"{row['package']:32} {row['recommendation']:14} "
              f"-> {row['action_taken']}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="release_cli", description="E13.5 Release Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("evaluate", help="decide next action (no write)")
    p.add_argument("package")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("advance", help="advance one stage (needs --apply)")
    p.add_argument("package")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_advance)

    p = sub.add_parser("halt", help="halt rollout (needs --apply)")
    p.add_argument("package")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_halt)

    p = sub.add_parser("daily", help="evaluate/act across packages")
    p.add_argument("packages", nargs="*")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_daily)

    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
