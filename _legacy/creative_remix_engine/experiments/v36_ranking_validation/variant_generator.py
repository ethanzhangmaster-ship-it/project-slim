"""Variant Generator — 生成 A/B 两组视频"""
import sys
from pathlib import Path
from typing import List, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from creative_remix_engine.director.story_planner import StoryPlanner
from creative_remix_engine.analyzer.shot_selector_v2 import ShotSelectorV2
from creative_remix_engine.generator.video_composer_v2 import VideoComposerV2
from creative_remix_engine.experiments.v36_ranking_validation.baseline_shot_selector import BaselineShotSelector


SOURCE_DIR = Path("D:/project_slim/output/P04_remix_videos/广告视频")
OUTPUT_BASE = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_experiment")


class VariantGenerator:
    """A/B 变体生成器"""

    def __init__(self):
        self.planner = StoryPlanner(game_code="P04")
        self.composer = None

    def _generate_video(self, plan, shot_map, video_id: str, output_dir: Path) -> Tuple[Path, dict]:
        """生成单条视频"""
        composer = VideoComposerV2(output_dir)
        final_path, report = composer.compose(plan, shot_map, video_id=video_id)
        return final_path, report

    def generate_pair(self, story_type: str, pair_id: int) -> Dict:
        """
        生成一对 A/B 视频（相同 Story，不同 Shot Selection）。
        返回: {"plan_id": str, "baseline": {...}, "ranking": {...}}
        """
        plan = self.planner.generate_plan(story_type, plan_id=f"pair_{pair_id:02d}")

        # Group A: Baseline (V3.4 随机)
        baseline_selector = BaselineShotSelector()
        baseline_selector.build_pool(source_dir=SOURCE_DIR)
        baseline_shots = baseline_selector.select_for_plan(plan.beats)

        baseline_dir = OUTPUT_BASE / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        baseline_path, baseline_report = self._generate_video(
            plan, baseline_shots,
            video_id=f"baseline_{pair_id:02d}",
            output_dir=baseline_dir
        )

        # Group B: Ranking (V3.5 Ranking Engine)
        ranking_selector = ShotSelectorV2(game_code="P04")
        ranking_selector.build_pool(source_dir=SOURCE_DIR)
        ranking_shots = ranking_selector.select_for_plan(plan.beats)

        ranking_dir = OUTPUT_BASE / "ranking"
        ranking_dir.mkdir(parents=True, exist_ok=True)
        ranking_path, ranking_report = self._generate_video(
            plan, ranking_shots,
            video_id=f"ranking_{pair_id:02d}",
            output_dir=ranking_dir
        )

        return {
            "pair_id": pair_id,
            "story_type": story_type,
            "title": plan.title,
            "baseline": {
                "video_path": str(baseline_path) if baseline_path else None,
                "report": baseline_report,
            },
            "ranking": {
                "video_path": str(ranking_path) if ranking_path else None,
                "report": ranking_report,
            },
        }

    def generate_batch(self, count: int = 10) -> List[Dict]:
        """生成 N 对 A/B 视频"""
        # 确保 A/B 组使用相同的故事分布
        story_types = ["evolution", "rescue", "challenge", "revenge", "impossible_level"]
        results = []
        for i in range(count):
            stype = story_types[i % len(story_types)]
            print(f"\n[VariantGenerator] Generating pair {i+1}/{count} — {stype}")
            pair = self.generate_pair(stype, i + 1)
            results.append(pair)

            b_ok = pair["baseline"]["video_path"] is not None
            r_ok = pair["ranking"]["video_path"] is not None
            print(f"  Baseline: {'OK' if b_ok else 'FAIL'}")
            print(f"  Ranking:  {'OK' if r_ok else 'FAIL'}")

        return results
