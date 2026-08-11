"""Production API - 统一入口 API

按 PRD 第十七节定义：
api = CreativeProductionAPI()

api.generate_script(variant)
api.generate_storyboard(variant)
api.generate_shots(variant)
api.plan_assets(variant)
api.build_timeline(variant)
api.build_workflow(variant)
api.export_kling(variant)
api.export_runway(variant)
api.export_comfyui(variant)
api.learn(result)
"""
from __future__ import annotations

import os
from typing import Any

from .creative_director import CreativeDirector
from .creative_script import CreativeScriptEngine
from .storyboard_engine import StoryboardEngine
from .shot_generator import ShotGenerator
from .asset_planner import AssetPlanner
from .editor_timeline import EditorTimeline
from .video_model_adapter import VideoModelAdapter
from .workflow_builder import WorkflowBuilder
from .production_pipeline import ProductionPipeline, ProductionOutput
from .production_memory import ProductionMemory


class CreativeProductionAPI:
    """统一 API 入口"""

    def __init__(
        self,
        output_dir: str = "output/creative_production",
        budget_usd: float = 10.0,
    ):
        self.output_dir = output_dir
        self.budget_usd = budget_usd

        # 共享组件
        self.director = CreativeDirector()
        self.script_engine = CreativeScriptEngine()
        self.storyboard_engine = StoryboardEngine()
        self.shot_generator = ShotGenerator()
        self.asset_planner = AssetPlanner()
        self.editor = EditorTimeline()
        self.model_adapter = VideoModelAdapter()
        self.workflow_builder = WorkflowBuilder()
        self.memory = ProductionMemory(
            os.path.join(output_dir, "production_memory.duckdb")
        )
        self.pipeline = ProductionPipeline(
            output_dir=output_dir,
            memory=self.memory,
            budget_usd=budget_usd,
        )

    # ------------------------------------------------------------------
    # 步骤化 API
    # ------------------------------------------------------------------
    def generate_strategy(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        return self.director.direct(variant, duration, platform, placement, country)

    def generate_script(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        strategy = self.generate_strategy(variant, duration, platform, placement, country)
        return self.script_engine.generate(strategy, variant)

    def generate_storyboard(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        strategy = self.generate_strategy(variant, duration, platform, placement, country)
        script = self.script_engine.generate(strategy, variant)
        return self.storyboard_engine.build(script, strategy, platform=platform)

    def generate_shots(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        strategy = self.generate_strategy(variant, duration, platform, placement, country)
        script = self.script_engine.generate(strategy, variant)
        storyboard = self.storyboard_engine.build(script, strategy, platform=platform)
        return self.shot_generator.generate(storyboard, strategy, variant)

    def plan_assets(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        strategy = self.generate_strategy(variant, duration, platform, placement, country)
        script = self.script_engine.generate(strategy, variant)
        storyboard = self.storyboard_engine.build(script, strategy, platform=platform)
        shot_list = self.shot_generator.generate(storyboard, strategy, variant)
        return self.asset_planner.plan(shot_list, strategy, variant, budget_usd=self.budget_usd)

    def build_timeline(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        output = self.run_full(variant, duration, platform, placement, country)
        return output.timeline

    def build_workflow(self, variant: dict[str, Any], duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> Any:
        output = self.run_full(variant, duration, platform, placement, country)
        return output.workflow

    # ------------------------------------------------------------------
    # 模型导出
    # ------------------------------------------------------------------
    def export_kling(self, variant: dict[str, Any], **kwargs: Any) -> list[Any]:
        return self._export_for_model(variant, "kling", **kwargs)

    def export_runway(self, variant: dict[str, Any], **kwargs: Any) -> list[Any]:
        return self._export_for_model(variant, "runway", **kwargs)

    def export_comfyui(self, variant: dict[str, Any], **kwargs: Any) -> list[Any]:
        return self._export_for_model(variant, "comfyui", **kwargs)

    def export_veo(self, variant: dict[str, Any], **kwargs: Any) -> list[Any]:
        return self._export_for_model(variant, "veo", **kwargs)

    def export_wan(self, variant: dict[str, Any], **kwargs: Any) -> list[Any]:
        return self._export_for_model(variant, "wan", **kwargs)

    def export_lovart(self, variant: dict[str, Any], **kwargs: Any) -> list[Any]:
        return self._export_for_model(variant, "lovart", **kwargs)

    def _export_for_model(self, variant: dict[str, Any], model: str, duration: float = 15.0, platform: str = "facebook", placement: str = "feed", country: str = "US") -> list[Any]:
        shot_list = self.generate_shots(variant, duration, platform, placement, country)
        aspect = self.storyboard_engine.PLATFORM_ASPECT.get(
            self.storyboard_engine._normalize_platform(platform), "9:16"
        )
        return self.model_adapter.adapt_batch(shot_list.shots, model, aspect)

    # ------------------------------------------------------------------
    # 完整运行
    # ------------------------------------------------------------------
    def run_full(
        self,
        variant: dict[str, Any],
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "feed",
        country: str = "US",
    ) -> ProductionOutput:
        """运行完整生产流程"""
        return self.pipeline.run(variant, duration, platform, placement, country)

    def run_batch(
        self,
        variants: list[dict[str, Any]],
        duration: float = 15.0,
        platform: str = "facebook",
    ) -> list[ProductionOutput]:
        return self.pipeline.run_batch(variants, duration, platform)

    def export(self, output: ProductionOutput, subdir: str | None = None) -> dict[str, str]:
        return self.pipeline.export(output, subdir)

    # ------------------------------------------------------------------
    # 持续学习
    # ------------------------------------------------------------------
    def learn(
        self,
        variant_id: str,
        ctr: float = 0.0,
        cvr: float = 0.0,
        roas: float = 0.0,
        spend: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """记录表现数据，支持持续学习"""
        self.memory.learn(
            variant_id=variant_id,
            ctr=ctr,
            cvr=cvr,
            roas=roas,
            spend=spend,
            **kwargs,
        )

    def get_winners(self, min_roas: float = 1.5, limit: int = 50) -> list[dict[str, Any]]:
        """查询历史 Winner"""
        return self.memory.get_winners(min_roas, limit)

    def get_stats(self) -> dict[str, Any]:
        """统计"""
        return self.memory.get_stats()


# 全局单例
_api_instance: CreativeProductionAPI | None = None


def get_production_api() -> CreativeProductionAPI:
    """获取全局 API 实例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = CreativeProductionAPI()
    return _api_instance
