"""E13.5 — Review Agent CLI (comment -> intelligence -> auto-reply).

Lean: argparse only, no server. Real review reads are READ-only and need no
unlock. The only real WRITE this agent can trigger is a single-review reply
(METADATA radius, the lowest-blast-radius write in the whole runtime), which
requires BOTH:
  * LAUNCHFORGE_AUTO_PUBLISH=1  (the auto-pilot gate)
  * an explicit --apply flag      (PRODUCTION writes are previewed otherwise)

Typical daily use (safe, reads only, classifies locally):
    python -m operation.publishing_factory.play_runtime.review_cli list com.x.app
    python -m operation.publishing_factory.play_runtime.review_cli run com.x.app

Actually post replies to new actionable reviews (needs real SA + proxy):
    python -m operation.publishing_factory.play_runtime.review_cli \
        run com.x.app --apply

Reply a single review (explicit text or auto-generated from classification):
    python -m operation.publishing_factory.play_runtime.review_cli \
        reply com.x.app <review_id> --auto --apply
"""
from __future__ import annotations

import argparse
import json
import sys

from monetization.providers.models import SandboxMode
from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.review_agent import (
    ReviewAgent, ReviewPolicy,
)


def _build_agent():
    conn = PlayConnector(sandbox=SandboxMode.PRODUCTION)
    agent = ReviewAgent(conn, policy=ReviewPolicy())
    return agent, conn


def _print_json(d):
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


def cmd_list(args):
    agent, _ = _build_agent()
    reps = agent.read_and_classify(args.package, max_results=args.max)
    if not reps:
        print("(no reviews read — check package ownership, or run with "
              "real SA + proxy)")
        return
    print(f"{'review_id':22} {'star':4} {'category':10} {'reply?':6} "
          f"recommended")
    for r in reps:
        preview = (r.recommended_reply or r.sentiment)[:52]
        print(f"{str(r.review_id)[:22]:22} "
              f"{str(r.star_rating or '-'):4} {r.category:10} "
              f"{'Y' if r.needs_reply else '-':6} {preview}")


def cmd_run(args):
    agent, _ = _build_agent()
    pkgs = args.packages or []
    out = agent.run_daily(pkgs, apply=args.apply, max_results=args.max)
    print(f"applied={out['applied']} skipped_seen={out['skipped_seen']} "
          f"failed={out['failed']} replied_total={out['replied_total']}")
    for pkg, agg in out["per_package"].items():
        print(f"  {pkg}: new={agg['new']} evaluated={agg['evaluated']} "
              f"needs_reply={agg['needs_reply']} posted={agg['posted']} "
              f"failed={agg['failed']}")
    for p in out["posted_this_run"]:
        print(f"  ✅ replied {p['review_id']} [{p['category']}]: "
              f"{p['reply_text'][:60]}")


def cmd_reply(args):
    agent, _ = _build_agent()
    text = args.text
    if args.auto:
        reps = agent.read_and_classify(args.package, max_results=args.max)
        match = next((r for r in reps
                      if str(r.review_id) == args.review_id), None)
        if not match:
            print(f"review_id {args.review_id} not found in latest read")
            return
        text = match.recommended_reply
        if not text:
            print(f"review classified as '{match.category}' — "
                  f"no reply recommended")
            return
    if not text:
        print("need --text T or --auto")
        return
    res = agent.reply(args.package, args.review_id, text, apply=args.apply)
    _print_json(res.to_dict())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="review_cli",
                                 description="E13.5 Review Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="read + classify one package (read only)")
    p.add_argument("package")
    p.add_argument("--max", type=int, default=100)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("run", help="evaluate + (--apply) reply across packages")
    p.add_argument("packages", nargs="*")
    p.add_argument("--max", type=int, default=100)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("reply", help="reply to one review (gated write)")
    p.add_argument("package")
    p.add_argument("review_id")
    p.add_argument("--text", default="")
    p.add_argument("--auto", action="store_true",
                   help="use the agent's classified recommended reply")
    p.add_argument("--max", type=int, default=100)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_reply)

    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
