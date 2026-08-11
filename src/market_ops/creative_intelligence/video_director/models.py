"""Video Director 数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WinnerDNA:
    """Winner 创意 DNA"""
    theme: str
    aspect_ratio: str
    lighting: str
    contrast: float
    saturation: float
    hook: str
    winning_elements: list[str] = field(default_factory=list)
    roas: float = 0.0
    ctr: float = 0.0
    cpi: float = 0.0
    source_video_id: str = ""
    content_type: str = ""  # 角色展示/剧情/玩法
    duration: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_adjust_row(cls, row: dict[str, Any]) -> WinnerDNA:
        """从 Adjust 数据行构建"""
        filename = row.get("filename", "")
        parts = filename.split("-")
        content_type = ""
        if len(parts) >= 5:
            content_type = parts[4] if parts[4] in ("juesezhanshi", "juqing", "wanfashipin", "chongwuzhanshi") else ""
        return cls(
            theme=row.get("content", ""),
            aspect_ratio=row.get("ratio", "9X16"),
            lighting="warm cinematic",
            contrast=0.15,
            saturation=0.45,
            hook=row.get("content", ""),
            roas=float(row.get("roas", 0)),
            ctr=float(row.get("ctr", 0)) if "ctr" in row else 0.0,
            cpi=float(row.get("cpi", 0)) if "cpi" in row else 0.0,
            source_video_id=row.get("v_num", ""),
            content_type=content_type,
            duration=row.get("duration", ""),
            metadata=row,
        )


@dataclass
class GameInfo:
    """游戏信息"""
    game: str
    genre: str
    core_loop: str
    target: str
    art_style: str = ""
    key_characters: list[str] = field(default_factory=list)
    key_items: list[str] = field(default_factory=list)


@dataclass
class AdGoal:
    """广告目标"""
    goal: str  # install / purchase / retention
    duration: int  # 秒
    platform: str  # facebook / tiktok / google
    format: str  # 9:16 / 1:1 / 16:9
    budget: float = 0.0
    cpi_target: float = 0.0
    roas_target: float = 0.0


@dataclass
class StoryboardScene:
    """分镜场景"""
    time: str
    scene: str
    camera: str
    motion: str
    action: str
    emotion: str
    visual_keywords: list[str] = field(default_factory=list)
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "scene": self.scene,
            "camera": self.camera,
            "motion": self.motion,
            "action": self.action,
            "emotion": self.emotion,
            "visual_keywords": self.visual_keywords,
            "duration": self.duration,
        }


@dataclass
class ComfyUIWorkflow:
    """ComfyUI 工作流配置"""
    positive: str
    negative: str
    workflow_type: str = "wan2.1_i2v"
    seed: int = -1
    steps: int = 30
    cfg: float = 6.0
    width: int = 832
    height: int = 480
    length: int = 81
    frame_rate: int = 8
    model: str = "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors"
    vae: str = "wan_2.1_vae.safetensors"
    clip: str = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    sampler: str = "euler"
    scheduler: str = "normal"
    image_ref: str = ""
    extra_nodes: dict[str, Any] = field(default_factory=dict)

    def to_api_json(self) -> dict[str, Any]:
        """生成 ComfyUI API 可用的 workflow JSON"""
        return {
            "1": {
                "inputs": {"unet_name": self.model, "weight_dtype": "fp8_e4m3fn"},
                "class_type": "UNETLoader",
            },
            "2": {
                "inputs": {"clip_name": self.clip, "type": "wan", "device": "default"},
                "class_type": "CLIPLoader",
            },
            "3": {
                "inputs": {"vae_name": self.vae},
                "class_type": "VAELoader",
            },
            "4": {
                "inputs": {"text": self.positive, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode",
            },
            "5": {
                "inputs": {"text": self.negative, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode",
            },
            "6": {
                "inputs": {"image": self.image_ref} if self.image_ref else {},
                "class_type": "LoadImage",
            },
            "7": {
                "inputs": {
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "vae": ["3", 0],
                    "width": self.width,
                    "height": self.height,
                    "length": self.length,
                    "batch_size": 1,
                    "start_image": ["6", 0],
                },
                "class_type": "WanImageToVideo",
            },
            "8": {
                "inputs": {
                    "model": ["1", 0],
                    "seed": self.seed if self.seed > 0 else 12345,
                    "steps": self.steps,
                    "cfg": self.cfg,
                    "sampler_name": self.sampler,
                    "scheduler": self.scheduler,
                    "positive": ["7", 0],
                    "negative": ["7", 1],
                    "latent_image": ["7", 2],
                    "denoise": 1.0,
                },
                "class_type": "KSampler",
            },
            "9": {
                "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
                "class_type": "VAEDecode",
            },
            "10": {
                "inputs": {
                    "images": ["9", 0],
                    "frame_rate": self.frame_rate,
                    "loop_count": 0,
                    "filename_prefix": "video_director_output",
                    "format": "video/h264-mp4",
                    "pingpong": False,
                    "save_output": True,
                },
                "class_type": "VHS_VideoCombine",
            },
        }


@dataclass
class VideoCreativePlan:
    """视频创意方案（最终输出）"""
    video_id: str
    creative_concept: str
    hook: dict[str, Any]
    storyboard: list[StoryboardScene]
    comfyui_workflow: ComfyUIWorkflow
    camera_plan: list[dict[str, Any]] = field(default_factory=list)
    action_plan: list[dict[str, Any]] = field(default_factory=list)
    quality_score: float = 0.0
    roas_reference: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "creative_concept": self.creative_concept,
            "hook": self.hook,
            "storyboard": [s.to_dict() for s in self.storyboard],
            "comfyui_prompt": {
                "positive": self.comfyui_workflow.positive,
                "negative": self.comfyui_workflow.negative,
            },
            "comfyui_workflow": self.comfyui_workflow.to_api_json(),
            "camera_plan": self.camera_plan,
            "action_plan": self.action_plan,
            "quality_score": self.quality_score,
            "roas_reference": self.roas_reference,
            "metadata": self.metadata,
        }
