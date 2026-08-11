"""E13.5 — Tester Pool CLI.

Manage the persistent closed-testing tester pool and auto-invite it to apps.

Usage:
    python -m operation.publishing_factory.play_runtime.tester_pool_cli add EMAIL [--group G] [--name N] [--note T]
    python -m operation.publishing_factory.play_runtime.tester_pool_cli remove EMAIL
    python -m operation.publishing_factory.play_runtime.tester_pool_cli list
    python -m operation.publishing_factory.play_runtime.tester_pool_cli propose PKG
    python -m operation.publishing_factory.play_runtime.tester_pool_cli run PKG [PKG ...] [--apply]
    python -m operation.publishing_factory.play_runtime.tester_pool_cli summary

The pool is entered ONCE; `run` then invites it to every app, so you never
re-enter 12 emails per app. Invites are TESTERS-radius (3-gate): SIM prints a
plan, PROD requires `LAUNCHFORGE_AUTO_PUBLISH=1` + `--apply` + ownership.
"""
from __future__ import annotations

import argparse
import sys
from typing import List


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tester_pool_cli",
        description="E13.5 persistent closed-testing tester pool")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a tester to the pool")
    a.add_argument("email")
    a.add_argument("--group", action="append", default=[],
                   help="Google Group to attach (repeatable)")
    a.add_argument("--name", default="")
    a.add_argument("--note", default="")

    r = sub.add_parser("remove", help="remove a tester from the pool")
    r.add_argument("email")

    sub.add_parser("list", help="list the pool")

    pr = sub.add_parser("propose", help="show invite diff for a package")
    pr.add_argument("package")

    rn = sub.add_parser("run", help="auto-invite the pool to packages")
    rn.add_argument("packages", nargs="+")
    rn.add_argument("--apply", action="store_true",
                    help="actually invite (else SIM plan only)")

    sub.add_parser("summary", help="pool + last invite status")

    sub.add_parser("promotion",
                   help="show promotion-ready apps (pool>=12 AND 14d clock done)")
    return p


def _connector():
    # Lazily build the real gated connector only when network is needed.
    from operation.publishing_factory.play_runtime.connector import (
        PlayConnector)
    return PlayConnector()


def main(argv: List[str] = None) -> int:
    args = _build_parser().parse_args(argv)
    from operation.publishing_factory.play_runtime.tester_pool_agent import (
        TesterPoolAgent, MIN_POOL)

    if args.cmd == "add":
        res = TesterPoolAgent().add_tester(
            args.email, groups=args.group, name=args.name, note=args.note)
        if res.get("ok"):
            print(f"✅ added {res['email']}"
                  + (" (already in pool)" if res.get("already") else ""))
        else:
            print(f"❌ {res.get('error')}")
            return 1
        return 0

    if args.cmd == "remove":
        res = TesterPoolAgent().remove_tester(args.email)
        if res.get("ok"):
            print(f"🗑️ removed {res['email']}")
        else:
            print(f"❌ {res.get('error')}")
            return 1
        return 0

    if args.cmd == "list":
        pool = TesterPoolAgent().list_pool()
        print(f"pool size: {len(pool)} (min required for promotion: "
              f"{MIN_POOL})")
        for t in pool:
            tags = []
            if t.get("groups"):
                tags.append("groups=" + ",".join(t["groups"]))
            if t.get("name"):
                tags.append(t["name"])
            line = f"  • {t['email']}"
            if tags:
                line += "  (" + ", ".join(tags) + ")"
            print(line)
        return 0

    if args.cmd == "propose":
        ag = TesterPoolAgent(_connector())
        prop = ag.propose_invite(args.package)
        print(f"package: {prop['package_name']}")
        print(f"pool size: {prop['pool_size']}")
        print(f"already on track: {len(prop['already'])}")
        print(f"missing (would invite): {len(prop['missing'])}")
        for e in prop["missing"]:
            print(f"    + {e}")
        print(f"union to PUT (preserves existing): {len(prop['union_to_put'])}")
        print(f"short by {prop['short_by']} to reach {MIN_POOL}")
        return 0

    if args.cmd == "run":
        ag = TesterPoolAgent(_connector())
        out = ag.run_daily(args.packages, apply=args.apply)
        print(f"applied={out['applied']} pool={out['pool_size']} "
              f"meets_min={out['meets_minimum']}")
        for pkg, per in out["per_package"].items():
            if per["invited"]:
                print(f"  ✉️ {pkg}: invited {len(per['invited'])} "
                      f"-> {per['invited']}")
            elif per.get("error"):
                print(f"  ❌ {pkg}: {per['error']}")
            else:
                print(f"  ✔️ {pkg}: already complete "
                      f"(skipped {per['skipped']})")
        print(f"total missing={out['total_missing']} "
              f"total invited={out['total_invited']}")
        return 0

    if args.cmd == "summary":
        from operation.publishing_factory.play_runtime.tester_pool_agent \
            import summary as pool_summary
        s = pool_summary()
        pool_status = "OK" if s['meets_minimum'] else f"short by {s['short_by']}"
        print(f"pool size: {s['pool_size']} / min {s['min_required']} "
              f"-> {pool_status}")
        print(f"last run: {s['last_run'] or 'never'}")
        if s["per_package"]:
            print("per-app last invite:")
            for pkg, st in s["per_package"].items():
                print(f"  • {pkg}: ok={st.get('last_ok')} "
                      f"apply={st.get('last_apply')} "
                      f"missing={len(st.get('last_missing', []))}")
        return 0

    if args.cmd == "promotion":
        from operation.publishing_factory.play_runtime.tester_pool_agent \
            import promotion_readiness, render_promotion_markdown
        rep = promotion_readiness()
        print(f"pool: {rep['pool_size']}/{rep['min_required']} "
              f"-> {'OK' if rep['pool_ok'] else '不足'}")
        print(f"promote-ready: {rep['promote_count']}")
        for r in rep["apps"]:
            flag = "🚀" if r["can_promote"] else (
                "缺测试员" if not r["pool_ok"] else f"{r['days_remaining']}d")
            print(f"  {flag} {r['package_name']} "
                  f"(库存 {r['tester_count']}/{rep['min_required']}, "
                  f"14天钟 {r['days_running']}d)")
        print(render_promotion_markdown(rep))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
