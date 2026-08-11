"""E13.5 — Play Runtime unified CLI.

Thin argparse wrapper over ``runner.run_play_ops`` so the whole Play console
fleet sweep is one command (mirrors the other ``*_cli.py`` in this package).

Usage:
  PYTHONPATH=. python operation/publishing_factory/play_runtime/play_runtime_cli.py run
  PYTHONPATH=. python operation/publishing_factory/play_runtime/play_runtime_cli.py run --apply
  PYTHONPATH=. python operation/publishing_factory/play_runtime/play_runtime_cli.py run --packages com.a,com.b
"""
from __future__ import annotations

import argparse
import sys


def _cmd_run(args: argparse.Namespace) -> int:
    from operation.publishing_factory.play_runtime.runner import (
        run_play_ops, render_status_line)
    pkgs = (args.packages.split(",") if args.packages else None)
    s = run_play_ops(pkgs, apply=args.apply)
    print(render_status_line(s))
    for name, v in s["agents"].items():
        tag = "✅" if v["status"] == "OK" else "❌"
        print(f"  {tag} {name:12s} {v['status']:8s} "
              f"items={v.get('items', 0)} {v.get('seconds', 0)}s")
    if s["failures"]:
        for f in s["failures"]:
            print(f"   ⚠️ {f}")
    print(f"   log -> {s['path']}")
    return 0 if s["status"] == "OK" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="play_runtime_cli",
        description="E13.5 — Unified Play Runtime daily orchestrator")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run the full Play console fleet sweep")
    run.add_argument("--apply", action="store_true",
                     help="Attempt real execution (needs LAUNCHFORGE_AUTO_PUBLISH"
                          " + credentials + proxy on your machine)")
    run.add_argument("--packages", default=None,
                     help="Comma-separated package list (overrides catalog)")
    run.set_defaults(func=_cmd_run)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
