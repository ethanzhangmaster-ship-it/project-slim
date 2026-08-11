"""Video Director Agent - AI 视频创意导演

核心编排器：
Winner DNA + Game Info + Ad Goal
    ↓
Camera Planner + Action Designer + Storyboard Generator + Prompt Builder
    ↓
VideoCreativePlan (含 ComfyUI Workflow)

解决：ComfyUI 能生成视频，但生成的视频没有广告价值。
"""
from __future__ import annotations

import uuid
from typing import Any

from .models import (
    WinnerDNA,
    GameInfo,
    AdGoal,
    VideoCreativePlan,
    ComfyUIWorkflow,
)
from .camera_planner import CameraPlanner
from .action_designer import ActionDesigner
from .storyboard_generator import StoryboardGenerator
from .prompt_builder import PromptBuilder
from .comfyui_adapter import ComfyUIAdapter


class VideoDirector:
    """AI 视频创意导演

    Usage:
        director = VideoDirector()
        plan = director.direct(
            winner_dna=WinnerDNA(...),
            game_info=GameInfo(...),
            ad_goal=AdGoal(...),
        )
        # plan.to_dict() -> 完整创意方案
    """

    def __init__(self):
        self.camera_planner = CameraPlanner()
        self.action_designer = ActionDesigner()
        self.storyboard_generator = StoryboardGenerator()
        self.prompt_builder = PromptBuilder()
        self.comfyui_adapter = ComfyUIAdapter()

    def direct(
        self,
        winner_dna: WinnerDNA,
        game_info: GameInfo,
        ad_goal: AdGoal,
    ) -> VideoCreativePlan:
        """导演核心方法：从 Winner DNA 到完整创意方案

        Args:
            winner_dna: Winner 创意 DNA（来自 Adjust 高 ROAS 视频）
            game_info: 游戏信息
            ad_goal: 广告目标

        Returns:
            VideoCreativePlan 包含 storyboard + prompt + workflow
        """
        video_id = f"VD-{uuid.uuid4().hex[:8].upper()}"

        # Step 1: 镜头规划
        camera_plan = self.camera_planner.plan(winner_dna, ad_goal)

        # Step 2: 动作设计
        action_plan = self.action_designer.design(winner_dna, game_info, ad_goal)

        # Step 3: 分镜生成
        storyboard = self.storyboard_generator.generate(
            winner_dna, game_info, ad_goal,
            camera_plan=camera_plan,
            action_plan=action_plan,
        )

        # Step 4: Prompt 构建
        prompts = self.prompt_builder.build(
            winner_dna, game_info, ad_goal,
            camera_plan=camera_plan,
            action_plan=action_plan,
        )

        # Step 5: ComfyUI Workflow
        comfyui_workflow = ComfyUIWorkflow(
            positive=prompts["positive"],
            negative=prompts["negative"],
            workflow_type="wan2.1_i2v",
            width=832 if ad_goal.format != "9:16" else 576,
            height=480 if ad_goal.format != "9:16" else 1024,
        )

        # Step 6: 质量评分
        quality_score = self._score_quality(
            storyboard, camera_plan, action_plan, winner_dna
        )

        # Step 7: 构建 Hook 信息
        hook = {
            "duration": "0-3s",
            "visual": winner_dna.hook,
            "camera": camera_plan[0]["camera"] if camera_plan else "fast_push_in",
            "action": action_plan[0]["action"] if action_plan else "transformation flash",
        }

        # Step 8: 创意概念
        creative_concept = self._build_concept(winner_dna, game_info)

        plan = VideoCreativePlan(
            video_id=video_id,
            creative_concept=creative_concept,
            hook=hook,
            storyboard=storyboard,
            comfyui_workflow=comfyui_workflow,
            camera_plan=camera_plan,
            action_plan=action_plan,
            quality_score=quality_score,
            roas_reference=winner_dna.roas,
            metadata={
                "flux_positive": prompts.get("flux_positive", ""),
                "prompt_notes": prompts.get("notes", ""),
                "format": ad_goal.format,
                "duration": ad_goal.duration,
                "platform": ad_goal.platform,
                "winner_video_id": winner_dna.source_video_id,
                "content_type": winner_dna.content_type,
            },
        )

        # Step 9: 验证
        self._validate(plan)

        return plan

    def direct_batch(
        self,
        winner_dnas: list[WinnerDNA],
        game_info: GameInfo,
        ad_goal: AdGoal,
    ) -> list[VideoCreativePlan]:
        """批量生成创意方案

        Args:
            winner_dnas: 多个 Winner DNA（ROAS 排序）
            game_info: 游戏信息
            ad_goal: 广告目标

        Returns:
            VideoCreativePlan 列表（按质量分排序）
        """
        plans: list[VideoCreativePlan] = []
        for dna in winner_dnas:
            try:
                plan = self.direct(dna, game_info, ad_goal)
                plans.append(plan)
            except Exception as e:
                print(f"[VideoDirector] 生成失败 {dna.source_video_id}: {e}")
                continue

        # 按质量分排序
        plans.sort(key=lambda p: p.quality_score, reverse=True)
        return plans

    def build_comfyui_workflow(
        self,
        plan: VideoCreativePlan,
        model_preset: str = "wan2.1_i2v_480p",
        image_ref: str = "",
    ) -> dict[str, Any]:
        """为已有 Plan 生成 ComfyUI Workflow JSON"""
        return self.comfyui_adapter.adapt(plan, model_preset, image_ref)

    def build_flux_keyframe(
        self,
        plan: VideoCreativePlan,
        seed: int = 42,
    ) -> dict[str, Any]:
        """生成 Flux 首帧图 Workflow"""
        flux_prompt = plan.metadata.get("flux_positive", plan.comfyui_workflow.positive)
        return self.comfyui_adapter.build_flux_workflow(
            prompt=flux_prompt,
            negative=plan.comfyui_workflow.negative,
            seed=seed,
            filename_prefix=f"{plan.video_id}_flux",
        )

    def _build_concept(self, winner_dna: WinnerDNA, game_info: GameInfo) -> str:
        """构建创意概念描述"""
        character = game_info.key_characters[0] if game_info.key_characters else "主角"
        content_type = winner_dna.content_type or "角色展示"

        concepts = {
            "juesezhanshi": f"{character} 华丽变身，展示传奇皮肤，吸引玩家下载",
            "juqing": f"{character} 史诗冒险，剧情冲突引发好奇",
            "wanfashipin": f"{game_info.core_loop} 玩法展示，合成升级爽感",
            "chongwuzhanshi": f"萌宠进化，从可爱到强大，激发收集欲",
        }
        return concepts.get(winner_dna.content_type, f"{character} 精彩展示，吸引下载")

    def _score_quality(
        self,
        storyboard: list[Any],
        camera_plan: list[dict[str, Any]],
        action_plan: list[dict[str, Any]],
        winner_dna: WinnerDNA,
    ) -> float:
        """评分：评估创意方案质量（0-100）"""
        score = 50.0

        # ROAS 参考加分
        if winner_dna.roas > 10:
            score += 20
        elif winner_dna.roas > 3:
            score += 10
        elif winner_dna.roas > 1:
            score += 5

        # 前3秒强度
        if camera_plan and camera_plan[0].get("intensity", 0) >= 0.8:
            score += 10

        # 动作丰富度
        if action_plan and len(action_plan) >= 4:
            score += 10

        # 分镜完整性
        if len(storyboard) >= 4:
            score += 10

        # 高 ROAS 特效关键词
        positive = winner_dna.theme.lower()
        effect_keywords = ["particle", "glow", "transform", "merge", "flash"]
        for kw in effect_keywords:
            if kw in positive:
                score += 2

        return min(100.0, score)

    def _validate(self, plan: VideoCreativePlan) -> None:
        """验证创意方案"""
        issues: list[str] = []

        # 检查前3秒
        if plan.storyboard:
            first = plan.storyboard[0]
            if "standing" in first.action.lower() and "still" in first.action.lower():
                issues.append("前3秒角色不能静止站立")

        # 检查是否有CTA
        has_cta = any("cta" in s.scene.lower() or "download" in s.scene.lower()
                      for s in plan.storyboard)
        if not has_cta:
            issues.append("缺少 CTA 场景")

        # 检查 Prompt 质量
        positive = plan.comfyui_workflow.positive.lower()
        if "dark forest" in positive or "landscape" in positive:
            issues.append("Prompt 包含低价值关键词（dark forest / landscape）")

        if "character" not in positive and "witch" not in positive:
            issues.append("Prompt 缺少角色主体")

        if issues:
            plan.metadata["validation_issues"] = issues
            print(f"[VideoDirector] {plan.video_id} 验证警告: {issues}")
