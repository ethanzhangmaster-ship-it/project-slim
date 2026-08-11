"""Generation Pipeline - 统一生成流程

完整流程:
Decision -> Prompt -> Optimize -> Negative -> Storyboard -> Model Adapter -> Task Builder -> Validator -> Output
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .image_task_builder import ImageTask, ImageTaskBuilder
from .model_adapter import ModelAdapter
from .negative_prompt import NegativePromptEngine
from .prompt_engine import MasterPrompt, PromptEngine
from .prompt_memory import PromptMemory
from .prompt_optimizer import OptimizedPrompt, PromptOptimizer
from .quality_validator import QualityValidator, ValidationResult
from .storyboard_generator import Storyboard, StoryboardGenerator


@dataclass
class GenerationOutput:
    """生成输出"""
    variant_id: str
    master_prompt: MasterPrompt | None = None
    optimized_prompts: list[OptimizedPrompt] = field(default_factory=list)
    negative_prompt: str = ""
    storyboard: Storyboard | None = None
    image_tasks: list[ImageTask] = field(default_factory=list)
    validation: dict[str, ValidationResult] = field(default_factory=dict)
    passed: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "master_prompt": self.master_prompt.to_dict() if self.master_prompt else None,
            "optimized_prompts": [p.to_dict() for p in self.optimized_prompts],
            "negative_prompt": self.negative_prompt,
            "storyboard": self.storyboard.to_dict() if self.storyboard else None,
            "image_tasks": [t.to_dict() for t in self.image_tasks],
            "validation": {k: v.to_dict() for k, v in self.validation.items()},
            "passed": self.passed,
            "errors": self.errors,
        }


class GenerationPipeline:
    """创意生成流水线

    将 Decision Portfolio 通过完整流程转换为可执行的 AI 生成任务。
    """

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

        # 初始化各子模块
        self.prompt_engine = PromptEngine()
        self.prompt_optimizer = PromptOptimizer()
        self.negative_engine = NegativePromptEngine()
        self.storyboard_gen = StoryboardGenerator()
        self.model_adapter = ModelAdapter()
        self.task_builder = ImageTaskBuilder()
        self.validator = QualityValidator()
        self.prompt_memory = PromptMemory(db_path) if db_path else None

    # ------------------------------------------------------------------
    # 核心流程
    # ------------------------------------------------------------------
    def run(
        self,
        variant: dict[str, Any],
        portfolio_tier: str = "safe",
        generate_storyboard: bool = True,
        validate: bool = True,
        save_to_memory: bool = True,
    ) -> GenerationOutput:
        """运行完整生成流程

        Args:
            variant: Decision Variant
            portfolio_tier: safe / growth / explore
            generate_storyboard: 是否生成分镜
            validate: 是否验证
            save_to_memory: 是否保存到 Prompt Memory

        Returns:
            GenerationOutput
        """
        output = GenerationOutput(variant_id=variant.get("variant_id", "unknown"))
        errors: list[str] = []

        # Step 1: Prompt Engine - 生成 Master Prompt
        try:
            master = self.prompt_engine.generate(
                variant=variant,
                style=self.style,
                placement=self.placement,
            )
            output.master_prompt = master
        except Exception as e:
            errors.append(f"Prompt Engine 失败: {e}")
            output.errors = errors
            return output

        # Step 2: Prompt Optimizer - 多版本优化
        try:
            decision_score = variant.get("decision_score", 0)
            risk_level = variant.get("risk_level", "medium")
            optimized = self.prompt_optimizer.smart_optimize(
                master_prompt=master.master_prompt,
                decision_score=decision_score,
                risk_level=risk_level,
                portfolio_tier=portfolio_tier,
            )
            output.optimized_prompts = optimized
        except Exception as e:
            errors.append(f"Prompt Optimizer 失败: {e}")

        # Step 3: Negative Prompt
        try:
            negative = self.negative_engine.generate(self.model)
            output.negative_prompt = negative
        except Exception as e:
            errors.append(f"Negative Prompt 失败: {e}")

        # Step 4: Storyboard Generator
        if generate_storyboard and output.master_prompt:
            try:
                sb = self.storyboard_gen.generate(
                    master_prompt=output.master_prompt.master_prompt,
                    variant=variant,
                    hook_type=output.master_prompt.hook_type,
                )
                output.storyboard = sb
            except Exception as e:
                errors.append(f"Storyboard 失败: {e}")

        # Step 5: Image Task Builder
        if output.optimized_prompts:
            try:
                opt_dicts = [o.to_dict() for o in output.optimized_prompts]
                tasks = self.task_builder.build(
                    variant_id=output.variant_id,
                    optimized_prompts=opt_dicts,
                    model=self.model,
                    placement=self.placement,
                    aspect_ratio=self.aspect_ratio,
                )
                output.image_tasks = tasks
            except Exception as e:
                errors.append(f"Task Builder 失败: {e}")

        # Step 6: Quality Validator
        if validate:
            try:
                # 验证 Master Prompt
                if output.master_prompt:
                    prompt_val = self.validator.validate_prompt(
                        output.master_prompt.master_prompt
                    )
                    output.validation["prompt"] = prompt_val

                # 验证 Storyboard
                if output.storyboard:
                    sb_val = self.validator.validate_storyboard(
                        output.storyboard.to_dict()
                    )
                    output.validation["storyboard"] = sb_val

                # 验证 Image Task
                if output.image_tasks:
                    task_val = self.validator.validate_image_task(
                        output.image_tasks[0].to_dict()
                    )
                    output.validation["image_task"] = task_val
            except Exception as e:
                errors.append(f"Validator 失败: {e}")

        # Step 7: 检查是否通过
        output.passed = len(errors) == 0
        output.errors = errors

        # Step 8: 保存到 Memory
        if save_to_memory and self.prompt_memory and output.master_prompt:
            try:
                for opt in output.optimized_prompts:
                    self.prompt_memory.save_prompt(
                        prompt_id=f"{output.variant_id}_{opt.version}",
                        variant_id=output.variant_id,
                        master_prompt=opt.prompt,
                        hook_type=output.master_prompt.hook_type,
                        style=opt.style,
                        placement=self.placement,
                        model=self.model,
                        negative_prompt=opt.negative_prompt,
                        storyboard=output.storyboard.to_dict() if output.storyboard else None,
                        tags=[portfolio_tier, opt.version],
                    )
            except Exception:
                pass

        return output

    # ------------------------------------------------------------------
    # 批量流程
    # ------------------------------------------------------------------
    def run_batch(
        self,
        portfolio: dict[str, list[dict[str, Any]]],
        generate_storyboard: bool = True,
        validate: bool = True,
    ) -> dict[str, list[GenerationOutput]]:
        """批量运行 Portfolio 中所有变体的生成流程

        Args:
            portfolio: {safe: [...], growth: [...], explore: [...]}
            generate_storyboard: 是否生成分镜
            validate: 是否验证

        Returns:
            {tier: [GenerationOutput, ...]}
        """
        results: dict[str, list[GenerationOutput]] = {
            "safe": [],
            "growth": [],
            "explore": [],
        }

        for tier, variants in portfolio.items():
            for variant in variants:
                try:
                    output = self.run(
                        variant=variant,
                        portfolio_tier=tier,
                        generate_storyboard=generate_storyboard,
                        validate=validate,
                    )
                    results[tier].append(output)
                except Exception:
                    continue

        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export_outputs(
        self,
        outputs: list[GenerationOutput],
        output_dir: Path,
    ) -> dict[str, Path]:
        """导出所有生成结果"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported = {}

        # 1. Prompts
        prompts_data = []
        for o in outputs:
            if o.master_prompt:
                prompts_data.append({
                    "variant_id": o.variant_id,
                    "master_prompt": o.master_prompt.to_dict(),
                    "optimized": [p.to_dict() for p in o.optimized_prompts],
                })

        prompts_path = output_dir / "prompts.json"
        with open(prompts_path, "w", encoding="utf-8") as f:
            json.dump(prompts_data, f, ensure_ascii=False, indent=2)
        exported["prompts"] = prompts_path

        # 2. Storyboards
        storyboards_data = []
        for o in outputs:
            if o.storyboard:
                storyboards_data.append(o.storyboard.to_dict())

        storyboard_path = output_dir / "storyboard.json"
        with open(storyboard_path, "w", encoding="utf-8") as f:
            json.dump(storyboards_data, f, ensure_ascii=False, indent=2)
        exported["storyboard"] = storyboard_path

        # 3. Image Tasks
        tasks_data = []
        for o in outputs:
            for t in o.image_tasks:
                tasks_data.append(t.to_dict())

        tasks_path = output_dir / "image_tasks.json"
        with open(tasks_path, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        exported["image_tasks"] = tasks_path

        # 4. Generation Report
        report = self._build_report(outputs)
        report_path = output_dir / "generation_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        exported["report"] = report_path

        return exported

    def _build_report(self, outputs: list[GenerationOutput]) -> str:
        """构建生成报告"""
        total = len(outputs)
        passed = sum(1 for o in outputs if o.passed)
        failed = total - passed

        total_tasks = sum(len(o.image_tasks) for o in outputs)
        total_storyboards = sum(1 for o in outputs if o.storyboard)

        lines = [
            "# Creative Generation Report (V4.3)",
            "",
            f"- **总变体数**: {total}",
            f"- **通过验证**: {passed}",
            f"- **失败**: {failed}",
            f"- **总生成任务**: {total_tasks}",
            f"- **分镜数**: {total_storyboards}",
            "",
            "## 生成详情",
            "",
        ]

        for o in outputs:
            status = "✅" if o.passed else "❌"
            lines.append(f"### {status} {o.variant_id}")
            if o.master_prompt:
                lines.append(f"- **Hook**: {o.master_prompt.hook_type}")
                lines.append(f"- **版本数**: {len(o.optimized_prompts)}")
            if o.errors:
                lines.append(f"- **错误**: {', '.join(o.errors)}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def get_stats(self, outputs: list[GenerationOutput]) -> dict[str, Any]:
        """获取生成统计"""
        return {
            "total_variants": len(outputs),
            "passed": sum(1 for o in outputs if o.passed),
            "failed": sum(1 for o in outputs if not o.passed),
            "total_prompts": sum(len(o.optimized_prompts) for o in outputs),
            "total_tasks": sum(len(o.image_tasks) for o in outputs),
            "total_storyboards": sum(1 for o in outputs if o.storyboard),
            "hook_types": list(set(
                o.master_prompt.hook_type
                for o in outputs
                if o.master_prompt
            )),
        }
