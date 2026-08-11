"""Integration smoke test for Video Intelligence Pipeline.

Verifies the pipeline's internal logic works with mock data,
without requiring Facebook API or Lovart credentials.

Run: python -m market_ops.video_intelligence.test_pipeline
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from market_ops.video_intelligence.models import (
    VideoAnalysis, HookAnalysis, StoryAnalysis, RewardAnalysis,
    CharacterAnalysis, EnvironmentAnalysis, CameraAnalysis,
    MotionAnalysis, EmotionAnalysis, CTAAnalysis, StyleAnalysis, AudioAnalysis,
)
from market_ops.video_intelligence.feature_statistics import FeatureStatisticsEngine
from market_ops.video_intelligence.pattern_analyzer import PatternAnalyzer
from market_ops.video_intelligence.direction_report import DirectionReportGenerator


def _build_mock_analysis(video_id: str, creative_id: str, **overrides) -> dict:
    base = VideoAnalysis(
        video_id=video_id,
        creative_id=creative_id,
        hook=HookAnalysis(hook_type="chest", description="giant chest opens", tags=["chest", "gold"]),
        story=StoryAnalysis(structure="failure_growth", description="fail then succeed"),
        reward=RewardAnalysis(reward_type="epic_chest", tags=["chest", "gold_coins"]),
        character=CharacterAnalysis(gender="female", age="adult", clothing="robe", hairstyle="long", profession="mage", action="casting spell", expression="surprised"),
        environment=EnvironmentAnalysis(scene="dungeon", tags=["dark", "treasure"]),
        camera=CameraAnalysis(shot_type="close_up", movement="zoom", tags=["zoom", "shake"]),
        motion=MotionAnalysis(pace="fast", cut_speed="rapid", action_speed="fast", rhythm_changes=["fast to faster"]),
        emotion=EmotionAnalysis(emotions=["surprise", "satisfaction"], intensity="high"),
        cta=CTAAnalysis(cta_type="play_now", timing="end", display_style="button"),
        style=StyleAnalysis(video_style="3d", color_tone="warm", saturation="high"),
        color=StyleAnalysis(video_style="3d", color_tone="warm", saturation="high"),
        audio=AudioAnalysis(has_narration=False, has_sfx=True, has_bgm=True, tempo="fast"),
        raw_response="mock",
    )
    d = base.to_flattened_dict()
    d.update(overrides)
    return d


def _build_metrics(video_id: str, ctr: float, roas: float, spend: float = 500) -> dict:
    return {
        "video_id": video_id,
        "creative_id": f"c_{video_id}",
        "spend": spend,
        "impression": 10000,
        "click": int(ctr * 10000 / 100),
        "ctr": ctr,
        "cpc": 0.5,
        "cpm": 15.0,
        "install": 200,
        "purchase": 50,
        "revenue": spend * roas,
        "roas": roas,
        "ipm": 20.0,
        "cpa": 10.0,
    }


def test_pipeline():
    print("=" * 60)
    print("Video Intelligence Pipeline - Integration Smoke Test")
    print("=" * 60)

    analyses = []
    metrics = []

    high_ctr_variants = [
        {"hook_hook_type": "chest", "story_structure": "failure_growth", "character_gender": "female",
         "camera_movement": "zoom", "style_video_style": "3d", "color_color_tone": "warm",
         "emotion_emotions": ["surprise", "satisfaction"], "reward_reward_type": "epic_chest",
         "cta_cta_type": "play_now", "motion_pace": "fast", "audio_tempo": "fast"},
    ] * 6

    low_ctr_variants = [
        {"hook_hook_type": "mystery", "story_structure": "exploration", "character_gender": "male",
         "camera_movement": "static", "style_video_style": "2d", "color_color_tone": "cool",
         "emotion_emotions": ["fear"], "reward_reward_type": "none",
         "cta_cta_type": "none_visible", "motion_pace": "slow", "audio_tempo": "slow"},
    ] * 6

    for i, overrides in enumerate(high_ctr_variants):
        vid = f"vid_high_{i}"
        analyses.append(_build_mock_analysis(vid, f"c_{vid}", **overrides))
        metrics.append(_build_metrics(vid, ctr=3.5 + i * 0.1, roas=2.0 + i * 0.1))

    for i, overrides in enumerate(low_ctr_variants):
        vid = f"vid_low_{i}"
        analyses.append(_build_mock_analysis(vid, f"c_{vid}", **overrides))
        metrics.append(_build_metrics(vid, ctr=0.3 + i * 0.05, roas=0.3 + i * 0.05))

    output_dir = Path(__file__).resolve().parents[3] / "output" / "video_intelligence" / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "video_records.json").write_text(
        json.dumps([{"video_id": a["video_id"], "creative_id": a["creative_id"]} for a in analyses]),
        encoding="utf-8",
    )
    (output_dir / "video_metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print(f"\n[Phase 3] Feature Statistics with {len(analyses)} videos...")
    stats_engine = FeatureStatisticsEngine(output_dir=output_dir)
    feature_stats = stats_engine.run(analyses, metrics, top_pct=0.5, bottom_pct=0.5)
    total = feature_stats["total_videos"]
    assert total == 12, f"Expected 12 videos, got {total}"
    print(f"  Total videos: {total}")
    print(f"  Segments: {list(feature_stats['segments'].keys())}")
    print("  Phase 3 PASSED")

    print("\n[Phase 4] Pattern Analysis...")
    pattern_analyzer = PatternAnalyzer(output_dir=output_dir)
    patterns = pattern_analyzer.run(feature_stats)
    diff_count = patterns.get("total_differentiated_features", 0)
    print(f"  Differentiated features: {diff_count}")
    assert diff_count > 0, f"Expected some differentiated features between top and bottom, got {diff_count}"
    print("  Phase 4 PASSED")

    print("\n[Phase 5] Direction Report...")
    report_gen = DirectionReportGenerator(output_dir=output_dir)
    report_paths = report_gen.run(patterns, feature_stats)
    md_path = report_paths.get("md_path", "")
    assert md_path and Path(md_path).exists(), f"Report not found at {md_path}"
    assert Path(report_paths.get("json_path", "")).exists()
    print(f"  MD Report: {md_path}")

    report_content = Path(md_path).read_text(encoding="utf-8")
    assert "Video Production Direction Report" in report_content
    assert "Suggested to Continue" in report_content
    assert "Suggested to Reduce" in report_content
    assert "Next Batch Production Directions" in report_content
    print("  Phase 5 PASSED")

    print("\n" + "=" * 60)
    print("ALL PHASES PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    test_pipeline()
