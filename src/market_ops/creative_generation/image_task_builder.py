"""Image Task Builder - 构建可执行 AI 生成任务

最终不是 Prompt，而是可以直接发送给 AI 模型的任务：
- Task001: Prompt / Negative Prompt / Model / Aspect Ratio / CFG / Steps / Seed / Scheduler
- 可以直接发送给 Lovart API 或 ComfyUI Queue
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model_adapter import ModelAdapter, ModelTask


@dataclass
class ImageTask:
    """图像生成任务"""
    task_id: str
    variant_id: str
    version: str                    # A/B/C/D
    model: str
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg_scale: float
    seed: int
    scheduler: str
    aspect_ratio: str
    output_folder: str
    status: str = "pending"         # pending / queued / generating / done / failed
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "variant_id": self.variant_id,
            "version": self.version,
            "model": self.model,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "seed": self.seed,
            "scheduler": self.scheduler,
            "aspect_ratio": self.aspect_ratio,
            "output_folder": self.output_folder,
            "status": self.status,
            "extra": self.extra,
        }


class ImageTaskBuilder:
    """图像任务构建器

    将优化后的 Prompt 转换为可执行的 AI 生成任务。
    """

    def __init__(self):
        self.model_adapter = ModelAdapter()

    # ------------------------------------------------------------------
    # 核心构建方法
    # ------------------------------------------------------------------
    def build(
        self,
        variant_id: str,
        optimized_prompts: list[dict[str, Any]],
        model: str = "lovart",
        placement: str = "feed",
        aspect_ratio: str = "1:1",
        output_folder: str = "output/creative_generation/images",
        seeds: list[int] | None = None,
    ) -> list[ImageTask]:
        """构建图像生成任务列表

        Args:
            variant_id: 变体ID
            optimized_prompts: 优化后的 Prompt 列表 (含 version, prompt, negative_prompt)
            model: 目标模型
            placement: 版位
            aspect_ratio: 宽高比
            output_folder: 输出目录
            seeds: 指定种子，默认随机

        Returns:
            ImageTask 列表
        """
        tasks = []
        for i, opt in enumerate(optimized_prompts):
            version = opt.get("version", "A")
            prompt = opt.get("prompt", "")
            negative = opt.get("negative_prompt", "")

            # 使用 ModelAdapter 转换
            model_task = self.model_adapter.adapt(
                master_prompt=prompt,
                negative_prompt=negative,
                model=model,
                placement=placement,
                aspect_ratio=aspect_ratio,
            )

            # 种子
            seed = seeds[i] if seeds and i < len(seeds) else -1

            task = ImageTask(
                task_id=f"task_{variant_id}_{version}_{model}",
                variant_id=variant_id,
                version=version,
                model=model,
                prompt=model_task.prompt,
                negative_prompt=model_task.negative_prompt,
                width=model_task.width,
                height=model_task.height,
                steps=model_task.steps,
                cfg_scale=model_task.cfg_scale,
                seed=seed,
                scheduler=model_task.scheduler,
                aspect_ratio=aspect_ratio,
                output_folder=f"{output_folder}/{variant_id}/{version}",
                extra={
                    "placement": placement,
                    "style": opt.get("style", ""),
                    "model_params": model_task.extra_params,
                },
            )
            tasks.append(task)

        return tasks

    def build_for_all_models(
        self,
        variant_id: str,
        optimized_prompts: list[dict[str, Any]],
        models: list[str] | None = None,
        placement: str = "feed",
        aspect_ratio: str = "1:1",
        output_folder: str = "output/creative_generation/images",
    ) -> dict[str, list[ImageTask]]:
        """为所有模型构建任务"""
        if models is None:
            models = ["lovart", "flux", "sdxl", "comfyui", "midjourney"]

        results = {}
        for model in models:
            results[model] = self.build(
                variant_id=variant_id,
                optimized_prompts=optimized_prompts,
                model=model,
                placement=placement,
                aspect_ratio=aspect_ratio,
                output_folder=output_folder,
            )
        return results

    # ------------------------------------------------------------------
    # 批量构建
    # ------------------------------------------------------------------
    def build_batch(
        self,
        variants: list[dict[str, Any]],
        model: str = "lovart",
        placement: str = "feed",
        aspect_ratio: str = "1:1",
    ) -> dict[str, list[ImageTask]]:
        """批量构建多个变体的任务"""
        results = {}
        for v in variants:
            variant_id = v.get("variant_id", "")
            opt_prompts = v.get("optimized_prompts", [])
            if variant_id and opt_prompts:
                results[variant_id] = self.build(
                    variant_id=variant_id,
                    optimized_prompts=opt_prompts,
                    model=model,
                    placement=placement,
                    aspect_ratio=aspect_ratio,
                )
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export_tasks(
        self,
        tasks: list[ImageTask],
        output_dir: Path,
        format: str = "json",
    ) -> list[Path]:
        """导出任务到文件

        Args:
            tasks: 任务列表
            output_dir: 输出目录
            format: 格式 (json / comfyui)

        Returns:
            导出的文件路径列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = []

        if format == "json":
            # 统一导出为 tasks.json
            data = [t.to_dict() for t in tasks]
            path = output_dir / "image_tasks.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            paths.append(path)

        elif format == "comfyui":
            # 导出 ComfyUI 工作流
            for task in tasks:
                if task.model == "comfyui":
                    model_task = ModelTask(
                        model=task.model,
                        prompt=task.prompt,
                        negative_prompt=task.negative_prompt,
                        width=task.width,
                        height=task.height,
                        steps=task.steps,
                        cfg_scale=task.cfg_scale,
                        seed=task.seed,
                        scheduler=task.scheduler,
                    )
                    workflow = self.model_adapter.build_comfyui_workflow(model_task)
                    path = output_dir / f"comfyui_{task.task_id}.json"
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(workflow, f, ensure_ascii=False, indent=2)
                    paths.append(path)

        elif format == "lovart":
            # Lovart 专用格式
            lovart_tasks = [t for t in tasks if t.model == "lovart"]
            if lovart_tasks:
                data = [t.to_dict() for t in lovart_tasks]
                path = output_dir / "lovart_tasks.json"
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                paths.append(path)

        return paths

    # ------------------------------------------------------------------
    # 生成预算规划
    # ------------------------------------------------------------------
    def estimate_generation_cost(
        self,
        tasks: list[ImageTask],
        cost_per_image: float = 0.05,
    ) -> dict[str, Any]:
        """估算生成成本"""
        total_images = len(tasks)
        total_cost = total_images * cost_per_image

        by_model: dict[str, int] = {}
        for t in tasks:
            by_model[t.model] = by_model.get(t.model, 0) + 1

        return {
            "total_images": total_images,
            "estimated_cost_usd": round(total_cost, 2),
            "cost_per_image": cost_per_image,
            "by_model": by_model,
            "by_variant": self._group_by_variant(tasks),
        }

    def _group_by_variant(self, tasks: list[ImageTask]) -> dict[str, int]:
        """按变体分组统计"""
        result = {}
        for t in tasks:
            result[t.variant_id] = result.get(t.variant_id, 0) + 1
        return result

    def plan_budget(
        self,
        portfolio: dict[str, list[dict[str, Any]]],
        total_budget: float = 100.0,
        cost_per_image: float = 0.05,
    ) -> dict[str, Any]:
        """根据 Portfolio 分配生成预算

        Args:
            portfolio: {safe: [...], growth: [...], explore: [...]}
            total_budget: 总预算 ($)
            cost_per_image: 每张图成本

        Returns:
            预算分配计划
        """
        safe_count = len(portfolio.get("safe", []))
        growth_count = len(portfolio.get("growth", []))
        explore_count = len(portfolio.get("explore", []))
        total_variants = safe_count + growth_count + explore_count

        if total_variants == 0:
            return {"error": "no_variants"}

        # 预算分配策略
        # Safe: 每 variant 生成 2 张（稳定输出）
        # Growth: 每 variant 生成 3 张（中等探索）
        # Explore: 每 variant 生成 4 张（大胆尝试）
        images_per_tier = {
            "safe": 2,
            "growth": 3,
            "explore": 4,
        }

        plan = {}
        total_images = 0
        for tier, variants in portfolio.items():
            count = len(variants)
            images = count * images_per_tier.get(tier, 2)
            cost = images * cost_per_image
            plan[tier] = {
                "variant_count": count,
                "images_per_variant": images_per_tier.get(tier, 2),
                "total_images": images,
                "estimated_cost": round(cost, 2),
            }
            total_images += images

        total_cost = total_images * cost_per_image

        return {
            "total_budget": total_budget,
            "total_images": total_images,
            "total_estimated_cost": round(total_cost, 2),
            "budget_utilization": round(total_cost / total_budget * 100, 1) if total_budget > 0 else 0,
            "plan": plan,
        }
