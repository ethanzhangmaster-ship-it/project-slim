"""Video Analysis Pipeline 测试

验证从视频文件到分析报告的完整链路。
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from market_ops.creative_intelligence.video_analysis import AnalysisPipeline
from market_ops.creative_intelligence.video_analysis.models import VideoAnalysisReport
from market_ops.creative_intelligence.video_analysis.visual_analyzer import VisualAnalyzer
from market_ops.creative_intelligence.video_analysis.hook_analyzer import HookAnalyzer
from market_ops.creative_intelligence.video_analysis.action_analyzer import ActionAnalyzer
from market_ops.creative_intelligence.video_analysis.gameplay_analyzer import GameplayAnalyzer
from market_ops.creative_intelligence.video_analysis.consistency_checker import ConsistencyChecker
from market_ops.creative_intelligence.video_analysis.ad_score_predictor import AdScorePredictor
from market_ops.creative_intelligence.video_analysis.video_parser import VideoParser
from market_ops.creative_intelligence.video_analysis.report_generator import ReportGenerator


# 测试用的 prompt（P04 V2-001 的高 ROAS DNA）
TEST_PROMPT = (
    "masterpiece, best quality, cinematic vertical shot, gorgeous female witch character close-up, "
    "dazzling magical transformation sequence, brilliant golden and purple glowing particles "
    "swirling around body, radiant light burst, elegant flowing dress transforming into legendary armor, "
    "sparkling gemstone staff, intense magical aura, dynamic camera rotation around character, "
    "slow motion particle fall, dramatic backlighting, high fantasy mobile game cinematic, "
    "1080x1920 vertical format, ultra detailed face, beautiful eyes with magical glow, "
    "silky hair flowing with wind, mobile game advertisement, high quality cinematic, "
    "dynamic motion, engaging gameplay footage, colorful vibrant"
)

TEST_NEGATIVE = (
    "dark forest, landscape, wide shot, scenery only, no character, text, watermark, "
    "blurry, low quality, deformed hands, extra fingers, bad anatomy"
)


def test_visual_analyzer():
    """测试视觉分析器"""
    analyzer = VisualAnalyzer()
    features = analyzer.analyze(TEST_PROMPT)

    print("="*60)
    print("Visual Analyzer Test")
    print(f"  Characters: {features.characters}")
    print(f"  Scenes: {features.scenes}")
    print(f"  Elements: {features.elements}")
    print(f"  Objects: {features.objects}")

    assert "witch" in features.characters, "未检测到 witch 角色"
    assert "magic" in features.scenes, "未检测到 magic 场景"
    assert "particle" in features.elements or "glow" in features.elements, "未检测到特效"

    richness = analyzer.score_visual_richness(features)
    print(f"  Visual Richness Score: {richness:.1f}")
    assert richness > 60, f"视觉丰富度不足: {richness}"

    print("Visual Analyzer Test PASSED!\n")


def test_hook_analyzer():
    """测试 Hook 分析器"""
    analyzer = HookAnalyzer()
    result = analyzer.analyze(TEST_PROMPT)

    print("="*60)
    print("Hook Analyzer Test")
    print(f"  Score: {result.score:.1f}")
    print(f"  Subject Size: {result.subject_size}")
    print(f"  Has Motion: {result.has_motion}")
    print(f"  Has Conflict: {result.has_conflict}")
    print(f"  Has Transformation: {result.has_transformation}")
    print(f"  Reasons: {result.reasons}")

    assert result.score > 70, f"Hook 分过低: {result.score}"
    assert result.has_transformation, "未检测到变身元素"
    assert result.subject_size == "large", f"主体大小不是 large: {result.subject_size}"

    print("Hook Analyzer Test PASSED!\n")


def test_action_analyzer():
    """测试动作分析器"""
    analyzer = ActionAnalyzer()
    result = analyzer.analyze(TEST_PROMPT)

    print("="*60)
    print("Action Analyzer Test")
    print(f"  Score: {result.score:.1f}")
    print(f"  Detected Actions: {result.detected_actions}")
    print(f"  Banned Actions: {result.banned_actions}")
    print(f"  Intensity: {result.action_intensity}")

    assert result.score > 50, f"Action 分过低: {result.score}"
    assert len(result.banned_actions) == 0, f"检测到禁止动作: {result.banned_actions}"

    print("Action Analyzer Test PASSED!\n")


def test_gameplay_analyzer():
    """测试玩法分析器"""
    analyzer = GameplayAnalyzer()
    result = analyzer.analyze(TEST_PROMPT, game_type="merge")

    print("="*60)
    print("Gameplay Analyzer Test")
    print(f"  Score: {result.score:.1f}")
    print(f"  Detected: {result.detected_gameplay}")
    print(f"  Has Merge: {result.has_merge}")
    print(f"  Has Upgrade: {result.has_upgrade}")

    # 这个 prompt 主要是角色展示，不一定有 merge
    assert result.score >= 30, f"Gameplay 分过低: {result.score}"

    print("Gameplay Analyzer Test PASSED!\n")


def test_consistency_checker():
    """测试一致性检查器"""
    checker = ConsistencyChecker()
    result = checker.check(TEST_PROMPT)

    print("="*60)
    print("Consistency Checker Test")
    print(f"  Character: {result.character_consistency:.1f}")
    print(f"  Color: {result.color_consistency:.1f}")
    print(f"  Style: {result.style_consistency:.1f}")
    print(f"  Issues: {result.issues}")

    assert result.character_consistency > 70, f"角色一致性过低: {result.character_consistency}"

    print("Consistency Checker Test PASSED!\n")


def test_ad_score_predictor():
    """测试广告评分预测器"""
    from market_ops.creative_intelligence.video_analysis.visual_analyzer import VisualAnalyzer

    hook = HookAnalyzer().analyze(TEST_PROMPT)
    action = ActionAnalyzer().analyze(TEST_PROMPT)
    gameplay = GameplayAnalyzer().analyze(TEST_PROMPT, "merge")
    consistency = ConsistencyChecker().check(TEST_PROMPT)
    visual = VisualAnalyzer().analyze(TEST_PROMPT)

    predictor = AdScorePredictor()
    result = predictor.predict(hook, action, gameplay, consistency, visual)

    print("="*60)
    print("Ad Score Predictor Test")
    print(f"  Total Score: {result['total_score']:.1f}")
    print(f"  Level: {result['level']}")
    print(f"  Prediction: {result['prediction']}")
    print(f"  Breakdown: {result['breakdown']}")

    assert result["total_score"] > 60, f"总分过低: {result['total_score']}"
    assert result["prediction"] in ("HIGH_POTENTIAL", "MEDIUM_POTENTIAL"), f"预测等级过低: {result['prediction']}"

    print("Ad Score Predictor Test PASSED!\n")


def test_video_parser():
    """测试视频解析器"""
    parser = VideoParser()

    # 测试不存在的文件
    result = parser.parse("nonexistent.mp4")
    assert not result.valid, "不存在的文件应该无效"
    print(f"Non-existent: valid={result.valid}")

    # 测试已有视频
    test_video = "P04-V2-001_wan_00001.mp4"
    if os.path.exists(test_video):
        result = parser.parse(test_video)
        print(f"Existing video: valid={result.valid}, resolution={result.resolution}, "
              f"duration={result.duration:.1f}s")
    else:
        print(f"Test video not found: {test_video}")

    print("Video Parser Test PASSED!\n")


def test_full_pipeline():
    """测试完整管线"""
    pipeline = AnalysisPipeline(output_dir="analysis_test_output")

    test_video = "P04-V2-001_wan_00001.mp4"
    if not os.path.exists(test_video):
        print(f"Skipping full pipeline test - video not found: {test_video}")
        return

    report = pipeline.analyze(
        video_path=test_video,
        prompt_text=TEST_PROMPT,
        game_type="merge",
        winner_dna_id="v2601523",
    )

    print("="*60)
    print("Full Pipeline Test")
    print(f"  Video ID: {report.video_id}")
    print(f"  Total Score: {report.total_score:.1f}")
    print(f"  Level: {report.level}")
    print(f"  Prediction: {report.prediction}")
    print(f"  Hook: {report.hook_score:.1f}")
    print(f"  Action: {report.action_score:.1f}")
    print(f"  Gameplay: {report.gameplay_score:.1f}")
    print(f"  Visual: {report.visual_score:.1f}")
    print(f"  Character: {report.character_score:.1f}")
    print(f"  Consistency: {report.consistency_score:.1f}")
    print(f"  Strengths: {report.strengths}")
    print(f"  Weaknesses: {report.weaknesses}")
    print(f"  Recommendation: {report.recommendation}")
    print(f"  Frames extracted: {len(report.frames)}")

    assert report.total_score > 50, f"总分过低: {report.total_score}"

    print("Full Pipeline Test PASSED!\n")

    # 清理
    import shutil
    shutil.rmtree("analysis_test_output", ignore_errors=True)
    shutil.rmtree("analysis_frames", ignore_errors=True)
    shutil.rmtree("analysis_reports", ignore_errors=True)


if __name__ == "__main__":
    print("Running Video Intelligence Analyzer Tests...\n")
    test_visual_analyzer()
    test_hook_analyzer()
    test_action_analyzer()
    test_gameplay_analyzer()
    test_consistency_checker()
    test_ad_score_predictor()
    test_video_parser()
    test_full_pipeline()
    print("="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
