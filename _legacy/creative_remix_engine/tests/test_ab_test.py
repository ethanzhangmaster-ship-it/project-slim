import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from shot_intelligence.real_shot_detector import RealShotDetector
from shot_intelligence.visual_dna_extractor import VisualDNAExtractor
from shot_intelligence.shot_database import ShotDatabase
from remix_engine.ad_timeline_planner import AdTimelinePlanner
from composer.export_manager import ExportManager, ExportConfig
from typing import List

class MockStructureTemplate:
    def __init__(self, name: str, pattern: str):
        self.name = name
        self.pattern = pattern

def main():
    print("=" * 70)
    print("V3.9.1 A/B Test Framework")
    print("=" * 70)

    base_dir = Path(__file__).resolve().parent.parent
    video_source_dir = base_dir / "storage" / "outputs" / "v36_1_experiment" / "winner_creatives"
    db_path = base_dir / "storage" / "shot_database_abtest.json"
    output_dir = base_dir / "storage" / "outputs" / "ab_test"

    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir = output_dir / "baseline"
    variant_dir = output_dir / "variant"
    baseline_dir.mkdir(exist_ok=True)
    variant_dir.mkdir(exist_ok=True)

    video_files = list(video_source_dir.glob("*.mp4"))
    print(f"\n[1/4] 准备阶段")
    print(f"  视频源目录: {video_source_dir}")
    print(f"  找到 {len(video_files)} 个视频文件")

    shot_detector = RealShotDetector()
    dna_extractor = VisualDNAExtractor()

    print(f"\n[2/4] Shot 分析")
    all_dna = []
    for video_file in video_files:
        video_id = video_file.stem
        shots = shot_detector.detect(video_file, video_id)
        for shot in shots:
            dna = dna_extractor.extract(str(video_file), shot, shot.shot_id, video_id)
            all_dna.append(dna)
    print(f"  ✅ 总计分析 {len(all_dna)} 个 shots")

    shot_db = ShotDatabase(db_path)
    shot_db.add_many(all_dna)
    shot_db.save()

    timeline_planner = AdTimelinePlanner(shot_db)

    structure_templates = [
        MockStructureTemplate("dragon_merge_001", "hook-gameplay-reward-cta"),
        MockStructureTemplate("evolution_001", "hook-gameplay-story-reward-cta"),
        MockStructureTemplate("challenge_001", "hook-problem-gameplay-reward-cta"),
    ]

    print(f"\n[3/4] 生成 Baseline (原始视频直接裁剪)")
    baseline_config = ExportConfig(
        output_dir=baseline_dir,
        add_subtitles=False,
        add_bgm=False,
        normalize_audio=True,
        smart_crop=False,
    )
    baseline_manager = ExportManager(video_source_dir, baseline_config)

    baseline_timelines = []
    for i in range(10):
        template = structure_templates[i % len(structure_templates)]
        timeline = timeline_planner.plan_timeline(
            template, target_duration=15.0, target_ratio="9X16"
        )
        timeline.creative_id = f"baseline_{i+1:02d}"
        baseline_timelines.append(timeline)

    baseline_results = baseline_manager.export_batch(baseline_timelines)
    baseline_success = sum(1 for r in baseline_results if r.success)
    print(f"  ✅ Baseline 成功: {baseline_success}/10")

    print(f"\n[4/4] 生成 Variant (Remix 重新组合)")
    variant_config = ExportConfig(
        output_dir=variant_dir,
        add_subtitles=False,
        add_bgm=False,
        normalize_audio=True,
        smart_crop=True,
    )
    variant_manager = ExportManager(video_source_dir, variant_config)

    variant_timelines = []
    for i in range(10):
        template = structure_templates[(i + 1) % len(structure_templates)]
        timeline = timeline_planner.plan_timeline(
            template, target_duration=15.0, target_ratio="9X16"
        )
        timeline.creative_id = f"variant_{i+1:02d}"
        variant_timelines.append(timeline)

    variant_results = variant_manager.export_batch(variant_timelines)
    variant_success = sum(1 for r in variant_results if r.success)
    print(f"  ✅ Variant 成功: {variant_success}/10")

    print(f"\n{'=' * 70}")
    print("A/B Test 结果汇总")
    print(f"{'=' * 70}")
    print(f"  Baseline (原始): {baseline_success}/10 条")
    print(f"  Variant (Remix): {variant_success}/10 条")
    print(f"  输出目录: {output_dir}")
    print(f"\n  测试结构:")
    print(f"    baseline/ - 基于原始视频直接裁剪")
    print(f"    variant/  - 基于 Remix 引擎重新组合")
    print(f"\n  后续步骤:")
    print(f"    1. 将两组视频分别投放至 Facebook/TikTok/Google")
    print(f"    2. 收集 CTR, CPI, D7 ROI, D30 ROI 数据")
    print(f"    3. 使用统计检验对比两组表现")

if __name__ == "__main__":
    main()