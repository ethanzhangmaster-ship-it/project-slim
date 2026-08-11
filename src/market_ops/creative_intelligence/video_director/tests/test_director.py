"""Video Director 测试

验证从 Winner DNA 到 ComfyUI Workflow 的完整链路。
"""
from __future__ import annotations

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from market_ops.creative_intelligence.video_director import (
    VideoDirector,
    WinnerDNA,
    GameInfo,
    AdGoal,
)


def test_director_with_p04_winner():
    """测试：用 P04 真实 Winner DNA（v2601523, ROAS 44.68）生成创意方案"""

    # v2601523 的 DNA（ROAS 44.68，角色展示，9X16，16s）
    winner_dna = WinnerDNA(
        theme="juesezhanshi",
        aspect_ratio="9X16",
        lighting="warm cinematic",
        contrast=0.15,
        saturation=0.45,
        hook="character transformation",
        winning_elements=["transformation", "particles", "glow"],
        roas=44.68,
        ctr=0.0,
        cpi=0.0,
        source_video_id="v2601523",
        content_type="juesezhanshi",
        duration="16s",
    )

    game_info = GameInfo(
        game="Merge Witch",
        genre="merge puzzle",
        core_loop="merge items upgrade castle",
        target="US female 25-45",
        art_style="fantasy 2D",
        key_characters=["witch", "dragon"],
        key_items=["magic crystal", "merge orb"],
    )

    ad_goal = AdGoal(
        goal="install",
        duration=15,
        platform="facebook",
        format="9:16",
    )

    director = VideoDirector()
    plan = director.direct(winner_dna, game_info, ad_goal)

    print("=" * 60)
    print(f"Video ID: {plan.video_id}")
    print(f"Quality Score: {plan.quality_score}")
    print(f"ROAS Reference: {plan.roas_reference}")
    print(f"Concept: {plan.creative_concept}")
    print("=" * 60)

    # 验证 Hook
    assert plan.hook["duration"] == "0-3s", "Hook 时间段错误"
    assert plan.hook["visual"] == "character transformation", "Hook 视觉错误"
    print(f"\nHook: {plan.hook}")

    # 验证 Storyboard
    assert len(plan.storyboard) >= 4, "分镜数量不足"
    print(f"\nStoryboard ({len(plan.storyboard)} scenes):")
    for scene in plan.storyboard:
        print(f"  [{scene.time}] {scene.scene}")
        print(f"    Camera: {scene.camera} | Action: {scene.action} | Emotion: {scene.emotion}")

    # 验证 Camera Plan
    assert len(plan.camera_plan) >= 4, "镜头方案数量不足"
    assert plan.camera_plan[0]["intensity"] >= 0.7, "前3秒运镜强度不足"
    print(f"\nCamera Plan:")
    for cam in plan.camera_plan:
        print(f"  [{cam['time']}] {cam['camera']} (intensity: {cam['intensity']})")

    # 验证 Action Plan
    assert len(plan.action_plan) >= 4, "动作方案数量不足"
    print(f"\nAction Plan:")
    for act in plan.action_plan:
        print(f"  [{act['time']}] {act['action']}")

    # 验证 Prompt
    positive = plan.comfyui_workflow.positive
    negative = plan.comfyui_workflow.negative
    assert "masterpiece" in positive, "缺少质量标签"
    assert "dark forest" not in positive, "Prompt 包含低价值关键词"
    assert "glowing particles" in positive or "transformation" in positive, "缺少高 ROAS 特效"
    print(f"\nPositive Prompt (前150字):\n  {positive[:150]}...")
    print(f"\nNegative Prompt:\n  {negative}")

    # 验证 ComfyUI Workflow
    workflow = plan.comfyui_workflow.to_api_json()
    assert "1" in workflow, "缺少 UNETLoader"
    assert "4" in workflow, "缺少正Prompt节点"
    assert "10" in workflow, "缺少视频输出节点"
    print(f"\nComfyUI Workflow: {len(workflow)} nodes")

    # 验证 Flux Keyframe Workflow
    flux_workflow = director.build_flux_keyframe(plan)
    assert "1" in flux_workflow, "Flux Workflow 错误"
    print(f"\nFlux Keyframe Workflow: {len(flux_workflow)} nodes")

    # 验证完整 JSON 输出
    output = plan.to_dict()
    assert "video_id" in output
    assert "storyboard" in output
    assert "comfyui_workflow" in output
    print(f"\n完整输出 keys: {list(output.keys())}")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)

    return plan


def test_batch_generation():
    """测试：批量生成多个创意方案"""

    dnas = [
        WinnerDNA(
            theme="juesezhanshi", aspect_ratio="9X16", lighting="warm", contrast=0.15,
            saturation=0.45, hook="transformation", roas=44.68, source_video_id="v2601523",
            content_type="juesezhanshi", duration="16s",
        ),
        WinnerDNA(
            theme="juesezhanshi", aspect_ratio="1X1", lighting="warm", contrast=0.15,
            saturation=0.45, hook="merge", roas=18.36, source_video_id="v2601163",
            content_type="juesezhanshi", duration="15s",
        ),
        WinnerDNA(
            theme="juqing", aspect_ratio="1X1", lighting="dramatic", contrast=0.2,
            saturation=0.5, hook="dragon attack", roas=3.63, source_video_id="v2601080",
            content_type="juqing", duration="40s",
        ),
    ]

    game_info = GameInfo(
        game="Merge Witch", genre="merge puzzle",
        core_loop="merge items upgrade castle", target="US female 25-45",
        key_characters=["witch"], key_items=["crystal"],
    )
    ad_goal = AdGoal(goal="install", duration=15, platform="facebook", format="9:16")

    director = VideoDirector()
    plans = director.direct_batch(dnas, game_info, ad_goal)

    print(f"\n批量生成结果: {len(plans)} 个方案")
    for i, plan in enumerate(plans):
        print(f"  #{i+1}: {plan.video_id} | Quality: {plan.quality_score:.1f} | "
              f"ROAS Ref: {plan.roas_reference:.2f} | Type: {plan.metadata.get('content_type', '')}")

    # 验证排序
    assert plans[0].quality_score >= plans[-1].quality_score, "未按质量分排序"
    print("\n批量生成测试通过！")


if __name__ == "__main__":
    print("Running Video Director Tests...\n")
    plan = test_director_with_p04_winner()
    test_batch_generation()
