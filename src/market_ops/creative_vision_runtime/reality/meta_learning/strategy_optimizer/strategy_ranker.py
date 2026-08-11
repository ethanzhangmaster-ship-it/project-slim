"""E12.5.4 — Strategy Ranker。

对 MetaStrategy 列表进行评分和排序。

评分模型:
  MetaScore = PerformanceImpact × 0.35
            + Confidence × 0.30
            + Transferability × 0.20
            - Risk × 0.15

排序策略:
  - 按 score 降序排列
  - 区分 exploit / explore 策略
  - 输出排名报告
"""

from __future__ import annotations

from .models import (
    MetaStrategy,
    OptimizationGoal,
    StrategyRanking,
    StrategyStatus,
)


class StrategyRanker:
    """策略排序器 —— 评分 + 排序。

    Usage:
        >>> ranker = StrategyRanker()
        >>> ranking = ranker.rank(strategies)
        >>> top = ranking.get_top(5)
    """

    # 权重配置
    WEIGHT_PERFORMANCE: float = 0.35
    WEIGHT_CONFIDENCE: float = 0.30
    WEIGHT_TRANSFER: float = 0.20
    WEIGHT_RISK: float = 0.15

    # 探索策略的额外 risk 惩罚
    EXPLORE_RISK_PENALTY: float = 0.10

    def __init__(
        self,
        w_performance: float = 0.35,
        w_confidence: float = 0.30,
        w_transfer: float = 0.20,
        w_risk: float = 0.15,
    ) -> None:
        self.WEIGHT_PERFORMANCE = w_performance
        self.WEIGHT_CONFIDENCE = w_confidence
        self.WEIGHT_TRANSFER = w_transfer
        self.WEIGHT_RISK = w_risk

    # ── Scoring ────────────────────────────────────────────

    def score_strategy(self, strategy: MetaStrategy) -> float:
        """计算单个策略的综合评分。

        MetaScore = PerformanceImpact × 0.35
                  + Confidence × 0.30
                  + Transferability × 0.20
                  - Risk × 0.15

        Args:
            strategy: MetaStrategy

        Returns:
            综合评分 [0, 1]
        """
        # 性能影响 (归一化到 [0, 1])
        performance = self._score_performance(strategy)

        # 置信度
        confidence = strategy.confidence

        # 可迁移性（基于 evidence_count 和市场/平台/受众数量）
        transferability = self._score_transferability(strategy)

        # 风险（反转：低风险 = 高分）
        risk = strategy.risk_score
        if strategy.exploration:
            risk += self.EXPLORE_RISK_PENALTY
        risk = min(risk, 1.0)

        score = (
            performance * self.WEIGHT_PERFORMANCE
            + confidence * self.WEIGHT_CONFIDENCE
            + transferability * self.WEIGHT_TRANSFER
            - risk * self.WEIGHT_RISK
        )

        return max(0.0, min(1.0, score))

    def _score_performance(self, strategy: MetaStrategy) -> float:
        """计算性能影响分数。

        使用 sigmoid 归一化，使得 delta 0.2 左右映射到 ~0.7。
        """
        total = (
            strategy.expected_ctr_delta
            + strategy.expected_roas_delta
            + strategy.expected_cvr_delta
            - strategy.expected_cpi_delta
        ) / 3.0

        # Sigmoid 归一化: 1 / (1 + exp(-5 * (x - 0.1)))
        import math
        try:
            normalized = 1.0 / (1.0 + math.exp(-5.0 * (total - 0.1)))
        except OverflowError:
            normalized = 1.0 if total > 0.1 else 0.0

        return normalized

    def _score_transferability(self, strategy: MetaStrategy) -> float:
        """计算可迁移性分数。

        基于:
          - evidence_count: 越多越可迁移
          - markets: 覆盖市场越多越可迁移
          - platforms: 覆盖平台越多越可迁移
          - audiences: 覆盖受众越多越可迁移
        """
        evidence_score = min(strategy.evidence_count / 100.0, 1.0)
        market_score = min(len(strategy.markets) / 5.0, 1.0)
        platform_score = min(len(strategy.platforms) / 3.0, 1.0)
        audience_score = min(len(strategy.audiences) / 5.0, 1.0)

        return (
            evidence_score * 0.40
            + market_score * 0.25
            + platform_score * 0.20
            + audience_score * 0.15
        )

    # ── Ranking ─────────────────────────────────────────────

    def rank(
        self,
        strategies: list[MetaStrategy],
    ) -> StrategyRanking:
        """对策略列表进行排序。

        Args:
            strategies: 策略列表

        Returns:
            StrategyRanking 排序结果
        """
        if not strategies:
            return StrategyRanking(
                strategies=[],
                ranking_summary="No strategies to rank.",
            )

        # 计算 score
        for s in strategies:
            s.score = self.score_strategy(s)
            s.status = StrategyStatus.RANKED

        # 按 score 降序排序
        sorted_strategies = sorted(strategies, key=lambda s: s.score, reverse=True)

        # 分离 exploit / explore
        top_exploit = [s for s in sorted_strategies if not s.exploration][:5]
        top_explore = [s for s in sorted_strategies if s.exploration][:5]

        ranking_summary = self._build_summary(sorted_strategies, top_exploit, top_explore)

        return StrategyRanking(
            strategies=sorted_strategies,
            top_exploit=top_exploit,
            top_explore=top_explore,
            ranking_summary=ranking_summary,
        )

    def _build_summary(
        self,
        all_strategies: list[MetaStrategy],
        top_exploit: list[MetaStrategy],
        top_explore: list[MetaStrategy],
    ) -> str:
        """构建排序摘要。"""
        parts = [f"Ranked {len(all_strategies)} strategies"]

        if top_exploit:
            best = top_exploit[0]
            parts.append(
                f"Top exploit: {best.name} "
                f"(score={best.score:.2f}, "
                f"conf={best.confidence:.2f})"
            )

        if top_explore:
            best_explore = top_explore[0]
            parts.append(
                f"Top explore: {best_explore.name} "
                f"(score={best_explore.score:.2f})"
            )

        return ". ".join(parts) + "."

    def rank_by_goal(
        self,
        strategies: list[MetaStrategy],
        goal: OptimizationGoal,
    ) -> StrategyRanking:
        """按特定优化目标排序。

        Args:
            strategies: 策略列表
            goal:       优化目标

        Returns:
            StrategyRanking 排序结果
        """
        # 匹配目标的策略排在前面
        matched = [s for s in strategies if s.optimization_goal == goal]
        others = [s for s in strategies if s.optimization_goal != goal]

        for s in matched:
            s.score = self.score_strategy(s) + 0.05  # 目标匹配加分
        for s in others:
            s.score = self.score_strategy(s)

        all_ranked = sorted(matched + others, key=lambda s: s.score, reverse=True)
        return self.rank(all_ranked)

    def __repr__(self) -> str:
        return (
            f"StrategyRanker(perf={self.WEIGHT_PERFORMANCE}, "
            f"conf={self.WEIGHT_CONFIDENCE}, "
            f"transfer={self.WEIGHT_TRANSFER}, "
            f"risk={self.WEIGHT_RISK})"
        )