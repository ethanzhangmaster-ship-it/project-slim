"""L1 - Asset Production Layer — 资产生产层

功能：
- Image Renderer：生成真实图片素材
- Video Renderer：生成视频素材（可选）
- Variant Generator：A/B 测试变体生成

输出标准：
{
  "asset_id": "img_001",
  "type": "image",
  "path": "/assets/img_001.png",
  "cdn_url": "https://cdn.xxx.com/img_001.png",
  "hash": "sha256..."
}
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class AssetMetadata:
    """资产元数据标准"""
    asset_id: str
    type: str  # image / video
    format: str  # png / jpg / mp4
    path: str
    cdn_url: str = ""
    hash: str = ""
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    duration_sec: float = 0.0  # for video
    version: int = 1
    creative_id: str = ""
    variant_type: str = "original"  # original / hook_a / hook_b / cta_variant
    variant_id: str = ""
    created_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "type": self.type,
            "format": self.format,
            "path": self.path,
            "cdn_url": self.cdn_url,
            "hash": self.hash,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
            "duration_sec": self.duration_sec,
            "version": self.version,
            "creative_id": self.creative_id,
            "variant_type": self.variant_type,
            "variant_id": self.variant_id,
            "created_at": self.created_at,
        }


@dataclass
class VariantConfig:
    """变体配置"""
    variant_type: str  # hook_a / hook_b / cta_variant / color_variant
    modifications: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_type": self.variant_type,
            "modifications": self.modifications,
        }


class ImageRenderer:
    """图片渲染器 — 将 layout_ast 转换为真实图片
    
    支持渲染引擎：
    - PIL（默认，本地渲染）
    - Canvas（预留）
    - Figma API（预留）
    """
    
    def __init__(self, output_dir: str = "memory/assets",
                 default_width: int = 1080,
                 default_height: int = 1080):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_width = default_width
        self.default_height = default_height
    
    def render(self,
               creative_id: str,
               layout_ast: Dict[str, Any],
               render_constraints: Dict[str, Any],
               variant_config: Optional[VariantConfig] = None) -> AssetMetadata:
        """渲染单个图片资产
        
        Args:
            creative_id: 创意ID
            layout_ast: 布局AST
            render_constraints: 渲染约束
            variant_config: 变体配置（可选）
        
        Returns:
            AssetMetadata: 资产元数据
        """
        if not PIL_AVAILABLE:
            return self._create_placeholder_asset(creative_id, variant_config)
        
        width = render_constraints.get("width", self.default_width)
        height = render_constraints.get("height", self.default_height)
        
        variant_type = variant_config.variant_type if variant_config else "original"
        variant_id = variant_config.variant_type if variant_config else ""
        
        asset_id = f"img_{uuid.uuid4().hex[:12]}"
        filename = f"{asset_id}.png"
        file_path = self.output_dir / filename
        
        img = Image.new('RGB', (width, height), color=self._get_background_color(render_constraints, variant_config))
        draw = ImageDraw.Draw(img)
        
        self._render_elements(draw, layout_ast, render_constraints, variant_config, width, height)
        
        img.save(file_path, 'PNG')
        
        sha256_hash = self._compute_hash(file_path)
        size_bytes = os.path.getsize(file_path)
        
        return AssetMetadata(
            asset_id=asset_id,
            type="image",
            format="png",
            path=str(file_path),
            hash=sha256_hash,
            size_bytes=size_bytes,
            width=width,
            height=height,
            creative_id=creative_id,
            variant_type=variant_type,
            variant_id=variant_id,
            created_at=int(time.time()),
        )
    
    def _get_background_color(self, constraints: Dict[str, Any],
                               variant: Optional[VariantConfig]) -> Tuple[int, int, int]:
        """获取背景颜色"""
        base_color = constraints.get("background_color", (30, 30, 50))
        
        if variant and "color_shift" in variant.modifications:
            shift = variant.modifications["color_shift"]
            return (
                min(255, base_color[0] + shift[0]),
                min(255, base_color[1] + shift[1]),
                min(255, base_color[2] + shift[2]),
            )
        
        return base_color
    
    def _render_elements(self, draw: ImageDraw.Draw,
                          ast: Dict[str, Any],
                          constraints: Dict[str, Any],
                          variant: Optional[VariantConfig],
                          width: int, height: int):
        """渲染视觉元素"""
        nodes_raw = ast.get("nodes", {})
        
        if isinstance(nodes_raw, dict):
            node_list = list(nodes_raw.values())
        else:
            node_list = list(nodes_raw)
        
        reward_node = None
        mechanism_node = None
        identity_node = None
        
        for node in node_list:
            node_id = node.get("node_id", "")
            if "reward" in node_id or "result" in node_id or "after" in node_id:
                reward_node = node
            elif "mechanism" in node_id or "mech" in node_id:
                mechanism_node = node
            elif "identity" in node_id or "character" in node_id or "witch" in node_id:
                identity_node = node
        
        if reward_node:
            self._render_reward(draw, reward_node, constraints, variant, width, height)
        
        if mechanism_node:
            self._render_mechanism(draw, mechanism_node, constraints, variant, width, height)
        
        if identity_node:
            self._render_identity(draw, identity_node, constraints, variant, width, height)
        
        self._render_hook_text(draw, constraints, variant, width, height)
        self._render_cta(draw, constraints, variant, width, height)
    
    def _render_reward(self, draw: ImageDraw.Draw,
                        node: Dict[str, Any],
                        constraints: Dict[str, Any],
                        variant: Optional[VariantConfig],
                        width: int, height: int):
        """渲染奖励视觉"""
        reward_text = constraints.get("reward_text", "WIN BIG!")
        
        if variant and "hook_text" in variant.modifications:
            reward_text = variant.modifications["hook_text"]
        
        x = width // 2
        y = height // 4
        
        draw.rectangle([x-200, y-50, x+200, y+50], fill=(255, 215, 0))
        
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()
        
        draw.text((x, y), reward_text, fill=(0, 0, 0), font=font, anchor="mm")
    
    def _render_mechanism(self, draw: ImageDraw.Draw,
                           node: Dict[str, Any],
                           constraints: Dict[str, Any],
                           variant: Optional[VariantConfig],
                           width: int, height: int):
        """渲染机制视觉"""
        mech_text = constraints.get("mechanism_text", "Spin to Win")
        
        x = width // 2
        y = height // 2
        
        draw.rectangle([x-150, y-30, x+150, y+30], fill=(100, 100, 200))
        
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        draw.text((x, y), mech_text, fill=(255, 255, 255), font=font, anchor="mm")
    
    def _render_identity(self, draw: ImageDraw.Draw,
                          node: Dict[str, Any],
                          constraints: Dict[str, Any],
                          variant: Optional[VariantConfig],
                          width: int, height: int):
        """渲染身份视觉"""
        identity_text = constraints.get("identity_text", "Hero")
        
        x = width // 2
        y = int(height * 0.7)
        
        draw.ellipse([x-60, y-60, x+60, y+60], fill=(50, 150, 50))
        
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        draw.text((x, y), identity_text, fill=(255, 255, 255), font=font, anchor="mm")
    
    def _render_hook_text(self, draw: ImageDraw.Draw,
                           constraints: Dict[str, Any],
                           variant: Optional[VariantConfig],
                           width: int, height: int):
        """渲染 Hook 文字"""
        hook = constraints.get("hook", "Limited Time!")
        
        if variant and "hook_text" in variant.modifications:
            hook = variant.modifications["hook_text"]
        
        x = width // 2
        y = 30
        
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except:
            font = ImageFont.load_default()
        
        draw.text((x, y), hook, fill=(255, 255, 255), font=font, anchor="mm")
    
    def _render_cta(self, draw: ImageDraw.Draw,
                    constraints: Dict[str, Any],
                    variant: Optional[VariantConfig],
                    width: int, height: int):
        """渲染 CTA 按钮"""
        cta = constraints.get("cta", "PLAY NOW")
        
        if variant and "cta_text" in variant.modifications:
            cta = variant.modifications["cta_text"]
        
        x = width // 2
        y = height - 80
        
        draw.rectangle([x-100, y-25, x+100, y+25], fill=(0, 200, 100))
        
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except:
            font = ImageFont.load_default()
        
        draw.text((x, y), cta, fill=(255, 255, 255), font=font, anchor="mm")
    
    def _compute_hash(self, file_path: Path) -> str:
        """计算 SHA256 哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _create_placeholder_asset(self, creative_id: str,
                                   variant: Optional[VariantConfig]) -> AssetMetadata:
        """创建占位资产（PIL 不可用时）"""
        asset_id = f"img_{uuid.uuid4().hex[:12]}"
        variant_type = variant.variant_type if variant else "original"
        
        return AssetMetadata(
            asset_id=asset_id,
            type="image",
            format="png",
            path="placeholder",
            creative_id=creative_id,
            variant_type=variant_type,
            created_at=int(time.time()),
        )


class VideoRenderer:
    """视频渲染器（可选）— 生成 MP4 视频素材
    
    5-15 sec ad clips
    预留实现
    """
    
    def __init__(self, output_dir: str = "memory/assets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def render(self,
               creative_id: str,
               layout_ast: Dict[str, Any],
               render_constraints: Dict[str, Any],
               duration_sec: float = 6.0,
               variant_config: Optional[VariantConfig] = None) -> AssetMetadata:
        """渲染视频资产（预留）"""
        asset_id = f"vid_{uuid.uuid4().hex[:12]}"
        variant_type = variant_config.variant_type if variant_config else "original"
        
        return AssetMetadata(
            asset_id=asset_id,
            type="video",
            format="mp4",
            path="video_placeholder.mp4",
            creative_id=creative_id,
            variant_type=variant_type,
            duration_sec=duration_sec,
            created_at=int(time.time()),
        )


class VariantGenerator:
    """变体生成器 — A/B 测试版本生成
    
    变体类型：
    - hook_a / hook_b：不同 Hook 文案
    - cta_variant：不同 CTA 按钮
    - color_variant：颜色变体
    """
    
    def __init__(self, image_renderer: ImageRenderer,
                 video_renderer: Optional[VideoRenderer] = None):
        self.image_renderer = image_renderer
        self.video_renderer = video_renderer
    
    def generate_variants(self,
                          creative_id: str,
                          layout_ast: Dict[str, Any],
                          render_constraints: Dict[str, Any],
                          variant_configs: List[VariantConfig]) -> List[AssetMetadata]:
        """生成多个变体资产
        
        Args:
            creative_id: 创意ID
            layout_ast: 布局AST
            render_constraints: 渲染约束
            variant_configs: 变体配置列表
        
        Returns:
            List[AssetMetadata]: 变体资产列表
        """
        assets = []
        
        for config in variant_configs:
            asset = self.image_renderer.render(
                creative_id=creative_id,
                layout_ast=layout_ast,
                render_constraints=render_constraints,
                variant_config=config,
            )
            assets.append(asset)
        
        return assets
    
    def generate_ab_test_set(self,
                              creative_id: str,
                              layout_ast: Dict[str, Any],
                              render_constraints: Dict[str, Any]) -> List[AssetMetadata]:
        """生成标准 A/B 测试集
        
        默认生成：
        - original：原始版本
        - hook_a：Hook 变体 A
        - hook_b：Hook 变体 B
        - cta_variant：CTA 变体
        """
        configs = [
            VariantConfig(variant_type="original"),
            VariantConfig(
                variant_type="hook_a",
                modifications={"hook_text": "NEW! Limited Offer"}
            ),
            VariantConfig(
                variant_type="hook_b",
                modifications={"hook_text": "Exclusive Reward!"}
            ),
            VariantConfig(
                variant_type="cta_variant",
                modifications={"cta_text": "CLAIM NOW"}
            ),
        ]
        
        return self.generate_variants(creative_id, layout_ast, render_constraints, configs)


class AssetProductionEngine:
    """资产生产引擎 — L1 层主入口
    
    统一管理：
    - ImageRenderer
    - VideoRenderer
    - VariantGenerator
    """
    
    def __init__(self, output_dir: str = "memory/assets",
                 enable_video: bool = False):
        self.output_dir = output_dir
        
        self.image_renderer = ImageRenderer(output_dir=output_dir)
        self.video_renderer = VideoRenderer(output_dir=output_dir) if enable_video else None
        self.variant_generator = VariantGenerator(
            image_renderer=self.image_renderer,
            video_renderer=self.video_renderer,
        )
        
        self._assets: Dict[str, AssetMetadata] = {}
    
    def produce_asset(self,
                      creative_id: str,
                      layout_ast: Dict[str, Any],
                      render_constraints: Dict[str, Any],
                      asset_type: str = "image",
                      generate_variants: bool = False) -> List[AssetMetadata]:
        """生产资产
        
        Args:
            creative_id: 创意ID
            layout_ast: 布局AST
            render_constraints: 渲染约束
            asset_type: image / video
            generate_variants: 是否生成变体
        
        Returns:
            List[AssetMetadata]: 资产列表（原始 + 变体）
        """
        assets = []
        
        if asset_type == "image":
            original = self.image_renderer.render(
                creative_id=creative_id,
                layout_ast=layout_ast,
                render_constraints=render_constraints,
            )
            assets.append(original)
            self._assets[original.asset_id] = original
            
            if generate_variants:
                variants = self.variant_generator.generate_ab_test_set(
                    creative_id=creative_id,
                    layout_ast=layout_ast,
                    render_constraints=render_constraints,
                )
                for v in variants:
                    if v.asset_id not in self._assets:
                        self._assets[v.asset_id] = v
                        assets.append(v)
        
        elif asset_type == "video" and self.video_renderer:
            video = self.video_renderer.render(
                creative_id=creative_id,
                layout_ast=layout_ast,
                render_constraints=render_constraints,
            )
            assets.append(video)
            self._assets[video.asset_id] = video
        
        return assets
    
    def get_asset(self, asset_id: str) -> Optional[AssetMetadata]:
        return self._assets.get(asset_id)
    
    def get_all_assets(self) -> Dict[str, AssetMetadata]:
        return self._assets