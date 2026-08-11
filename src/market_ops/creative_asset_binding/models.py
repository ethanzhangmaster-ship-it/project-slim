"""E11 Phase 3 — Asset Binding 数据模型。

定义素材绑定相关数据结构：
  - EagleAsset:       Eagle 素材库中的单个素材
  - LovartAsset:      Lovart 生成的单个素材
  - AssetBindingResult: 单次绑定结果
  - BindingMethod:    匹配方法枚举
  - AssetSourceType:  素材来源类型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BindingMethod(str, Enum):
    """匹配方法枚举。"""
    EXACT_ID = "exact_id"               # 精确 creative_asset_id 匹配
    FILENAME = "filename"               # 文件名解析匹配
    VISUAL_HASH = "visual_hash"         # 视觉 Hash / CLIP 匹配
    LEGACY_ID = "legacy_id"             # 旧格式 ID 匹配
    CAMPAIGN_ADGROUP = "campaign_adgroup"  # Campaign+Adgroup 回退
    UNKNOWN = "unknown"


class AssetSourceType(str, Enum):
    """素材来源类型。"""
    FACEBOOK = "FACEBOOK"
    LOVART = "LOVART"
    EAGLE = "EAGLE"


@dataclass
class EagleAsset:
    """Eagle 素材库中的单个素材。

    Usage:
        asset = EagleAsset(
            filename="MW_VIDEO_260721_000123.mp4",
            path="D:/eagle/MW_VIDEO_260721_000123.mp4",
            duration=32.5,
            resolution="1080x1920",
            file_hash="abc123",
        )
    """

    filename: str = ""           # 文件名
    path: str = ""               # 完整路径
    creative_asset_id: str = ""  # 解析出的统一编号
    duration: float = 0.0        # 视频时长（秒）
    resolution: str = ""         # 分辨率 "WxH"
    file_hash: str = ""          # 文件哈希
    file_size: int = 0           # 文件大小（bytes）
    created_at: str = ""         # 文件创建时间

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "path": self.path,
            "creative_asset_id": self.creative_asset_id,
            "duration": self.duration,
            "resolution": self.resolution,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EagleAsset:
        return cls(
            filename=data.get("filename", ""),
            path=data.get("path", ""),
            creative_asset_id=data.get("creative_asset_id", ""),
            duration=float(data.get("duration", 0.0)),
            resolution=data.get("resolution", ""),
            file_hash=data.get("file_hash", ""),
            file_size=int(data.get("file_size", 0)),
            created_at=data.get("created_at", ""),
        )


@dataclass
class LovartAsset:
    """Lovart 生成的单个素材。

    Usage:
        asset = LovartAsset(
            generation_id="lovart_gen_001",
            image_path="D:/lovart/outputs/img_001.png",
            prompt="A witch merging two dragons...",
            seed=42,
        )
    """

    generation_id: str = ""      # Lovart 生成任务 ID
    image_path: str = ""         # 图片本地路径
    image_url: str = ""          # 图片 URL
    prompt: str = ""             # 生成 prompt
    seed: int = 0                # 随机种子
    model: str = ""              # 模型名称
    created_at: str = ""         # 生成时间

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "image_path": self.image_path,
            "image_url": self.image_url,
            "prompt": self.prompt,
            "seed": self.seed,
            "model": self.model,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LovartAsset:
        return cls(
            generation_id=data.get("generation_id", ""),
            image_path=data.get("image_path", ""),
            image_url=data.get("image_url", ""),
            prompt=data.get("prompt", ""),
            seed=int(data.get("seed", 0)),
            model=data.get("model", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class AssetBindingResult:
    """单次素材绑定结果。

    Usage:
        result = AssetBindingResult(
            creative_asset_id="MW_VIDEO_260721_000123",
            source=AssetSourceType.EAGLE,
            matched=True,
            confidence=1.0,
            method=BindingMethod.EXACT_ID,
            asset_path="D:/eagle/MW_VIDEO_260721_000123.mp4",
        )
    """

    creative_asset_id: str = ""
    source: AssetSourceType = AssetSourceType.EAGLE
    matched: bool = False
    confidence: float = 0.0
    method: BindingMethod = BindingMethod.UNKNOWN
    asset_path: str = ""
    asset_filename: str = ""
    error: str = ""

    @property
    def is_high_confidence(self) -> bool:
        return self.matched and self.confidence >= 0.85

    @property
    def is_possible_match(self) -> bool:
        return self.matched and 0.85 > self.confidence >= 0.5

    @property
    def is_low_confidence(self) -> bool:
        return self.matched and self.confidence <= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "source": self.source.value,
            "matched": self.matched,
            "confidence": self.confidence,
            "method": self.method.value,
            "asset_path": self.asset_path,
            "asset_filename": self.asset_filename,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetBindingResult:
        return cls(
            creative_asset_id=data.get("creative_asset_id", ""),
            source=AssetSourceType(data.get("source", "EAGLE")),
            matched=bool(data.get("matched", False)),
            confidence=float(data.get("confidence", 0.0)),
            method=BindingMethod(data.get("method", "unknown")),
            asset_path=data.get("asset_path", ""),
            asset_filename=data.get("asset_filename", ""),
            error=data.get("error", ""),
        )