"""V3.7 Creative Asset Intelligence Expansion — Runner

执行流程：
1. Asset Intelligence 分析（DNA + Cluster + Hook/Gameplay Mining + Quality Gate）
2. 基于 Creative Library 重新生成 A/B 视频
3. 质量分析 + 报告
"""
import sys, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ========== Step 1: Asset Intelligence ==========
from creative_remix_engine.asset_intelligence.asset_profiler import AssetProfiler

VIDEO_DIR = Path("D:/project_slim/output/P04_remix_videos/广告视频")
OUTPUT_DIR = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v37")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("V3.7 Creative Asset Intelligence Expansion")
print("=" * 70)

profiler = AssetProfiler(
    video_dir=VIDEO_DIR,
    output_dir=OUTPUT_DIR,
    ranking_db_path=Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json"),
)
result = profiler.run()

# 加载 Hook/Gameplay Library
import json
with open(OUTPUT_DIR / "hook_library.json", "r", encoding="utf-8") as f:
    hook_lib = json.load(f)
with open(OUTPUT_DIR / "gameplay_library.json", "r", encoding="utf-8") as f:
    gp_lib = json.load(f)

print(f"\n[Asset Intelligence Summary]")
print(f"  Total Assets: {result['dna_count']}")
print(f"  Hook Candidates: {result['hook_count']}")
print(f"  Gameplay Candidates: {result['gameplay_count']}")
print(f"  Archetypes: {result['archetypes']}")
print(f"  Quality: S={result['quality']['S']} A={result['quality']['A']} B={result['quality']['B']} C={result['quality']['C']}")

# ========== Step 2: V3.7 A/B Test ==========
print("\n" + "=" * 70)
print("V3.7 A/B Validation")
print("=" * 70)

from creative_remix_engine.director.story_planner import StoryPlanner
from creative_remix_engine.analyzer.shot_selector_v2 import ShotSelectorV2
from creative_remix_engine.generator.video_composer_v2 import VideoComposerV2
from creative_remix_engine.experiments.v36_ranking_validation.baseline_shot_selector import BaselineShotSelector
from creative_remix_engine.experiments.v36_ranking_validation.video_quality_analyzer_v2 import VideoQualityAnalyzerV2
from creative_remix_engine.experiments.v36_ranking_validation.comparison_report import ComparisonReport

EXPERIMENT_DIR = OUTPUT_DIR / "experiment"
EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)

planner = StoryPlanner(game_code="P04")
story_types = ["evolution", "rescue", "challenge", "revenge", "impossible_level"]

pairs = []
for i in range(10):
    stype = story_types[i % len(story_types)]
    plan = planner.generate_plan(stype, plan_id=f"v37_{i+1:02d}")
    print(f"\n[Pair {i+1}/10] {stype}")

    # Baseline (V3.4)
    baseline_sel = BaselineShotSelector()
    baseline_sel.build_pool(source_dir=VIDEO_DIR)
    baseline_shots = baseline_sel.select_for_plan(plan.beats)
    baseline_dir = EXPERIMENT_DIR / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    composer_b = VideoComposerV2(baseline_dir)
    baseline_path, baseline_report = composer_b.compose(plan, baseline_shots, video_id=f"baseline_{i+1:02d}")
    print(f"  Baseline: {'OK' if baseline_path else 'FAIL'}")

    # Ranking V3.7 — 使用新的 Ranking DB
    ranking_sel = ShotSelectorV2(
        game_code="P04",
        ranking_db_path=Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
    )
    ranking_sel.build_pool(source_dir=VIDEO_DIR)
    ranking_shots = ranking_sel.select_for_plan(plan.beats)
    ranking_dir = EXPERIMENT_DIR / "ranking"
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

# ========== Step 3: Quality Analysis ==========
print("\n[Step 3] Quality Analysis...")
analyzer = VideoQualityAnalyzerV2()
enriched = []
for pair in pairs:
    b_path = Path(pair["baseline"]["video_path"]) if pair["baseline"]["video_path"] else None
    r_path = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
    pair["baseline_analysis"] = analyzer.analyze(b_path) if b_path and b_path.exists() else {}
    pair["ranking_analysis"] = analyzer.analyze(r_path) if r_path and r_path.exists() else {}
    b_ad = pair["baseline_analysis"].get("ad_value_score", 0)
    r_ad = pair["ranking_analysis"].get("ad_value_score", 0)
    print(f"  Pair {pair['pair_id']}: B={b_ad:.1f} R={r_ad:.1f} ({'+' if r_ad > b_ad else ''}{r_ad - b_ad:.1f})")
    enriched.append(pair)

# ========== Step 4: Report ==========
print("\n[Step 4] Generating Report...")
reporter = ComparisonReport(EXPERIMENT_DIR)
report = reporter.generate(enriched)

# TOP 3 Winners
winner_dir = EXPERIMENT_DIR / "winner_creatives"
winner_dir.mkdir(parents=True, exist_ok=True)
sorted_pairs = sorted(enriched, key=lambda x: x.get("ranking_analysis", {}).get("ad_value_score", 0), reverse=True)
for i, pair in enumerate(sorted_pairs[:3], 1):
    src = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
    if src and src.exists():
        dst = winner_dir / f"winner_{i:02d}_{pair['story_type']}.mp4"
        shutil.copy2(str(src), str(dst))

# Final Summary
print("\n" + "=" * 70)
print("V3.7 Complete!")
print("=" * 70)
s = report["report"]["summary"]
print(f"\n  [A/B Results]")
print(f"  Baseline Overall: {s['baseline_avg']['overall']}")
print(f"  Ranking Overall:  {s['ranking_avg']['overall']}")
print(f"  Improvement:      {s.get('overall_improvement_pct', 0):+.1f}%")

print(f"\n  [Ad Value]")
print(f"  Baseline: {sum(p['baseline_analysis'].get('ad_value_score',0) for p in enriched)/len(enriched):.1f}")
print(f"  Ranking:  {sum(p['ranking_analysis'].get('ad_value_score',0) for p in enriched)/len(enriched):.1f}")

print(f"\n  [Files]")
print(f"  Creative Library: {OUTPUT_DIR / 'creative_library.json'}")
print(f"  Hook Library:     {OUTPUT_DIR / 'hook_library.json'}")
print(f"  Gameplay Library: {OUTPUT_DIR / 'gameplay_library.json'}")
print(f"  Cluster Report:   {OUTPUT_DIR / 'creative_cluster_report.html'}")
print(f"  A/B Report:       {report['html_path']}")
