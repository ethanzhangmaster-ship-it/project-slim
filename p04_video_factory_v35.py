"""
V3.5 Visual Intelligence Ranking Engine — 全量分析 Runner

对 Eagle 全部 599 个视频进行视觉分析，生成：
- Ranking Database (JSON)
- HTML 排名报告
- 排行榜数据
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from creative_remix_engine.visual_intelligence.scorer import VisualIntelligenceScorer
from creative_remix_engine.visual_intelligence.report_generator import ReportGenerator

SOURCE_DIR = Path("D:/project_slim/output/P04_remix_videos/广告视频")
CACHE_DIR = Path("D:/project_slim/output/P04_remix_videos/v35_cache")
DB_PATH = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v35_ranking_db.json")
REPORT_DIR = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v35_reports")


def run_full_analysis(force: bool = False):
    print("=" * 70)
    print("V3.5 Visual Intelligence Ranking Engine — Full Analysis")
    print("=" * 70)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    scorer = VisualIntelligenceScorer(
        cache_dir=CACHE_DIR,
        db_path=DB_PATH,
        video_source_dir=SOURCE_DIR,
    )

    video_paths = sorted(SOURCE_DIR.glob("*.mp4"))
    print(f"\nSource videos: {len(video_paths)}")
    print(f"Cache dir: {CACHE_DIR}")
    print(f"DB path: {DB_PATH}")

    # 1. 批量分析
    print("\n[Phase 1] Analyzing all videos...")
    results = scorer.analyze_all(video_paths, force=force)

    # 2. 构建排行榜
    print("\n[Phase 2] Building rankings...")
    rankings = scorer.build_rankings()

    print(f"  Total in ranking: {rankings.get('total', 0)}")
    print(f"  Top Hook: {len(rankings.get('top_hook', []))}")
    print(f"  Top Gameplay: {len(rankings.get('top_gameplay', []))}")
    print(f"  Top Reward: {len(rankings.get('top_reward', []))}")
    print(f"  Top Overall: {len(rankings.get('top_overall', []))}")

    # 3. 生成 HTML 报告
    print("\n[Phase 3] Generating HTML report...")
    reporter = ReportGenerator(REPORT_DIR)
    report_path = reporter.generate(rankings, scorer.db.get_all())
    print(f"  Report: {report_path}")

    # 4. 保存 JSON 排行榜
    import json
    json_path = REPORT_DIR / "rankings.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rankings, f, ensure_ascii=False, indent=2, default=str)
    print(f"  JSON: {json_path}")

    # 5. 打印 TOP 预览
    print("\n[Preview] TOP 10 Hook:")
    for i, r in enumerate(rankings.get("top_hook", [])[:10], 1):
        print(f"  #{i:2d} {r['video_name'][:45]:45s} Hook={r['hook_score']:.1f} Impact={r['impact_score']:.1f}")

    print("\n[Preview] TOP 10 Gameplay:")
    for i, r in enumerate(rankings.get("top_gameplay", [])[:10], 1):
        print(f"  #{i:2d} {r['video_name'][:45]:45s} GP={r['gameplay_score']:.1f} Motion={r['motion_score']:.1f}")

    print("\n[Preview] TOP 10 Reward:")
    for i, r in enumerate(rankings.get("top_reward", [])[:10], 1):
        print(f"  #{i:2d} {r['video_name'][:45]:45s} Reward={r['reward_score']:.1f} Impact={r['impact_score']:.1f}")

    print("\n" + "=" * 70)
    print("V3.5 Analysis Complete!")
    print("=" * 70)
    print(f"Cache:   {CACHE_DIR}")
    print(f"Report:  {report_path}")
    print(f"JSON:    {json_path}")

    return rankings


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force re-analyze all videos")
    args = parser.parse_args()
    run_full_analysis(force=args.force)
