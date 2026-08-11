"""Video Generation API - 统一入口

提供单一接口调用整个 V4.3.1 视频生成流程。

用法:
    from src.market_ops.video_generation import VideoGenerationAPI, get_video_api

    api = get_video_api()
    result = api.generate_video(variant)
    results = api.generate_portfolio(portfolio)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .generation_memory import GenerationMemory
from .video_pipeline import VideoPipeline


class VideoGenerationAPI:
    """视频生成 API 统一入口
    
    所有 Agent（V4.2.2 Decision → V4.3.1 Video Generation）统一调用此 API。
    """

    _instance: VideoGenerationAPI | None = None

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
        self.models = models or ["kling", "lovart", "runway", "wan"]

        # 初始化 Pipeline
        resolved_db = db_path or (
            Path(__file__).resolve().parents[3] / "db" / "video_memory.duckdb"
        )
        self.pipeline = VideoPipeline(
            duration=duration,
            platform=platform,
            placement=placement,
            style=style,
            models=models,
            db_path=resolved_db,
        )

        # 独立 Memory 接口
        self.memory = GenerationMemory(resolved_db)

    # ------------------------------------------------------------------
    # 核心生成接口
    # ------------------------------------------------------------------
    def generate_video(
        self,
        variant: dict[str, Any],
        models: list[str] | None = None,
    ) -> dict[str, Any]:
        """生成单个变体的完整视频工作流

        Args:
            variant: V4.2.2 Decision Variant
            models: 目标模型列表

        Returns:
            完整视频生成结果
        """
        output = self.pipeline.run(variant, models)
        return output.to_dict()

    def generate_portfolio(
        self,
        portfolio: dict[str, list[dict[str, Any]]],
        models: list[str] | None = None,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """生成整个 Portfolio 的视频工作流

        Args:
            portfolio: {safe: [...], growth: [...], explore: [...]}
            models: 目标模型列表
            output_dir: 输出目录

        Returns:
            批量生成结果
        """
        results = self.pipeline.run_portfolio(portfolio, models)

        # 展平所有输出
        all_outputs = []
        for tier, outputs in results.items():
            all_outputs.extend(outputs)

        # 导出
        exported = {}
        if output_dir:
            export_dir = Path(output_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            exported = self.pipeline.export_outputs(all_outputs, export_dir)

        # 统计
        stats = self.pipeline.get_stats(all_outputs)

        return {
            "stats": stats,
            "results_by_tier": {
                tier: [o.to_dict() for o in outputs]
                for tier, outputs in results.items()
            },
            "exported_files": {k: str(v) for k, v in exported.items()},
        }

    # ------------------------------------------------------------------
    # Video Prompt 接口
    # ------------------------------------------------------------------
    def generate_video_prompt(self, variant: dict[str, Any]) -> dict[str, Any]:
        """仅生成视频提示词"""
        video_prompt = self.pipeline.prompt_engine.generate(
            variant=variant,
            duration=self.duration,
            platform=self.platform,
            placement=self.placement,
            style=self.style,
        )
        return video_prompt.to_dict()

    # ------------------------------------------------------------------
    # Storyboard 接口
    # ------------------------------------------------------------------
    def generate_storyboard(
        self,
        variant: dict[str, Any],
        hook_type: str = "collection",
        duration: float = 15.0,
    ) -> dict[str, Any]:
        """仅生成分镜"""
        storyboard = self.pipeline.storyboard_engine.generate(
            variant=variant,
            hook_type=hook_type,
            duration=duration,
        )
        return storyboard.to_dict()

    # ------------------------------------------------------------------
    # Workflow 接口
    # ------------------------------------------------------------------
    def generate_workflow(
        self,
        variant: dict[str, Any],
        model: str = "kling",
    ) -> dict[str, Any]:
        """生成单个模型的工作流"""
        output = self.pipeline.run(variant, [model])
        workflow = output.workflows.get(model)
        return workflow.to_dict() if workflow else {}

    def export_comfyui(self, variant: dict[str, Any], output_dir: Path) -> Path:
        """导出 ComfyUI 工作流"""
        output = self.pipeline.run(variant, ["comfyui"])
        workflow = output.workflows.get("comfyui")
        if workflow:
            return self.pipeline.workflow_builder.export(workflow, output_dir)
        return output_dir

    def export_kling(self, variant: dict[str, Any], output_dir: Path) -> Path:
        """导出 Kling 任务"""
        output = self.pipeline.run(variant, ["kling"])
        workflow = output.workflows.get("kling")
        if workflow:
            return self.pipeline.workflow_builder.export(workflow, output_dir)
        return output_dir

    def export_wan(self, variant: dict[str, Any], output_dir: Path) -> Path:
        """导出 Wan 任务"""
        output = self.pipeline.run(variant, ["wan"])
        workflow = output.workflows.get("wan")
        if workflow:
            return self.pipeline.workflow_builder.export(workflow, output_dir)
        return output_dir

    # ------------------------------------------------------------------
    # Memory 接口
    # ------------------------------------------------------------------
    def save_video_result(self, video_id: str, performance: dict[str, Any]) -> None:
        """保存视频投放结果"""
        self.memory.update_performance(
            video_id=video_id,
            ctr=performance.get("ctr"),
            cvr=performance.get("cvr"),
            roas=performance.get("roas"),
            ipm=performance.get("ipm"),
            spend=performance.get("spend"),
            status=performance.get("status"),
        )

    def get_top_videos(self, metric: str = "roas", limit: int = 10) -> list[dict[str, Any]]:
        """获取表现最好的视频"""
        return self.memory.get_top_videos(metric, limit)

    def get_winning_videos(self) -> list[dict[str, Any]]:
        """获取 Winner 视频"""
        return self.memory.get_winning_videos()

    def mark_winner(self, video_id: str, winner_score: float) -> None:
        """标记 Winner"""
        self.memory.mark_winner(video_id, winner_score)

    def learn_from_winners(self) -> dict[str, Any]:
        """从 Winner 学习"""
        return self.memory.learn_from_winners()

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def set_duration(self, duration: float) -> None:
        """设置视频时长"""
        self.duration = duration
        self.pipeline.duration = duration

    def set_placement(self, placement: str) -> None:
        """设置版位"""
        self.placement = placement
        self.pipeline.placement = placement

    def set_style(self, style: str) -> None:
        """设置风格"""
        self.style = style
        self.pipeline.style = style

    def set_models(self, models: list[str]) -> None:
        """设置目标模型"""
        self.models = models
        self.pipeline.models = models

    # ------------------------------------------------------------------
    # 模型列表
    # ------------------------------------------------------------------
    def list_models(self) -> list[str]:
        """列出支持的模型"""
        return self.pipeline.model_adapter.list_models()


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------
def get_video_api(
    duration: float = 15.0,
    placement: str = "reels",
    style: str = "pixar",
) -> VideoGenerationAPI:
    """获取 VideoGenerationAPI 单例"""
    if VideoGenerationAPI._instance is None:
        VideoGenerationAPI._instance = VideoGenerationAPI(
            duration=duration,
            placement=placement,
            style=style,
        )
    return VideoGenerationAPI._instance