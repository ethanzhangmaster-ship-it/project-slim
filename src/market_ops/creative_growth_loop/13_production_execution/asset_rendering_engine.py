"""Asset Rendering Layer - 素材渲染层（真实素材生成）

将 Render Constraint JSON 转换为真实文件：
- image/png / image/jpg
- thumbnail
- 带 hash/version

输出必须包含：
- asset_id
- file_path
- sha256
- size
- format
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class RenderedAsset:
    """渲染后的素材"""
    asset_id: str
    file_path: str
    sha256: str
    size_bytes: int
    format: str
    width: int = 0
    height: int = 0
    version: int = 1
    creative_id: str = ""
    template_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "file_path": self.file_path,
            "sha256": self.sha256,
            "size": self.size_bytes,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "version": self.version,
            "creative_id": self.creative_id,
            "template_id": self.template_id,
        }


class AssetRenderingEngine:
    """素材渲染引擎 - Render Constraints → 真实图片文件"""
    
    def __init__(self, output_dir: str = "assets/renders"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._assets: Dict[str, RenderedAsset] = {}
    
    def render_from_constraints(self, render_constraints: Dict[str, Any],
                                 creative_id: str = "",
                                 template_id: str = "",
                                 format: str = "png",
                                 width: int = 1080,
                                 height: int = 1080) -> RenderedAsset:
        """根据 Render Constraints 生成真实图片素材
        
        Args:
            render_constraints: 渲染约束（reward/mechanism/identity 结构）
            creative_id: 创意ID
            template_id: 模板ID
            format: 图片格式 png/jpg
            width: 宽度
            height: 高度
        
        Returns:
            RenderedAsset: 包含真实文件路径和hash
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return self._render_fallback(render_constraints, creative_id, template_id, format, width, height)
        
        asset_id = f"img_{uuid.uuid4().hex[:12]}"
        file_name = f"{asset_id}.{format}"
        file_path = self.output_dir / file_name
        
        img = Image.new('RGB', (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        
        reward_cfg = render_constraints.get("reward", {})
        mechanism_cfg = render_constraints.get("mechanism", {})
        identity_cfg = render_constraints.get("identity", {})
        
        reward_size = reward_cfg.get("size", 0.45)
        reward_pos = reward_cfg.get("position", "center")
        reward_glow = reward_cfg.get("glow", "high")
        
        reward_w = int(width * reward_size)
        reward_h = int(height * reward_size)
        
        if reward_pos == "center":
            reward_x = (width - reward_w) // 2
            reward_y = (height - reward_h) // 2
        elif reward_pos == "right":
            reward_x = width - reward_w - 40
            reward_y = (height - reward_h) // 2
        else:
            reward_x = 40
            reward_y = (height - reward_h) // 2
        
        glow_intensity = {"high": 60, "medium": 30, "low": 10}.get(reward_glow, 30)
        for i in range(10):
            alpha = int(glow_intensity * (1 - i / 10))
            glow_color = (min(255, 100 + alpha), min(255, 200 + alpha), min(255, 255))
            pad = i * 8
            draw.rounded_rectangle(
                [reward_x - pad, reward_y - pad,
                 reward_x + reward_w + pad, reward_y + reward_h + pad],
                radius=24 + pad,
                fill=glow_color
            )
        
        draw.rounded_rectangle(
            [reward_x, reward_y, reward_x + reward_w, reward_y + reward_h],
            radius=24,
            fill=(255, 215, 100),
            outline=(255, 180, 50),
            width=4
        )
        
        try:
            font = ImageFont.truetype("arial.ttf", int(reward_h * 0.15))
        except:
            font = ImageFont.load_default()
        
        reward_text = "REWARD"
        bbox = draw.textbbox((0, 0), reward_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((reward_x + (reward_w - tw) // 2, reward_y + (reward_h - th) // 2),
                 reward_text, fill=(139, 69, 19), font=font)
        
        mech_visibility = mechanism_cfg.get("visibility", "high")
        mech_alpha = {"high": 200, "medium": 150, "low": 100}.get(mech_visibility, 150)
        
        mech_w = int(width * 0.3)
        mech_h = int(height * 0.15)
        mech_x = (width - mech_w) // 2
        mech_y = reward_y + reward_h + 30
        
        mech_color = (70, 130, 180, mech_alpha)
        draw.rounded_rectangle(
            [mech_x, mech_y, mech_x + mech_w, mech_y + mech_h],
            radius=12,
            fill=mech_color[:3]
        )
        
        try:
            mech_font = ImageFont.truetype("arial.ttf", int(mech_h * 0.4))
        except:
            mech_font = ImageFont.load_default()
        
        mech_text = "MECHANISM"
        bbox = draw.textbbox((0, 0), mech_text, font=mech_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((mech_x + (mech_w - tw) // 2, mech_y + (mech_h - th) // 2),
                 mech_text, fill=(255, 255, 255), font=mech_font)
        
        ident_opacity = identity_cfg.get("opacity", "low")
        ident_size = {"high": 0.15, "medium": 0.1, "low": 0.06}.get(ident_opacity, 0.08)
        
        ident_w = int(width * ident_size)
        ident_h = ident_w
        ident_x = width - ident_w - 30
        ident_y = 30
        
        ident_color = (100, 100, 120)
        draw.ellipse(
            [ident_x, ident_y, ident_x + ident_w, ident_y + ident_h],
            fill=ident_color
        )
        
        title_text = template_id.replace("_", " ").upper()
        try:
            title_font = ImageFont.truetype("arial.ttf", 40)
        except:
            title_font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, 60), title_text, fill=(200, 220, 255), font=title_font)
        
        footer_text = f"asset: {asset_id} | v1"
        try:
            footer_font = ImageFont.truetype("arial.ttf", 20)
        except:
            footer_font = ImageFont.load_default()
        
        draw.text((30, height - 50), footer_text, fill=(100, 120, 150), font=footer_font)
        
        save_kwargs = {}
        if format == "jpg":
            save_kwargs["quality"] = 90
            format_save = "JPEG"
        else:
            format_save = "PNG"
        
        img.save(file_path, format=format_save, **save_kwargs)
        
        sha256_hash = self._compute_sha256(file_path)
        file_size = os.path.getsize(file_path)
        
        asset = RenderedAsset(
            asset_id=asset_id,
            file_path=str(file_path),
            sha256=sha256_hash,
            size_bytes=file_size,
            format=format,
            width=width,
            height=height,
            version=1,
            creative_id=creative_id,
            template_id=template_id,
        )
        
        self._assets[asset_id] = asset
        return asset
    
    def _render_fallback(self, render_constraints: Dict[str, Any],
                         creative_id: str, template_id: str,
                         format: str, width: int, height: int) -> RenderedAsset:
        """无PIL时的降级方案：生成一个带约束信息的JSON文件"""
        asset_id = f"img_{uuid.uuid4().hex[:12]}"
        file_name = f"{asset_id}.{format}.json"
        file_path = self.output_dir / file_name
        
        content = {
            "asset_id": asset_id,
            "format": format,
            "width": width,
            "height": height,
            "render_constraints": render_constraints,
            "creative_id": creative_id,
            "template_id": template_id,
            "generated_at": int(time.time()),
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        
        sha256_hash = self._compute_sha256(file_path)
        file_size = os.path.getsize(file_path)
        
        return RenderedAsset(
            asset_id=asset_id,
            file_path=str(file_path),
            sha256=sha256_hash,
            size_bytes=file_size,
            format=format,
            width=width,
            height=height,
            version=1,
            creative_id=creative_id,
            template_id=template_id,
        )
    
    def generate_thumbnail(self, asset_id: str, size: int = 200) -> Optional[RenderedAsset]:
        """生成缩略图"""
        if asset_id not in self._assets:
            return None
        
        original = self._assets[asset_id]
        
        try:
            from PIL import Image
            
            img = Image.open(original.file_path)
            img.thumbnail((size, size))
            
            thumb_id = f"thumb_{asset_id}"
            file_name = f"{thumb_id}.{original.format}"
            thumb_path = self.output_dir / file_name
            
            if original.format == "jpg":
                img.save(thumb_path, "JPEG", quality=80)
            else:
                img.save(thumb_path, "PNG")
            
            sha256_hash = self._compute_sha256(thumb_path)
            
            return RenderedAsset(
                asset_id=thumb_id,
                file_path=str(thumb_path),
                sha256=sha256_hash,
                size_bytes=os.path.getsize(thumb_path),
                format=original.format,
                width=size,
                height=int(size * original.height / original.width),
                version=1,
                creative_id=original.creative_id,
                template_id=original.template_id,
            )
        except:
            return None
    
    def get_asset(self, asset_id: str) -> Optional[RenderedAsset]:
        return self._assets.get(asset_id)
    
    def _compute_sha256(self, file_path: str) -> str:
        """计算文件 SHA256"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
