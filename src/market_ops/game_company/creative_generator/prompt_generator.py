from typing import Dict, List, Any, Optional

from .variant_engine import CreativeAsset


class PromptGenerator:
    def __init__(self):
        self._platforms = ["openai", "veo", "runway", "kling", "pixverse", "pika", "hailuo", "luma"]

    def generate_all(self, asset: CreativeAsset) -> Dict[str, Dict[str, str]]:
        return {p: self.generate(asset, p) for p in self._platforms}

    def generate(self, asset: CreativeAsset, platform: str) -> Dict[str, str]:
        base = self._build_base_prompts(asset)
        platform_specific = self._apply_platform_rules(platform, base)
        return platform_specific

    def _build_base_prompts(self, asset: CreativeAsset) -> Dict[str, str]:
        hero = asset.hero
        env = asset.environment
        obj = asset.merge_object
        reward = asset.reward
        camera = asset.camera

        system = f"""You are generating a {asset.hook_type}-hook mobile game ad for {asset.creative_id}.
Project: {asset.project}
Style: 3D cartoon, warm palette, high saturation
Rules:
- Subject in center 40% of frame within 0.8s
- First frame contrast >= 0.15
- No text overlay in first 3 seconds
- Visual structure change between 0.8-3.0s
- Visual reward event after 6s
- Warm palette preferred (warm:cool = 1039:790 in historical data)"""

        user = f"""Create a {asset.hook_type}-hook mobile game ad video.

Hero: {hero.get('name')} ({hero.get('style')}) with {hero.get('pet')}
Environment: {env.get('name')} with {env.get('lighting')} lighting ({env.get('mood')})
Merge Object: {obj.get('name')} (evolution chain: {obj.get('chain')})
Reward: {reward.get('name')} - {reward.get('effect')}
Camera: {camera.get('name')} - {camera.get('angle')}, {camera.get('movement')}
Palette: {hero.get('palette')}

Scene 1 (0-0.8s): {hero.get('name')} appears center frame with {hero.get('pet')}. {env.get('lighting')}. High contrast, high saturation.
Scene 2 (0.8-3s): {hero.get('pet')} interacts with {hero.get('name')}. First {obj.get('name')} appears. Visual change.
Scene 3 (3-6s): Merge gameplay: {obj.get('chain')}. Progress indicators. Collection counter.
Scene 4 (6-9s): REWARD: {reward.get('name')}! {reward.get('effect')}. Screen brightens, saturation spikes.
Scene 5 (9s-end): CTA: '{asset.cta.get('text')}'. Social proof. App store badges.

Aspect ratio: 9:16 vertical
Style: Warm {hero.get('palette')} palette. 3D cartoon. Magical atmosphere. High saturation."""

        negative = ("dark, cold/icy palette, hyper-realistic, text overlay in first 3 seconds, "
                    "empty background, flat lighting, low contrast, washed out, hazy, "
                    "horror elements, scary witch, abstract UI, camera movement only without visual change")

        style = (f"High quality 3D cartoon mobile game ad. {hero.get('style')} witch character. "
                 f"Warm {hero.get('palette')} palette. {env.get('mood')} atmosphere. "
                 f"Magical particle effects. High saturation, high contrast. Bright, inviting.")

        camera_prompt = (f"{camera.get('name')}: {camera.get('angle')}, {camera.get('movement')}. "
                         f"Dynamic but smooth. Dramatic zoom on reward moment. Steady for CTA.")

        return {
            "system_prompt": system,
            "user_prompt": user,
            "negative_prompt": negative,
            "style_prompt": style,
            "camera_prompt": camera_prompt,
            "duration": "20 seconds",
            "aspect_ratio": "9:16",
        }

    def _apply_platform_rules(self, platform: str, base: Dict) -> Dict[str, str]:
        prompts = dict(base)
        platform_formats = {
            "openai": {"prefix": "Sora video generation:\n", "negative": False, "max_length": 1000},
            "veo": {"prefix": "Veo video:\n", "negative": False, "max_length": 500},
            "runway": {"prefix": "Runway Gen-3:\n", "negative": True, "style_prefix": "Cinematic, high quality, "},
            "kling": {"prefix": "Kling 1.6:\n", "negative": True, "style_prefix": "High quality mobile game ad, "},
            "pixverse": {"prefix": "PixVerse V4:\n", "negative": True, "style_prefix": None},
            "pika": {"prefix": "Pika 2.0:\n", "negative": True, "style_prefix": None},
            "hailuo": {"prefix": "Hailuo (Shengshu):\n", "negative": True, "style_prefix": "Game trailer style, "},
            "luma": {"prefix": "Luma Dream Machine:\n", "negative": True, "style_prefix": "Cinematic game ad, "},
        }
        fmt = platform_formats.get(platform, platform_formats["runway"])
        prompts["platform"] = platform
        prompts["user_prompt"] = fmt["prefix"] + prompts["user_prompt"]
        if fmt.get("style_prefix"):
            prompts["style_prompt"] = fmt["style_prefix"] + prompts["style_prompt"]
        if not fmt.get("negative", False):
            prompts["negative_prompt"] = ""
        return prompts

    def get_platforms(self) -> List[str]:
        return list(self._platforms)

    def get_stats(self) -> Dict[str, Any]:
        return {"total_platforms": len(self._platforms)}
