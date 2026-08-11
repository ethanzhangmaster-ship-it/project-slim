"""Phase 3.0: Lighting Planner — key light, fill light, back light, shadow, bloom.

Outputs lighting tokens for each lighting type.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


LIGHTING_TOKENS: dict[str, dict[str, str]] = {
    "warm": {
        "key_light": "warm golden key light from upper right",
        "fill_light": "soft warm fill light from left",
        "back_light": "gentle warm rim light on subject edges",
        "shadow": "soft warm shadows, no harsh contrast",
        "bloom": "subtle warm glow bloom effect",
        "description": "Warm, inviting golden lighting",
    },
    "golden_hour": {
        "key_light": "golden hour sunlight, warm and directional",
        "fill_light": "warm ambient bounce light",
        "back_light": "strong golden rim light, hair light",
        "shadow": "long soft shadows, golden tone",
        "bloom": "natural lens flare, golden bloom",
        "description": "Golden hour cinematic lighting",
    },
    "soft_diffuse": {
        "key_light": "large soft diffused light source",
        "fill_light": "even ambient fill, no strong shadows",
        "back_light": "subtle hair light for separation",
        "shadow": "barely visible shadows, flat lighting",
        "bloom": "no bloom, clean and crisp",
        "description": "Soft diffused studio lighting",
    },
    "sunset": {
        "key_light": "warm sunset light, orange and pink tones",
        "fill_light": "purple ambient twilight fill",
        "back_light": "dramatic sunset backlight, silhouette rim",
        "shadow": "long dramatic shadows",
        "bloom": "warm sunset bloom, atmospheric haze",
        "description": "Dramatic sunset lighting",
    },
    "fantasy_glow": {
        "key_light": "magical glow from subject or object",
        "fill_light": "soft ethereal ambient fill",
        "back_light": "mystical backlight, particle illumination",
        "shadow": "minimal shadows, glowing atmosphere",
        "bloom": "strong magical bloom, floating light particles",
        "description": "Fantasy magical glow lighting",
    },
    "cinematic": {
        "key_light": "dramatic cinematic key light",
        "fill_light": "controlled fill for contrast",
        "back_light": "strong rim light, cinematic separation",
        "shadow": "deep cinematic shadows, high contrast",
        "bloom": "subtle cinematic bloom, anamorphic feel",
        "description": "Cinematic Hollywood lighting",
    },
    "dramatic": {
        "key_light": "intense dramatic spotlight",
        "fill_light": "minimal fill, high contrast ratio",
        "back_light": "powerful backlight, dramatic separation",
        "shadow": "deep dark shadows, chiaroscuro",
        "bloom": "controlled bloom on highlights",
        "description": "Dramatic high-contrast lighting",
    },
    "volumetric": {
        "key_light": "visible light rays through atmosphere",
        "fill_light": "scattered volumetric fill",
        "back_light": "god rays through environment",
        "shadow": "soft volumetric shadows",
        "bloom": "strong volumetric bloom, fog glow",
        "description": "Volumetric atmospheric lighting",
    },
    "cool": {
        "key_light": "cool blue moonlight from above",
        "fill_light": "soft cool ambient fill",
        "back_light": "silver cool rim light",
        "shadow": "cool blue shadows",
        "bloom": "subtle cool glow",
        "description": "Cool moonlight lighting",
    },
    "moonlight": {
        "key_light": "silver moonlight from above",
        "fill_light": "dark blue ambient fill",
        "back_light": "moonlit rim light, ethereal",
        "shadow": "deep blue shadows",
        "bloom": "moon glow, star-like particles",
        "description": "Mystical moonlight",
    },
    "magical_glow": {
        "key_light": "magical rune or crystal glow",
        "fill_light": "multi-colored magical ambient",
        "back_light": "magical particle backlight",
        "shadow": "colored magical shadows",
        "bloom": "strong magical bloom, particle effects",
        "description": "Magical glow from artifacts",
    },
    "neon": {
        "key_light": "vibrant neon pink/cyan key light",
        "fill_light": "neon ambient bounce",
        "back_light": "neon rim light, cyberpunk",
        "shadow": "colored neon shadows",
        "bloom": "strong neon bloom, light leak",
        "description": "Vibrant neon lighting",
    },
}


class LightingPlanner:
    """Plans lighting setup for a prompt based on lighting type."""

    def plan(self, lighting: str, strategy: str = "balanced") -> PromptComponent:
        tokens = LIGHTING_TOKENS.get(lighting, LIGHTING_TOKENS["warm"])
        return PromptComponent(
            dimension="lighting",
            value=lighting,
            label=tokens.get("description", lighting),
            weight=1.0,
        )

    def get_tokens(self, lighting: str) -> dict[str, str]:
        return LIGHTING_TOKENS.get(lighting, LIGHTING_TOKENS["warm"])