"""Gameplay Analyzer - 玩法分析器

针对游戏广告，检测是否包含：
- 核心玩法
- 成长
- 奖励
"""
from __future__ import annotations

from typing import Any

from .models import GameplayAnalysis


class GameplayAnalyzer:
    """玩法分析器"""

    # Merge 游戏玩法关键词
    MERGE_KEYWORDS: list[str] = [
        "merge", "combine", "fuse", "blend", "synthesize",
        "match", "pair", "connect", "join", "unite",
    ]

    # 升级关键词
    UPGRADE_KEYWORDS: list[str] = [
        "upgrade", "evolve", "level up", "power up", "enhance",
        "improve", "advance", "promote", "ascend", "tier up",
    ]

    # 奖励关键词
    REWARD_KEYWORDS: list[str] = [
        "reward", "treasure", "loot", "prize", "bonus",
        "gift", "chest", "drop", "collect", "gain",
    ]

    # 收集关键词
    COLLECTION_KEYWORDS: list[str] = [
        "collect", "gather", "assemble", "hoard", "accumulate",
        "complete", "unlock", "discover", "find", "obtain",
    ]

    # 通用游戏玩法
    GAMEPLAY_KEYWORDS: list[str] = [
        "puzzle", "strategy", "battle", "fight", "quest",
        "adventure", "explore", "build", "craft", "defend",
    ]

    def __init__(self):
        self._merge = list(self.MERGE_KEYWORDS)
        self._upgrade = list(self.UPGRADE_KEYWORDS)
        self._reward = list(self.REWARD_KEYWORDS)
        self._collect = list(self.COLLECTION_KEYWORDS)
        self._gameplay = list(self.GAMEPLAY_KEYWORDS)

    def analyze(self, prompt_text: str, game_type: str = "merge") -> GameplayAnalysis:
        """分析玩法

        Args:
            prompt_text: 视频生成 prompt
            game_type: 游戏类型

        Returns:
            GameplayAnalysis
        """
        text = prompt_text.lower()
        result = GameplayAnalysis()

        # 检测 merge
        result.has_merge = any(kw in text for kw in self._merge)
        if result.has_merge:
            result.detected_gameplay.append("merge")

        # 检测 upgrade
        result.has_upgrade = any(kw in text for kw in self._upgrade)
        if result.has_upgrade:
            result.detected_gameplay.append("upgrade")

        # 检测 reward
        result.has_reward = any(kw in text for kw in self._reward)
        if result.has_reward:
            result.detected_gameplay.append("reward")

        # 检测 collection
        result.has_collection = any(kw in text for kw in self._collect)
        if result.has_collection:
            result.detected_gameplay.append("collection")

        # 检测通用玩法
        for kw in self._gameplay:
            if kw in text and kw not in result.detected_gameplay:
                result.detected_gameplay.append(kw)

        # 计算分数
        result.score = self._calculate_score(result, game_type)
        return result

    def _calculate_score(self, result: GameplayAnalysis, game_type: str) -> float:
        """计算玩法分数（0-100）"""
        score = 30.0

        # 根据游戏类型调整权重
        if game_type == "merge":
            if result.has_merge:
                score += 25
            if result.has_upgrade:
                score += 20
            if result.has_reward:
                score += 15
            if result.has_collection:
                score += 10
        elif game_type == "rpg":
            if result.has_upgrade:
                score += 25
            if "battle" in result.detected_gameplay or "fight" in result.detected_gameplay:
                score += 20
            if result.has_reward:
                score += 15
        elif game_type == "casual":
            if result.has_merge or result.has_collection:
                score += 25
            if result.has_reward:
                score += 20
        else:
            # 通用评分
            if result.has_merge:
                score += 20
            if result.has_upgrade:
                score += 20
            if result.has_reward:
                score += 15
            if result.has_collection:
                score += 10

        # 通用玩法加分
        score += len(result.detected_gameplay) * 5

        return min(100.0, score)
