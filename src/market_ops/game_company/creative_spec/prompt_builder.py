from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


PROMPT_PLATFORMS = {
    "openai": {"name": "OpenAI Sora", "supports_negative": False, "style_prefix": None},
    "runway": {"name": "Runway Gen-3", "supports_negative": True, "style_prefix": "Cinematic, high quality, "},
    "veo": {"name": "Google Veo", "supports_negative": False, "style_prefix": "Professional, "},
    "pika": {"name": "Pika 2.0", "supports_negative": True, "style_prefix": None},
    "hailuo": {"name": "Hailuo (Shengshu)", "supports_negative": True, "style_prefix": "Game trailer style, "},
    "kling": {"name": "Kling 1.6", "supports_negative": True, "style_prefix": "High quality mobile game ad, "},
    "pixverse": {"name": "PixVerse V4", "supports_negative": True, "style_prefix": None},
}


@dataclass
class VideoPrompt:
    platform: str
    system_prompt: str = ""
    user_prompt: str = ""
    negative_prompt: str = ""
    style_prompt: str = ""
    camera_prompt: str = ""
    duration: int = 25

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "negative_prompt": self.negative_prompt,
            "style_prompt": self.style_prompt,
            "camera_prompt": self.camera_prompt,
            "duration_seconds": self.duration,
        }


class PromptBuilder:
    def __init__(self):
        self._platforms = PROMPT_PLATFORMS

    def build(
        self, storyboard: Dict[str, Any], hook_type: str = "collection", platform: str = "runway"
    ) -> VideoPrompt:
        platform_info = self._platforms.get(platform, self._platforms["runway"])
        scenes = storyboard.get("scenes", [])
        scene_prompts = [s.get("prompt", "") for s in scenes]

        if hook_type == "collection":
            hook_desc = "Collection hook: Show cute witch character surrounded by many magical creatures. Warm colors, high saturation."
        elif hook_type == "reward":
            hook_desc = "Reward hook: Show dramatic evolution or level-up moment. Bright flash, particle effects."
        elif hook_type == "curiosity":
            hook_desc = "Curiosity hook: Start with mystery element (hidden object/question mark). Gradual reveal."
        elif hook_type == "comparison":
            hook_desc = "Comparison hook: Before/after split screen showing dramatic transformation."
        elif hook_type == "crisis":
            hook_desc = "Crisis hook: Urgent situation with countdown or danger. Quick pacing, dynamic camera."
        else:
            hook_desc = f"{hook_type} hook style for mobile game ad."

        system = (
            "You are a professional mobile game ad creative director specialized in Merge games. "
            "Generate a video that follows the P04 Witch production spec based on historically proven winning patterns. "
            "Use high saturation, warm palette, center-framed character. "
            "NO text overlay in first 3 seconds. "
            f"Total duration: {storyboard.get('total_duration_seconds', 25)} seconds."
        )

        user = f"""
Scene 1 (0-0.8s): {scene_prompts[0] if len(scene_prompts) > 0 else 'High contrast witch character appears in center frame. Warm lighting.'}
Scene 2 (0.8-3s): {scene_prompts[1] if len(scene_prompts) > 1 else 'Character interacts with magical creatures. Visual change occurs.'}
Scene 3 (3-6s): {scene_prompts[2] if len(scene_prompts) > 2 else 'Merge gameplay showcase with creatures collecting.'}
Scene 4 (6-9s): {scene_prompts[3] if len(scene_prompts) > 3 else 'Epic reward moment with bright visuals and particles.'}
Scene 5 (9s-end): {scene_prompts[4] if len(scene_prompts) > 4 else 'CTA button with social proof. App store badges visible.'}

{hook_desc}
Aspect ratio: 9:16 (vertical)
Style: Warm golden yellows, soft purples, pastel blues. 3D cartoon style. Cosy magical atmosphere."""

        negative = (
            "dark, cold/icy palette, hyper-realistic, text overlay in first 3 seconds, "
            "empty background, flat lighting, low contrast, washed out, hazy, "
            "horror elements, scary, menacing witch, abstract UI, "
            "camera movement only without visual change, minimal design"
        )

        style = platform_info.get("style_prefix", "") or ""
        style += (
            "High quality 3D cartoon mobile game ad. Warm golden amber palette with soft purple accents. "
            "Cute whimsical witch character. Bright magical particle effects. "
            "Satisfying merge progression visualization. Power fantasy payoff."
        )

        camera = (
            "Start with medium shot centered on character. Slow zoom in during hook. "
            "Dynamic but smooth camera movement. "
            "Dramatic zoom on reward moment. Steady for CTA."
        )

        return VideoPrompt(
            platform=platform,
            system_prompt=system,
            user_prompt=user,
            negative_prompt=negative,
            style_prompt=style,
            camera_prompt=camera,
            duration=storyboard.get("total_duration_seconds", 25),
        )

    def get_platforms(self) -> List[str]:
        return list(self._platforms.keys())

    def get_stats(self) -> Dict[str, Any]:
        return {"total_platforms": len(self._platforms)}
