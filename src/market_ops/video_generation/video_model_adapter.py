"""Video Model Adapter - 视频模型适配器

统一适配:
- ComfyUI (Workflow JSON)
- Wan 2.2
- Kling
- Veo
- Runway
- Hailuo
- Lovart
- Pika
- Luma
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VideoModelTask:
    """视频模型任务"""
    model: str
    task_id: str
    shot_id: str
    prompt: str
    negative_prompt: str
    duration: float
    aspect_ratio: str = "9:16"
    resolution: tuple[int, int] = (576, 1024)
    fps: int = 30
    style: str = "pixar"
    motion_type: str = ""
    camera_motion: str = ""
    seed: int = -1
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "task_id": self.task_id,
            "shot_id": self.shot_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "duration": self.duration,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "fps": self.fps,
            "style": self.style,
            "motion_type": self.motion_type,
            "camera_motion": self.camera_motion,
            "seed": self.seed,
            "extra_params": self.extra_params,
        }


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    max_duration: float
    supported_aspect_ratios: list[str]
    default_resolution: tuple[int, int]
    prompt_max_length: int
    supports_negative: bool
    supports_camera_motion: bool
    supports_character_ref: bool
    api_format: str  # json / prompt_only / workflow


class VideoModelAdapter:
    """视频模型适配器
    
    支持的模型:
    - ComfyUI: Workflow JSON 格式
    - Wan 2.2: Wan Prompt 格式
    - Kling: Task JSON 格式
    - Veo: Prompt 格式
    - Runway: Prompt 格式
    - Hailuo: Prompt 格式
    - Lovart: Prompt 格式
    - Pika: Prompt 格式
    - Luma: Prompt 格式
    """

    # 模型配置库
    MODEL_CONFIGS: dict[str, ModelConfig] = {
        "comfyui": ModelConfig(
            name="comfyui",
            max_duration=60.0,
            supported_aspect_ratios=["1:1", "4:5", "9:16", "16:9"],
            default_resolution=(1024, 1024),
            prompt_max_length=1000,
            supports_negative=True,
            supports_camera_motion=True,
            supports_character_ref=True,
            api_format="workflow",
        ),
        "wan": ModelConfig(
            name="wan",
            max_duration=30.0,
            supported_aspect_ratios=["9:16", "16:9", "1:1"],
            default_resolution=(576, 1024),
            prompt_max_length=800,
            supports_negative=True,
            supports_camera_motion=True,
            supports_character_ref=False,
            api_format="json",
        ),
        "kling": ModelConfig(
            name="kling",
            max_duration=10.0,
            supported_aspect_ratios=["9:16", "16:9", "1:1"],
            default_resolution=(576, 1024),
            prompt_max_length=500,
            supports_negative=False,
            supports_camera_motion=True,
            supports_character_ref=True,
            api_format="json",
        ),
        "veo": ModelConfig(
            name="veo",
            max_duration=60.0,
            supported_aspect_ratios=["9:16", "16:9"],
            default_resolution=(720, 1280),
            prompt_max_length=600,
            supports_negative=True,
            supports_camera_motion=True,
            supports_character_ref=False,
            api_format="prompt_only",
        ),
        "runway": ModelConfig(
            name="runway",
            max_duration=18.0,
            supported_aspect_ratios=["9:16", "16:9", "1:1"],
            default_resolution=(768, 1344),
            prompt_max_length=400,
            supports_negative=True,
            supports_camera_motion=True,
            supports_character_ref=True,
            api_format="json",
        ),
        "hailuo": ModelConfig(
            name="hailuo",
            max_duration=15.0,
            supported_aspect_ratios=["9:16", "1:1"],
            default_resolution=(540, 960),
            prompt_max_length=400,
            supports_negative=False,
            supports_camera_motion=True,
            supports_character_ref=False,
            api_format="prompt_only",
        ),
        "lovart": ModelConfig(
            name="lovart",
            max_duration=30.0,
            supported_aspect_ratios=["9:16", "4:5", "1:1"],
            default_resolution=(576, 1024),
            prompt_max_length=1000,
            supports_negative=True,
            supports_camera_motion=True,
            supports_character_ref=False,
            api_format="json",
        ),
        "pika": ModelConfig(
            name="pika",
            max_duration=15.0,
            supported_aspect_ratios=["9:16", "1:1", "16:9"],
            default_resolution=(512, 512),
            prompt_max_length=300,
            supports_negative=False,
            supports_camera_motion=True,
            supports_character_ref=False,
            api_format="prompt_only",
        ),
        "luma": ModelConfig(
            name="luma",
            max_duration=30.0,
            supported_aspect_ratios=["9:16", "16:9", "1:1"],
            default_resolution=(720, 1280),
            prompt_max_length=500,
            supports_negative=False,
            supports_camera_motion=True,
            supports_character_ref=True,
            api_format="json",
        ),
    }

    # 版位尺寸映射
    PLACEMENT_RESOLUTIONS: dict[str, dict[str, tuple[int, int]]] = {
        "feed": {"1:1": (1024, 1024), "4:5": (1024, 1280)},
        "reels": {"9:16": (576, 1024)},
        "stories": {"9:16": (576, 1024)},
    }

    def __init__(self):
        self._configs = dict(self.MODEL_CONFIGS)

    # ------------------------------------------------------------------
    # 核心适配方法
    # ------------------------------------------------------------------
    def adapt_shot(
        self,
        shot: dict[str, Any],
        model: str = "kling",
        placement: str = "feed",
        aspect_ratio: str = "9:16",
    ) -> VideoModelTask:
        """将镜头适配到特定模型

        Args:
            shot: Shot.to_dict()
            model: 目标模型
            placement: 版位
            aspect_ratio: 画面比例

        Returns:
            VideoModelTask
        """
        config = self._configs.get(model.lower())
        if not config:
            config = self._configs.get("kling")

        # 获取分辨率
        resolution = self._get_resolution(placement, aspect_ratio, config)

        # 优化提示词长度
        prompt = self._optimize_prompt(shot.get("prompt", ""), config.prompt_max_length)
        negative = shot.get("negative_prompt", "") if config.supports_negative else ""

        return VideoModelTask(
            model=model.lower(),
            task_id=f"task_{shot.get('shot_id', 'unknown')}_{model}",
            shot_id=shot.get("shot_id", "unknown"),
            prompt=prompt,
            negative_prompt=negative,
            duration=min(shot.get("duration", 2.0), config.max_duration),
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            fps=30,
            style=shot.get("extra_params", {}).get("style", "pixar"),
            motion_type=shot.get("character_motion", ""),
            camera_motion=shot.get("camera_motion", "") if config.supports_camera_motion else "",
            extra_params={
                "scene_type": shot.get("scene_type", ""),
                "transition": shot.get("transition", ""),
                "sound": shot.get("sound", ""),
            },
        )

    def adapt_shot_list(
        self,
        shot_list: dict[str, Any],
        model: str = "kling",
        placement: str = "feed",
        aspect_ratio: str = "9:16",
    ) -> list[VideoModelTask]:
        """适配整个镜头列表"""
        shots = shot_list.get("shots", [])
        tasks = []
        for shot in shots:
            task = self.adapt_shot(shot, model, placement, aspect_ratio)
            tasks.append(task)
        return tasks

    # ------------------------------------------------------------------
    # 多模型批量适配
    # ------------------------------------------------------------------
    def adapt_all_models(
        self,
        shot: dict[str, Any],
        placement: str = "feed",
        aspect_ratio: str = "9:16",
    ) -> dict[str, VideoModelTask]:
        """适配到所有模型"""
        results = {}
        for model in self._configs.keys():
            results[model] = self.adapt_shot(shot, model, placement, aspect_ratio)
        return results

    # ------------------------------------------------------------------
    # ComfyUI Workflow JSON
    # ------------------------------------------------------------------
    def build_comfyui_workflow(
        self,
        task: VideoModelTask,
        character_ref: str = "",
    ) -> dict[str, Any]:
        """构建 ComfyUI Workflow JSON

        Args:
            task: VideoModelTask
            character_ref: 角色参考图片路径

        Returns:
            ComfyUI Workflow JSON
        """
        workflow = {
            "prompt": {
                "1": {
                    "inputs": {
                        "prompt": task.prompt,
                        "negative_prompt": task.negative_prompt,
                        "width": task.resolution[0],
                        "height": task.resolution[1],
                        "steps": 30,
                        "cfg": 7.0,
                        "seed": task.seed if task.seed >= 0 else 42,
                        "scheduler": "euler_a",
                    },
                    "class_type": "VideoGenerationNode",
                },
                "2": {
                    "inputs": {
                        "video_path": ["1", 0],
                        "duration": task.duration,
                        "fps": task.fps,
                        "motion_prompt": task.camera_motion,
                    },
                    "class_type": "MotionControlNode",
                },
                "3": {
                    "inputs": {
                        "video": ["2", 0],
                        "filename_prefix": task.task_id,
                    },
                    "class_type": "SaveVideo",
                },
            },
            "extra_data": {
                "task_info": task.to_dict(),
            },
        }

        # 如果有角色参考
        if character_ref:
            workflow["prompt"]["4"] = {
                "inputs": {
                    "image_path": character_ref,
                    "strength": 0.8,
                },
                "class_type": "CharacterReferenceLoader",
            }
            workflow["prompt"]["1"]["inputs"]["character_ref"] = ["4", 0]

        return workflow

    # ------------------------------------------------------------------
    # Kling Task JSON
    # ------------------------------------------------------------------
    def build_kling_task(self, task: VideoModelTask) -> dict[str, Any]:
        """构建 Kling Task JSON"""
        return {
            "task_id": task.task_id,
            "prompt": task.prompt,
            "negative_prompt": task.negative_prompt,
            "duration": task.duration,
            "aspect_ratio": task.aspect_ratio,
            "resolution": f"{task.resolution[0]}x{task.resolution[1]}",
            "camera_control": {
                "type": task.camera_motion,
                "strength": 0.8,
            },
            "model_version": "kling-v1",
            "quality": "high",
            "seed": task.seed,
        }

    # ------------------------------------------------------------------
    # Wan Task JSON
    # ------------------------------------------------------------------
    def build_wan_task(self, task: VideoModelTask) -> dict[str, Any]:
        """构建 Wan 2.2 Task JSON"""
        return {
            "task_id": task.task_id,
            "prompt": task.prompt,
            "negative_prompt": task.negative_prompt,
            "duration": task.duration,
            "aspect_ratio": task.aspect_ratio,
            "resolution": f"{task.resolution[0]}x{task.resolution[1]}",
            "motion": {
                "camera": task.camera_motion,
                "character": task.motion_type,
            },
            "model": "wan-2.2",
            "cfg_scale": 7.0,
            "seed": task.seed,
        }

    # ------------------------------------------------------------------
    # Runway Task JSON
    # ------------------------------------------------------------------
    def build_runway_task(self, task: VideoModelTask) -> dict[str, Any]:
        """构建 Runway Gen-3 Task JSON"""
        return {
            "task_id": task.task_id,
            "prompt": task.prompt,
            "negative_prompt": task.negative_prompt,
            "duration": task.duration,
            "aspect_ratio": task.aspect_ratio,
            "resolution": f"{task.resolution[0]}x{task.resolution[1]}",
            "motion_strength": 0.7,
            "camera_motion": task.camera_motion,
            "model": "gen-3-alpha",
            "seed": task.seed,
        }

    # ------------------------------------------------------------------
    # Lovart Task JSON
    # ------------------------------------------------------------------
    def build_lovart_task(self, task: VideoModelTask) -> dict[str, Any]:
        """构建 Lovart Task JSON"""
        return {
            "task_id": task.task_id,
            "prompt": task.prompt,
            "negative_prompt": task.negative_prompt,
            "duration": task.duration,
            "aspect_ratio": task.aspect_ratio,
            "resolution": f"{task.resolution[0]}x{task.resolution[1]}",
            "style": task.style,
            "camera_motion": task.camera_motion,
            "model": "lovart-video-v1",
            "seed": task.seed,
        }

    # ------------------------------------------------------------------
    # 通用 Prompt 格式（Veo / Hailuo / Pika / Luma）
    # ------------------------------------------------------------------
    def build_prompt_only(self, task: VideoModelTask) -> str:
        """构建纯 Prompt 格式"""
        lines = [
            f"Prompt: {task.prompt}",
            f"Duration: {task.duration}s",
            f"Aspect: {task.aspect_ratio}",
            f"Camera: {task.camera_motion}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export_tasks(
        self,
        tasks: list[VideoModelTask],
        output_dir: Path,
        model: str,
    ) -> Path:
        """导出任务到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        model_lower = model.lower()

        if model_lower == "comfyui":
            # 导出 Workflow
            for task in tasks:
                workflow = self.build_comfyui_workflow(task)
                path = output_dir / f"{task.task_id}_workflow.json"
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)
            return output_dir

        elif model_lower == "kling":
            data = [self.build_kling_task(t) for t in tasks]
            path = output_dir / "kling_tasks.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path

        elif model_lower == "wan":
            data = [self.build_wan_task(t) for t in tasks]
            path = output_dir / "wan_tasks.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path

        elif model_lower == "runway":
            data = [self.build_runway_task(t) for t in tasks]
            path = output_dir / "runway_tasks.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path

        elif model_lower == "lovart":
            data = [self.build_lovart_task(t) for t in tasks]
            path = output_dir / "lovart_tasks.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path

        else:
            # Prompt only
            prompts = [self.build_prompt_only(t) for t in tasks]
            path = output_dir / f"{model_lower}_prompts.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(prompts))
            return path

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    def _get_resolution(
        self,
        placement: str,
        aspect_ratio: str,
        config: ModelConfig,
    ) -> tuple[int, int]:
        """获取分辨率"""
        # 首先尝试版位映射
        placement_res = self.PLACEMENT_RESOLUTIONS.get(placement.lower(), {})
        if aspect_ratio in placement_res:
            return placement_res[aspect_ratio]
        # 其次用模型默认
        if aspect_ratio in config.supported_aspect_ratios:
            return config.default_resolution
        # 最后回退
        return (576, 1024)

    def _optimize_prompt(self, prompt: str, max_length: int) -> str:
        """优化提示词长度"""
        if len(prompt) <= max_length:
            return prompt
        # 截断到最后一个逗号
        truncated = prompt[:max_length]
        last_comma = truncated.rfind(",")
        if last_comma > 0:
            return truncated[:last_comma]
        return truncated

    def list_models(self) -> list[str]:
        """列出支持的模型"""
        return list(self._configs.keys())

    def get_model_config(self, model: str) -> ModelConfig | None:
        """获取模型配置"""
        return self._configs.get(model.lower())