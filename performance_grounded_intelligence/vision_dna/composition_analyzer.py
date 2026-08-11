"""Composition Analyzer — 构图区域分析

分析图片的 gameplay/reward/character/background 区域占比和位置。
可作为 DNAExtractor 的子模块独立使用，或被 dna_extractor.py 调用。
"""
import json
from pathlib import Path
from typing import Dict, Optional


DEFAULT_COMPOSITION = {
    "gameplay_area": {"ratio": 0.50, "position": "center"},
    "reward_area": {"ratio": 0.25, "position": "top_right"},
    "character_area": {"ratio": 0.15, "position": "bottom_left"},
    "background_area": {"ratio": 0.10},
}

COMPOSITION_PROMPT = """Analyze the spatial composition of this mobile game ad image.
Identify the following regions and their approximate area ratios (sum to 1.0):

1. gameplay_area: The main game board/puzzle area
2. reward_area: Reward/treasure/loot display area
3. character_area: Character/dragon/creature area
4. background_area: Background/decorative area

Return JSON:
{
  "gameplay_area": {"ratio": 0.0-1.0, "position": "center|top|bottom|left|right|top_left|top_right|bottom_left|bottom_right"},
  "reward_area": {"ratio": 0.0-1.0, "position": "..."},
  "character_area": {"ratio": 0.0-1.0, "position": "..."},
  "background_area": {"ratio": 0.0-1.0}
}
Only return JSON."""


class CompositionAnalyzer:
    """构图分析器"""

    def __init__(self, client=None):
        """
        Args:
            client: OpenAI client (可选, 无则使用规则模式)
        """
        self.client = client

    def analyze(self, image_path: Optional[Path] = None,
                ad_name: str = "") -> Dict:
        """分析单张图片的构图

        Args:
            image_path: 图片路径 (有则使用 Vision API)
            ad_name: 广告名 (用于规则推断)

        Returns:
            composition dict
        """
        if image_path and self.client:
            return self._analyze_with_vision(image_path)
        return self._analyze_rule_based(ad_name)

    def _analyze_with_vision(self, image_path: Path) -> Dict:
        """使用 Vision API 分析构图"""
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
                        {"type": "text", "text": COMPOSITION_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }}
                    ]
                }],
                max_tokens=500,
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content)
        except Exception as e:
            print(f"    [CompositionAnalyzer] Vision 失败: {e}")
            return DEFAULT_COMPOSITION.copy()

    def _analyze_rule_based(self, ad_name: str = "") -> Dict:
        """规则模式: 基于广告名关键词推断构图"""
        name_lower = ad_name.lower()
        comp = DEFAULT_COMPOSITION.copy()

        # 对比类广告: gameplay 区域更大
        if "对比" in ad_name or "before" in name_lower or "vs" in name_lower:
            comp = {
                "gameplay_area": {"ratio": 0.65, "position": "center"},
                "reward_area": {"ratio": 0.15, "position": "top"},
                "character_area": {"ratio": 0.10, "position": "bottom"},
                "background_area": {"ratio": 0.10},
            }
        # 奖励重点: reward 区域更大
        elif "奖励" in ad_name or "reward" in name_lower or "宝箱" in ad_name:
            comp = {
                "gameplay_area": {"ratio": 0.30, "position": "bottom"},
                "reward_area": {"ratio": 0.45, "position": "center"},
                "character_area": {"ratio": 0.15, "position": "left"},
                "background_area": {"ratio": 0.10},
            }

        return comp

    def validate(self, composition: Dict) -> bool:
        """验证构图数据合法性"""
        required = ["gameplay_area", "reward_area", "character_area", "background_area"]
        if not all(k in composition for k in required):
            return False
        total = sum(
            composition[k].get("ratio", 0) if isinstance(composition[k], dict)
            else composition[k]
            for k in required
        )
        return 0.9 <= total <= 1.1  # 允许 ±10% 误差
