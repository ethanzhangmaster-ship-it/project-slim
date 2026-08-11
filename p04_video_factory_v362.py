"""V3.6.2 Runner — Asset Intelligence Expansion Layer

执行流程：
1. Asset Coverage Analysis（素材覆盖度分析）
2. A/B 实验：10 Baseline vs 10 Ranking V3.6.2（ShotRankerV362）
3. 质量分析 + 报告生成
"""
import sys, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Step 1: Asset Coverage Analysis
print("=" * 70)
print("V3.6.2 Asset Intelligence Expansion — Step 1: Coverage Analysis")
print("=" * 70)

from creative_remix_engine.intelligence.asset_coverage_analyzer import AssetCoverageAnalyzer

DB_PATH = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
COVERAGE_REPORT_PATH = Path("d:/project_slim/project_slim/creative_remix_engine/storage/asset_coverage_report.json")

analyzer = AssetCoverageAnalyzer(DB_PATH)
report = analyzer.analyze()
analyzer.save_report(report, COVERAGE_REPORT_PATH)
print(f"[Coverage] Report saved: {COVERAGE_REPORT_PATH}")

# Step 2: A/B Experiment with V3.6.2 Ranking Engine
print("\n" + "=" * 70)
print("V3.6.2 Step 2: A/B Validation (ShotRankerV362)")
print("=" * 70)

from creative_remix_engine.director.story_planner import StoryPlanner
from creative_remix_engine.ranking.shot_ranker_v362 import ShotRankerV362
from creative_remix_engine.generator.video_composer_v2 import VideoComposerV2
from creative_remix_engine.experiments.v36_ranking_validation.baseline_shot_selector import BaselineShotSelector
from creative_remix_engine.experiments.v36_ranking_validation.video_quality_analyzer_v2 import VideoQualityAnalyzerV2
from creative_remix_engine.experiments.v36_ranking_validation.comparison_report import ComparisonReport

SOURCE_VIDEOS = Path("D:/project_slim/output/P04_remix_videos/广告视频")
OUTPUT_BASE = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_2_experiment")
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

planner = StoryPlanner(game_code="P04")
story_types = ["evolution", "rescue", "challenge", "revenge", "impossible_level"]

pairs = []
for i in range(10):
    stype = story_types[i % len(story_types)]
    plan = planner.generate_plan(stype, plan_id=f"pair_{i+1:02d}")
    print(f"\n[Pair {i+1}/10] {stype}")

    # Baseline（复用 V3.6.1 的 baseline 逻辑）
    baseline_sel = BaselineShotSelector()
    baseline_sel.build_pool(source_dir=SOURCE_VIDEOS)
    baseline_shots = baseline_sel.select_for_plan(plan.beats)
    baseline_dir = OUTPUT_BASE / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    composer_b = VideoComposerV2(baseline_dir)
    baseline_path, baseline_report = composer_b.compose(plan, baseline_shots, video_id=f"baseline_{i+1:02d}")
    print(f"  Baseline: {'OK' if baseline_path else 'FAIL'}")

    # Ranking V3.6.2（使用 ShotRankerV362）
    ranking_sel = ShotRankerV362(game_code="P04", ranking_db_path=DB_PATH)
    ranking_sel.build_pool(source_dir=SOURCE_VIDEOS)
    ranking_shots = ranking_sel.select_for_plan(plan.beats)
    ranking_dir = OUTPUT_BASE / "ranking"
    ranking_dir.mkdir(parents=True, exist_ok=True)
    composer_r = VideoComposerV2(ranking_dir)
    ranking_path, ranking_report = composer_r.compose(plan, ranking_shots, video_id=f"ranking_{i+1:02d}")
    print(f"  Ranking:  {'OK' if ranking_path else 'FAIL'}")

    pairs.append({
        "pair_id": i + 1,
        "story_type": stype,
        "baseline": {"video_path": str(baseline_path) if baseline_path else None},
        "ranking": {"video_path": str(ranking_path) if ranking_path else None},
    })

# Step 3: Quality Analysis
print("\n[Step 3] Quality Analysis...")
analyzer_v2 = VideoQualityAnalyzerV2()
enriched = []
for pair in pairs:
    b_path = Path(pair["baseline"]["video_path"]) if pair["baseline"]["video_path"] else None
    r_path = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
    pair["baseline_analysis"] = analyzer_v2.analyze(b_path) if b_path and b_path.exists() else {}
    pair["ranking_analysis"] = analyzer_v2.analyze(r_path) if r_path and r_path.exists() else {}
    print(f"  Pair {pair['pair_id']}: B={pair['baseline_analysis'].get('ad_value_score',0):.1f} R={pair['ranking_analysis'].get('ad_value_score',0):.1f}")
    enriched.append(pair)

# Step 4: Report
print("\n[Step 4] Generating Report...")
reporter = ComparisonReport(OUTPUT_BASE)
report = reporter.generate(enriched)

# TOP 3 Winners
winner_dir = OUTPUT_BASE / "winner_creatives"
winner_dir.mkdir(parents=True, exist_ok=True)
sorted_pairs = sorted(enriched, key=lambda x: x.get("ranking_analysis", {}).get("ad_value_score", 0), reverse=True)
for i, pair in enumerate(sorted_pairs[:3], 1):
    src = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
    if src and src.exists():
        dst = winner_dir / f"winner_{i:02d}_{pair['story_type']}.mp4"
        shutil.copy2(str(src), str(dst))

# Summary
print("\n" + "=" * 70)
print("V3.6.2 Asset Intelligence Expansion — Complete!")
print("=" * 70)
s = report["report"]["summary"]
print(f"  Baseline Overall: {s['baseline_avg']['overall']}")
print(f"  Ranking V3.6.2:   {s['ranking_avg']['overall']}")
print(f"  Improvement:      {s.get('overall_improvement_pct', 0):+.1f}%")
print(f"  HTML: {report['html_path']}")
print(f"  JSON: {report['json_path']}")
