"""Model Adapter - 多 AI 模型适配器

一个 Prompt 转换为不同模型格式:
- Lovart -> Lovart Prompt
- Flux -> Flux Prompt
- ComfyUI -> Workflow JSON
- SDXL -> SDXL Prompt
- Midjourney -> MJ Prompt
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelTask:
    """模型任务定义"""
    model: str
    prompt: str
    negative_prompt: str
    width: int = 1024
    height: int = 1024
    steps: int = 30
    cfg_scale: float = 7.0
    seed: int = -1
    scheduler: str = "euler_a"
    aspect_ratio: str = "1:1"
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
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
            "extra_params": self.extra_params,
        }


class ModelAdapter:
    """AI 模型适配器

    将统一的 Master Prompt 转换为各模型的具体格式。
    """

    # 各模型推荐参数
    MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
        "lovart": {
            "width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7.0,
            "scheduler": "euler_a", "model_name": "lovart-xl-v1",
        },
        "flux": {
            "width": 1024, "height": 1024, "steps": 4, "cfg_scale": 1.0,
            "scheduler": "flowmatch", "model_name": "flux-dev",
        },
        "sdxl": {
            "width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7.0,
            "scheduler": "euler_a", "model_name": "sdxl-base",
        },
        "comfyui": {
            "width": 1024, "height": 1024, "steps": 25, "cfg_scale": 7.5,
            "scheduler": "euler", "model_name": "sdxl",
            "workflow": "standard_txt2img",
        },
        "midjourney": {
            "width": 1024, "height": 1024, "steps": 0, "cfg_scale": 0,
            "scheduler": "n/a", "model_name": "midjourney-v6",
            "version": "--v 6", "style": "--style raw",
        },
    }

    # 版位对应的尺寸
    PLACEMENT_SIZES: dict[str, dict[str, tuple[int, int]]] = {
        "feed": {
            "1:1": (1024, 1024),
            "4:5": (1024, 1280),
        },
        "reels": {
            "9:16": (576, 1024),
            "4:5": (1024, 1280),
        },
        "stories": {
            "9:16": (576, 1024),
        },
        "audience_network": {
            "1:1": (1024, 1024),
            "16:9": (1024, 576),
        },
    }

    def __init__(self):
        self._model_defaults = dict(self.MODEL_DEFAULTS)

    # ------------------------------------------------------------------
    # 核心适配方法
    # ------------------------------------------------------------------
    def adapt(
        self,
        master_prompt: str,
        negative_prompt: str,
        model: str,
        placement: str = "feed",
        aspect_ratio: str = "1:1",
        style: str = "pixar",
    ) -> ModelTask:
        """将 Master Prompt 适配到指定模型

        Args:
            master_prompt: 主提示词
            negative_prompt: 负面提示词
            model: 目标模型
            placement: 版位
            aspect_ratio: 宽高比
            style: 风格

        Returns:
            ModelTask
        """
        model_lower = model.lower()
        defaults = self._model_defaults.get(model_lower, {})

        # 获取版位尺寸
        size = self._get_size(placement, aspect_ratio)

        # 根据模型转换 prompt
        adapted_prompt = self._convert_prompt(master_prompt, model_lower, style)
        adapted_negative = self._convert_negative(negative_prompt, model_lower)

        return ModelTask(
            model=model_lower,
            prompt=adapted_prompt,
            negative_prompt=adapted_negative,
            width=size[0],
            height=size[1],
            steps=defaults.get("steps", 30),
            cfg_scale=defaults.get("cfg_scale", 7.0),
            scheduler=defaults.get("scheduler", "euler_a"),
            aspect_ratio=aspect_ratio,
            extra_params={
                "model_name": defaults.get("model_name", ""),
                "placement": placement,
                "style": style,
            },
        )

    def _convert_prompt(self, prompt: str, model: str, style: str) -> str:
        """模型特定的 prompt 转换"""
        if model == "midjourney":
            # Midjourney: 更简洁，参数在末尾
            return self._to_midjourney_prompt(prompt, style)
        elif model == "flux":
            # Flux: 擅长自然语言，保留完整描述
            return self._to_flux_prompt(prompt)
        elif model == "lovart":
            # Lovart: 游戏广告优化
            return self._to_lovart_prompt(prompt)
        elif model == "comfyui":
            # ComfyUI: 标准 SD 格式
            return prompt
        else:
            # SDXL: 标准格式
            return prompt

    def _convert_negative(self, negative: str, model: str) -> str:
        """模型特定的 negative prompt 转换"""
        if model == "flux":
            # Flux 负面词效果有限，精简
            return ""
        elif model == "midjourney":
            # Midjourney 用 --no 参数
            return negative
        return negative

    # ------------------------------------------------------------------
    # 各模型专用转换
    # ------------------------------------------------------------------
    def _to_midjourney_prompt(self, prompt: str, style: str) -> str:
        """转换为 Midjourney 格式"""
        style_map = {
            "pixar": "in the style of Pixar 3D animation",
            "disney": "in the style of Disney animation",
            "dreamworks": "in the style of DreamWorks animation",
            "semi_realistic": "semi-realistic digital art, anime game style",
            "chibi": "chibi kawaii style, super deformed",
        }
        style_suffix = style_map.get(style.lower(), "")
        if style_suffix:
            prompt = f"{prompt}, {style_suffix}"
        return prompt

    def _to_flux_prompt(self, prompt: str) -> str:
        """转换为 Flux 格式（Flux 擅长自然语言，不需要大量标签）"""
        # Flux 更喜欢完整句子描述
        return prompt

    def _to_lovart_prompt(self, prompt: str) -> str:
        """转换为 Lovart 格式（游戏广告专用优化）"""
        # Lovart 对游戏广告有专门优化
        if "mobile game" not in prompt.lower():
            prompt = f"mobile game advertisement, {prompt}"
        return prompt

    # ------------------------------------------------------------------
    # 版位 & 尺寸
    # ------------------------------------------------------------------
    def _get_size(self, placement: str, aspect_ratio: str) -> tuple[int, int]:
        """获取版位 + 宽高比对应的像素尺寸"""
        placement_sizes = self.PLACEMENT_SIZES.get(placement.lower(), {})
        return placement_sizes.get(aspect_ratio, (1024, 1024))

    def list_supported_sizes(self, placement: str) -> list[str]:
        """列出某版位支持的宽高比"""
        sizes = self.PLACEMENT_SIZES.get(placement.lower(), {})
        return list(sizes.keys())

    # ------------------------------------------------------------------
    # 批量适配
    # ------------------------------------------------------------------
    def adapt_all(
        self,
        master_prompt: str,
        negative_prompt: str,
        models: list[str] | None = None,
        placement: str = "feed",
        aspect_ratio: str = "1:1",
        style: str = "pixar",
    ) -> dict[str, ModelTask]:
        """批量适配到所有模型"""
        if models is None:
            models = list(self._model_defaults.keys())

        results = {}
        for m in models:
            results[m] = self.adapt(
                master_prompt, negative_prompt, m, placement, aspect_ratio, style
            )
        return results

    # ------------------------------------------------------------------
    # ComfyUI Workflow JSON
    # ------------------------------------------------------------------
    def build_comfyui_workflow(
        self,
        task: ModelTask,
        workflow_name: str = "standard_txt2img",
    ) -> dict[str, Any]:
        """构建 ComfyUI 工作流 JSON

        Args:
            task: 模型任务
            workflow_name: 工作流名称

        Returns:
            ComfyUI 可执行的 workflow JSON
        """
        if workflow_name == "standard_txt2img":
            return {
                "prompt": {
                    "3": {
                        "inputs": {
                            "text": task.prompt,
                            "clip": ["4", 1],
                        },
                        "class_type": "CLIPTextEncode",
                    },
                    "4": {
                        "inputs": {
                            "ckpt_name": task.extra_params.get("model_name", "sdxl.safetensors"),
                        },
                        "class_type": "CheckpointLoaderSimple",
                    },
                    "5": {
                        "inputs": {
                            "width": task.width,
                            "height": task.height,
                            "batch_size": 1,
                        },
                        "class_type": "EmptyLatentImage",
                    },
                    "6": {
                        "inputs": {
                            "text": task.negative_prompt,
                            "clip": ["4", 1],
                        },
                        "class_type": "CLIPTextEncode",
                    },
                    "7": {
                        "inputs": {
                            "seed": task.seed if task.seed >= 0 else 42,
                            "steps": task.steps,
                            "cfg": task.cfg_scale,
                            "sampler_name": task.scheduler,
                            "scheduler": "normal",
                            "denoise": 1.0,
                            "model": ["4", 0],
                            "positive": ["3", 0],
                            "negative": ["6", 0],
                            "latent_image": ["5", 0],
                        },
                        "class_type": "KSampler",
                    },
                    "8": {
                        "inputs": {
                            "samples": ["7", 0],
                            "vae": ["4", 2],
                        },
                        "class_type": "VAEDecode",
                    },
                    "9": {
                        "inputs": {
                            "filename_prefix": "fb_creative",
                            "images": ["8", 0],
                        },
                        "class_type": "SaveImage",
                    },
                },
                "extra_data": {
                    "task_info": task.to_dict(),
                },
            }
        return {}

    def export_task(
        self,
        task: ModelTask,
        output_dir: Path,
        model: str | None = None,
    ) -> Path:
        """导出任务到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        model_name = model or task.model
        file_path = output_dir / f"{model_name}.json"

        if model_name == "comfyui":
            data = self.build_comfyui_workflow(task)
        else:
            data = task.to_dict()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path
