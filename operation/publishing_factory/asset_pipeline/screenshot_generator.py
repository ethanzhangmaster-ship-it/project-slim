"""
E15.1.1 — Screenshot Factory
==============================

Deterministic store-screenshot spec generator.

Input:  GameProduct (genre + selling_points)
Output: ScreenshotSet — a list of ScreenshotSpec, each a structured
        creative brief (headline, subheadline, layout, palette, cta).
        No pixel bytes: the factory emits the *plan*; humans/design
        tools render it. This keeps the system Lean + testable and
        respects the "system proposes, human executes" boundary.

Store-page CVR is driven heavily by screenshots, so the generator
emits a conversion-oriented sequence: hook -> proof -> fantasy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from operation.publishing_factory.catalog.product_profile import GameProduct

# Palette per genre (deterministic brand colors, hex).
_GENRE_PALETTE: Dict[str, Dict[str, str]] = {
    "merge":   {"bg": "#2D1B69", "accent": "#FFC93C", "text": "#FFFFFF"},
    "puzzle":  {"bg": "#0B6E4F", "accent": "#F4D35E", "text": "#FFFFFF"},
    "idle":    {"bg": "#1B3B6F", "accent": "#FF9F1C", "text": "#FFFFFF"},
    "word":    {"bg": "#6F1B6F", "accent": "#4CC9F0", "text": "#FFFFFF"},
    "casual":  {"bg": "#118AB2", "accent": "#FFD166", "text": "#FFFFFF"},
    "simulation": {"bg": "#3A0CA3", "accent": "#F72585", "text": "#FFFFFF"},
    "action":  {"bg": "#5C0000", "accent": "#FFBA08", "text": "#FFFFFF"},
}


@dataclass
class ScreenshotSpec:
    index: int
    headline: str
    subheadline: str
    layout: str               # "hook" | "proof" | "fantasy" | "feature"
    palette: Dict[str, str]
    cta: str = ""
    selling_point: str = ""

    def to_dict(self) -> dict:
        return {
            "index": self.index, "headline": self.headline,
            "subheadline": self.subheadline, "layout": self.layout,
            "palette": self.palette, "cta": self.cta,
            "selling_point": self.selling_point,
        }


@dataclass
class ScreenshotSet:
    game_id: str
    genre: str
    screenshots: List[ScreenshotSpec] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "genre": self.genre,
            "count": len(self.screenshots),
            "screenshots": [s.to_dict() for s in self.screenshots],
        }


class ScreenshotGenerator:
    """Emits a conversion-oriented screenshot sequence for a game."""

    def __init__(self, count: int = 5):
        self.count = count

    def generate(self, product: GameProduct) -> ScreenshotSet:
        points = product.default_selling_points()
        palette = _GENRE_PALETTE.get(product.genre,
                                     _GENRE_PALETTE["casual"])
        name = product.display_name or product.game_id
        specs: List[ScreenshotSpec] = []

        # 1) Hook: brand + core fantasy
        specs.append(ScreenshotSpec(
            index=0, headline=f"YOUR {name.upper()} WORLD",
            subheadline=" ".join(points[:3]),
            layout="hook", palette=palette,
            cta="Play Free", selling_point=points[0] if points else ""))

        # 2..n-1) Feature proof, one selling point each
        layouts = ["proof", "feature", "fantasy"]
        for i in range(1, self.count - 1):
            sp = points[i % len(points)] if points else f"Feature {i}"
            specs.append(ScreenshotSpec(
                index=i,
                headline=f"{sp.upper()} NOW",
                subheadline=_proof_line(sp, product.genre),
                layout=layouts[(i - 1) % len(layouts)],
                palette=palette, selling_point=sp))

        # last) Fantasy / collection hook
        last_sp = points[-1] if points else "Win"
        specs.append(ScreenshotSpec(
            index=self.count - 1,
            headline=f"1000+ ITEMS TO COLLECT",
            subheadline=f"Restore your lost {_fantasy_noun(product.genre)}",
            layout="fantasy", palette=palette,
            cta="Download", selling_point=last_sp))

        return ScreenshotSet(game_id=product.game_id,
                             genre=product.genre, screenshots=specs)


def _proof_line(sp: str, genre: str) -> str:
    return f"Tap to {sp.lower()} — easy & satisfying"


def _fantasy_noun(genre: str) -> str:
    return {
        "merge": "kingdom", "puzzle": "realm", "idle": "empire",
        "word": "library", "casual": "world", "simulation": "city",
        "action": "battlefield",
    }.get(genre, "world")


__all__ = ["ScreenshotGenerator", "ScreenshotSpec", "ScreenshotSet"]
