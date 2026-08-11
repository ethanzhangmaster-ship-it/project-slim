"""E12.5.5 — Decision Engine。

核心决策引擎 —— Context → Policy Evaluation → Risk Check → Ranking → MetaDecision。

流程:
  DecisionContext → Evaluate All Policies → Risk Check → Rank by Priority → Output

优先级:
  ROLLBACK > STOP_EXPERIMENT > START_EXPERIMENT > START_LEARNING
  > CONTINUE_EVOLUTION > SCALE_WINNER > WAIT

支持:
  - 多策略并行评估
  - 冲突解决（优先级排序）
  - 风险检查
  - 置信度校准
"""

from __future__ import annotations

from .decision_policy import (
    ContinueEvolutionRule,
    DecisionPolicy,
    DEFAULT_POLICIES,
    ExperimentFailureRule,
    FatigueRule,
    InsufficientDataRule,
    PopulationDegradationRule,
    RoasGrowthRule,
    RollbackRule,
)
from .models import (
    DecisionContext,
    MetaDecision,
    MetaDecisionType,
    get_decision_priority,
)


class MetaDecisionEngine:
    """元决策引擎 —— E12.6.1 核心。

    Usage:
        >>> engine = MetaDecisionEngine()
        >>> context = DecisionContext(
        ...     product_id="p04",
        ...     fatigue_score=0.85,
        ...     prediction_confidence=0.91,
        ... )
        >>> decision = engine.decide(context)
        >>> print(decision.action)
    """

    # 风险阈值
    RISK_CONFIDENCE_MIN: float = 0.40
    MAX_DECISIONS: int = 3

    def __init__(
        self,
        policies: list[DecisionPolicy] | None = None,
        risk_confidence_min: float = 0.40,
    ) -> None:
        self.policies = policies or DEFAULT_POLICIES.copy()
        self.RISK_CONFIDENCE_MIN = risk_confidence_min

    # ── Decide ─────────────────────────────────────────────

    def decide(self, context: DecisionContext) -> MetaDecision:
        """评估上下文并返回最佳决策。

        Args:
            context: 决策上下文

        Returns:
            MetaDecision（最佳决策）
        """
        decisions = self.evaluate_all(context)

        if not decisions:
            return MetaDecision(
                product_id=context.product_id,
                action=MetaDecisionType.WAIT,
                confidence=0.50,
                reasons=["No policies matched — defaulting to WAIT"],
                context_snapshot=context.to_dict(),
            )

        # 风险检查
        decisions = self._risk_check(decisions)

        # 排序
        ranked = self.rank(decisions)

        # 选择最佳决策
        best = ranked[0]

        return best

    def evaluate_all(self, context: DecisionContext) -> list[MetaDecision]:
        """评估所有策略。

        Args:
            context: 决策上下文

        Returns:
            匹配的决策列表
        """
        decisions: list[MetaDecision] = []
        for policy in self.policies:
            decision = policy.evaluate(context)
            if decision is not None:
                decisions.append(decision)
        return decisions

    # ── Ranking ────────────────────────────────────────────

    def rank(self, decisions: list[MetaDecision]) -> list[MetaDecision]:
        """对决策进行排序。

        排序规则:
          1. 优先级（priority）降序
          2. 同优先级按置信度降序

        Args:
            decisions: 决策列表

        Returns:
            排序后的决策列表
        """
        return sorted(
            decisions,
            key=lambda d: (d.priority, d.confidence),
            reverse=True,
        )

    def rank_by_priority(self, decisions: list[MetaDecision]) -> list[MetaDecision]:
        """按优先级排序。

        Args:
            decisions: 决策列表

        Returns:
            排序后的决策列表
        """
        return sorted(
            decisions,
            key=lambda d: get_decision_priority(d.action),
            reverse=True,
        )

    def get_top_decisions(
        self,
        decisions: list[MetaDecision],
        n: int = 3,
    ) -> list[MetaDecision]:
        """获取 Top N 决策。

        Args:
            decisions: 决策列表
            n:         数量

        Returns:
            Top N 决策
        """
        ranked = self.rank(decisions)
        return ranked[:n]

    # ── Risk Check ─────────────────────────────────────────

    def _risk_check(self, decisions: list[MetaDecision]) -> list[MetaDecision]:
        """风险检查 —— 过滤不可靠的决策。

        Args:
            decisions: 决策列表

        Returns:
            过滤后的决策列表
        """
        filtered = [
            d for d in decisions
            if d.confidence >= self.RISK_CONFIDENCE_MIN
        ]
        if not filtered:
            return decisions  # 保留所有决策而不是清空
        return filtered

    def is_decision_safe(self, decision: MetaDecision) -> bool:
        """判断决策是否安全。

        Args:
            decision: MetaDecision

        Returns:
            True if safe
        """
        if decision.is_risky and decision.confidence < 0.70:
            return False
        return decision.confidence >= self.RISK_CONFIDENCE_MIN

    # ── Confidence Calibration ─────────────────────────────

    def calibrate_confidence(
        self,
        decision: MetaDecision,
        context: DecisionContext,
    ) -> MetaDecision:
        """校准决策置信度。

        基于上下文数据丰富度调整置信度。

        Args:
            decision: MetaDecision
            context:  DecisionContext

        Returns:
            校准后的 MetaDecision
        """
        # 数据丰富度因子
        data_richness = 0.0
        if context.spend_last_7d > 0:
            data_richness += 0.2
        if context.active_experiments > 0:
            data_richness += 0.2
        if context.mutation_count > 5:
            data_richness += 0.2
        if context.knowledge_confidence > 0.60:
            data_richness += 0.2
        if context.prediction_confidence > 0.60:
            data_richness += 0.2

        # 校准: 数据少时降权
        calibrated = decision.confidence * (0.5 + data_richness * 0.5)
        decision.confidence = round(min(calibrated, 1.0), 4)

        return decision

    def __repr__(self) -> str:
        return f"MetaDecisionEngine(policies={len(self.policies)})"