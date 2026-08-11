"""Workflow Builder - 工作流构建器

自动拼装:
Prompt → Negative Prompt → Reference → Motion → Camera → Duration → Model Config → Workflow

最后输出 workflow.json，直接可执行。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .shot_generator import ShotList
from .video_model_adapter import VideoModelAdapter, VideoModelTask


@dataclass
class VideoWorkflow:
    """视频工作流"""
    workflow_id: str
    variant_id: str
    model: str
    tasks: list[VideoModelTask] = field(default_factory=list)
    workflow_json: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "variant_id": self.variant_id,
            "model": self.model,
            "tasks": [t.to_dict() for t in self.tasks],
            "workflow_json": self.workflow_json,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class WorkflowBuilder:
    """工作流构建器
    
    自动拼装完整的视频生成工作流。
    """

    def __init__(self):
        self.adapter = VideoModelAdapter()

    # ------------------------------------------------------------------
    # 核心构建方法
    # ------------------------------------------------------------------
    def build(
        self,
        shot_list: ShotList | dict[str, Any],
        model: str = "kling",
        placement: str = "feed",
        aspect_ratio: str = "9:16",
        character_ref: str = "",
    ) -> VideoWorkflow:
        """构建完整工作流

        Args:
            shot_list: 镜头列表
            model: 目标模型
            placement: 版位
            aspect_ratio: 画面比例
            character_ref: 角色参考图片路径

        Returns:
            VideoWorkflow
        """
        if isinstance(shot_list, ShotList):
            shot_list_dict = shot_list.to_dict()
        else:
            shot_list_dict = shot_list

        variant_id = shot_list_dict.get("variant_id", "unknown")
        shots = shot_list_dict.get("shots", [])

        # 适配所有镜头
        tasks = []
        for shot in shots:
            task = self.adapter.adapt_shot(shot, model, placement, aspect_ratio)
            tasks.append(task)

        # 构建工作流 JSON
        workflow_json = self._build_workflow_json(tasks, model, character_ref)

        return VideoWorkflow(
            workflow_id=f"wf_{variant_id}_{model}",
            variant_id=variant_id,
            model=model,
            tasks=tasks,
            workflow_json=workflow_json,
            created_at=datetime.now().isoformat(),
            metadata={
                "total_tasks": len(tasks),
                "total_duration": sum(t.duration for t in tasks),
                "placement": placement,
                "aspect_ratio": aspect_ratio,
                "character_ref": character_ref,
            },
        )

    def _build_workflow_json(
        self,
        tasks: list[VideoModelTask],
        model: str,
        character_ref: str,
    ) -> dict[str, Any]:
        """构建工作流 JSON"""
        workflow = {
            "metadata": {
                "model": model,
                "created_at": datetime.now().isoformat(),
                "total_duration": sum(t.duration for t in tasks),
                "task_count": len(tasks),
            },
            "tasks": [],
            "execution_order": [],
            "merge_config": {
                "output_format": "mp4",
                "fps": 30,
                "quality": "high",
            },
        }

        for i, task in enumerate(tasks):
            # 根据模型构建任务格式
            if model.lower() == "comfyui":
                task_json = self.adapter.build_comfyui_workflow(task, character_ref)
            elif model.lower() == "kling":
                task_json = self.adapter.build_kling_task(task)
            elif model.lower() == "wan":
                task_json = self.adapter.build_wan_task(task)
            elif model.lower() == "runway":
                task_json = self.adapter.build_runway_task(task)
            elif model.lower() == "lovart":
                task_json = self.adapter.build_lovart_task(task)
            else:
                task_json = {"prompt": task.prompt, "duration": task.duration}

            workflow["tasks"].append(task_json)
            workflow["execution_order"].append(task.task_id)

        return workflow

    # ------------------------------------------------------------------
    # 批量构建
    # ------------------------------------------------------------------
    def build_all_models(
        self,
        shot_list: ShotList | dict[str, Any],
        placement: str = "feed",
        aspect_ratio: str = "9:16",
        models: list[str] | None = None,
    ) -> dict[str, VideoWorkflow]:
        """为所有模型构建工作流"""
        if models is None:
            models = self.adapter.list_models()

        results = {}
        for model in models:
            results[model] = self.build(shot_list, model, placement, aspect_ratio)
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export(
        self,
        workflow: VideoWorkflow,
        output_dir: Path,
    ) -> Path:
        """导出工作流"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 主工作流文件
        workflow_path = output_dir / f"{workflow.workflow_id}.json"
        with open(workflow_path, "w", encoding="utf-8") as f:
            json.dump(workflow.workflow_json, f, ensure_ascii=False, indent=2)

        # 任务详情
        tasks_path = output_dir / f"{workflow.workflow_id}_tasks.json"
        with open(tasks_path, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in workflow.tasks], f, ensure_ascii=False, indent=2)

        return workflow_path

    def export_all_models(
        self,
        workflows: dict[str, VideoWorkflow],
        output_dir: Path,
    ) -> dict[str, Path]:
        """导出所有模型的工作流"""
        output_dir = Path(output_dir)
        paths = {}

        for model, workflow in workflows.items():
            model_dir = output_dir / model
            path = self.export(workflow, model_dir)
            paths[model] = path

        return paths

    # ------------------------------------------------------------------
    # 执行摘要
    # ------------------------------------------------------------------
    def generate_execution_summary(self, workflow: VideoWorkflow) -> str:
        """生成执行摘要"""
        lines = [
            f"# Video Workflow: {workflow.workflow_id}",
            f"",
            f"- **Model**: {workflow.model}",
            f"- **Variant**: {workflow.variant_id}",
            f"- **Tasks**: {len(workflow.tasks)}",
            f"- **Total Duration**: {sum(t.duration for t in workflow.tasks)}s",
            f"- **Created**: {workflow.created_at}",
            f"",
            f"## Task List",
            f"",
        ]

        for task in workflow.tasks:
            lines.extend([
                f"### {task.shot_id}",
                f"- Duration: {task.duration}s",
                f"- Prompt: {task.prompt[:100]}...",
                f"- Camera: {task.camera_motion}",
                f"",
            ])

        return "\n".join(lines)