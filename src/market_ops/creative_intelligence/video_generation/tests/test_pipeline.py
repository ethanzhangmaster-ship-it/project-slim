"""Generation Pipeline 测试

验证从 Winner DNA 到 GenerationResult 的完整链路。
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from market_ops.creative_intelligence.video_director import (
    WinnerDNA, GameInfo, AdGoal,
)
from market_ops.creative_intelligence.video_generation import (
    GenerationPipeline, ComfyUIClient,
)
from market_ops.creative_intelligence.video_generation.workflow_executor import WorkflowExecutor
from market_ops.creative_intelligence.video_generation.video_validator import VideoValidator
from market_ops.creative_intelligence.video_generation.quality_scorer import QualityScorer
from market_ops.creative_intelligence.video_generation.output_manager import OutputManager


def test_quality_scorer():
    """测试质量评分器"""
    from market_ops.creative_intelligence.video_director import VideoDirector

    director = VideoDirector()
    scorer = QualityScorer()

    winner = WinnerDNA(
        theme="juesezhanshi", aspect_ratio="9X16", lighting="warm",
        contrast=0.15, saturation=0.45, hook="transformation",
        roas=44.68, source_video_id="v2601523",
        content_type="juesezhanshi", duration="16s",
    )
    game = GameInfo(
        game="Merge Witch", genre="merge puzzle",
        core_loop="merge items upgrade castle", target="US female 25-45",
        key_characters=["witch"], key_items=["crystal"],
    )
    goal = AdGoal(goal="install", duration=15, platform="facebook", format="9:16")

    plan = director.direct(winner, game, goal)
    score = scorer.score(plan)

    print("="*60)
    print(f"Quality Score Test")
    print(f"  Hook Score:     {score.hook_score:.1f}")
    print(f"  Action Score:   {score.action_score:.1f}")
    print(f"  Gameplay Score: {score.gameplay_score:.1f}")
    print(f"  Visual Score:   {score.visual_score:.1f}")
    print(f"  Total Score:    {score.total_score:.1f}")
    print("="*60)

    assert score.total_score > 60, f"总分过低: {score.total_score}"
    assert score.hook_score > 50, f"Hook 分过低: {score.hook_score}"
    print("Quality Scorer Test PASSED!\n")


def test_workflow_executor():
    """测试工作流执行器"""
    from market_ops.creative_intelligence.video_director import VideoDirector

    director = VideoDirector()
    executor = WorkflowExecutor()

    winner = WinnerDNA(
        theme="juesezhanshi", aspect_ratio="9X16", lighting="warm",
        contrast=0.15, saturation=0.45, hook="transformation",
        roas=44.68, source_video_id="v2601523",
        content_type="juesezhanshi", duration="16s",
    )
    game = GameInfo(
        game="Merge Witch", genre="merge puzzle",
        core_loop="merge items upgrade castle", target="US female 25-45",
        key_characters=["witch"], key_items=["crystal"],
    )
    goal = AdGoal(goal="install", duration=15, platform="facebook", format="9:16")

    plan = director.direct(winner, game, goal)

    # 测试 video workflow
    wf = executor.build_video_workflow(plan, model_preset="wan2.1_i2v_480p", seed=12345)
    assert "1" in wf, "缺少 UNETLoader"
    assert "4" in wf, "缺少正Prompt"
    assert "10" in wf, "缺少视频输出"
    print(f"Video Workflow: {len(wf)} nodes OK")

    # 测试 flux workflow
    flux_wf = executor.build_flux_workflow(plan, seed=42)
    assert "1" in flux_wf, "Flux Workflow 错误"
    print(f"Flux Workflow: {len(flux_wf)} nodes OK")

    print("Workflow Executor Test PASSED!\n")


def test_comfyui_connection():
    """测试 ComfyUI 连接"""
    client = ComfyUIClient(host="192.168.124.13", port=8188)
    status = client.health_check()

    print("="*60)
    print(f"ComfyUI Connection Test")
    print(f"  Connected: {status.get('ok', False)}")
    if status.get("ok"):
        print(f"  Version: {status.get('version', '')}")
        for d in status.get("devices", []):
            print(f"  Device: {d['name']} | VRAM Free: {d['vram_free_mb']}MB")
    else:
        print(f"  Error: {status.get('error', '')}")
    print("="*60)

    # 不强制要求连接成功（ComfyUI 可能不在线）
    print("ComfyUI Connection Test DONE\n")


def test_video_validator():
    """测试视频验证器"""
    validator = VideoValidator()

    # 测试不存在的文件
    result = validator.validate("nonexistent.mp4")
    assert not result.valid, "不存在的文件应该验证失败"
    print(f"Non-existent file: valid={result.valid}, issues={result.issues}")

    # 测试已有视频（如果有）
    test_video = "P04-V2-001_wan_00001.mp4"
    if os.path.exists(test_video):
        result = validator.validate(test_video)
        print(f"Existing video: valid={result.valid}, "
              f"resolution={result.resolution}, "
              f"duration={result.duration:.1f}s, "
              f"fps={result.fps:.1f}")
    else:
        print(f"Test video not found: {test_video}")

    print("Video Validator Test PASSED!\n")


def test_output_manager():
    """测试输出管理器"""
    from market_ops.creative_intelligence.video_generation.models import (
        GenerationResult, GenerationStatus, VideoScore, VideoValidation,
    )

    out_mgr = OutputManager(base_dir="generated_videos_test")

    result = GenerationResult(
        video_id="TEST001",
        status=GenerationStatus.VALIDATED,
        winner_dna_id="v2601523",
        prompt="test prompt",
        negative_prompt="test negative",
        score=VideoScore(hook_score=90, action_score=85, gameplay_score=80,
                         visual_score=88, total_score=86),
        validation=VideoValidation(valid=True, resolution="832x480",
                                   width=832, height=480, fps=8.0,
                                   duration=10.0, frame_count=80),
    )

    out_dir = out_mgr.save_result(result)
    assert os.path.exists(out_dir), f"输出目录未创建: {out_dir}"
    assert os.path.exists(os.path.join(out_dir, "metadata.json")), "metadata.json 未创建"
    assert os.path.exists(os.path.join(out_dir, "score.json")), "score.json 未创建"
    print(f"Output saved to: {out_dir}")

    # 测试报告
    report_path = out_mgr.save_generation_report([result])
    assert os.path.exists(report_path), f"报告未创建: {report_path}"
    print(f"Report saved to: {report_path}")

    # 清理
    import shutil
    shutil.rmtree("generated_videos_test", ignore_errors=True)
    print("Output Manager Test PASSED!\n")


if __name__ == "__main__":
    print("Running Video Generation Pipeline Tests...\n")
    test_quality_scorer()
    test_workflow_executor()
    test_comfyui_connection()
    test_video_validator()
    test_output_manager()
    print("="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
