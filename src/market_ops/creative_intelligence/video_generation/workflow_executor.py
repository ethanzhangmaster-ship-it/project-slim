"""Workflow Executor - 工作流执行器

将 Video Director 输出转换为 ComfyUI 可执行任务。
支持：Wan2.1 I2V / Wan2.1 T2V / Flux 首帧图
"""
from __future__ import annotations

from typing import Any

from ..video_director.models import VideoCreativePlan


class WorkflowExecutor:
    """工作流执行器"""

    # 模型预设配置
    PRESETS: dict[str, dict[str, Any]] = {
        "wan2.1_i2v_480p": {
            "model": "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "max_length": 81,
            "class_type_i2v": "WanImageToVideo",
        },
        "wan2.1_i2v_720p": {
            "model": "Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "max_length": 81,
            "class_type_i2v": "WanImageToVideo",
        },
        "wan2.1_t2v_480p": {
            "model": "Wan2_1-T2V-14B_fp8_e4m3fn.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "max_length": 81,
            "class_type_t2v": "WanTextToVideo",
        },
    }

    # 分辨率映射
    RESOLUTIONS: dict[str, tuple[int, int]] = {
        "9:16": (576, 1024),
        "1:1": (1024, 1024),
        "16:9": (1024, 576),
        "4:5": (1024, 1280),
        "9X16": (576, 1024),
        "1X1": (1024, 1024),
    }

    def __init__(self):
        self._presets = {k: dict(v) for k, v in self.PRESETS.items()}
        self._resolutions = dict(self.RESOLUTIONS)

    def build_video_workflow(
        self,
        plan: VideoCreativePlan,
        model_preset: str = "wan2.1_i2v_480p",
        image_ref: str = "",
        seed: int = -1,
    ) -> dict[str, Any]:
        """构建视频生成 workflow

        Args:
            plan: VideoCreativePlan
            model_preset: 模型预设
            image_ref: 首帧参考图文件名（I2V 模式）
            seed: 随机种子

        Returns:
            ComfyUI API workflow JSON
        """
        cfg = self._presets.get(model_preset, self._presets["wan2.1_i2v_480p"])
        workflow = plan.comfyui_workflow

        # 分辨率
        fmt = plan.metadata.get("format", "9:16")
        width, height = self._resolutions.get(fmt, (832, 480))

        # 如果不是 9:16，使用默认横版分辨率
        if fmt not in self._resolutions:
            width, height = 832, 480

        s = seed if seed > 0 else (workflow.seed if workflow.seed > 0 else 12345)

        return self._build_wan_workflow(
            positive=workflow.positive,
            negative=workflow.negative,
            model=cfg["model"],
            vae=cfg["vae"],
            clip=cfg["clip"],
            width=width,
            height=height,
            length=cfg.get("max_length", 81),
            seed=s,
            steps=workflow.steps,
            cfg_scale=workflow.cfg,
            image_ref=image_ref,
            filename_prefix=plan.video_id,
        )

    def build_flux_workflow(
        self,
        plan: VideoCreativePlan,
        seed: int = 42,
        width: int = 1024,
        height: int = 1024,
    ) -> dict[str, Any]:
        """构建 Flux 首帧图 workflow"""
        flux_prompt = plan.metadata.get("flux_positive", plan.comfyui_workflow.positive)
        negative = plan.comfyui_workflow.negative

        return {
            "1": {
                "inputs": {"ckpt_name": "flux\\flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple",
            },
            "2": {
                "inputs": {"text": flux_prompt, "clip": ["1", 1]},
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
                "inputs": {
                    "filename_prefix": f"{plan.video_id}_flux",
                    "images": ["6", 0],
                },
                "class_type": "SaveImage",
            },
        }

    def _build_wan_workflow(
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
        """构建 Wan 工作流"""
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
