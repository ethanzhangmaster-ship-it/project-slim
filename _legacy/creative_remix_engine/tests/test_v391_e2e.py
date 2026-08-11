"""V3.9.1 端到端测试脚本

测试流程：
1. Real Shot Boundary Detection（真实镜头边界检测）
2. Visual DNA Extraction（视觉 DNA 提取）
3. Shot Database 存储
4. Ad Timeline Planning（广告时间线规划）
5. FFmpeg Composition（FFmpeg 合成）
6. Export Management（导出管理）

输入：现有的 MP4 视频文件
输出：20条混剪创意视频
"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from creative_remix_engine.shot_intelligence.real_shot_detector import RealShotDetector
from creative_remix_engine.shot_intelligence.visual_dna_extractor import VisualDNAExtractor
from creative_remix_engine.shot_intelligence.shot_database import ShotDatabase
from creative_remix_engine.remix_engine.ad_timeline_planner import AdTimelinePlanner
from creative_remix_engine.composer.export_manager import ExportManager, ExportConfig


class MockStructureTemplate:
    """模拟结构模板"""
    def __init__(self, name: str, pattern: str):
        self.name = name
        self.pattern = pattern


def run_e2e_test():
    """运行端到端测试"""
    print("=" * 70)
    print("V3.9.1 Creative Remix Reality Engine - 端到端测试")
    print("=" * 70)

    base_dir = Path(__file__).parent.parent
    storage_dir = base_dir / "storage"
    video_source_dir = storage_dir / "outputs" / "v36_1_experiment" / "winner_creatives"
    db_path = storage_dir / "shot_database_v391.json"
    output_dir = storage_dir / "outputs" / "v391_test"

    print(f"\n[1/6] 准备阶段")
    print(f"  视频源目录: {video_source_dir}")
    print(f"  Shot数据库: {db_path}")
    print(f"  输出目录: {output_dir}")

    video_files = list(video_source_dir.glob("*.mp4"))
    if not video_files:
        video_files = list(storage_dir.glob("**/*.mp4"))[:10]

    print(f"  找到 {len(video_files)} 个视频文件")

    if not video_files:
        print("  ❌ 未找到视频文件，请确保有测试视频")
        return False

    print("\n[2/6] Real Shot Boundary Detection")
    shot_detector = RealShotDetector()
    all_shots = []

    for video_file in video_files[:5]:
        video_id = video_file.stem
        print(f"  处理: {video_file.name}")
        shots = shot_detector.detect(video_file, video_id)
        all_shots.extend(shots)
        print(f"    → 检测到 {len(shots)} 个 shots")

    print(f"  ✅ 总计检测到 {len(all_shots)} 个 shots")

    print("\n[3/6] Visual DNA Extraction")
    dna_extractor = VisualDNAExtractor()
    all_dna = []

    for video_file in video_files[:5]:
        video_id = video_file.stem
        shots_for_video = [s for s in all_shots if s.shot_id.startswith(video_id)]
        print(f"  处理: {video_file.name} ({len(shots_for_video)} shots)")

        for shot in shots_for_video:
            dna = dna_extractor.extract(video_file, shot, shot.shot_id, video_id)
            all_dna.append(dna)

    print(f"  ✅ 总计提取 {len(all_dna)} 个 VisualDNA")

    print("\n[4/6] Shot Database 存储")
    shot_db = ShotDatabase(db_path)
    shot_db.add_many(all_dna)
    shot_db.save()

    stats = shot_db.get_stats()
    print(f"  ✅ 数据库统计:")
    print(f"    - 总 shots: {stats['total']}")
    print(f"    - VisualDNA: {stats['dna_type_distribution'].get('VisualDNA', 0)}")
    print(f"    - 平均视觉质量: {stats['avg_visual_score']}")
    print(f"    - 平均 Hook 强度: {stats['avg_hook_strength']}")

    print("\n[5/6] Ad Timeline Planning")
    timeline_planner = AdTimelinePlanner(shot_db)

    structure_templates = [
        MockStructureTemplate("dragon_merge_001", "hook-gameplay-reward-cta"),
        MockStructureTemplate("evolution_001", "hook-gameplay-story-reward-cta"),
        MockStructureTemplate("challenge_001", "hook-problem-gameplay-reward-cta"),
    ]

    timelines = []
    for i in range(20):
        template = structure_templates[i % len(structure_templates)]
        timeline = timeline_planner.plan_timeline(
            template, target_duration=15.0, target_ratio="9X16"
        )
        timeline.creative_id = f"creative_{i+1:03d}"
        timelines.append(timeline)

    print(f"  ✅ 生成 {len(timelines)} 条时间线")

    print("\n[6/6] FFmpeg Composition & Export")
    export_config = ExportConfig(
        output_dir=output_dir,
        add_subtitles=True,
        add_bgm=False,
        normalize_audio=True,
        smart_crop=True,
    )

    export_manager = ExportManager(video_source_dir, export_config)
    export_manager.prepare_output_structure()

    results = export_manager.export_batch(timelines)

    success_count = sum(1 for r in results if r.success)
    total_count = len(results)

    print(f"\n{'=' * 70}")
    print("测试结果汇总")
    print(f"{'=' * 70}")
    print(f"  成功: {success_count}/{total_count}")
    print(f"  成功率: {success_count/total_count*100:.1f}%")

    if success_count > 0:
        report_path = export_manager.generate_report(results)
        print(f"\n  导出报告: {report_path}")

        output_stats = export_manager.get_output_stats()
        print(f"  输出统计:")
        print(f"    - 总视频数: {output_stats['total']}")
        print(f"    - 平均分辨率: {output_stats['avg_width']}x{output_stats['avg_height']}")
        print(f"    - 平均时长: {output_stats['avg_duration']}s")
        print(f"    - 平均大小: {output_stats['avg_size_mb']}MB")

    export_manager.cleanup_temp_files()

    return success_count == total_count


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)