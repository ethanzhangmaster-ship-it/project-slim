"""Ad Score Predictor - 广告评分预测器

计算 Video Potential Score。

公式：
Total Score = 0.35 * Hook + 0.25 * Action + 0.20 * Gameplay + 0.10 * Character + 0.10 * Visual
"""
from __future__ import annotations

from typing import Any

from .models import (
    HookAnalysis, ActionAnalysis, GameplayAnalysis,
    ConsistencyResult, VisualFeatures,
)


class AdScorePredictor:
    """广告评分预测器"""

    # 权重配置
    WEIGHTS: dict[str, float] = {
        "hook": 0.35,
        "action": 0.25,
        "gameplay": 0.20,
        "character": 0.10,
        "visual": 0.10,
    }

    def __init__(self):
        self._weights = dict(self.WEIGHTS)

    def predict(
        self,
        hook: HookAnalysis,
        action: ActionAnalysis,
        gameplay: GameplayAnalysis,
        consistency: ConsistencyResult,
        visual: VisualFeatures,
        visual_score: float = 0.0,
    ) -> dict[str, Any]:
        """预测广告潜力

        Returns:
            {"total_score": float, "level": str, "prediction": str}
        """
        # 角色分数取一致性的 character_consistency
        char_score = consistency.character_consistency

        # 视觉分数（如果没有传入，基于 visual richness）
        if visual_score <= 0:
            visual_score = self._calculate_visual_score(visual)

        # 加权总分
        total = (
            hook.score * self._weights["hook"] +
            action.score * self._weights["action"] +
            gameplay.score * self._weights["gameplay"] +
            char_score * self._weights["character"] +
            visual_score * self._weights["visual"]
        )

        # 等级判定
        level, prediction = self._classify(total)

        return {
            "total_score": round(total, 1),
            "level": level,
            "prediction": prediction,
            "breakdown": {
                "hook": round(hook.score, 1),
                "action": round(action.score, 1),
                "gameplay": round(gameplay.score, 1),
                "character": round(char_score, 1),
                "visual": round(visual_score, 1),
            },
        }

    def _calculate_visual_score(self, visual: VisualFeatures) -> float:
        """计算视觉分数"""
        score = 30.0
        score += len(visual.characters) * 10
        score += len(visual.scenes) * 5
        score += len(visual.elements) * 8
        if visual.characters and visual.elements:
            score += 20
        return min(100.0, score)

    def _classify(self, total_score: float) -> tuple[str, str]:
        """分类等级"""
        if total_score >= 80:
            return "A", "HIGH_POTENTIAL"
        elif total_score >= 65:
            return "B", "MEDIUM_POTENTIAL"
        elif total_score >= 50:
            return "C", "LOW_POTENTIAL"
        else:
            return "D", "REJECT"
