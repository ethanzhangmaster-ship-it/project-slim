"""Style Analyzer — 视觉风格分析

检测: color_palette / lighting / camera_angle / render_style
"""
import json
from pathlib import Path
from typing import Dict, Optional


COLOR_PALETTES = [
    "purple_gold",    # 紫金 (奢华/魔法)
    "green_nature",   # 绿色自然
    "blue_magic",     # 蓝色魔法
    "warm_sunset",    # 暖色夕阳
    "dark_fantasy",   # 暗黑奇幻
    "bright_colorful",# 明亮多彩
]

LIGHTING_TYPES = ["magic_glow", "natural", "dramatic", "flat"]
CAMERA_ANGLES = ["top_down", "isometric", "front", "close_up"]
RENDER_STYLES = ["3d_cartoon", "2d_flat", "semi_realistic", "painted"]

STYLE_PROMPT = """Analyze the visual style of this mobile game ad image.

Identify:
1. color_palette: Overall color scheme
   - purple_gold: purple/gold luxury/magic tones
   - green_nature: green/nature tones
   - blue_magic: blue/cyan magic tones
   - warm_sunset: warm orange/red sunset tones
   - dark_fantasy: dark moody fantasy tones
   - bright_colorful: bright saturated multiple colors

2. lighting: Lighting style
   - magic_glow: glowing/sparkle magical lighting
   - natural: natural/daylight
   - dramatic: high contrast dramatic
   - flat: even/flat lighting

3. camera: Camera angle
   - top_down: looking directly down
   - isometric: 3/4 view angled
   - front: straight-on front view
   - close_up: zoomed in close up

4. render_style: Art/render style
   - 3d_cartoon: 3D cartoon render
   - 2d_flat: flat 2D illustration
   - semi_realistic: semi-realistic 3D
   - painted: hand-painted style

Return JSON:
{
  "color_palette": "purple_gold|green_nature|blue_magic|warm_sunset|dark_fantasy|bright_colorful",
  "lighting": "magic_glow|natural|dramatic|flat",
  "camera": "top_down|isometric|front|close_up",
  "render_style": "3d_cartoon|2d_flat|semi_realistic|painted"
}
Only return JSON."""


class StyleAnalyzer:
    """视觉风格分析器"""

    def __init__(self, client=None):
        self.client = client

    def analyze(self, image_path: Optional[Path] = None,
                ad_name: str = "") -> Dict:
        """分析图片的视觉风格

        Args:
            image_path: 图片路径
            ad_name: 广告名

        Returns:
            {"color_palette": str, "lighting": str, "camera": str, "render_style": str}
        """
        if image_path and self.client:
            return self._analyze_with_vision(image_path)
        return self._analyze_rule_based(ad_name)

    def _analyze_with_vision(self, image_path: Path) -> Dict:
        """使用 Vision API 分析"""
        import base64
        from ..config import VISION_MODEL

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": STYLE_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }}
                    ]
                }],
                max_tokens=300,
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content)
        except Exception as e:
            print(f"    [StyleAnalyzer] Vision 失败: {e}")
            return self._analyze_rule_based("")

    def _analyze_rule_based(self, ad_name: str = "") -> Dict:
        """规则模式: 默认游戏风格"""
        name_lower = ad_name.lower()

        # 大部分 Merge Dragon 类广告都是 purple_gold + 3d_cartoon
        color = "purple_gold"
        if "自然" in ad_name or "nature" in name_lower or "绿" in ad_name:
            color = "green_nature"
        elif "暗" in ad_name or "dark" in name_lower:
            color = "dark_fantasy"
        elif "蓝" in ad_name or "blue" in name_lower or "magic" in name_lower:
            color = "blue_magic"

        return {
            "color_palette": color,
            "lighting": "magic_glow",
            "camera": "isometric",
            "render_style": "3d_cartoon",
            "_source": "rule_based",
        }
