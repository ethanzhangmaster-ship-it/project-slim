"""
E15.1.1 — Icon Generator
=========================

Deterministic app-icon spec from genre. Emits an IconSpec (style,
base color, glyph, text) — the creative brief, not pixels.

Icon *similarity* across the fleet is the #1 Apple 4.3 spam trigger,
so the generator biases toward genre-distinct glyphs and the
compliance scanner later checks pairwise similarity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from operation.publishing_factory.catalog.product_profile import GameProduct

_GLYPH: Dict[str, str] = {
    "merge": "spark", "puzzle": "piece", "idle": "coin",
    "word": "letter", "casual": "star", "simulation": "city",
    "action": "sword",
}
_STYLE: Dict[str, str] = {
    "merge": "neon_glass", "puzzle": "flat_minimal", "idle": "gold_3d",
    "word": "typo_bold", "casual": "rounded_flat", "simulation": "isometric",
    "action": "ember_metal",
}


@dataclass
class IconSpec:
    game_id: str
    genre: str
    style: str
    base_color: str
    glyph: str
    text: str = ""

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "genre": self.genre,
                "style": self.style, "base_color": self.base_color,
                "glyph": self.glyph, "text": self.text}


class IconGenerator:
    """Produces a genre-distinct icon brief."""

    def generate(self, product: GameProduct) -> IconSpec:
        palette = {
            "merge": "#2D1B69", "puzzle": "#0B6E4F", "idle": "#1B3B6F",
            "word": "#6F1B6F", "casual": "#118AB2", "simulation": "#3A0CA3",
            "action": "#5C0000",
        }.get(product.genre, "#118AB2")
        return IconSpec(
            game_id=product.game_id,
            genre=product.genre,
            style=_STYLE.get(product.genre, "rounded_flat"),
            base_color=palette,
            glyph=_GLYPH.get(product.genre, "star"),
            text=(product.display_name or product.game_id)[:1].upper(),
        )


__all__ = ["IconGenerator", "IconSpec"]
