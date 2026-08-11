"""Action Analyzer - 动作分析器

判断视频是否存在有效动作。
低分：standing, idle, slow movement, empty scene
高分：merge, attack, upgrade, transform, collect, reward
"""
from __future__ import annotations

from typing import Any

from .models import ActionAnalysis


class ActionAnalyzer:
    """动作分析器"""

    # 高价值动作
    HIGH_VALUE_ACTIONS: list[str] = [
        "merge", "attack", "upgrade", "transform", "evolution",
        "collect", "reward", "cast", "spell", "battle",
        "fight", "dash", "charge", "unlock", "power up",
    ]

    # 禁止动作（低留存）
    BANNED_ACTIONS: list[str] = [
        "standing still", "idle", "slow movement", "empty scene",
        "looking around", "walking slowly", "static pose",
        "no action", "frozen", "freeze frame",
    ]

    # 动作强度指标
    INTENSITY_KEYWORDS: dict[str, list[str]] = {
        "high": ["explosion", "burst", "flash", "rapid", "fast", "intense", "powerful"],
        "medium": ["casting", "merging", "attacking", "transforming", "upgrading"],
        "low": ["walking", "standing", "looking", "slow", "gentle"],
    }

    def __init__(self):
        self._high_value = list(self.HIGH_VALUE_ACTIONS)
        self._banned = list(self.BANNED_ACTIONS)
        self._intensity = {k: list(v) for k, v in self.INTENSITY_KEYWORDS.items()}

    def analyze(self, prompt_text: str) -> ActionAnalysis:
        """分析动作

        Args:
            prompt_text: 视频生成 prompt

        Returns:
            ActionAnalysis
        """
        text = prompt_text.lower()
        result = ActionAnalysis()

        # 检测高价值动作
        for action in self._high_value:
            if action in text:
                result.detected_actions.append(action)

        # 检测禁止动作
        for banned in self._banned:
            if banned in text:
                result.banned_actions.append(banned)

        # 判断动作强度
        result.action_intensity = self._detect_intensity(text)

        # 计算分数
        result.score = self._calculate_score(result)
        return result

    def _detect_intensity(self, text: str) -> str:
        """检测动作强度"""
        for intensity, kws in self._intensity.items():
            if any(kw in text for kw in kws):
                return intensity
        return "medium"

    def _calculate_score(self, result: ActionAnalysis) -> float:
        """计算动作分数（0-100）"""
        score = 40.0

        # 高价值动作加分
        score += len(result.detected_actions) * 12

        # 禁止动作扣分
        score -= len(result.banned_actions) * 25

        # 强度加分
        if result.action_intensity == "high":
            score += 15
        elif result.action_intensity == "medium":
            score += 8
        elif result.action_intensity == "low":
            score -= 10

        # 无动作惩罚
        if not result.detected_actions:
            score -= 20

        return min(100.0, max(0.0, score))
