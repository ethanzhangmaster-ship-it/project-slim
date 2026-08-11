"""E13.5 — Listing Experiment Agent CLI (true ASO: listing A/B test).

Lean: argparse only, no server. Real experiment reads are READ-only and need
no unlock. Creating an experiment (METADATA radius, the lowest-blast-radius
ASO write) requires BOTH:
  * LAUNCHFORGE_AUTO_PUBLISH=1  (the auto-pilot gate)
  * an explicit --apply flag      (PRODUCTION writes are previewed otherwise)

Propose an ASO title test (safe, simulated until --apply):
    python -m operation.publishing_factory.play_runtime.experiment_cli \
        propose com.x.app --locale fil --title "Short OFW Title" --apply

List running experiments (read only):
    python -m operation.publishing_factory.play_runtime.experiment_cli \
        list com.x.app

Evaluate + recommend a winner across packages (read only):
    python -m operation.publishing_factory.play_runtime.experiment_cli \
        evaluate com.x.app com.y.app
"""
from __future__ import annotations

import argparse
import json
import sys

from monetization.providers.models import SandboxMode
from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.experiment_agent import (
    ListingExperimentAgent, ExperimentPolicy, ListingExperimentProposal,
)


def _build_agent():
    conn = PlayConnector(sandbox=SandboxMode.PRODUCTION)
    return ListingExperimentAgent(conn, policy=ExperimentPolicy()), conn


def _print_json(d):
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


def cmd_propose(args):
    agent, _ = _build_agent()
    res = agent.propose(
        args.package, name=args.name, locale=args.locale,
        variant_title=args.title, variant_short=args.short,
        variant_full=args.full, baseline_title=args.baseline_title,
        user_fraction=args.fraction, apply=args.apply)
    _print_json(res.to_dict())


def cmd_title_test(args):
    agent, _ = _build_agent()
    res = agent.propose_title_test(
        args.package, args.locale, args.title,
        name=args.name or None, baseline_title=args.baseline_title,
        apply=args.apply)
    _print_json(res.to_dict())


def cmd_list(args):
    agent, _ = _build_agent()
    exps = agent.read_results(args.package)
    if not exps:
        print("(no experiments read — check package ownership, or run with "
              "real SA + proxy)")
        return
    print(f"{'id':16} {'status':10} {'name':28} locale")
    for e in exps:
        eid = str(e.get("experimentId") or e.get("id"))[:16]
        variants = e.get("variants") or [{}]
        last = variants[-1] if variants else {}
        lang = (last.get("storeListing") or {}).get("languageCode") or "-"
        print(f"{eid:16} {str(e.get('status')):10} "
              f"{str(e.get('name'))[:28]:28} {lang}")


def cmd_evaluate(args):
    agent, _ = _build_agent()
    out = agent.run_daily(args.packages)
    _print_json(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="experiment_cli",
                                 description="E13.5 Listing Experiment Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("propose", help="propose/create a listing experiment")
    p.add_argument("package")
    p.add_argument("--name", required=True)
    p.add_argument("--locale", default="en-US")
    p.add_argument("--title", default=None)
    p.add_argument("--short", default=None)
    p.add_argument("--full", default=None)
    p.add_argument("--baseline-title", default=None)
    p.add_argument("--fraction", type=float, default=0.1)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("title-test",
                       help="ASO helper: test a new listing title for a locale")
    p.add_argument("package")
    p.add_argument("locale")
    p.add_argument("title")
    p.add_argument("--name", default=None)
    p.add_argument("--baseline-title", default=None)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_title_test)

    p = sub.add_parser("list", help="read experiments for one package (read only)")
    p.add_argument("package")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("evaluate",
                       help="read + recommend winners across packages")
    p.add_argument("packages", nargs="*")
    p.set_defaults(func=cmd_evaluate)

    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
