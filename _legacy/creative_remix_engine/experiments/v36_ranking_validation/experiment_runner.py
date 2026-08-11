"""Experiment Runner — V3.6 A/B Validation 总入口"""
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from creative_remix_engine.experiments.v36_ranking_validation.variant_generator import VariantGenerator
from creative_remix_engine.experiments.v36_ranking_validation.video_quality_analyzer import VideoQualityAnalyzer
from creative_remix_engine.experiments.v36_ranking_validation.comparison_report import ComparisonReport

OUTPUT_BASE = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_experiment")


def run_experiment(count: int = 10):
    print("=" * 70)
    print("V3.6 Ranking Driven Video Generation — A/B Validation")
    print("=" * 70)

    # Phase 1: 生成视频
    print("\n[Phase 1] Generating A/B video pairs...")
    generator = VariantGenerator()
    pairs = generator.generate_batch(count=count)

    # Phase 2: 质量分析
    print("\n[Phase 2] Analyzing video quality...")
    analyzer = VideoQualityAnalyzer()
    enriched = []

    for pair in pairs:
        pair_id = pair["pair_id"]
        print(f"  Pair #{pair_id} — Analyzing...")

        # Baseline
        b_path = Path(pair["baseline"]["video_path"]) if pair["baseline"]["video_path"] else None
        b_analysis = analyzer.analyze(b_path) if b_path and b_path.exists() else None
        if b_analysis:
            print(f"    Baseline: Hook={b_analysis['hook_score']:.1f} GP={b_analysis['gameplay_clarity']:.1f} Overall={b_analysis['overall_score']:.1f}")

        # Ranking
        r_path = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
        r_analysis = analyzer.analyze(r_path) if r_path and r_path.exists() else None
        if r_analysis:
            print(f"    Ranking:  Hook={r_analysis['hook_score']:.1f} GP={r_analysis['gameplay_clarity']:.1f} Overall={r_analysis['overall_score']:.1f}")

        pair["baseline_analysis"] = b_analysis or {}
        pair["ranking_analysis"] = r_analysis or {}
        enriched.append(pair)

    # Phase 3: 生成报告
    print("\n[Phase 3] Generating comparison report...")
    reporter = ComparisonReport(OUTPUT_BASE)
    report = reporter.generate(enriched)

    # Phase 4: 选出 TOP 3 Winner 并复制
    print("\n[Phase 4] Selecting TOP 3 Winners...")
    winner_dir = OUTPUT_BASE / "winner_creatives"
    winner_dir.mkdir(parents=True, exist_ok=True)

    # 按 ranking overall 排序
    sorted_pairs = sorted(enriched, key=lambda x: x.get("ranking_analysis", {}).get("overall_score", 0), reverse=True)
    for i, pair in enumerate(sorted_pairs[:3], 1):
        src = Path(pair["ranking"]["video_path"]) if pair["ranking"]["video_path"] else None
        if src and src.exists():
            dst = winner_dir / f"winner_{i:02d}_{pair['story_type']}.mp4"
            shutil.copy2(str(src), str(dst))
            print(f"  #{i} Winner: Pair {pair['pair_id']} ({pair['story_type']}) -> {dst}")

    # Summary
    print("\n" + "=" * 70)
    print("V3.6 Validation Complete!")
    print("=" * 70)
    print(f"  Total pairs: {count}")
    print(f"  HTML Report: {report['html_path']}")
    print(f"  JSON Report: {report['json_path']}")
    print(f"  Winners:     {winner_dir}")

    s = report["report"]["summary"]
    print(f"\n  Baseline Avg: Overall={s['baseline_avg']['overall']}")
    print(f"  Ranking Avg:  Overall={s['ranking_avg']['overall']}")
    print(f"  Improvement:  {s.get('overall_improvement_pct', 0):+.1f}%")

    return report


if __name__ == "__main__":
    run_experiment(count=10)
