"""Winner DNA Matcher — DNA 匹配评分"""
from typing import Dict, List
from collections import Counter

from ..models import PerformanceData, DNAMatch, WinnerDNA
from ..config import DEFAULT_WINNER_DNA


class DNAMatcher:
    """素材与 Winner DNA 的匹配评分"""

    def __init__(self, winner_dna: WinnerDNA = None):
        self.dna = winner_dna or WinnerDNA(**DEFAULT_WINNER_DNA)

    def match(self, video_id: str, content_type: str,
              performance: PerformanceData = None) -> DNAMatch:
        """
        计算素材的 DNA 匹配分

        Score = theme_match * 0.3 + visual_match * 0.3 + scene_match * 0.2 + historical_perf * 0.2
        """
        match = DNAMatch(video_id=video_id)

        # Theme 匹配（内容类型 vs DNA theme）
        theme_keywords = {
            "角色展示": ["witch", "character"],
            "宠物展示": ["pet", "dragon"],
            "场景展示": ["castle", "scene"],
            "玩法展示": ["gameplay", "merge"],
            "剧情": ["story", "emotion"],
            "开场": ["hook", "intro"],
            "文字滚动": ["text", "info"],
        }
        keywords = theme_keywords.get(content_type, [])
        match.theme_match = self._calc_theme_match(keywords)

        # Visual 匹配（基于内容类型的视觉强度）
        visual_scores = {
            "角色展示": 90,
            "宠物展示": 88,
            "场景展示": 75,
            "玩法展示": 85,
            "剧情": 80,
            "开场": 85,
            "文字滚动": 60,
            "其他": 65,
        }
        match.visual_match = visual_scores.get(content_type, 65)

        # Scene 匹配（结构匹配）
        scene_map = {
            "角色展示": "reward",
            "宠物展示": "hook",
            "场景展示": "hook",
            "玩法展示": "gameplay",
            "剧情": "problem",
            "开场": "hook",
            "文字滚动": "problem",
        }
        role = scene_map.get(content_type, "hook")
        match.scene_match = 85 if role in self.dna.structure else 50

        # Historical Performance
        if performance:
            match.historical_perf = min(performance.roas * 25, 100)
        else:
            match.historical_perf = 50

        # Overall
        match.overall = (
            match.theme_match * 0.30 +
            match.visual_match * 0.30 +
            match.scene_match * 0.20 +
            match.historical_perf * 0.20
        )

        return match

    def _calc_theme_match(self, keywords: List[str]) -> float:
        """计算主题匹配度"""
        if not keywords:
            return 50
        dna_themes = set(t.lower() for t in self.dna.theme)
        matches = sum(1 for k in keywords if k.lower() in dna_themes)
        return 50 + min(matches * 20, 50)

    def update_dna(self, winners: List[PerformanceData]):
        """根据新的赢家更新 DNA"""
        if not winners:
            return

        # 统计赢家主题
        themes = Counter()
        for w in winners:
            content = w.content_type or ""
            if "角色" in content:
                themes["witch"] += 1
            if "宠物" in content:
                themes["dragon"] += 1
            if "场景" in content:
                themes["castle"] += 1
            if "玩法" in content:
                themes["merge"] += 1

        # 更新 DNA
        self.dna.theme = [t for t, c in themes.most_common(5)]
        self.dna.avg_ctr = sum(w.ctr for w in winners) / len(winners)
        self.dna.avg_cvr = sum(w.cvr for w in winners) / len(winners)
        self.dna.avg_roas = sum(w.roas for w in winners) / len(winners)
