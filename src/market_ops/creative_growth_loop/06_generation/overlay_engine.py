"""Overlay Engine - V15素材增长闭环"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from PIL import Image, ImageDraw, ImageFont


@dataclass
class OverlayTemplate:
    overlay_type: str
    text: str
    position: tuple
    font_size: int
    color: tuple
    background_color: tuple = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overlay_type": self.overlay_type,
            "text": self.text,
            "position": self.position,
            "font_size": self.font_size,
            "color": self.color,
            "background_color": self.background_color,
        }


class OverlayEngine:
    OVERLAY_TEMPLATES = {
        "challenge": [
            OverlayTemplate("challenge", "Can You Reach Lv100?", (512, 100), 48, (255, 255, 255)),
            OverlayTemplate("challenge", "Only 1% Can Beat This", (512, 100), 48, (255, 255, 255)),
            OverlayTemplate("challenge", "Challenge Accepted?", (512, 100), 48, (255, 255, 255)),
        ],
        "secret": [
            OverlayTemplate("secret", "SECRET", (512, 100), 60, (255, 215, 0)),
            OverlayTemplate("secret", "Secret Dragon", (512, 100), 48, (255, 215, 0)),
            OverlayTemplate("secret", "Hidden Treasure", (512, 100), 48, (255, 215, 0)),
        ],
        "wrong_choice": [
            OverlayTemplate("wrong_choice", "Don't Merge Them!", (512, 100), 48, (255, 0, 0)),
            OverlayTemplate("wrong_choice", "Wrong Choice!", (512, 100), 48, (255, 0, 0)),
            OverlayTemplate("wrong_choice", "STOP!", (512, 100), 60, (255, 0, 0)),
        ],
        "before_after": [
            OverlayTemplate("before_after", "Before → After", (512, 100), 48, (255, 255, 255)),
            OverlayTemplate("before_after", "Lv1 → Lv100", (512, 100), 48, (255, 255, 255)),
        ],
        "reward": [
            OverlayTemplate("reward", "Golden Dragon", (512, 100), 48, (255, 215, 0)),
            OverlayTemplate("reward", "+999 REWARD", (512, 100), 48, (255, 215, 0)),
            OverlayTemplate("reward", "CLAIM NOW", (512, 100), 48, (255, 215, 0)),
        ],
        "level": [
            OverlayTemplate("level", "LEVEL 100", (512, 100), 60, (255, 255, 255)),
            OverlayTemplate("level", "MAX LEVEL", (512, 100), 60, (255, 255, 255)),
            OverlayTemplate("level", "ULTIMATE", (512, 100), 60, (255, 215, 0)),
        ],
    }
    
    ARROW_POSITIONS = [
        (200, 800),
        (800, 800),
        (512, 1200),
    ]
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/overlays"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def add_overlay(self, image_path: str, overlay_type: str, 
                    custom_text: str = None) -> Path:
        """添加Overlay"""
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        img = Image.open(image_path)
        
        templates = self.OVERLAY_TEMPLATES.get(overlay_type, [])
        if not templates:
            return image_path
        
        template = templates[0]
        if custom_text:
            template = OverlayTemplate(
                overlay_type=overlay_type,
                text=custom_text,
                position=template.position,
                font_size=template.font_size,
                color=template.color,
            )
        
        img = self._apply_overlay(img, template)
        
        output_path = self.output_dir / f"{image_path.stem}_overlay.png"
        img.save(output_path)
        
        return output_path
    
    def _apply_overlay(self, img: Image.Image, template: OverlayTemplate) -> Image.Image:
        """应用Overlay"""
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", template.font_size)
        except:
            font = ImageFont.load_default()
        
        if template.background_color:
            bbox = draw.textbbox(template.position, template.text, font=font)
            draw.rectangle(bbox, fill=template.background_color)
        
        draw.text(template.position, template.text, fill=template.color, font=font)
        
        return img
    
    def add_arrow(self, image_path: str, position: tuple = None) -> Path:
        """添加箭头"""
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        position = position or self.ARROW_POSITIONS[0]
        
        arrow_points = [
            (position[0] - 50, position[1]),
            (position[0], position[1] - 30),
            (position[0] + 50, position[1]),
        ]
        
        draw.polygon(arrow_points, fill=(255, 0, 0))
        
        output_path = self.output_dir / f"{image_path.stem}_arrow.png"
        img.save(output_path)
        
        return output_path
    
    def add_circle_highlight(self, image_path: str, center: tuple = None) -> Path:
        """添加圆形高亮"""
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        center = center or (512, 900)
        radius = 100
        
        draw.ellipse(
            [center[0] - radius, center[1] - radius, 
             center[0] + radius, center[1] + radius],
            outline=(255, 215, 0),
            width=5
        )
        
        output_path = self.output_dir / f"{image_path.stem}_circle.png"
        img.save(output_path)
        
        return output_path
    
    def generate_overlay_variants(self, image_path: str, count: int = 20) -> List[Path]:
        """生成Overlay变体"""
        variants = []
        
        for overlay_type, templates in self.OVERLAY_TEMPLATES.items():
            for template in templates[:3]:
                output = self.add_overlay(image_path, overlay_type, template.text)
                variants.append(output)
        
        if len(variants) < count:
            output = self.add_arrow(image_path)
            variants.append(output)
            
            output = self.add_circle_highlight(image_path)
            variants.append(output)
        
        return variants[:count]