"""
E15.1.2 — Growth source pipeline CLI
=====================================

Usage:
  python -m operation.factory_brain.growth_sources run
      Run mock + real (inert) sources, write data/market_opportunities.json,
      print the ranked discovery summary.

  python -m operation.factory_brain.growth_sources run --source mock
  python -m operation.factory_brain.growth_sources run --source real
  python -m operation.factory_brain.growth_sources run --dry-run
  python -m operation.factory_brain.growth_sources run --out /tmp/opps.json

  python -m operation.factory_brain.growth_sources brief
      Run discovery + render a weekly briefing card, write
      outputs/growth/<date>.md, and push it to Feishu (best-effort).
      Flags: --no-notify  --dry-run  --top-n N  --out-dir DIR
"""
from __future__ import annotations

import argparse
import sys

from .ingester import MarketOpportunityIngester, build_default_sources, build_pipeline_sources
from .mock_source import MockMarketSource
from .real_source import RealMarketSource
from .public_chart_source import AppleTopFreeSource
from operation.factory_brain.opportunity_intake import DEFAULT_DROPIN


def _build_sources(which: str):
    if which == "mock":
        return [MockMarketSource()]
    if which == "real":
        return [RealMarketSource()]
    if which in ("public", "chart"):
        return [AppleTopFreeSource()]
    if which == "all":
        return build_pipeline_sources()
    return build_default_sources()


def _cmd_run(args) -> int:
    sources = _build_sources(args.source)
    ing = MarketOpportunityIngester(sources, out_path=args.out)
    res = ing.run(dry_run=args.dry_run)

    print(f"\n=== Growth opportunity discovery ({args.source}) ===")
    for s in res["sources"]:
        print(f"  [{s['kind']:4}] {s['name']:<14} "
              f"configured={s['configured']}  fetched={s['count']}")
    print(f"\n  ranked {res['count']} opportunity(ies):")
    for i, o in enumerate(res["opportunities"], 1):  # type: ignore[union-attr]
        print(f"   {i:>2}. score={o['score']:.3f}  "
              f"{o['genre']:<8}/{o['theme']:<10}  {o['opportunity_id']}")
    if args.dry_run:
        print("\n  (dry-run: drop-in file NOT written)")
    else:
        print(f"\n  wrote -> {args.out}")
    return 0


def _cmd_brief(args) -> int:
    from .briefing import run as brief_run
    out = brief_run(notify=not args.no_notify,
                    dry_run=args.dry_run,
                    top_n=args.top_n,
                    out_dir=args.out_dir,
                    sources=build_pipeline_sources())
    print(f"\n=== Growth weekly briefing ===")
    print(f"  opportunities : {out['report']['count']}")
    print(f"  briefing file : {out['file']}")
    print(f"  feishu pushed : {out['notified']}"
          + (f"  (error: {out['notify_error']})" if out['notify_error'] else ""))
    print(f"  real_api_called: {out['real_api_called']}")
    if args.dry_run:
        print("  (dry-run: drop-in + briefing file NOT written)")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    p = argparse.ArgumentParser(
        prog="growth_sources",
        description="Run market-opportunity sources -> data/market_opportunities.json")
    sub = p.add_subparsers(dest="cmd", metavar="cmd")

    pr = sub.add_parser("run", help="discover + write drop-in file")
    pr.add_argument("--source", choices=["mock", "real", "public", "all"],
                    default="all", help="which source(s) to run")
    pr.add_argument("--dry-run", action="store_true",
                    help="compute but do NOT write the drop-in file")
    pr.add_argument("--out", default=DEFAULT_DROPIN,
                    help="drop-in output path")
    pr.set_defaults(func=_cmd_run)

    pb = sub.add_parser("brief", help="discover + weekly Feishu briefing card")
    pb.add_argument("--no-notify", action="store_true",
                    help="render + write md but do NOT push Feishu")
    pb.add_argument("--dry-run", action="store_true",
                    help="compute but write nothing")
    pb.add_argument("--top-n", type=int, default=5,
                    help="how many top opportunities to show")
    pb.add_argument("--out-dir", default="outputs/growth",
                    help="briefing markdown output dir")
    pb.set_defaults(func=_cmd_brief)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
