"""Pattern Engine - 从赢家素材提取ImagePattern (DEPRECATED)
Use market_ops.creative_growth_loop.03_gene.gene_extractor instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.03_gene.gene_extractor")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from market_ops.clients.lovart import LovartClient


@dataclass
class ImagePattern:
    subject: str
    style: str
    emotion: str
    background: str
    hook: str
    palette: str = ""
    composition: str = ""
    lighting: str = ""
    character_pose: str = ""
    ui_elements: list = None
    overlay_text: str = ""
    standout_features: list = None
    
    def __post_init__(self):
        if self.ui_elements is None:
            self.ui_elements = []
        if self.standout_features is None:
            self.standout_features = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "style": self.style,
            "emotion": self.emotion,
            "background": self.background,
            "hook": self.hook,
            "palette": self.palette,
            "composition": self.composition,
            "lighting": self.lighting,
            "character_pose": self.character_pose,
            "ui_elements": self.ui_elements,
            "overlay_text": self.overlay_text,
            "standout_features": self.standout_features,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImagePattern":
        return cls(
            subject=data.get("subject", ""),
            style=data.get("style", ""),
            emotion=data.get("emotion", ""),
            background=data.get("background", ""),
            hook=data.get("hook", ""),
            palette=data.get("palette", ""),
            composition=data.get("composition", ""),
            lighting=data.get("lighting", ""),
            character_pose=data.get("character_pose", ""),
            ui_elements=data.get("ui_elements", []),
            overlay_text=data.get("overlay_text", ""),
            standout_features=data.get("standout_features", []),
        )


class PatternEngine:
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path("output/creative_loop_v2/patterns")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()

    def extract_pattern(self, image_path: str | Path, image_name: str = "winner") -> ImagePattern:
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        visual_dna = self._describe_image(image_path)
        pattern = self._dna_to_pattern(visual_dna)
        
        self._save_pattern(pattern, image_name)
        return pattern

    def _describe_image(self, image_path: Path) -> Dict[str, Any]:
        try:
            result = self.lovart_client.describe_image(str(image_path))
            return result.get("visual_dna", result)
        except Exception as e:
            return self._fallback_describe(image_path.name)

    def _fallback_describe(self, image_name: str) -> Dict[str, Any]:
        return {
            "subject": "fantasy character",
            "style": "3D cartoon",
            "emotion": "neutral",
            "background": "magical forest",
            "hook": "mysterious",
            "palette": "purple, blue, gold",
            "composition": "centered hero shot",
            "lighting": "magical glow",
            "character_pose": "standing",
            "standout_features": ["fantasy elements"],
        }

    def _dna_to_pattern(self, dna: Dict[str, Any]) -> ImagePattern:
        return ImagePattern(
            subject=dna.get("subject", "unknown"),
            style=dna.get("style", "3D cartoon") or self._infer_style(dna),
            emotion=dna.get("emotion", dna.get("mood", "neutral")),
            background=dna.get("background", "unknown"),
            hook=dna.get("hook", dna.get("hook_type", "unknown")),
            palette=dna.get("palette", ""),
            composition=dna.get("composition", ""),
            lighting=dna.get("lighting", ""),
            character_pose=dna.get("character_pose", ""),
            ui_elements=dna.get("ui_elements", []),
            overlay_text=dna.get("overlay_text", ""),
            standout_features=dna.get("standout_features", []),
        )

    def _infer_style(self, dna: Dict[str, Any]) -> str:
        mood = dna.get("mood", "").lower()
        if "whimsical" in mood or "cute" in mood:
            return "3D cartoon"
        elif "dark" in mood or "mysterious" in mood:
            return "dark fantasy"
        elif "epic" in mood or "cinematic" in mood:
            return "cinematic"
        return "3D cartoon"

    def _save_pattern(self, pattern: ImagePattern, name: str) -> Path:
        filename = f"{name}_pattern.json"
        output_path = self.output_dir / filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(pattern.to_dict(), f, indent=2, ensure_ascii=False)
        
        return output_path

    def load_pattern(self, name: str) -> Optional[ImagePattern]:
        pattern_path = self.output_dir / f"{name}_pattern.json"
        if pattern_path.exists():
            with open(pattern_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ImagePattern.from_dict(data)
        return None