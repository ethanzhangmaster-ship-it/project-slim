"""
P3-auto — Local runner for the REAL Google Play auto-pilot closed loop.

WHY LOCAL ONLY
==============
The sandbox is GFW-blocked and cannot reach androidpublisher.googleapis.com.
You MUST run this on your own machine (Windows/Mac/Linux) where the
network egress to Google works (and the proxy env is set if needed).

SAFETY
======
* Requires LAUNCHFORGE_AUTO_PUBLISH=1 — without it the script refuses to
  run (the three-gate policy stays intact by default).
* Only games/apps with a VERIFIED package_name are touched. Empty / fake
  package names are skipped — no blind app creation.
* Before any write it verifies the package is owned by THIS service
  account (real READ). If not, it refuses.
* Only listing metadata (title / description) is written — the
  lowest-blast-radius change. No app creation, no build upload.
* Default is DRY-RUN (reads + shows what WOULD be written, writes nothing).
  Use --apply to actually push.

TWO MODES
=========
1) Fleet auto-pilot (no --game):
     LAUNCHFORGE_AUTO_PUBLISH=1 python -m operation.publishing_factory.run_auto_pilot
   Scans the whole fleet, auto-approves recommended plans, pushes the
   ones with a verified package_name. (Most catalog games have no real
   package yet, so they are skipped.)

2) Operator-directed single app (--game <pkg>):
     # prove the Edits API + service account can SEE the app (no write):
     LAUNCHFORGE_AUTO_PUBLISH=1 python -m operation.publishing_factory.run_auto_pilot --game com.ofwsalary.ofwcalculator --verify

     # push a localized listing from a JSON file (one locale per run):
     #   data/ofw_calculator_listings.json = {"en-US": {...}, "fil": {...}, "ar": {...}}
     # show what WOULD be pushed (ownership verified, no write):
     LAUNCHFORGE_AUTO_PUBLISH=1 python -m operation.publishing_factory.run_auto_pilot --game com.ofwsalary.ofwcalculator --meta-file data/ofw_calculator_listings.json --locale en-US

     # push the Filipino listing for real:
     LAUNCHFORGE_AUTO_PUBLISH=1 python -m operation.publishing_factory.run_auto_pilot --game com.ofwsalary.ofwcalculator --meta-file data/ofw_calculator_listings.json --locale fil --apply

     # or push ad-hoc copy without a file:
     LAUNCHFORGE_AUTO_PUBLISH=1 python -m operation.publishing_factory.run_auto_pilot --game com.ofwsalary.ofwcalculator --title "..." --short "..." --full "..." --apply
"""
from __future__ import annotations

import argparse
import json
import sys

from monetization.providers.models import SandboxMode

from operation.publishing_factory.auto_pilot import auto_pilot_enabled
from operation.publishing_factory.batch_orchestrator import BatchOrchestrator
from operation.publishing_factory.catalog.game_registry import GameRegistry


def _print_status(st: dict) -> None:
    # Persist full status to a file (utf-8) so the diagnosis is never
    # lost to a console-encoding crash on Windows (cp1252 cannot encode
    # CJK, which would raise UnicodeEncodeError mid-print).
    try:
        with open("last_push_status.json", "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass
    # ASCII-safe summary line ALWAYS prints, even if CJK can't encode:
    print(">>> RESULT: ok=%s stage=%s http_status=%s"
          % (st.get("ok"), st.get("stage"), st.get("http_status")),
          flush=True)
    # Full JSON — fall back to escaped ASCII if the console can't encode CJK.
    text = json.dumps(st, ensure_ascii=False, indent=2)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(json.dumps(st, ensure_ascii=True, indent=2), flush=True)
    if st.get("stage") == "ownership" and not st.get("ok"):
        sc = st.get("http_status")
        diag = st.get("diagnosis", "")
        print("", flush=True)
        if sc is not None:
            print(f">>> HTTP {sc}", flush=True)
        try:
            print(f">>> DIAGNOSIS: {diag}", flush=True)
        except UnicodeEncodeError:
            print(">>> DIAGNOSIS (ascii-only): " +
                  diag.encode("ascii", "ignore").decode("ascii"), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Real Google Play auto-pilot closed loop (local runner).")
    ap.add_argument("--game", default=None,
                    help="target ONE game_id / package_name (operator mode)")
    ap.add_argument("--title", default=None, help="listing title to push")
    ap.add_argument("--short", default=None, help="short description to push")
    ap.add_argument("--full", default=None, help="full description to push")
    ap.add_argument("--apply", action="store_true",
                    help="actually write to Play Console (default: dry-run)")
    ap.add_argument("--verify", action="store_true",
                    help="only verify ownership (real READ), write nothing")
    ap.add_argument("--locale", default="en-US",
                    help="listing locale BCP-47 code (en-US, fil, ar, ...) "
                         "for the metadata write")
    ap.add_argument("--meta-file", default=None,
                    help="path to a JSON file with localized listings, "
                         "e.g. {\"en-US\": {...}, \"fil\": {...}, \"ar\": "
                         "{...}}; the --locale entry is used (top-level "
                         "fields used as fallback). Overrides --title/--short/--full.")
    args = ap.parse_args()

    if not auto_pilot_enabled():
        print("ERROR: LAUNCHFORGE_AUTO_PUBLISH=1 is not set. "
              "Refusing to run (safety gate).")
        return 2

    registry = GameRegistry().load()
    orch = BatchOrchestrator(
        registry, sandbox=SandboxMode.PRODUCTION, auto_pilot=True)

    # ---- operator-directed single app ----
    if args.game:
        if args.game not in registry.ids():
            print(f"ERROR: '{args.game}' not found in registry. "
                  f"Available ids are the package_names in data/catalog.json.")
            return 2
        # resolve metadata: --meta-file (by --locale) takes precedence,
        # otherwise individual --title/--short/--full flags.
        meta = {
            "title": args.title,
            "short_description": args.short,
            "full_description": args.full,
        }
        if args.meta_file:
            try:
                with open(args.meta_file, "r", encoding="utf-8") as fh:
                    blob = json.load(fh)
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR: cannot read --meta-file "
                      f"{args.meta_file}: {exc}")
                return 2
            entry = blob.get(args.locale) or {
                k: blob[k] for k in ("title", "short_description",
                                     "full_description") if k in blob
            }
            if not entry:
                print(f"ERROR: --meta-file has no entry for locale "
                      f"'{args.locale}' and no top-level fields.")
                return 2
            meta = {
                "title": entry.get("title"),
                "short_description": entry.get("short_description"),
                "full_description": entry.get("full_description"),
            }
        has_meta = any(meta.values())
        dry_run = not args.apply
        if args.verify or (dry_run and not has_meta):
            mode = "VERIFY-ONLY (ownership READ, no write)"
        elif dry_run:
            mode = "DRY-RUN (ownership READ + show payload, no write)"
        else:
            mode = "APPLY (real listing WRITE)"
        print("=" * 64)
        print(f"Google Play auto-pilot  |  mode: {mode}")
        print(f"  target         = {args.game}")
        print(f"  locale         = {args.locale}")
        print("-" * 64)
        st = orch.push_single(args.game, meta, dry_run=dry_run,
                              locale=args.locale)
        _print_status(st)
        return 0

    # ---- fleet auto-pilot ----
    report = orch.run_daily()
    mode = "APPLY (real writes)" if args.apply else "DRY-RUN (reads only)"
    print("=" * 64)
    print(f"Google Play auto-pilot  |  mode: {mode}")
    print(f"  sandbox        = {report.sandbox}")
    print(f"  scanned        = {report.scanned}")
    print(f"  recommended    = {report.recommended_count}")
    print(f"  executed/would = {report.executed}")
    print("-" * 64)
    for n in report.notes:
        print("  -", n)
    if not args.apply:
        print("-" * 64)
        print("This was a DRY-RUN. Re-run with --apply to push to Play Console.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
