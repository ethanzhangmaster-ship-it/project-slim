"""V3.6.1 Runner — Ranking Engine Calibration & Re-validation

执行流程：
1. Scorer V2 全量分析（生成 hook_score_v2, gameplay_clarity, role_scores, ad_value）
2. A/B 实验：10 Baseline vs 10 Ranking V3.6.1
3. 质量分析 + 报告生成
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Step 1: Scorer V2 全量分析
print("=" * 70)
print("V3.6.1 Ranking Engine Calibration — Step 1: Scorer V2 Analysis")
print("=" * 70)

from creative_remix_engine.visual_intelligence.scorer_v2 import VisualIntelligenceScorerV2

CACHE_DIR = Path("D:/project_slim/output/P04_remix_videos/v35_cache")
DB_PATH = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
SOURCE_DIR = Path("D:/project_slim/output/P04_remix_videos/广告视频")

scorer = VisualIntelligenceScorerV2(
    cache_dir=CACHE_DIR,
    db_path=DB_PATH,
    video_source_dir=SOURCE_DIR,
)

# 增量分析（只处理缺少 V2 字段的视频）
results = scorer.analyze_all(force=False)

# Step 2: A/B 实验
print("\n" + "=" * 70)
print("V3.6.1 Step 2: A/B Validation")
print("=" * 70)

from creative_remix_engine.experiments.v36_ranking_validation.variant_generator import VariantGenerator
from creative_remix_engine.experiments.v36_ranking_validation.video_quality_analyzer_v2 import VideoQualityAnalyzerV2
from creative_remix_engine.experiments.v36_ranking_validation.comparison_report import ComparisonReport
from creative_remix_engine.experiments.v36_ranking_validation.baseline_shot_selector import BaselineShotSelector

OUTPUT_BASE = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_experiment")
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

# 生成视频
from creative_remix_engine.director.story_planner import StoryPlanner
from creative_remix_engine.analyzer.shot_selector_v2 import ShotSelectorV2
from creative_remix_engine.generator.video_composer_v2 import VideoComposerV2

SOURCE_VIDEOS = Path("D:/project_slim/output/P04_remix_videos/广告视频")

planner = StoryPlanner(game_code="P04")
story_types = ["evolution", "rescue", "challenge", "revenge", "impossible_level"]

pairs = []
for i in range(10):
    stype = story_types[i % len(story_types)]
    plan = planner.generate_plan(stype, plan_id=f"pair_{i+1:02d}")
    print(f"\n[Pair {i+1}/10] {stype}")

    # Baseline
    baseline_sel = BaselineShotSelector()
    baseline_sel.build_pool(source_dir=SOURCE_VIDEOS)
    baseline_shots = baseline_sel.select_for_plan(plan.beats)
    baseline_dir = OUTPUT_BASE / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    composer_b = VideoComposerV2(baseline_dir)
    baseline_path, baseline_report = composer_b.compose(plan, baseline_shots, video_id=f"baseline_{i+1:02d}")
    print(f"  Baseline: {'OK' if baseline_path else 'FAIL'}")

    # Ranking V3.6.1
    ranking_sel = ShotSelectorV2(game_code="P04", ranking_db_path=DB_PATH)
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

# Step 3: 质量分析
print("\n[Step 3] Quality Analysis...")
analyzer = VideoQualityAnalyzerV2()
enriched = []
for pair in pairs:
    b_path = Path(pair["baseline"]["video_path"]) if pair["baseline"]["video_path"] else None
    r_path = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
    pair["baseline_analysis"] = analyzer.analyze(b_path) if b_path and b_path.exists() else {}
    pair["ranking_analysis"] = analyzer.analyze(r_path) if r_path and r_path.exists() else {}
    print(f"  Pair {pair['pair_id']}: B={pair['baseline_analysis'].get('ad_value_score',0):.1f} R={pair['ranking_analysis'].get('ad_value_score',0):.1f}")
    enriched.append(pair)

# Step 4: 报告
print("\n[Step 4] Generating Report...")
reporter = ComparisonReport(OUTPUT_BASE)
report = reporter.generate(enriched)

# TOP 3 Winners
import shutil
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
print("V3.6.1 Validation Complete!")
print("=" * 70)
s = report["report"]["summary"]
print(f"  Baseline Overall: {s['baseline_avg']['overall']}")
print(f"  Ranking Overall:  {s['ranking_avg']['overall']}")
print(f"  Improvement:      {s.get('overall_improvement_pct', 0):+.1f}%")
print(f"  HTML: {report['html_path']}")
print(f"  JSON: {report['json_path']}")
