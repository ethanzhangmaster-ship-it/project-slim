"""Gameplay Recognizer — 玩法类型识别

检测: merge_board / before_after / upgrade_arrow / progression
"""
import json
from pathlib import Path
from typing import Dict, List, Optional


GAMEPLAY_TYPES = [
    "merge_board",      # 合并棋盘
    "before_after",     # 前后对比
    "upgrade_arrow",    # 升级箭头
    "progression",      # 关卡进度
    "mixed",            # 混合
]

GAMEPLAY_ELEMENTS = [
    "merge_items",      # 合并物品
    "board_grid",       # 棋盘网格
    "arrows",           # 箭头指示
    "numbers",          # 等级数字
    "comparison",       # 对比展示
    "level_indicator",  # 关卡指示
]

GAMEPLAY_PROMPT = """Analyze the gameplay mechanics shown in this mobile game ad image.

Identify:
1. gameplay_type: What type of gameplay is shown?
   - merge_board: merge/puzzle board with items to combine
   - before_after: comparison showing before/after states
   - upgrade_arrow: upgrade path with arrows
   - progression: level/stage progression
   - mixed: combination of multiple types

2. elements: What specific game elements are visible?
   Options: merge_items, board_grid, arrows, numbers, comparison, level_indicator

Return JSON:
{
  "type": "merge_board|before_after|upgrade_arrow|progression|mixed",
  "elements": ["merge_items", "board_grid", ...],
  "clarity_score": 0.0-1.0
}
Only return JSON."""


class GameplayRecognizer:
    """玩法类型识别器"""

    def __init__(self, client=None):
        self.client = client

    def recognize(self, image_path: Optional[Path] = None,
                  ad_name: str = "") -> Dict:
        """识别图片中的玩法类型

        Args:
            image_path: 图片路径
            ad_name: 广告名

        Returns:
            {"type": str, "elements": list, "clarity_score": float}
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
                        {"type": "text", "text": GAMEPLAY_PROMPT},
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
            print(f"    [GameplayRecognizer] Vision 失败: {e}")
            return self._recognize_rule_based("")

    def _recognize_rule_based(self, ad_name: str = "") -> Dict:
        """规则模式: 基于广告名推断玩法类型"""
        name_lower = ad_name.lower()

        if "对比" in ad_name or "before" in name_lower or "ba" in name_lower:
            return {
                "type": "before_after",
                "elements": ["comparison", "arrows"],
                "clarity_score": 0.7,
                "_source": "rule_based",
            }
        elif "升级" in ad_name or "upgrade" in name_lower or "lv" in name_lower:
            return {
                "type": "upgrade_arrow",
                "elements": ["arrows", "numbers", "level_indicator"],
                "clarity_score": 0.7,
                "_source": "rule_based",
            }
        elif "关卡" in ad_name or "level" in name_lower or "stage" in name_lower:
            return {
                "type": "progression",
                "elements": ["level_indicator", "numbers"],
                "clarity_score": 0.6,
                "_source": "rule_based",
            }
        else:
            # 默认: merge board (最常见)
            return {
                "type": "merge_board",
                "elements": ["merge_items", "board_grid"],
                "clarity_score": 0.6,
                "_source": "rule_based",
            }
