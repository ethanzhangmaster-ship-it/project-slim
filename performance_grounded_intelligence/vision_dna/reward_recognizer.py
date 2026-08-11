"""Reward Recognizer — 奖励元素识别

检测: dragon / castle / magic_item / rare_reward / character
"""
import json
from pathlib import Path
from typing import Dict, List, Optional


REWARD_TYPES = [
    "dragon",       # 龙
    "castle",       # 城堡
    "magic_item",   # 魔法物品
    "rare_reward",  # 稀有奖励
    "character",    # 角色
    "mixed",        # 混合
]

REWARD_ELEMENTS = [
    "dragon", "castle", "gems", "chest", "coins",
    "magic_staff", "crown", "potion", "egg", "crystal",
]

REWARD_PROMPT = """Analyze the reward/treasure elements shown in this mobile game ad image.

Identify:
1. reward_type: What is the primary reward category?
   - dragon: dragon or dragon-like creature as reward
   - castle: castle/building upgrade as reward
   - magic_item: magic wand/staff/potion as reward
   - rare_reward: rare chest/gem/crystal as reward
   - character: character unlock as reward
   - mixed: multiple reward types

2. elements: List specific reward objects visible
   Options: dragon, castle, gems, chest, coins, magic_staff, crown, potion, egg, crystal

3. prominence: How prominent is the reward in the ad (0.0-1.0)

Return JSON:
{
  "type": "dragon|castle|magic_item|rare_reward|character|mixed",
  "elements": ["dragon", "gems", ...],
  "prominence": 0.0-1.0
}
Only return JSON."""


class RewardRecognizer:
    """奖励元素识别器"""

    def __init__(self, client=None):
        self.client = client

    def recognize(self, image_path: Optional[Path] = None,
                  ad_name: str = "") -> Dict:
        """识别图片中的奖励元素

        Args:
            image_path: 图片路径
            ad_name: 广告名

        Returns:
            {"type": str, "elements": list, "prominence": float}
        """
        if image_path and self.client:
            return self._recognize_with_vision(image_path)
        return self._recognize_rule_based(ad_name)

    def _recognize_with_vision(self, image_path: Path) -> Dict:
        """使用 Vision API 识别"""
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
                        {"type": "text", "text": REWARD_PROMPT},
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
            print(f"    [RewardRecognizer] Vision 失败: {e}")
            return self._recognize_rule_based("")

    def _recognize_rule_based(self, ad_name: str = "") -> Dict:
        """规则模式: 基于广告名推断奖励类型"""
        name_lower = ad_name.lower()

        if "龙" in ad_name or "dragon" in name_lower:
            return {
                "type": "dragon",
                "elements": ["dragon", "egg"],
                "prominence": 0.7,
                "_source": "rule_based",
            }
        elif "城堡" in ad_name or "castle" in name_lower:
            return {
                "type": "castle",
                "elements": ["castle"],
                "prominence": 0.7,
                "_source": "rule_based",
            }
        elif "宝箱" in ad_name or "chest" in name_lower or "宝石" in ad_name:
            return {
                "type": "rare_reward",
                "elements": ["chest", "gems"],
                "prominence": 0.7,
                "_source": "rule_based",
            }
        elif "魔法" in ad_name or "magic" in name_lower:
            return {
                "type": "magic_item",
                "elements": ["magic_staff", "potion"],
                "prominence": 0.6,
                "_source": "rule_based",
            }
        else:
            return {
                "type": "mixed",
                "elements": ["gems", "coins"],
                "prominence": 0.5,
                "_source": "rule_based",
            }
