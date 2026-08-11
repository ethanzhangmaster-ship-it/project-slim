"""Generation API - 统一入口

提供单一接口调用整个 V4.3 生成流程。

用法:
    from src.market_ops.creative_generation import GenerationAPI, get_generation_api

    api = get_generation_api()
    result = api.generate(variant)
    results = api.generate_portfolio(portfolio)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .generation_pipeline import GenerationPipeline
from .prompt_memory import PromptMemory


class GenerationAPI:
    """创意生成 API 统一入口

    所有 Agent（V4.2.2 Decision -> V4.3 Generation）统一调用此 API。
    """

    _instance: GenerationAPI | None = None

    def __init__(
        self,
        model: str = "lovart",
        placement: str = "feed",
        aspect_ratio: str = "1:1",
        style: str = "pixar",
        db_path: str | Path | None = None,
    ):
        self.model = model
        self.placement = placement
        self.aspect_ratio = aspect_ratio
        self.style = style

        # 初始化 Pipeline
        resolved_db = db_path or (
            Path(__file__).resolve().parents[3] / "db" / "prompt_memory.duckdb"
        )
        self.pipeline = GenerationPipeline(
            model=model,
            placement=placement,
            aspect_ratio=aspect_ratio,
            style=style,
            db_path=resolved_db,
        )

        # 独立 Prompt Memory 接口
        self.prompt_memory = PromptMemory(resolved_db)

    # ------------------------------------------------------------------
    # 核心生成接口
    # ------------------------------------------------------------------
    def generate(
        self,
        variant: dict[str, Any],
        portfolio_tier: str = "safe",
        generate_storyboard: bool = True,
        validate: bool = True,
    ) -> dict[str, Any]:
        """生成单个变体的完整创意素材

        Args:
            variant: Decision Variant
            portfolio_tier: safe / growth / explore
            generate_storyboard: 是否生成分镜
            validate: 是否验证

        Returns:
            完整生成结果字典
        """
        output = self.pipeline.run(
            variant=variant,
            portfolio_tier=portfolio_tier,
            generate_storyboard=generate_storyboard,
            validate=validate,
        )
        return output.to_dict()

    def generate_portfolio(
        self,
        portfolio: dict[str, list[dict[str, Any]]],
        generate_storyboard: bool = True,
        validate: bool = True,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """生成整个 Portfolio 的创意素材

        Args:
            portfolio: {safe: [...], growth: [...], explore: [...]}
            generate_storyboard: 是否生成分镜
            validate: 是否验证
            output_dir: 输出目录

        Returns:
            批量生成结果
        """
        results = self.pipeline.run_batch(
            portfolio=portfolio,
            generate_storyboard=generate_storyboard,
            validate=validate,
        )

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
    # Prompt 相关接口
    # ------------------------------------------------------------------
    def generate_prompt(self, variant: dict[str, Any]) -> dict[str, Any]:
        """仅生成 Prompt（不生成其他素材）"""
        master = self.pipeline.prompt_engine.generate(
            variant=variant,
            style=self.style,
            placement=self.placement,
        )
        return master.to_dict()

    def optimize_prompt(self, prompt: str, portfolio_tier: str = "safe") -> list[dict[str, Any]]:
        """优化单个 Prompt"""
        negative = self.pipeline.negative_engine.generate(self.model)
        optimized = self.pipeline.prompt_optimizer.optimize(
            master_prompt=prompt,
            negative_prompt=negative,
            portfolio_tier=portfolio_tier,
        )
        return [o.to_dict() for o in optimized]

    # ------------------------------------------------------------------
    # Storyboard 接口
    # ------------------------------------------------------------------
    def generate_storyboard(
        self,
        variant: dict[str, Any],
        master_prompt: str = "",
        hook_type: str = "collection",
        total_duration: float = 15.0,
    ) -> dict[str, Any]:
        """仅生成分镜"""
        if not master_prompt:
            master = self.pipeline.prompt_engine.generate(variant, style=self.style)
            master_prompt = master.master_prompt if master else ""

        sb = self.pipeline.storyboard_gen.generate(
            master_prompt=master_prompt,
            variant=variant,
            hook_type=hook_type,
            total_duration=total_duration,
        )
        return sb.to_dict()

    # ------------------------------------------------------------------
    # Image Task 接口
    # ------------------------------------------------------------------
    def build_image_tasks(
        self,
        variant_id: str,
        optimized_prompts: list[dict[str, Any]],
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """仅构建图像任务"""
        m = model or self.model
        tasks = self.pipeline.task_builder.build(
            variant_id=variant_id,
            optimized_prompts=optimized_prompts,
            model=m,
            placement=self.placement,
            aspect_ratio=self.aspect_ratio,
        )
        return [t.to_dict() for t in tasks]

    # ------------------------------------------------------------------
    # 验证接口
    # ------------------------------------------------------------------
    def validate(self, prompt: str | None = None, storyboard: dict | None = None, image_task: dict | None = None) -> dict[str, Any]:
        """验证生成物"""
        results = self.pipeline.validator.validate_all(
            prompt=prompt,
            storyboard=storyboard,
            image_task=image_task,
        )
        return {k: v.to_dict() for k, v in results.items()}

    # ------------------------------------------------------------------
    # Memory 接口
    # ------------------------------------------------------------------
    def save_prompt_result(self, prompt_id: str, performance: dict[str, Any]) -> None:
        """保存 Prompt 投放结果"""
        self.prompt_memory.update_performance(
            prompt_id=prompt_id,
            ctr=performance.get("ctr"),
            cvr=performance.get("cvr"),
            roas=performance.get("roas"),
            ipm=performance.get("ipm"),
            spend=performance.get("spend"),
            status=performance.get("status"),
        )

    def get_top_prompts(self, metric: str = "roas", limit: int = 10) -> list[dict[str, Any]]:
        """获取表现最好的 Prompt"""
        return self.prompt_memory.get_top_prompts(metric, limit)

    def get_prompt_stats(self) -> dict[str, Any]:
        """获取 Prompt 统计"""
        return self.prompt_memory.get_prompt_stats()

    # ------------------------------------------------------------------
    # 预算规划
    # ------------------------------------------------------------------
    def plan_generation_budget(
        self,
        portfolio: dict[str, list[dict[str, Any]]],
        total_budget: float = 100.0,
    ) -> dict[str, Any]:
        """规划生成预算"""
        return self.pipeline.task_builder.plan_budget(portfolio, total_budget)

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def set_model(self, model: str) -> None:
        """设置目标模型"""
        self.model = model
        self.pipeline.model = model

    def set_placement(self, placement: str) -> None:
        """设置版位"""
        self.placement = placement
        self.pipeline.placement = placement

    def set_style(self, style: str) -> None:
        """设置风格"""
        self.style = style
        self.pipeline.style = style


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------
def get_generation_api(
    model: str = "lovart",
    placement: str = "feed",
    style: str = "pixar",
) -> GenerationAPI:
    """获取 GenerationAPI 单例"""
    if GenerationAPI._instance is None:
        GenerationAPI._instance = GenerationAPI(
            model=model,
            placement=placement,
            style=style,
        )
    return GenerationAPI._instance
