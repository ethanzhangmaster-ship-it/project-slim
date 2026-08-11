"""E13.5.5 Decision Scorer — 策略评分与风险调整.

对候选策略进行综合评分，结合策略价值、置信度和风险，输出排序后的决策评分。

核心公式:
  final_score = strategy_reward × confidence × (1 - risk_score)

连接:
  E13.5.3 StrategySelector → E13.5.4 RiskController → E13.5.5 DecisionScorer
"""

from __future__ import annotations

from typing import Any

from ..intelligence_models import StrategyCandidate
from ..risk_models import RiskAssessment, RiskDecision
from .models import DecisionScore


class DecisionScorer:
    """决策评分器 — 综合策略价值、置信度与风险进行评分.

    公式:
      risk_adjusted_reward = strategy_reward × (1 - risk_score)
      final_score = strategy_reward × confidence × (1 - risk_score)

    用法:
        scorer = DecisionScorer()
        scores = scorer.score_all(candidates, risk_assessments)
        best = scores[0]  # 最高分策略
        print(f"Best: {best.strategy_name} → {best.final_score:.2f}")
    """

    # ── 权重配置 ──────────────────────────────────────────────

    # 默认权重 (可配置)
    reward_weight: float = 1.0
    confidence_weight: float = 1.0
    risk_weight: float = 1.0

    # 可行阈值
    min_viable_score: float = 0.3
    strong_score: float = 0.6

    def __init__(
        self,
        reward_weight: float = 1.0,
        confidence_weight: float = 1.0,
        risk_weight: float = 1.0,
        min_viable_score: float = 0.3,
        strong_score: float = 0.6,
    ):
        """初始化评分器.

        Args:
            reward_weight: 策略价值权重
            confidence_weight: 置信度权重
            risk_weight: 风险惩罚权重
            min_viable_score: 可行最低分数
            strong_score: 强推荐分数阈值
        """
        self.reward_weight = reward_weight
        self.confidence_weight = confidence_weight
        self.risk_weight = risk_weight
        self.min_viable_score = min_viable_score
        self.strong_score = strong_score

    # ═══════════════════════════════════════════════════════════
    # 核心评分
    # ═══════════════════════════════════════════════════════════

    def score_strategy(
        self,
        candidate: StrategyCandidate,
        risk: RiskAssessment | None = None,
    ) -> DecisionScore:
        """对单个策略进行评分.

        Args:
            candidate: 策略候选
            risk: 风险评估 (可为 None，此时 risk_score = 0)

        Returns:
            DecisionScore: 评分结果
        """
        # 提取策略价值 (historical_score 作为 strategy_reward)
        strategy_reward = self._clamp(candidate.historical_score)
        confidence = self._clamp(candidate.confidence_score)

        # 风险评分
        risk_score = 0.0
        if risk is not None:
            risk_score = self._clamp(risk.risk_score)

        # 风险调整后收益
        risk_adjusted_reward = self._compute_risk_adjusted_reward(
            strategy_reward, risk_score
        )

        # 最终评分
        final_score = self._compute_final_score(
            strategy_reward, confidence, risk_score
        )

        return DecisionScore(
            strategy_id=candidate.strategy_id,
            strategy_name=candidate.strategy_name,
            strategy_reward=strategy_reward,
            confidence=confidence,
            risk_score=risk_score,
            risk_adjusted_reward=risk_adjusted_reward,
            final_score=final_score,
            rank=0,  # 由 score_all 统一设置
        )

    def score_all(
        self,
        candidates: list[StrategyCandidate],
        risk_assessments: dict[str, RiskAssessment] | None = None,
        top_n: int = 10,
    ) -> list[DecisionScore]:
        """对所有候选策略进行评分并排序.

        Args:
            candidates: 候选策略列表
            risk_assessments: 策略风险评估 dict (keyed by strategy_id)
            top_n: 保留前 N 个 (0 表示全部保留)

        Returns:
            list[DecisionScore]: 排序后的评分列表 (按 final_score 降序)
        """
        if risk_assessments is None:
            risk_assessments = {}

        # 逐个评分
        scores: list[DecisionScore] = []
        for candidate in candidates:
            risk = risk_assessments.get(candidate.strategy_id)
            score = self.score_strategy(candidate, risk)
            scores.append(score)

        # 按 final_score 降序排列
        scores.sort(key=lambda s: s.final_score, reverse=True)

        # 重新设置排名
        for i, score in enumerate(scores, start=1):
            score.rank = i

        # 截断
        if top_n > 0 and len(scores) > top_n:
            scores = scores[:top_n]

        return scores

    # ═══════════════════════════════════════════════════════════
    # 评分计算
    # ═══════════════════════════════════════════════════════════

    def _compute_risk_adjusted_reward(
        self,
        strategy_reward: float,
        risk_score: float,
    ) -> float:
        """计算风险调整后收益.

        Formula:
          risk_adjusted_reward = strategy_reward × (1 - risk_score × risk_weight)

        风险越高，实际收益折扣越大。
        """
        penalty = risk_score * self.risk_weight
        penalty = min(penalty, 1.0)  # 最多折到 0
        return self._clamp(strategy_reward * (1.0 - penalty))

    def _compute_final_score(
        self,
        strategy_reward: float,
        confidence: float,
        risk_score: float,
    ) -> float:
        """计算最终综合评分.

        Formula:
          final_score = strategy_reward^reward_weight × confidence^confidence_weight
                       × (1 - risk_score × risk_weight)

        三个维度相乘，任何一维低都会拉低总分。
        """
        reward_factor = strategy_reward ** self.reward_weight
        confidence_factor = confidence ** self.confidence_weight
        risk_factor = 1.0 - (risk_score * self.risk_weight)
        risk_factor = max(risk_factor, 0.0)  # 不低于 0

        return self._clamp(reward_factor * confidence_factor * risk_factor)

    # ═══════════════════════════════════════════════════════════
    # 筛选与查询
    # ═══════════════════════════════════════════════════════════

    def get_best(self, scores: list[DecisionScore]) -> DecisionScore | None:
        """获取最高分策略 (已排序列表的第一项)."""
        return scores[0] if scores else None

    def get_viable(
        self,
        scores: list[DecisionScore],
        min_score: float | None = None,
    ) -> list[DecisionScore]:
        """筛选可行策略 (final_score >= min_score)."""
        threshold = min_score if min_score is not None else self.min_viable_score
        return [s for s in scores if s.final_score >= threshold]

    def get_strong(
        self,
        scores: list[DecisionScore],
        min_score: float | None = None,
    ) -> list[DecisionScore]:
        """筛选强推荐策略 (final_score >= strong_score)."""
        threshold = min_score if min_score is not None else self.strong_score
        return [s for s in scores if s.final_score >= threshold]

    def get_by_risk_level(
        self,
        scores: list[DecisionScore],
        max_risk: float = 0.5,
    ) -> list[DecisionScore]:
        """筛选低风险策略 (risk_score <= max_risk)."""
        return [s for s in scores if s.risk_score <= max_risk]

    # ═══════════════════════════════════════════════════════════
    # 工具
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        """将值限制在 [low, high] 范围内."""
        return max(low, min(high, value))