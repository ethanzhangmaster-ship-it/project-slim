"""ComfyUI Adapter - ComfyUI 工作流适配器

把 Video Director 输出转换为 ComfyUI 可执行的 workflow JSON。

支持：
- Wan2.1 I2V（本地）
- Wan2.1 T2V（本地）
- ComfyUI API 提交
"""
from __future__ import annotations

from typing import Any

from .models import VideoCreativePlan, ComfyUIWorkflow


class ComfyUIAdapter:
    """ComfyUI 工作流适配器"""

    # 分辨率映射
    RESOLUTION_MAP: dict[str, tuple[int, int]] = {
        "9:16": (576, 1024),
        "1:1": (1024, 1024),
        "16:9": (1024, 576),
        "4:5": (1024, 1280),
    }

    # 模型配置
    MODEL_CONFIGS: dict[str, dict[str, Any]] = {
        "wan2.1_i2v_480p": {
            "model": "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "max_length": 81,
            "default_length": 81,
        },
        "wan2.1_i2v_720p": {
            "model": "Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "max_length": 81,
            "default_length": 81,
        },
        "wan2.1_t2v_480p": {
            "model": "Wan2_1-T2V-14B_fp8_e4m3fn.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "max_length": 81,
            "default_length": 81,
        },
    }

    def __init__(self, base_url: str = "http://192.168.124.13:8188"):
        self.base_url = base_url
        self._res_map = dict(self.RESOLUTION_MAP)
        self._model_cfg = {k: dict(v) for k, v in self.MODEL_CONFIGS.items()}

    def adapt(
        self,
        plan: VideoCreativePlan,
        model_preset: str = "wan2.1_i2v_480p",
        image_ref: str = "",
    ) -> dict[str, Any]:
        """把 VideoCreativePlan 转换为 ComfyUI Workflow JSON

        Args:
            plan: 视频创意方案
            model_preset: 模型预设
            image_ref: 首帧参考图文件名

        Returns:
            ComfyUI API 可用的 workflow JSON
        """
        cfg = self._model_cfg.get(model_preset, self._model_cfg["wan2.1_i2v_480p"])
        workflow = plan.comfyui_workflow

        # 根据比例调整分辨率
        format_key = plan.metadata.get("format", "9:16")
        width, height = self._res_map.get(format_key, (832, 480))

        # 构建完整 workflow
        return self._build_workflow(
            positive=workflow.positive,
            negative=workflow.negative,
            model=cfg["model"],
            vae=cfg["vae"],
            clip=cfg["clip"],
            width=width,
            height=height,
            length=cfg["default_length"],
            seed=workflow.seed if workflow.seed > 0 else 12345,
            steps=workflow.steps,
            cfg_scale=workflow.cfg,
            image_ref=image_ref or workflow.image_ref,
            filename_prefix=plan.video_id,
        )

    def _build_workflow(
        self,
        positive: str,
        negative: str,
        model: str,
        vae: str,
        clip: str,
        width: int,
        height: int,
        length: int,
        seed: int,
        steps: int,
        cfg_scale: float,
        image_ref: str,
        filename_prefix: str,
    ) -> dict[str, Any]:
        """构建 ComfyUI Workflow JSON"""
        workflow: dict[str, Any] = {
            "1": {
                "inputs": {"unet_name": model, "weight_dtype": "fp8_e4m3fn"},
                "class_type": "UNETLoader",
            },
            "2": {
                "inputs": {"clip_name": clip, "type": "wan", "device": "default"},
                "class_type": "CLIPLoader",
            },
            "3": {
                "inputs": {"vae_name": vae},
                "class_type": "VAELoader",
            },
            "4": {
                "inputs": {"text": positive, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode",
            },
            "5": {
                "inputs": {"text": negative, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode",
            },
        }

        # 如果有参考图，加入 LoadImage + WanImageToVideo
        if image_ref:
            workflow["6"] = {
                "inputs": {"image": image_ref},
                "class_type": "LoadImage",
            }
            workflow["7"] = {
                "inputs": {
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "vae": ["3", 0],
                    "width": width,
                    "height": height,
                    "length": length,
                    "batch_size": 1,
                    "start_image": ["6", 0],
                },
                "class_type": "WanImageToVideo",
            }
        else:
            # T2V 模式
            workflow["7"] = {
                "inputs": {
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "vae": ["3", 0],
                    "width": width,
                    "height": height,
                    "length": length,
                    "batch_size": 1,
                },
                "class_type": "WanTextToVideo",
            }

        workflow["8"] = {
            "inputs": {
                "model": ["1", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg_scale,
                "sampler_name": "euler",
                "scheduler": "normal",
                "positive": ["7", 0],
                "negative": ["7", 1],
                "latent_image": ["7", 2],
                "denoise": 1.0,
            },
            "class_type": "KSampler",
        }
        workflow["9"] = {
            "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
            "class_type": "VAEDecode",
        }
        workflow["10"] = {
            "inputs": {
                "images": ["9", 0],
                "frame_rate": 8,
                "loop_count": 0,
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
            "class_type": "VHS_VideoCombine",
        }

        return workflow

    def build_flux_workflow(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: int = 42,
        filename_prefix: str = "flux_keyframe",
    ) -> dict[str, Any]:
        """构建 Flux 首帧图生成 Workflow"""
        return {
            "1": {
                "inputs": {"ckpt_name": "flux\\flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple",
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "3": {
                "inputs": {"text": negative or "", "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "4": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage",
            },
            "5": {
                "inputs": {
                    "seed": seed,
                    "steps": 30,
                    "cfg": 6.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                },
                "class_type": "KSampler",
            },
            "6": {
                "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode",
            },
            "7": {
                "inputs": {"filename_prefix": filename_prefix, "images": ["6", 0]},
                "class_type": "SaveImage",
            },
        }

    def submit_to_comfyui(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """提交 workflow 到 ComfyUI API（需要外部调用）

        Returns:
            {"prompt_id": ..., "number": ...}
        """
        import requests
        import os

        os.environ["NO_PROXY"] = self.base_url.split("://")[-1].split(":")[0]
        url = f"{self.base_url}/prompt"
        r = requests.post(url, json={"prompt": workflow}, timeout=30)
        return r.json()
