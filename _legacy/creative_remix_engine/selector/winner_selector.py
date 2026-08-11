"""Winner Selector — Winner DNA 提取"""
from typing import List, Dict
from collections import Counter

from ..models import PerformanceData


class WinnerSelector:
    """从赢家素材中提取 DNA"""

    def extract_dna(self, data: List[PerformanceData], top_n: int = 10) -> Dict:
        """提取 Winner DNA"""
        winners = sorted(data, key=lambda x: -x.roas)[:top_n]

        themes = Counter()
        structures = []

        for w in winners:
            content = w.content_type or "其他"
            if "角色" in content:
                themes["witch"] += 1
            if "龙" in content or "dragon" in content:
                themes["dragon"] += 1
            if "城堡" in content or "场景" in content:
                themes["castle"] += 1

        # 结构分析
        structures = [
            {"role": "hook", "duration": 3},
            {"role": "gameplay", "duration": 10},
            {"role": "reward", "duration": 3},
        ]

        return {
            "theme": list(themes.keys()),
            "structures": structures,
            "winner_count": len(winners),
            "avg_roas": sum(w.roas for w in winners) / len(winners) if winners else 0,
        }
