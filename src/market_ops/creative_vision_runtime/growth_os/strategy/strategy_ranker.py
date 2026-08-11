"""E12.7.3 — Strategy Ranker。

策略排名器 —— 对多个策略进行评分排名。

职责:
  1. 接收多个 GrowthStrategy
  2. 计算综合评分
  3. 按评分排序

评分公式:
  score = expected_impact × 0.40 + confidence × 0.30 + (1 - risk_score) × 0.20 + action_count_factor × 0.10
"""

from __future__ import annotations

from .models import GrowthStrategy


class StrategyRanker:
    """策略排名器。

    对多个策略进行评分排名。
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._weights = weights or {
            "expected_impact": 0.40,
            "confidence": 0.30,
            "risk_inverse": 0.20,
            "action_count": 0.10,
        }

    def rank(
        self, strategies: list[GrowthStrategy]
    ) -> list[GrowthStrategy]:
        """排名策略。

        Args:
            strategies: 策略列表

        Returns:
            排名后的策略列表（按 score 降序）
        """
        scored = [(s, self._score(s)) for s in strategies]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored]

    def get_top(
        self, strategies: list[GrowthStrategy]
    ) -> GrowthStrategy | None:
        """获取最优策略。"""
        ranked = self.rank(strategies)
        return ranked[0] if ranked else None

    def get_top_n(
        self, strategies: list[GrowthStrategy], n: int = 3
    ) -> list[GrowthStrategy]:
        """获取前 N 个策略。"""
        ranked = self.rank(strategies)
        return ranked[:n]

    def _score(self, strategy: GrowthStrategy) -> float:
        """计算策略综合评分。

        score = expected_impact × w1 + confidence × w2
              + (1 - risk_score) × w3 + action_count_normalized × w4
        """
        # 动作数量归一化（最多 10 个动作得满分）
        action_factor = min(1.0, strategy.action_count / 10.0)

        score = (
            strategy.expected_impact * self._weights["expected_impact"]
            + strategy.confidence * self._weights["confidence"]
            + (1.0 - strategy.risk_score) * self._weights["risk_inverse"]
            + action_factor * self._weights["action_count"]
        )

        return round(score, 4)

    def get_scores(
        self, strategies: list[GrowthStrategy]
    ) -> dict[str, float]:
        """获取所有策略的评分。

        Returns:
            {strategy_id: score}
        """
        return {s.strategy_id: self._score(s) for s in strategies}

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def __repr__(self) -> str:
        w = self._weights
        return (
            f"StrategyRanker(impact={w['expected_impact']:.2f}, "
            f"conf={w['confidence']:.2f})"
        )