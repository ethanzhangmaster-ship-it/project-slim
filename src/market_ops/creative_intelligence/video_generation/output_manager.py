"""Output Manager - 输出管理器

管理生成结果目录结构：
generated_videos/
  video_id/
    video.mp4
    workflow.json
    prompt.json
    score.json
    metadata.json
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Any

from .models import GenerationResult


class OutputManager:
    """输出管理器"""

    def __init__(self, base_dir: str = ""):
        if not base_dir:
            base_dir = os.path.join(os.getcwd(), "generated_videos")
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save_result(self, result: GenerationResult) -> str:
        """保存生成结果到目录

        Returns:
            输出目录路径
        """
        out_dir = os.path.join(self.base_dir, result.video_id)
        os.makedirs(out_dir, exist_ok=True)

        # 保存元数据
        metadata = {
            "video_id": result.video_id,
            "status": result.status.value,
            "winner_dna_id": result.winner_dna_id,
            "prompt": result.prompt,
            "negative_prompt": result.negative_prompt,
            "seed": result.seed,
            "model_preset": result.model_preset,
            "comfyui_prompt_id": result.comfyui_prompt_id,
            "created_at": result.created_at,
            "completed_at": result.completed_at,
            "error": result.error,
            **result.metadata,
        }
        self._write_json(os.path.join(out_dir, "metadata.json"), metadata)

        # 保存评分
        self._write_json(os.path.join(out_dir, "score.json"), result.score.to_dict())

        # 保存验证结果
        self._write_json(os.path.join(out_dir, "validation.json"), result.validation.to_dict())

        # 保存 prompt
        self._write_json(os.path.join(out_dir, "prompt.json"), {
            "positive": result.prompt,
            "negative": result.negative_prompt,
        })

        # 移动视频文件
        if result.video_path and os.path.exists(result.video_path):
            dest = os.path.join(out_dir, "video.mp4")
            shutil.copy2(result.video_path, dest)
            result.video_path = dest

        # 保存 workflow
        if result.workflow_path and os.path.exists(result.workflow_path):
            dest = os.path.join(out_dir, "workflow.json")
            shutil.copy2(result.workflow_path, dest)
            result.workflow_path = dest

        return out_dir

    def save_generation_report(self, results: list[GenerationResult], report_path: str = "") -> str:
        """生成批量生成报告

        Returns:
            报告文件路径
        """
        if not report_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(self.base_dir, f"generation_report_{timestamp}.json")

        report = {
            "generated_at": datetime.now().isoformat(),
            "total": len(results),
            "success": sum(1 for r in results if r.status.value == "completed"),
            "failed": sum(1 for r in results if r.status.value == "failed"),
            "avg_score": sum(r.score.total_score for r in results) / len(results) if results else 0,
            "videos": [r.to_dict() for r in results],
        }

        self._write_json(report_path, report)
        return report_path

    def list_outputs(self) -> list[dict[str, Any]]:
        """列出所有输出"""
        outputs: list[dict[str, Any]] = []
        for video_id in os.listdir(self.base_dir):
            video_dir = os.path.join(self.base_dir, video_id)
            if not os.path.isdir(video_dir):
                continue
            meta_path = os.path.join(video_dir, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    outputs.append(json.load(f))
        return outputs

    def _write_json(self, path: str, data: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
