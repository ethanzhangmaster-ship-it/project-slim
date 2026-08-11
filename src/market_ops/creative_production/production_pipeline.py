"""Production Pipeline - 统一生产流水线

按 PRD 第十六节定义的标准流程：
Decision
↓ Creative Director
↓ Creative Script
↓ Storyboard
↓ Shot List
↓ Asset Planner
↓ Asset Consistency
↓ Camera
↓ Motion
↓ Editor Timeline
↓ Workflow
↓ Export
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .creative_director import CreativeDirector
from .creative_script import CreativeScriptEngine
from .storyboard_engine import StoryboardEngine
from .shot_generator import ShotGenerator
from .asset_planner import AssetPlanner
from .asset_consistency import AssetConsistency
from .camera_language import CameraLanguageEngine
from .motion_engine import MotionEngine
from .editor_timeline import EditorTimeline
from .video_model_adapter import VideoModelAdapter
from .workflow_builder import WorkflowBuilder
from .production_memory import ProductionMemory


@dataclass
class ProductionOutput:
    """完整生产输出"""
    variant_id: str
    strategy: Any
    script: Any
    storyboard: Any
    shot_list: Any
    plan: Any
    consistency: Any
    timeline: Any
    workflow: Any
    model_tasks: dict[str, list[Any]] = field(default_factory=dict)  # model → tasks
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "variant_id": self.variant_id,
            "strategy": self.strategy.to_dict() if hasattr(self.strategy, "to_dict") else self.strategy,
            "script": self.script.to_dict() if hasattr(self.script, "to_dict") else self.script,
            "storyboard": self.storyboard.to_dict() if hasattr(self.storyboard, "to_dict") else self.storyboard,
            "shot_list": self.shot_list.to_dict() if hasattr(self.shot_list, "to_dict") else self.shot_list,
            "plan": self.plan.to_dict() if hasattr(self.plan, "to_dict") else self.plan,
            "consistency": self.consistency.to_dict() if hasattr(self.consistency, "to_dict") else self.consistency,
            "timeline": self.timeline.to_dict() if hasattr(self.timeline, "to_dict") else self.timeline,
            "workflow": self.workflow.to_dict() if hasattr(self.workflow, "to_dict") else self.workflow,
            "model_tasks": {
                m: [t.to_dict() for t in tasks]
                for m, tasks in self.model_tasks.items()
            },
            "metadata": self.metadata,
        }
        return out


class ProductionPipeline:
    """统一生产流水线"""

    def __init__(
        self,
        output_dir: str = "output/creative_production",
        memory: ProductionMemory | None = None,
        budget_usd: float = 10.0,
    ):
        self.output_dir = output_dir
        self.budget_usd = budget_usd

        # 初始化所有模块
        self.director = CreativeDirector()
        self.script_engine = CreativeScriptEngine()
        self.storyboard_engine = StoryboardEngine()
        self.shot_generator = ShotGenerator()
        self.asset_planner = AssetPlanner()
        self.consistency_engine = AssetConsistency()
        self.camera_engine = CameraLanguageEngine()
        self.motion_engine = MotionEngine()
        self.editor = EditorTimeline()
        self.model_adapter = VideoModelAdapter()
        self.workflow_builder = WorkflowBuilder()
        self.memory = memory or ProductionMemory(
            os.path.join(output_dir, "production_memory.duckdb")
        )

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(
        self,
        variant: dict[str, Any],
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "feed",
        country: str = "US",
    ) -> ProductionOutput:
        """运行完整生产流程

        Args:
            variant: V4.2.2 Decision Variant
            duration: 视频时长
            platform: 平台
            placement: 版位
            country: 国家
        """
        variant_id = variant.get("variant_id", "unknown")

        # 1. Creative Director
        strategy = self.director.direct(
            variant=variant,
            duration=duration,
            platform=platform,
            placement=placement,
            country=country,
        )

        # 2. Creative Script
        script = self.script_engine.generate(strategy, variant)

        # 3. Storyboard
        storyboard = self.storyboard_engine.build(script, strategy, platform=platform)

        # 4. Shot Generator
        shot_list = self.shot_generator.generate(storyboard, strategy, variant)

        # 5. Asset Planner
        plan = self.asset_planner.plan(shot_list, strategy, variant, budget_usd=self.budget_usd)

        # 6. Asset Consistency
        consistency = self.consistency_engine.build_profile(variant, strategy)
        # 把一致性配置附加到 shot metadata（用于后续 adapter）
        for shot in shot_list.shots:
            cons = self.consistency_engine.apply_to_shot(consistency, shot)
            shot.metadata.update(cons)

        # 7. Camera + Motion（已通过 shot_generator 注入；这里返回建议）
        camera_recs = {
            scene.scene_id: [c.to_dict() for c in self.camera_engine.recommend(
                scene.segment_type,
                gameplay=strategy.gameplay,
                emotion=strategy.emotion,
                editing_style=strategy.editing_style,
            )]
            for scene in storyboard.scenes
        }
        motion_recs = {
            scene.scene_id: self.motion_engine.build_motion_prompt(scene.segment_type)
            for scene in storyboard.scenes
        }

        # 8. Editor Timeline
        timeline = self.editor.build(shot_list, plan, strategy, aspect_ratio=storyboard.aspect_ratio)

        # 9. Workflow Builder
        workflow = self.workflow_builder.build(shot_list, plan, strategy)

        # 10. Model Adapter（按模型分组）
        model_tasks: dict[str, list[Any]] = {}
        for assign in plan.assignments:
            if assign.source in ("ai", "image_anim"):
                shot = next((s for s in shot_list.shots if s.shot_id == assign.shot_id), None)
                if shot is None:
                    continue
                task = self.model_adapter.adapt(
                    shot=shot,
                    model=assign.model or "kling",
                    aspect_ratio=storyboard.aspect_ratio,
                )
                model_tasks.setdefault(task.model, []).append(task)

        # 11. 持久化到 memory
        try:
            self.memory.save_strategy(strategy)
            self.memory.save_script(script)
            self.memory.save_storyboard(storyboard)
            self.memory.save_shot_list(shot_list)
            self.memory.save_production_plan(plan)
            self.memory.save_workflow(workflow)
        except Exception:
            pass

        return ProductionOutput(
            variant_id=variant_id,
            strategy=strategy,
            script=script,
            storyboard=storyboard,
            shot_list=shot_list,
            plan=plan,
            consistency=consistency,
            timeline=timeline,
            workflow=workflow,
            model_tasks=model_tasks,
            metadata={
                "camera_recommendations": camera_recs,
                "motion_recommendations": motion_recs,
                "duration": duration,
                "platform": platform,
                "placement": placement,
                "country": country,
            },
        )

    def run_batch(
        self,
        variants: list[dict[str, Any]],
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "feed",
        country: str = "US",
    ) -> list[ProductionOutput]:
        """批量运行"""
        results = []
        for v in variants:
            try:
                results.append(self.run(v, duration, platform, placement, country))
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export(
        self,
        output: ProductionOutput,
        subdir: str | None = None,
    ) -> dict[str, str]:
        """导出所有产物到目录"""
        target_dir = self.output_dir
        if subdir:
            target_dir = os.path.join(self.output_dir, subdir)
        os.makedirs(target_dir, exist_ok=True)
        results: dict[str, str] = {}

        vid = output.variant_id

        # 1. creative_script.json
        p = os.path.join(target_dir, "creative_script.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(output.script.to_dict(), f, ensure_ascii=False, indent=2)
        results["creative_script"] = p

        # 2. storyboard.json
        p = os.path.join(target_dir, "storyboard.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(output.storyboard.to_dict(), f, ensure_ascii=False, indent=2)
        results["storyboard"] = p

        # 3. shot_list.json
        p = os.path.join(target_dir, "shot_list.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(output.shot_list.to_dict(), f, ensure_ascii=False, indent=2)
        results["shot_list"] = p

        # 4. asset_plan.json
        p = os.path.join(target_dir, "asset_plan.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(output.plan.to_dict(), f, ensure_ascii=False, indent=2)
        results["asset_plan"] = p

        # 5. timeline + 各种编辑器格式
        editor_dir = os.path.join(target_dir, "timeline")
        os.makedirs(editor_dir, exist_ok=True)
        timeline_paths = self.editor.export_all(output.timeline, editor_dir)
        results.update({f"timeline_{k}": v for k, v in timeline_paths.items()})

        # 6. workflow.json + 各模型专属
        workflow_dir = os.path.join(target_dir, "workflows")
        os.makedirs(workflow_dir, exist_ok=True)
        wf_path = self.workflow_builder.export_main(
            output.workflow,
            os.path.join(workflow_dir, "workflow.json"),
        )
        results["workflow"] = wf_path

        # 各执行器
        per_model = self.workflow_builder.export_per_model(output.workflow, workflow_dir)
        results.update({f"workflow_{m}": p for m, p in per_model.items()})

        # 7. 各模型 task JSON
        model_dir = os.path.join(target_dir, "model_tasks")
        os.makedirs(model_dir, exist_ok=True)
        for model_name, tasks in output.model_tasks.items():
            p = os.path.join(model_dir, f"{model_name}_tasks.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in tasks], f, ensure_ascii=False, indent=2)
            results[f"model_{model_name}"] = p

        # 8. consistency.json
        p = os.path.join(target_dir, "consistency.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(output.consistency.to_dict(), f, ensure_ascii=False, indent=2)
        results["consistency"] = p

        # 9. production_report.md
        p = os.path.join(target_dir, "production_report.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(self._generate_report(output))
        results["report"] = p

        return results

    # ------------------------------------------------------------------
    # 报告
    # ------------------------------------------------------------------
    def _generate_report(self, output: ProductionOutput) -> str:
        """生成生产报告（中文）"""
        s = output.strategy
        plan = output.plan
        wf = output.workflow
        lines = [
            f"# Facebook 创意生产报告 - {output.variant_id}",
            f"",
            f"## 创意总监指令",
            f"- 目标: {s.objective}",
            f"- Hook: {s.hook}",
            f"- 情绪: {s.emotion}",
            f"- 时长: {s.duration} 秒",
            f"- 优先级: P{s.priority}",
            f"- 平台: {s.platform} / {s.placement}",
            f"- 国家: {s.country}",
            f"",
            f"## 脚本",
            f"- 段落数: {len(output.script.segments)}",
            f"",
        ]
        for seg in output.script.segments:
            lines.append(f"### {seg.segment_type} [{seg.start_time}-{seg.end_time}秒]")
            lines.append(f"- 画面: {seg.visual}")
            lines.append(f"- 动作: {seg.action}")
            lines.append(f"- 脚本: {seg.text}")
            lines.append(f"")

        lines.extend([
            f"## 分镜",
            f"- 平台: {output.storyboard.platform}",
            f"- 画幅: {output.storyboard.aspect_ratio}",
            f"- 场景数: {len(output.storyboard.scenes)}",
            f"",
            f"## 镜头列表",
            f"- 总镜头: {output.shot_list.total_shots}",
            f"- 总时长: {output.shot_list.total_duration} 秒",
            f"",
            f"## 素材分配",
            f"- 总成本: ${plan.total_estimated_cost}",
            f"- 估算耗时: {plan.total_estimated_time_sec/60:.1f} 分钟",
            f"- 需人工审核: {plan.requires_human_review_count} 镜头",
            f"",
            f"### 来源分布",
        ])
        for src, n in plan.source_summary.items():
            lines.append(f"- {src}: {n} 镜头")
        lines.append(f"")

        lines.extend([
            f"## 工作流",
            f"- 总步骤: {wf.total_steps}",
            f"- 估算耗时: {wf.total_estimated_duration_sec/60:.1f} 分钟",
            f"",
            f"### 执行器分布",
        ])
        for ex, n in wf.executors_used.items():
            lines.append(f"- {ex}: {n} 步")
        lines.append(f"")

        if output.model_tasks:
            lines.append(f"## AI 模型任务")
            for model, tasks in output.model_tasks.items():
                lines.append(f"- {model}: {len(tasks)} 任务")
            lines.append(f"")

        lines.extend([
            f"## 时间线",
            f"- 分辨率: {output.timeline.resolution}",
            f"- FPS: {output.timeline.fps}",
            f"- 时长: {output.timeline.total_duration} 秒",
            f"- 视频轨: {len(output.timeline.video_tracks)}",
            f"- 音频轨: {len(output.timeline.audio_tracks)}",
            f"- 字幕轨: {len(output.timeline.subtitle_tracks)}",
        ])

        return "\n".join(lines)
