"""
V3.4 Video Generator V2 — Phase 1→2→3 集成 runner
生成3条差异化AI导演视频，输出人工评估报告。
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# 确保模块路径
sys.path.insert(0, str(Path(__file__).parent))

from creative_remix_engine.director.story_planner import StoryPlanner
from creative_remix_engine.analyzer.shot_selector_v2 import ShotSelectorV2
from creative_remix_engine.generator.video_composer_v2 import VideoComposerV2

SOURCE_VIDEOS_DIR = Path("D:/project_slim/output/P04_remix_videos/广告视频")
OUTPUT_DIR = Path("D:/project_slim/output/P04_remix_videos/v34_v2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_videos(count: int = 3):
    print("=" * 70)
    print("V3.4 Video Generator V2 — AI Creative Director Pipeline")
    print("=" * 70)

    # Phase 1: Story Planner
    print("\n[Phase 1] AI Story Planner — 生成差异化故事板...")
    planner = StoryPlanner(game_code="P04")
    # 强制3种不同故事类型，确保差异化
    forced_types = ["evolution", "rescue", "challenge"]
    plans = []
    for i in range(count):
        plan = planner.generate_plan(
            story_type=forced_types[i % len(forced_types)],
            plan_id=f"v2_{i+1:03d}"
        )
        plans.append(plan)
        print(f"  Plan {plan.plan_id}: {plan.story_type} | '{plan.title}' | "
              f"{len(plan.beats)} beats | DNA match={plan.dna_match_score}")
        for b in plan.beats:
            print(f"    → {b.role:10s} {b.duration:4.1f}s | {b.transition_in:12s} | {b.subtitle}")

    # Phase 2: Shot Selector
    print("\n[Phase 2] Shot Intelligence Selector V2 — 构建镜头池...")
    selector = ShotSelectorV2(game_code="P04")
    pool = selector.build_pool(source_dir=SOURCE_VIDEOS_DIR, min_duration=2.5)
    if len(pool) < 10:
        print(f"  WARNING: Only {len(pool)} shots available. Need more source videos.")

    # 按内容类型统计
    from collections import Counter
    ctype_counts = Counter(s.content_type for s in pool)
    print(f"  Pool stats: {dict(ctype_counts)}")

    # Phase 3: Video Composer
    print("\n[Phase 3] AI Video Composer V2 — 合成视频...")
    composer = VideoComposerV2(output_dir=OUTPUT_DIR)

    results = []
    for plan in plans:
        print(f"\n  [{plan.plan_id}] {plan.story_type} — selecting shots...")
        shot_map = selector.select_for_plan(plan.beats, avoid_duplicate_source=True)

        # 打印选中的镜头
        for beat in plan.beats:
            cands = shot_map.get(beat.beat_id, [])
            if cands:
                shot, start, dur = cands[0]
                print(f"    {beat.role:10s} ← {shot.filepath.name[:40]:40s} "
                      f"@{start:5.1f}s len={dur:4.1f}s score={shot.overall_score:.1f}")
            else:
                print(f"    {beat.role:10s} ← NO SHOT FOUND")

        print(f"  [{plan.plan_id}] Composing...")
        final_path, report = composer.compose(plan, shot_map, video_id=plan.plan_id)

        if final_path and final_path.exists():
            print(f"  [{plan.plan_id}] ✅ SUCCESS → {final_path}")
            print(f"    Duration: {report.get('duration', 0):.1f}s | "
                  f"Resolution: {report.get('resolution', 'N/A')} | "
                  f"Size: {report.get('size_mb', 0)}MB")
        else:
            print(f"  [{plan.plan_id}] ❌ FAILED: {report.get('error', 'unknown')}")

        results.append(report)

    # 输出报告
    print("\n[Report] Generating quality report...")
    summary = {
        "pipeline": "V3.4 Video Generator V2",
        "phases": ["StoryPlanner", "ShotSelectorV2", "VideoComposerV2"],
        "generated_at": datetime.now().isoformat(),
        "source_dir": str(SOURCE_VIDEOS_DIR),
        "output_dir": str(OUTPUT_DIR),
        "total_videos": len(results),
        "successful": sum(1 for r in results if "error" not in r),
        "failed": sum(1 for r in results if "error" in r),
        "videos": results,
    }
    report_path = OUTPUT_DIR / "v34_v2_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  Total: {summary['total_videos']} | Successful: {summary['successful']} | Failed: {summary['failed']}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Report: {report_path}")
    for r in results:
        vid = r.get("video_id", "?")
        if "error" in r:
            print(f"    ❌ {vid}: ERROR — {r['error']}")
        else:
            print(f"    ✅ {vid}: {r.get('story_type','?'):12s} | {r.get('duration',0):.1f}s | {r.get('resolution','?')}")

    return summary


if __name__ == "__main__":
    generate_videos(count=3)
