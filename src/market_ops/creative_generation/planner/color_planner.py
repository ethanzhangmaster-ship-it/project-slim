"""Phase 3.0: Color Planner — palette selection and color harmony.

Outputs color tokens: primary, secondary, accent, mood, saturation.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


COLOR_TOKENS: dict[str, dict[str, str]] = {
    "purple_gold": {
        "primary": "rich purple, magical violet",
        "secondary": "shimmering gold, warm yellow",
        "accent": "bright cyan sparkles",
        "mood": "luxurious magical fantasy",
        "saturation": "vibrant, saturated",
        "description": "Purple and Gold — royal magic",
    },
    "purple": {
        "primary": "deep purple, mystical violet",
        "secondary": "lavender, soft lilac",
        "accent": "silver or white sparkles",
        "mood": "mysterious magical",
        "saturation": "rich, saturated",
        "description": "Purple — magical mystery",
    },
    "purple_silver": {
        "primary": "royal purple",
        "secondary": "shimmering silver, moonlight",
        "accent": "white sparkles",
        "mood": "elegant magical",
        "saturation": "balanced",
        "description": "Purple and Silver — elegant magic",
    },
    "purple_blue": {
        "primary": "deep purple",
        "secondary": "cool cyan blue",
        "accent": "bright blue glow",
        "mood": "cool mystical",
        "saturation": "rich, cool-toned",
        "description": "Purple and Blue — cool mysticism",
    },
    "deep_purple": {
        "primary": "dark intense purple",
        "secondary": "black, dark violet",
        "accent": "neon violet glow",
        "mood": "dark magical, intense",
        "saturation": "deep, intense",
        "description": "Deep Purple — dark intensity",
    },
    "warm_golden": {
        "primary": "warm gold, amber",
        "secondary": "soft orange, peach",
        "accent": "bright yellow sparkles",
        "mood": "warm, inviting, rewarding",
        "saturation": "warm, rich",
        "description": "Warm Golden — reward and achievement",
    },
    "warm_orange": {
        "primary": "warm orange, tangerine",
        "secondary": "gold, amber",
        "accent": "yellow sparkles",
        "mood": "energetic, exciting",
        "saturation": "vibrant, warm",
        "description": "Warm Orange — energetic excitement",
    },
    "blue_cool": {
        "primary": "cool blue, sapphire",
        "secondary": "ice blue, cyan",
        "accent": "white sparkles",
        "mood": "cool, calm, mystical",
        "saturation": "cool, crisp",
        "description": "Cool Blue — mystical calm",
    },
    "green": {
        "primary": "emerald green, forest",
        "secondary": "mint, sage",
        "accent": "golden sparkles",
        "mood": "natural, enchanted",
        "saturation": "rich, natural",
        "description": "Green — enchanted nature",
    },
    "emerald": {
        "primary": "deep emerald green",
        "secondary": "jade, teal",
        "accent": "gold or white sparkles",
        "mood": "premium, natural magic",
        "saturation": "deep, rich",
        "description": "Emerald — premium nature",
    },
    "warm_red": {
        "primary": "intense fire red, crimson",
        "secondary": "orange, amber",
        "accent": "yellow sparks",
        "mood": "intense, powerful, dangerous",
        "saturation": "intense, fiery",
        "description": "Fire Red — intense power",
    },
    "rose_gold": {
        "primary": "soft rose gold, pink gold",
        "secondary": "cream, peach",
        "accent": "sparkling white",
        "mood": "elegant, feminine, premium",
        "saturation": "soft, elegant",
        "description": "Rose Gold — elegant premium",
    },
}


class ColorPlanner:
    """Plans color palette for a prompt based on palette type."""

    def plan(self, palette: str, strategy: str = "balanced") -> PromptComponent:
        tokens = COLOR_TOKENS.get(palette, COLOR_TOKENS["purple_gold"])
        return PromptComponent(
            dimension="palette",
            value=palette,
            label=tokens.get("description", palette),
            weight=0.8,
        )

    def get_tokens(self, palette: str) -> dict[str, str]:
        return COLOR_TOKENS.get(palette, COLOR_TOKENS["purple_gold"])