"""remix.py — THE single CLI entry for P04 Remix System V3.9.1.

All video production now goes through this one command. It routes through
RemixController -> unified VideoComposer -> FFmpegValidator (Quality Gate).

Usage:
    python remix.py --template bomb_15s --ratio 9X16 --count 100
    python remix.py --template story_40s --ratio 9X16 --count 20 --transition xfade
    python remix.py --template bomb_15s --ratio 9X16 --count 5 --subtitle --bgm bgm.mp3
"""
import argparse
import sys
from pathlib import Path

# make the creative_remix_engine package importable when run as a script
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from creative_remix_engine.production.remix_controller import RemixController


DEFAULT_SOURCE = "d:/project_slim/output/P04_remix_videos/广告视频"
DEFAULT_OUT = "d:/project_slim/output/P04_remix_videos/remix_output_v391"
DEFAULT_CSV = "d:/project_slim/project_slim/output/video_intelligence/p04/final_adjust_material_report.csv"


def main():
    ap = argparse.ArgumentParser(
        description="P04 Remix System V3.9.1 — single production entry (RemixController)"
    )
    ap.add_argument("--template", default="bomb_15s",
                    choices=["standard_30s", "bomb_15s", "story_40s"])
    ap.add_argument("--ratio", default="9X16", choices=["9X16", "1X1", "16X9"])
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--transition", default="concat", choices=["concat", "xfade"])
    ap.add_argument("--subtitle", action="store_true")
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--source-dir", default=DEFAULT_SOURCE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--adjust-csv", default=DEFAULT_CSV)
    args = ap.parse_args()

    print("=" * 64)
    print("P04 Remix System V3.9.1 — Production Hardening")
    print("=" * 64)
    print(f"template   : {args.template}")
    print(f"ratio      : {args.ratio}")
    print(f"count      : {args.count}")
    print(f"transition : {args.transition}")
    print(f"source     : {args.source_dir}")
    print(f"out        : {args.out}")
    print()

    ctrl = RemixController(args.source_dir, args.adjust_csv, args.out)
    print(f"indexed sources: {len(ctrl.sources)}")
    res = ctrl.generate(
        template=args.template,
        ratio=args.ratio,
        count=args.count,
        transition=args.transition,
        subtitle=args.subtitle,
        bgm=args.bgm,
    )
    s = res["summary"]
    print()
    print("-" * 64)
    print("GATE 1 SUMMARY")
    print("-" * 64)
    print(f"  requested        : {s['requested']}")
    print(f"  built (planned)  : {s['built']}")
    print(f"  rendered         : {s['rendered']}")
    print(f"  passed Gate 1    : {s['passed_gate1']}")
    print(f"  failed           : {s['failed']}")
    print(f"  pass rate        : {s['pass_rate'] * 100:.1f}%")
    print(f"  report           : {s['report_path']}")
    if s["failed"]:
        print()
        print("  FAILED (first 10):")
        for r in res["details"]:
            if not r.get("success"):
                print(f"    - {r['recipe_id']}: {r.get('error')}")
    print("=" * 64)


if __name__ == "__main__":
    main()
