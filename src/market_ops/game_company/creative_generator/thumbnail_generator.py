from typing import Dict, List, Any, Optional
from .variant_engine import CreativeAsset


class ThumbnailGenerator:
    def generate(self, asset: CreativeAsset) -> Dict[str, Any]:
        hero = asset.hero
        env = asset.environment
        obj = asset.merge_object
        reward = asset.reward

        return {
            "creative_id": asset.creative_id,
            "title": asset.title,
            "design": self._design_spec(asset),
            "flux_prompt": self._flux_prompt(hero, env, obj, reward),
            "midjourney_prompt": self._midjourney_prompt(hero, env),
            "ideogram_prompt": self._ideogram_prompt(hero, env, asset),
        }

    def _design_spec(self, asset: CreativeAsset) -> Dict[str, str]:
        return {
            "subject": f"{asset.hero.get('name')} with {asset.hero.get('pet')}",
            "background": asset.environment.get("name", "Magic Forest"),
            "color_palette": asset.hero.get("palette", "warm golden"),
            "title_text": asset.title[:30] if asset.title else "Merge Magic!",
            "cta_text": asset.cta.get("text", "Download Free!")[:20],
            "composition": "Center hero with pet, background environment, title at top, CTA at bottom",
            "style": "3D cartoon, high saturation, warm lighting",
        }

    def _flux_prompt(self, hero: Dict, env: Dict, obj: Dict, reward: Dict) -> str:
        return (f"A cute {hero.get('style')} witch character holding a {hero.get('pet')} in {env.get('name')} with {env.get('lighting')}. "
                f"Object: {obj.get('name')} floating nearby. Magical sparkles everywhere. "
                f"Reward energy: {reward.get('effect')}. "
                f"3D cartoon style, warm {hero.get('palette')} palette, high saturation, golden hour lighting. "
                f"9:16 vertical. Text space at top and bottom. Game ad style. High quality, professional lighting.")

    def _midjourney_prompt(self, hero: Dict, env: Dict) -> str:
        return (f"3D render of a cute {hero.get('style')} witch with {hero.get('pet')} in {env.get('name')} -- "
                f"warm palette {hero.get('palette')} -- magical atmosphere -- golden hour lighting -- "
                f"high detail character design -- soft glowing particles -- "
                f"mobile game advertisement style -- 9:16 -- --ar 9:16 --v 6")

    def _ideogram_prompt(self, hero: Dict, env: Dict, asset: CreativeAsset) -> str:
        return (f"A cute 3D cartoon {hero.get('style')} witch with magical {hero.get('pet')} in {env.get('name')}. "
                f"Warm golden and purple color scheme. High saturation, bright magical glow. "
                f"Mobile game ad art. 9:16 vertical. Professional lighting, "
                f"text 'Merge Magic!' at top, 'Download Free' button at bottom. Realistic 3D render style.")

    def get_stats(self) -> Dict[str, Any]:
        return {"supported_platforms": 3}
