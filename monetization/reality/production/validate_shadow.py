"""
E14.7.1 — Shadow Mode Acceptance Test
=======================================

Validates the P04 Witch Merge reality connector in READ-ONLY shadow mode.

Acceptance criteria (per spec):
  P04 data loaded                  PASS
  Adjust Snapshot                  PASS
  Meta Creative Reality            PASS
  MAX Revenue Reality              PASS
  RealitySnapshot                  PASS
  DecisionTrace completeness       >95%
  Shadow-only mode                 100%
  Production API writes            0
  Report generated                 PASS

Lean: pure-Python, sample-backed, no real API keys needed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.reality.production.p04_connector import P04Connector, P04ShadowReport
from monetization.reality.production.shadow_validator import ShadowValidator

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


def main() -> int:
    global _passed, _failed
    print("E14.7.1 — P04 Witch Merge Shadow Mode Acceptance\n")

    module_dir = Path(__file__).resolve().parent
    sample = module_dir / "sample_data"
    game_profile = module_dir.parent.parent.parent / "games" / "p04_witch_merge.json"

    # resolve paths
    adjust_f = sample / "p04_adjust_sample.json"
    meta_f = sample / "p04_meta_sample.json"
    max_f = sample / "p04_max_sample.json"

    # verify data loaded
    adjust_loaded = adjust_f.exists()
    meta_loaded = meta_f.exists()
    max_loaded = max_f.exists()
    profile_loaded = game_profile.exists()

    print("=== 1. Data loading ===")
    check("P04 game profile loaded", profile_loaded)
    check("Adjust sample loaded", adjust_loaded)
    check("Meta sample loaded", meta_loaded)
    check("MAX sample loaded", max_loaded)

    if not all([adjust_loaded, meta_loaded, max_loaded, profile_loaded]):
        print("\n  Missing data files — aborting.")
        return 1

    # ------------------------------------------------------------------ #
    print("\n=== 2. Connector: read → normalize → detect → shadow agent ===")
    store_dir = str(Path(tempfile.mkdtemp(prefix="p04_shadow_")) / "stores")
    conn = P04Connector(
        game_profile_path=str(game_profile),
        adjust_path=str(adjust_f), meta_path=str(meta_f), max_path=str(max_f),
        store_dir=store_dir,
    )

    # build normalised snapshot
    snap = conn.normalizer.build(conn.game_id)
    check("RealitySnapshot generated", snap is not None)
    check("RealitySnapshot has segments",
          len(snap.segments) > 0, f"segments={len(snap.segments)}")
    check("RealitySnapshot has creatives",
          len(snap.creatives) > 0, f"creatives={len(snap.creatives)}")
    check("RealitySnapshot has MAX trends",
          len(snap.max_trends) > 0, f"trends={len(snap.max_trends)}")

    # detect opportunities
    opps = conn.detect_opportunities(snap)
    check("Opportunities detected from real data",
          len(opps) > 0, f"opportunities={len(opps)}")

    # showcase detected opportunities
    print("  --- detected opportunities ---")
    for o in opps:
        print(f"    [{o.type}] {o.id} platform={o.segment.get('platform','')} "
              f"severity={o.severity:.2f}")

    # ------------------------------------------------------------------ #
    print("\n=== 3. Shadow decision run ===")
    report = conn.run(day=0)
    check("Shadow agent produced actions",
          len(report.actions) > 0, f"actions={len(report.actions)}")
    for a in report.actions:
        check(f"  action [{a.action}] {a.strategy_type}: reason present",
              bool(a.reason),
              f"conf={a.confidence:.0%} status={a.result_status}")

    # ------------------------------------------------------------------ #
    print("\n=== 4. Shadow integrity checks ===")
    valid = ShadowValidator()
    result = valid.validate(
        report, adjust_loaded=adjust_loaded,
        meta_loaded=meta_loaded, max_loaded=max_loaded)
    for ck, cv in result["checks"].items():
        check(f"validator: {ck}", cv)
    complete_pct = result["decision_completeness_pct"]
    check(f"Decision completeness > 95%", complete_pct >= 95.0,
          f"{complete_pct:.0f}%")

    # zero-write verification
    check("Production API writes: 0",
          not report.real_api_called,
          f"calls={report.total_api_calls} real={report.real_api_called}")
    check("Shadow mode confirmed: 100%",
          report.mode == "shadow")

    # ------------------------------------------------------------------ #
    print("\n=== 5. Report generation ===")
    report_text = report.to_markdown("2026-07-23")
    out_dir = module_dir / "outputs"
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / "p04_daily_operation_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    check("P04 Daily Operation Report generated",
          report_path.exists(), f"path={report_path}")
    check("Report has TOP RISKS section",
          "TOP RISKS" in report_text)
    check("Report has SHADOW DECISIONS section",
          "SHADOW DECISIONS" in report_text)
    check("Report declares shadow mode",
          "no production writes" in report_text.lower())

    print(f"\n  Report: {report_path}")
    print(f"{'='*50}")
    print(report_text[:2000])

    print(f"\n=== RESULT: {_passed} passed, {_failed} failed ===")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
