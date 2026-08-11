"""CLI V3.3"""
import argparse

from .core.remix_engine import RemixEngine
from .config import RECIPE_DIR, OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(description="Creative Remix Engine V3.3 — AI Creative Factory")
    parser.add_argument("--game", default="P04")
    parser.add_argument("--template", default="bomb_15s", choices=["standard_30s", "bomb_15s", "story_40s"])
    parser.add_argument("--ratio", default="9X16", choices=["9X16", "1X1", "16X9"])
    parser.add_argument("--count", type=int, default=300, help="生成数量")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--no-video", action="store_true")
    parser.add_argument("--platform", default="facebook", choices=["facebook", "tiktok"])
    parser.add_argument("--objective", default="purchase", choices=["purchase", "install", "click"])

    args = parser.parse_args()

    print("=" * 70)
    print("Creative Remix Engine V3.3 — AI Creative Intelligence Factory")
    print("=" * 70)
    print(f"Game:     {args.game}")
    print(f"Template: {args.template}")
    print(f"Ratio:    {args.ratio}")
    print(f"Count:    {args.count}")
    print(f"Platform: {args.platform}")
    print(f"Objective:{args.objective}")
    print()

    engine = RemixEngine(game_code=args.game)

    if args.train:
        engine.train_models()

    result = engine.generate(
        template=args.template,
        target_ratio=args.ratio,
        count=args.count,
        build_video=not args.no_video,
    )

    # 输出
    print("\n" + "=" * 70)
    print("V3.3 RESULT")
    print("=" * 70)
    print(f"Generated:  {result['total_generated']}")
    print(f"After Dedup:{result['after_dedup']}")
    print(f"ML Ready:   {result['ml_model_ready']}")

    print(f"\n{'#':<5} {'ID':<28} {'eROAS':<8} {'eCTR':<8} {'eCVR':<8} {'Score':<8} {'Rec':<15}")
    print("-" * 70)
    for i, p in enumerate(result["top20"][:10]):
        icon = "✅" if p["recommendation"] == "TEST" else "⚠️"
        print(f"{icon} {i+1:<4} {p['creative_id']:<26} "
              f"{p['expected_roas']:<8.2f} {p['expected_ctr']:<8.3f} "
              f"{p['expected_cvr']:<8.3f} {p['overall_score']:<8.1f} {p['recommendation']}")

    tp = result.get("test_plan", {})
    for camp in tp.get("campaigns", []):
        print(f"\n📢 {camp['name']} | ${camp['budget_per_day']:.0f}/day | {len(camp['creatives'])} creatives")

    print(f"\nReport: {OUTPUT_DIR / f'remix_report_{args.game}_v33.json'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
