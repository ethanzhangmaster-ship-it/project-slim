"""E13.5.3 Strategy Ranker — 策略排序器.

对候选策略进行综合评分排序，融合历史成功率、匹配度、置信度和风险。

评分公式:
  final_score = historical_success × 0.35 + match_score × 0.30
               + confidence × 0.20 - risk_score × 0.15

连接:
  StrategyMatcher → StrategyRanker → StrategySelector
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .intelligence_models import StrategyCandidate

if TYPE_CHECKING:
    from ..memory.failure_models import FailureWarning
    from ..memory.strategy_models import GrowthStrategyPattern


class StrategyRanker:
    """策略排序器 — 多维度评分排序.

    用法:
        ranker = StrategyRanker()
        candidates = ranker.rank(matched_strategies, risk_data)
    """

    # 评分权重
    WEIGHT_HISTORICAL = 0.35
    WEIGHT_MATCH = 0.30
    WEIGHT_CONFIDENCE = 0.20
    WEIGHT_RISK = 0.15

    # 风险惩罚参数
    RISK_BLOCK_THRESHOLD = 0.8      # 风险 >= 此值直接拦截
    RISK_SEVERE_PENALTY = 0.6       # 风险 >= 此值大幅降分
    RISK_MODERATE_PENALTY = 0.4     # 风险 >= 此值适度降分
    SEVERE_PENALTY_FACTOR = 0.5     # 大幅降分因子
    MODERATE_PENALTY_FACTOR = 0.8   # 适度降分因子

    def rank(
        self,
        matched_strategies: list[dict[str, Any]],
        risk_data: dict[str, Any] | None = None,
        top_n: int = 5,
    ) -> list[StrategyCandidate]:
        """对匹配策略评分排序.

        Args:
            matched_strategies: StrategyMatcher.match() 的输出
            risk_data: FailureMemory 风险数据 (strategy_id → risk info)
            top_n: 返回前 N 个候选

        Returns:
            list[StrategyCandidate]: 按 final_score 降序排列的候选列表
        """
        candidates: list[StrategyCandidate] = []

        for entry in matched_strategies:
            strategy: GrowthStrategyPattern = entry["strategy"]
            match_score: float = entry["match_score"]
            scores: dict[str, float] = entry["scores"]

            # 历史成功率
            historical_score = strategy.performance.success_rate

            # 策略置信度
            confidence_score = strategy.confidence

            # 风险评分
            risk_score = self._compute_risk_score(strategy, risk_data)

            # 综合评分
            final_score = self._compute_final_score(
                historical_score=historical_score,
                match_score=match_score,
                confidence_score=confidence_score,
                risk_score=risk_score,
            )

            # 失败警告
            failure_warnings: list[str] = []
            if risk_data:
                strategy_risks = risk_data.get(strategy.strategy_id, {})
                warnings = strategy_risks.get("warnings", [])
                failure_warnings = [
                    w.get("pattern_name", w.get("suggestion", "Unknown risk"))
                    for w in warnings
                ]

            # 选择理由
            reason = self._generate_reason(strategy, match_score, historical_score, risk_score)

            candidate = StrategyCandidate(
                strategy_id=strategy.strategy_id,
                strategy_name=strategy.name,
                strategy=strategy.to_dict(),
                match_score=round(match_score, 4),
                historical_score=round(historical_score, 4),
                confidence_score=round(confidence_score, 4),
                risk_score=round(risk_score, 4),
                final_score=round(final_score, 4),
                reason=reason,
                failure_warnings=failure_warnings,
            )
            candidates.append(candidate)

        # 排序
        candidates.sort(key=lambda c: -c.final_score)

        return candidates[:top_n] if top_n > 0 else candidates

    def _compute_final_score(
        self,
        historical_score: float,
        match_score: float,
        confidence_score: float,
        risk_score: float,
    ) -> float:
        """计算最终综合评分.

        final_score = historical × 0.35 + match × 0.30 + confidence × 0.20 - risk × 0.15
        """
        base = (
            historical_score * self.WEIGHT_HISTORICAL
            + match_score * self.WEIGHT_MATCH
            + confidence_score * self.WEIGHT_CONFIDENCE
        )

        # 风险惩罚
        if risk_score >= self.RISK_BLOCK_THRESHOLD:
            # 强制拦截: 分数趋近于 0
            return round(base * 0.01, 4)
        elif risk_score >= self.RISK_SEVERE_PENALTY:
            base *= self.SEVERE_PENALTY_FACTOR
        elif risk_score >= self.RISK_MODERATE_PENALTY:
            base *= self.MODERATE_PENALTY_FACTOR

        risk_penalty = risk_score * self.WEIGHT_RISK
        return round(max(0.0, base - risk_penalty), 4)

    def _compute_risk_score(
        self,
        strategy: GrowthStrategyPattern,
        risk_data: dict[str, Any] | None = None,
    ) -> float:
        """计算策略的风险评分.

        从 FailureMemory 的 check_strategy 结果中提取风险。
        """
        if risk_data is None:
            return 0.0

        strategy_risks = risk_data.get(strategy.strategy_id, {})
        if not strategy_risks:
            return 0.0

        warnings = strategy_risks.get("warnings", [])
        if not warnings:
            return 0.0

        # 取最高风险评分
        max_risk = max(
            (w.get("risk_score", 0.0) for w in warnings),
            default=0.0,
        )

        # 警告数量额外加成
        warning_bonus = min(len(warnings) * 0.05, 0.15)
        return round(min(max_risk + warning_bonus, 1.0), 4)

    def _generate_reason(
        self,
        strategy: GrowthStrategyPattern,
        match_score: float,
        historical_score: float,
        risk_score: float,
    ) -> str:
        """生成选择理由."""
        parts: list[str] = []

        if match_score >= 0.8:
            parts.append("high opportunity match")
        elif match_score >= 0.5:
            parts.append("moderate opportunity match")

        if historical_score >= 0.8:
            parts.append(f"proven success ({historical_score:.0%})")
        elif historical_score >= 0.6:
            parts.append(f"reliable ({historical_score:.0%})")

        if risk_score >= 0.8:
            parts.append("BLOCKED: high risk")
        elif risk_score >= 0.6:
            parts.append("warning: moderate risk")
        elif risk_score >= 0.4:
            parts.append("low risk")

        if not parts:
            parts.append("unproven strategy")

        return f"{strategy.name}: {', '.join(parts)}"

    def get_best(self, candidates: list[StrategyCandidate]) -> StrategyCandidate | None:
        """获取最佳候选 (已排序列表的第一个)."""
        return candidates[0] if candidates else None

    def get_viable(self, candidates: list[StrategyCandidate]) -> list[StrategyCandidate]:
        """获取所有可行候选 (未被风险拦截)."""
        return [c for c in candidates if c.is_viable]

    def get_blocked(self, candidates: list[StrategyCandidate]) -> list[StrategyCandidate]:
        """获取被风险拦截的候选."""
        return [c for c in candidates if c.is_blocked]