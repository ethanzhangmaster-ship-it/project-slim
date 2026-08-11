"""Video Pipeline - 视频生成统一流程

完整流程:
Decision → Video Prompt → Storyboard → Shot List → Camera → Motion → Workflow → Validate → Export
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .character_consistency import CharacterConsistency
from .generation_memory import GenerationMemory
from .shot_generator import ShotGenerator, ShotList
from .storyboard_engine import StoryboardEngine, VideoStoryboard
from .video_model_adapter import VideoModelAdapter
from .video_prompt_engine import VideoPrompt, VideoPromptEngine
from .workflow_builder import VideoWorkflow, WorkflowBuilder


@dataclass
class VideoOutput:
    """视频生成输出"""
    variant_id: str
    video_prompt: VideoPrompt | None = None
    storyboard: VideoStoryboard | None = None
    shot_list: ShotList | None = None
    workflows: dict[str, VideoWorkflow] = field(default_factory=dict)
    passed: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "video_prompt": self.video_prompt.to_dict() if self.video_prompt else None,
            "storyboard": self.storyboard.to_dict() if self.storyboard else None,
            "shot_list": self.shot_list.to_dict() if self.shot_list else None,
            "workflows": {k: v.to_dict() for k, v in self.workflows.items()},
            "passed": self.passed,
            "errors": self.errors,
        }


class VideoPipeline:
    """视频生成流水线
    
    将 V4.2.2 Decision Variant 通过完整流程转换为可执行的视频生成工作流。
    """

    def __init__(
        self,
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "reels",
        style: str = "pixar",
        models: list[str] | None = None,
        db_path: str | Path | None = None,
    ):
        self.duration = duration
        self.platform = platform
        self.placement = placement
        self.style = style
        self.models = models or ["kling", "lovart", "runway"]

        # 初始化各子模块
        self.prompt_engine = VideoPromptEngine()
        self.storyboard_engine = StoryboardEngine()
        self.shot_generator = ShotGenerator()
        self.model_adapter = VideoModelAdapter()
        self.workflow_builder = WorkflowBuilder()
        self.character_consistency = CharacterConsistency()
        self.memory = GenerationMemory(db_path) if db_path else None

    # ------------------------------------------------------------------
    # 核心流程
    # ------------------------------------------------------------------
    def run(
        self,
        variant: dict[str, Any],
        models: list[str] | None = None,
        apply_character_consistency: bool = True,
        save_to_memory: bool = True,
    ) -> VideoOutput:
        """运行完整视频生成流程

        Args:
            variant: V4.2.2 Decision Variant
            models: 目标模型列表
            apply_character_consistency: 是否应用角色一致性
            save_to_memory: 是否保存到记忆

        Returns:
            VideoOutput
        """
        models = models or self.models
        output = VideoOutput(variant_id=variant.get("variant_id", "unknown"))
        errors: list[str] = []

        # Step 1: Video Prompt Engine
        try:
            video_prompt = self.prompt_engine.generate(
                variant=variant,
                duration=self.duration,
                platform=self.platform,
                placement=self.placement,
                style=self.style,
            )
            output.video_prompt = video_prompt
        except Exception as e:
            errors.append(f"Video Prompt Engine 失败: {e}")
            output.errors = errors
            return output

        # Step 2: Storyboard Engine
        try:
            storyboard = self.storyboard_engine.generate(
                variant=variant,
                video_prompt=video_prompt.master_prompt,
                hook_type=video_prompt.hook_type,
                duration=self.duration,
            )
            output.storyboard = storyboard
        except Exception as e:
            errors.append(f"Storyboard Engine 失败: {e}")

        # Step 3: Shot Generator
        if output.storyboard:
            try:
                shot_list = self.shot_generator.generate(
                    storyboard=output.storyboard.to_dict(),
                    variant=variant,
                    video_prompt=video_prompt.master_prompt,
                )
                output.shot_list = shot_list
            except Exception as e:
                errors.append(f"Shot Generator 失败: {e}")

        # Step 4: Character Consistency
        if apply_character_consistency and output.shot_list:
            try:
                character = self.character_consistency.get_character_from_dna(
                    variant.get("dna", {})
                )
                shots = output.shot_list.to_dict().get("shots", [])
                consistent_shots = self.character_consistency.apply_to_all_shots(
                    shots, character, strength=0.8
                )
                # 更新 shot_list
                output.shot_list.shots = [
                    self.shot_generator._build_shot(
                        shot_id=s.get("shot_id"),
                        scene_number=s.get("scene_number"),
                        scene_type=s.get("scene_type"),
                        duration=s.get("duration"),
                        character=s.get("character"),
                        creature_type=s.get("creature"),
                        environment=s.get("environment"),
                        lighting=s.get("lighting"),
                        scene_data=s,
                        video_prompt=video_prompt.master_prompt,
                    )
                    for s in consistent_shots
                ]
            except Exception:
                pass

        # Step 5: Workflow Builder
        if output.shot_list:
            try:
                workflows = {}
                for model in models:
                    workflow = self.workflow_builder.build(
                        shot_list=output.shot_list.to_dict(),
                        model=model,
                        placement=self.placement,
                        aspect_ratio="9:16" if self.placement in ["reels", "stories"] else "4:5",
                    )
                    workflows[model] = workflow
                output.workflows = workflows
            except Exception as e:
                errors.append(f"Workflow Builder 失败: {e}")

        # Step 6: 验证
        output.passed = len(errors) == 0
        output.errors = errors

        # Step 7: 保存到记忆
        if save_to_memory and self.memory and output.passed:
            try:
                video_id = f"video_{output.variant_id}"
                self.memory.save_video(
                    video_id=video_id,
                    variant_id=output.variant_id,
                    video_prompt=video_prompt.master_prompt,
                    storyboard=output.storyboard.to_dict() if output.storyboard else None,
                    shot_list=output.shot_list.to_dict() if output.shot_list else None,
                    workflow={k: v.workflow_json for k, v in output.workflows.items()},
                    model=models[0] if models else "",
                    platform=self.platform,
                    placement=self.placement,
                    duration=self.duration,
                    hook_type=video_prompt.hook_type,
                    style=self.style,
                )
            except Exception:
                pass

        return output

    # ------------------------------------------------------------------
    # 批量流程
    # ------------------------------------------------------------------
    def run_batch(
        self,
        variants: list[dict[str, Any]],
        models: list[str] | None = None,
    ) -> list[VideoOutput]:
        """批量运行"""
        results = []
        for v in variants:
            try:
                output = self.run(v, models)
                results.append(output)
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # Portfolio 流程
    # ------------------------------------------------------------------
    def run_portfolio(
        self,
        portfolio: dict[str, list[dict[str, Any]]],
        models: list[str] | None = None,
    ) -> dict[str, list[VideoOutput]]:
        """运行 Portfolio 中所有变体"""
        results = {}
        for tier, variants in portfolio.items():
            tier_results = []
            for v in variants:
                try:
                    output = self.run(v, models)
                    tier_results.append(output)
                except Exception:
                    continue
            results[tier] = tier_results
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export_outputs(
        self,
        outputs: list[VideoOutput],
        output_dir: Path,
    ) -> dict[str, Path]:
        """导出所有生成结果"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported = {}

        # 1. Video Prompts
        prompts_data = []
        for o in outputs:
            if o.video_prompt:
                prompts_data.append(o.video_prompt.to_dict())
        prompts_path = output_dir / "video_prompts.json"
        with open(prompts_path, "w", encoding="utf-8") as f:
            json.dump(prompts_data, f, ensure_ascii=False, indent=2)
        exported["prompts"] = prompts_path

        # 2. Storyboards
        storyboards_data = []
        for o in outputs:
            if o.storyboard:
                storyboards_data.append(o.storyboard.to_dict())
        storyboard_path = output_dir / "storyboards.json"
        with open(storyboard_path, "w", encoding="utf-8") as f:
            json.dump(storyboards_data, f, ensure_ascii=False, indent=2)
        exported["storyboards"] = storyboard_path

        # 3. Shot Lists
        shots_data = []
        for o in outputs:
            if o.shot_list:
                shots_data.append(o.shot_list.to_dict())
        shots_path = output_dir / "shot_lists.json"
        with open(shots_path, "w", encoding="utf-8") as f:
            json.dump(shots_data, f, ensure_ascii=False, indent=2)
        exported["shots"] = shots_path

        # 4. Workflows (按模型分目录)
        workflows_dir = output_dir / "workflows"
        workflows_dir.mkdir(exist_ok=True)

        model_outputs = {}
        for o in outputs:
            for model, workflow in o.workflows.items():
                model_dir = workflows_dir / model
                model_dir.mkdir(exist_ok=True)
                wf_path = model_dir / f"{workflow.workflow_id}.json"
                with open(wf_path, "w", encoding="utf-8") as f:
                    json.dump(workflow.workflow_json, f, ensure_ascii=False, indent=2)
                model_outputs[model] = model_dir

        exported["workflows"] = workflows_dir

        # 5. Generation Report
        report = self._build_report(outputs)
        report_path = output_dir / "video_generation_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        exported["report"] = report_path

        return exported

    def _build_report(self, outputs: list[VideoOutput]) -> str:
        """构建生成报告"""
        total = len(outputs)
        passed = sum(1 for o in outputs if o.passed)

        lines = [
            "# Video Generation Report (V4.3.1)",
            "",
            f"- **总变体数**: {total}",
            f"- **通过验证**: {passed}",
            f"- **失败**: {total - passed}",
            f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 生成详情",
            "",
        ]

        for o in outputs:
            status = "✅" if o.passed else "❌"
            lines.append(f"### {status} {o.variant_id}")
            if o.video_prompt:
                lines.append(f"- **Hook**: {o.video_prompt.hook_type}")
                lines.append(f"- **时长**: {o.video_prompt.duration}s")
                lines.append(f"- **提示词长度**: {len(o.video_prompt.master_prompt)}")
            if o.shot_list:
                lines.append(f"- **镜头数**: {len(o.shot_list.shots)}")
            if o.workflows:
                lines.append(f"- **工作流模型**: {list(o.workflows.keys())}")
            if o.errors:
                lines.append(f"- **错误**: {', '.join(o.errors)}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def get_stats(self, outputs: list[VideoOutput]) -> dict[str, Any]:
        """获取生成统计"""
        return {
            "total_variants": len(outputs),
            "passed": sum(1 for o in outputs if o.passed),
            "failed": sum(1 for o in outputs if not o.passed),
            "total_shots": sum(len(o.shot_list.shots) for o in outputs if o.shot_list),
            "total_workflows": sum(len(o.workflows) for o in outputs),
            "hook_types": list(set(
                o.video_prompt.hook_type
                for o in outputs
                if o.video_prompt
            )),
            "models_used": list(set(
                m for o in outputs for m in o.workflows.keys()
            )),
        }