"""Purchase Probability — 购买概率预测"""
import numpy as np
from typing import Dict

from ..predictor.feature_schema import CreativeFeatureVector


class PurchaseProbability:
    """预测购买概率"""

    def predict(self, feature: CreativeFeatureVector) -> float:
        """
        基于创意特征预测购买概率
        如果ML模型不可用，使用规则评分
        """
        # 基础概率
        base = 0.005

        # Hook影响 (购买前3秒最关键)
        hook_boost = min(feature.hook_score / 100, 1.0) * 0.015

        # Gameplay影响
        gameplay_boost = min(feature.gameplay_score / 100, 1.0) * 0.010

        # DNA匹配影响
        dna_boost = min(feature.dna_match / 100, 1.0) * 0.008

        # 情感影响
        emotion_boost = min(feature.emotion_score / 100, 1.0) * 0.005

        # 时长影响（太长降低概率）
        duration_penalty = 0
        if feature.duration > 30:
            duration_penalty = -0.003

        prob = base + hook_boost + gameplay_boost + dna_boost + emotion_boost + duration_penalty
        return max(0.001, min(0.05, prob))
