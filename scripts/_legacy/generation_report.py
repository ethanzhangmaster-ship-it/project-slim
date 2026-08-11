"""Phase 2.1.1: Generation Report — dashboard with full state machine.

Shows:
  - Status breakdown (PENDING, CLAIM, PROCESSING, RETRY, SUCCESS, FAILED)
  - Retry analysis (retry rate, avg retry count)
  - Cost & quality metrics
  - Recent task list

Usage:
    python scripts/generation_report.py
    python scripts/generation_report.py --db output/creative_analysis/generations.db
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.generation_store import GenerationStore

# Status display order
STATUS_ORDER = ["PENDING", "CLAIM", "PROCESSING", "RETRY", "SUCCESS", "FAILED"]


def main(db_path: str = "output/creative_analysis/generations.db") -> None:
    store = GenerationStore(db_path=db_path)
    stats = store.get_stats()
    retry = stats.get("retry_analysis", {})

    print("=" * 65)
    print("  LOVART GENERATION DASHBOARD")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print()
    print(f"  Database: {db_path}")
    print()

    # ── Summary ──
    print(f"  Total Tasks:     {stats['total']}")
    print(f"  Success:         {stats['success_count']}")
    print(f"  Failed:          {stats['failed_count']}")
    print(f"  ─────────────────────")
    print(f"  Success Rate:    {stats['success_rate']:.0f}%")
    print(f"  Avg Time:        {stats['avg_generation_time']:.1f}s")
    print(f"  Total Cost:      ${stats['total_cost']:.2f}")
    print(f"  Avg Quality:     {stats['avg_quality']:.0f}/100")
    print()

    # ── Status Breakdown ──
    by_status = stats.get("by_status", {})
    if by_status:
        print("  Status Breakdown:")
        for status in STATUS_ORDER:
            count = by_status.get(status, 0)
            if count > 0:
                bar = "█" * min(count, 40)
                print(f"    {status:<12} {count:>4}  {bar}")
        # Show any unknown statuses
        for status, count in sorted(by_status.items()):
            if status not in STATUS_ORDER:
                print(f"    {status:<12} {count:>4}")

    # ── Retry Analysis ──
    if retry:
        print()
        print("  Retry Analysis:")
        print(f"    Success after retry:  {retry.get('retried_success', 0)} tasks "
              f"({retry.get('retry_success_rate', 0):.0f}%)")
        print(f"    Average retry count:  {retry.get('avg_retry_count', 0)}")

    # ── Recent Tasks ──
    tasks = store.list_all(limit=20)
    if tasks:
        print()
        print(f"  Recent Tasks ({len(tasks)}):")
        print(f"  {'ID':<20} {'Creative':<28} {'Status':<12} {'Retry':>5} {'Time':>6} {'Cost':>6}")
        print(f"  {'─'*79}")
        for t in tasks[:20]:
            tid = t["id"][:18]
            cid = t["creative_id"][:26]
            status = t["status"]
            retries = t.get("retry_count", 0)
            gen_time = f"{t['generation_time']:.1f}s" if t["generation_time"] else "-"
            cost = f"${t['cost']:.2f}" if t["cost"] else "-"
            print(f"  {tid:<20} {cid:<28} {status:<12} {retries:>5} {gen_time:>6} {cost:>6}")

    # ── Failed Tasks ──
    failed = [t for t in tasks if t["status"] == "FAILED"]
    if failed:
        print()
        print(f"  Failed Tasks ({len(failed)}):")
        for t in failed[:5]:
            err = t.get("last_error") or t.get("error_message", "no error")
            print(f"    {t['id']}: {err[:80]}")

    # ── Stuck Tasks ──
    stuck = store.reset_stuck(max_minutes=10)
    if stuck > 0:
        print()
        print(f"  Reset {stuck} stuck task(s) back to PENDING")

    print()
    print("=" * 65)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Lovart Generation Dashboard")
    parser.add_argument("--db", default="output/creative_analysis/generations.db",
                        help="Path to SQLite database")
    args = parser.parse_args()
    main(db_path=args.db)