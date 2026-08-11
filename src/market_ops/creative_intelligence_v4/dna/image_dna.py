"""V4.0: Image DNA — structured creative DNA for image ads.

Extracted from Facebook ad images. 18 dimensions.
Compatible with Phase 3.0 Prompt Planner input format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageDNA:
    """Complete Image Creative DNA from Facebook ad analysis.

    Compatible with Phase 3.0 Prompt Planner (character, reward, camera, etc.).
    """
    dna_type: str = "image"

    # Core creative elements
    character: str = ""          # "witch", "dragon", "fairy"
    reward: str = ""             # "baby_dragon", "treasure", "castle"
    gameplay: str = ""           # "merge", "evolution", "collection"
    composition: str = ""        # "center", "triangle", "diagonal"
    camera: str = ""             # "45_degree", "close_up", "top_down"
    lighting: str = ""           # "warm", "dramatic", "magical_glow"
    palette: str = ""            # "purple_gold", "warm_golden", "blue_cool"
    emotion: str = ""            # "surprise", "excitement", "determination"
    hook: str = ""               # "collection", "merge", "evolution", "fail"
    typography: str = ""         # "Merge Now!", "Collect Them All!"
    background: str = ""         # "magical_garden", "castle", "dark_forest"
    style: str = ""              # "cartoon", "pixar", "anime", "semi_realistic"
    ui_elements: str = ""        # "merge_board", "progress_bar", "coin_counter"
    icon: str = ""               # "app_icon", "game_logo", "character_icon"
    cta: str = ""                # "Play Now", "Install", "Download"
    brand: str = ""              # "Merge Witches", "Merge Dragons"

    # Source
    source_creative_id: str = ""
    facebook_ad_id: str = ""
    confidence: float = 0.0

    # Metadata
    notes: str = ""

    def to_planner_input(self) -> dict[str, str]:
        """Convert to Phase 3.0 Prompt Planner input format."""
        result = {}
        if self.character:
            result["character"] = self.character
        if self.reward:
            result["reward"] = self.reward
        if self.gameplay:
            result["gameplay"] = self.gameplay
        if self.composition:
            result["composition"] = self.composition
        if self.camera:
            result["camera"] = self.camera
        if self.lighting:
            result["lighting"] = self.lighting
        if self.palette:
            result["palette"] = self.palette
        if self.emotion:
            result["emotion"] = self.emotion
        if self.hook:
            result["hook"] = self.hook
        if self.style:
            result["style"] = self.style
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_type": self.dna_type,
            "character": self.character,
            "reward": self.reward,
            "gameplay": self.gameplay,
            "composition": self.composition,
            "camera": self.camera,
            "lighting": self.lighting,
            "palette": self.palette,
            "emotion": self.emotion,
            "hook": self.hook,
            "typography": self.typography,
            "background": self.background,
            "style": self.style,
            "ui_elements": self.ui_elements,
            "icon": self.icon,
            "cta": self.cta,
            "brand": self.brand,
            "source_creative_id": self.source_creative_id,
            "facebook_ad_id": self.facebook_ad_id,
            "confidence": self.confidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageDNA:
        return cls(
            dna_type=data.get("dna_type", "image"),
            character=data.get("character", ""),
            reward=data.get("reward", ""),
            gameplay=data.get("gameplay", ""),
            composition=data.get("composition", ""),
            camera=data.get("camera", ""),
            lighting=data.get("lighting", ""),
            palette=data.get("palette", ""),
            emotion=data.get("emotion", ""),
            hook=data.get("hook", ""),
            typography=data.get("typography", ""),
            background=data.get("background", ""),
            style=data.get("style", ""),
            ui_elements=data.get("ui_elements", ""),
            icon=data.get("icon", ""),
            cta=data.get("cta", ""),
            brand=data.get("brand", ""),
            source_creative_id=data.get("source_creative_id", ""),
            facebook_ad_id=data.get("facebook_ad_id", ""),
            confidence=data.get("confidence", 0),
            notes=data.get("notes", ""),
        )