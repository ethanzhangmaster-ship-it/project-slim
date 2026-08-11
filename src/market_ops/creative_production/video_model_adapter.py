"""Video Model Adapter - 视频模型适配器

统一适配 9 种视频模型：
- ComfyUI
- Wan
- Kling
- Runway
- Veo
- Lovart
- Pika
- Luma
- Hailuo

每个模型输出：
- Workflow（任务配置）
- Task（任务）
- Prompt（提示词）
- JSON（统一接口）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelTask:
    """单个模型任务"""
    task_id: str
    model: str
    shot_id: str
    prompt: str
    negative_prompt: str
    duration: float
    resolution: str              # 720p / 1080p / 4k
    aspect_ratio: str
    seed: int = -1
    guidance_scale: float = 7.5
    steps: int = 30
    fps: int = 24
    extra: dict[str, Any] = field(default_factory=dict)
    workflow_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "shot_id": self.shot_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "duration": self.duration,
            "resolution": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "seed": self.seed,
            "guidance_scale": self.guidance_scale,
            "steps": self.steps,
            "fps": self.fps,
            "extra": self.extra,
            "workflow_json": self.workflow_json,
        }


class VideoModelAdapter:
    """视频模型适配器"""

    # 模型注册表
    MODEL_REGISTRY: dict[str, dict[str, Any]] = {
        "comfyui": {
            "name": "comfyui",
            "display_name": "ComfyUI",
            "max_duration": 8.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": True,
            "supports_lora": True,
            "api_style": "workflow_json",
        },
        "wan": {
            "name": "wan",
            "display_name": "Wan",
            "max_duration": 10.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": False,
            "supports_lora": True,
            "api_style": "http",
        },
        "kling": {
            "name": "kling",
            "display_name": "Kling",
            "max_duration": 10.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": False,
            "supports_lora": False,
            "api_style": "http",
        },
        "runway": {
            "name": "runway",
            "display_name": "Runway Gen-3",
            "max_duration": 10.0,
            "resolutions": ["720p", "1080p", "4k"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": True,
            "supports_lora": False,
            "api_style": "http",
        },
        "veo": {
            "name": "veo",
            "display_name": "Veo",
            "max_duration": 8.0,
            "resolutions": ["1080p", "4k"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": True,
            "supports_lora": False,
            "api_style": "http",
        },
        "lovart": {
            "name": "lovart",
            "display_name": "Lovart",
            "max_duration": 6.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": False,
            "supports_lora": True,
            "api_style": "http",
        },
        "pika": {
            "name": "pika",
            "display_name": "Pika",
            "max_duration": 4.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": False,
            "supports_lora": False,
            "api_style": "http",
        },
        "luma": {
            "name": "luma",
            "display_name": "Luma Dream Machine",
            "max_duration": 5.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": False,
            "supports_lora": False,
            "api_style": "http",
        },
        "hailuo": {
            "name": "hailuo",
            "display_name": "Hailuo",
            "max_duration": 6.0,
            "resolutions": ["720p", "1080p"],
            "default_resolution": "1080p",
            "supports_image_ref": True,
            "supports_video_ref": False,
            "supports_lora": False,
            "api_style": "http",
        },
    }

    def __init__(self):
        self._registry = {k: dict(v) for k, v in self.MODEL_REGISTRY.items()}

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def adapt(
        self,
        shot: Any,
        model: str,
        aspect_ratio: str = "9:16",
        resolution: str | None = None,
    ) -> ModelTask:
        """把 Shot 适配到指定模型的 Task

        Args:
            shot: 镜头
            model: 模型名
            aspect_ratio: 画幅
            resolution: 分辨率
        """
        if model not in self._registry:
            model = "kling"
        cfg = self._registry[model]

        # 截断 duration 到模型最大
        duration = min(shot.duration, cfg["max_duration"])
        if duration < 1.0:
            duration = 1.0

        # 分辨率
        if resolution is None:
            resolution = cfg["default_resolution"]
        elif resolution not in cfg["resolutions"]:
            resolution = cfg["default_resolution"]

        # 模型特定 prompt 调整
        prompt = self._adapt_prompt(shot.prompt, model)
        negative = self._adapt_negative(shot.negative_prompt, model)

        # 模型特定参数
        guidance, steps = self._model_specific_params(model)
        extra = self._build_extra(shot, model, cfg)

        # workflow_json
        workflow = self._build_workflow_json(model, shot, prompt, negative, duration, resolution)

        return ModelTask(
            task_id=f"task_{model}_{shot.shot_id}",
            model=model,
            shot_id=shot.shot_id,
            prompt=prompt,
            negative_prompt=negative,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            guidance_scale=guidance,
            steps=steps,
            fps=24,
            extra=extra,
            workflow_json=workflow,
        )

    def adapt_batch(
        self,
        shots: list[Any],
        model: str,
        aspect_ratio: str = "9:16",
    ) -> list[ModelTask]:
        """批量适配"""
        return [self.adapt(s, model, aspect_ratio) for s in shots]

    # ------------------------------------------------------------------
    # 模型特定
    # ------------------------------------------------------------------
    def _adapt_prompt(self, base_prompt: str, model: str) -> str:
        """模型特定 prompt 调整"""
        if model == "kling":
            return f"{base_prompt} --motion moderate --style cinematic"
        if model == "runway":
            return f"Cinematic shot. {base_prompt}"
        if model == "veo":
            return f"High quality video. {base_prompt}"
        if model == "pika":
            # pika 适合短 prompt
            return base_prompt[:300]
        if model == "luma":
            return f"{base_prompt} --quality high"
        if model == "lovart":
            return f"{base_prompt} --style vivid"
        if model == "hailuo":
            return f"{base_prompt} [cinematic]"
        if model == "wan":
            return base_prompt
        if model == "comfyui":
            return base_prompt
        return base_prompt

    def _adapt_negative(self, base_negative: str, model: str) -> str:
        """模型特定反向 prompt"""
        return base_negative

    def _model_specific_params(self, model: str) -> tuple[float, int]:
        """guidance_scale, steps"""
        params = {
            "kling":   (7.5, 30),
            "runway":  (8.0, 28),
            "veo":     (7.0, 25),
            "wan":     (7.5, 30),
            "comfyui": (7.0, 25),
            "lovart":  (8.0, 30),
            "pika":    (6.5, 20),
            "luma":    (7.5, 25),
            "hailuo":  (7.5, 28),
        }
        return params.get(model, (7.5, 30))

    def _build_extra(
        self,
        shot: Any,
        model: str,
        cfg: dict[str, Any],
    ) -> dict[str, Any]:
        """构造模型特定扩展参数"""
        extra: dict[str, Any] = {}
        if cfg["supports_image_ref"]:
            ref = shot.metadata.get("ref_image", "") if hasattr(shot, "metadata") else ""
            if ref:
                extra["image_ref"] = ref
        if cfg["supports_video_ref"]:
            ref = shot.metadata.get("ref_video", "") if hasattr(shot, "metadata") else ""
            if ref:
                extra["video_ref"] = ref
        if cfg["supports_lora"]:
            lora = shot.metadata.get("lora", "") if hasattr(shot, "metadata") else ""
            if lora:
                extra["lora"] = lora
        # 摄像机
        if hasattr(shot, "camera_motion") and shot.camera_motion:
            extra["camera_motion"] = shot.camera_motion
        return extra

    def _build_workflow_json(
        self,
        model: str,
        shot: Any,
        prompt: str,
        negative: str,
        duration: float,
        resolution: str,
    ) -> dict[str, Any]:
        """构造模型 workflow JSON"""
        if model == "comfyui":
            return {
                "3": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": 42,
                        "steps": 25,
                        "cfg": 7.0,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                    },
                },
                "prompt": prompt,
                "negative_prompt": negative,
                "duration": duration,
                "resolution": resolution,
            }
        # 默认 HTTP 风格
        return {
            "model": model,
            "prompt": prompt,
            "negative_prompt": negative,
            "duration": duration,
            "resolution": resolution,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        }

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def list_models(self) -> list[str]:
        """列出所有支持的模型"""
        return list(self._registry.keys())

    def get_model_info(self, model: str) -> dict[str, Any] | None:
        """获取模型信息"""
        return self._registry.get(model)

    def select_best_model(
        self,
        duration: float,
        needs_image_ref: bool = False,
        needs_video_ref: bool = False,
        needs_lora: bool = False,
    ) -> str:
        """根据需求选择最佳模型"""
        candidates = list(self._registry.keys())
        for m in candidates:
            cfg = self._registry[m]
            if duration > cfg["max_duration"]:
                continue
            if needs_image_ref and not cfg["supports_image_ref"]:
                continue
            if needs_video_ref and not cfg["supports_video_ref"]:
                continue
            if needs_lora and not cfg["supports_lora"]:
                continue
            return m
        return "kling"
