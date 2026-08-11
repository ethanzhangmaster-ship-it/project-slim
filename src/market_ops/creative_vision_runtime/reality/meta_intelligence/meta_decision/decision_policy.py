"""E12.6.1 — Decision Policy。

规则策略层 —— Context → Decision。

决策规则:
  Rule 1 — 高疲劳:            fatigue > 0.8  → START_EXPERIMENT
  Rule 2 — ROAS 增长:          roas_trend > 0.15 → SCALE_WINNER
  Rule 3 — 实验失败:           roas_drop > 30%  → STOP_EXPERIMENT
  Rule 4 — 数据不足:           confidence < 0.5 → WAIT
  Rule 5 — 种群退化:           diversity < 0.2  → START_LEARNING
  Rule 6 — 持续进化:           diversity > 0.3 AND fatigue < 0.6 → CONTINUE_EVOLUTION
  Rule 7 — ROAS 严重下降:      roas_trend < -0.3  → ROLLBACK

每条规则:
  - 输入: DecisionContext
  - 输出: MetaDecision | None (None = 规则不匹配)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import DecisionContext, MetaDecision, MetaDecisionType


class DecisionPolicy(ABC):
    """决策规则基类。"""

    @abstractmethod
    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        """评估规则。

        Args:
            context: 决策上下文

        Returns:
            MetaDecision if matched, None otherwise
        """
        ...

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """规则名称。"""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ── Rule 1: 高疲劳 → START_EXPERIMENT ─────────────────────


class FatigueRule(DecisionPolicy):
    """高疲劳检测规则。

    条件: fatigue_score >= 0.80 AND prediction_confidence >= 0.70
    输出: START_EXPERIMENT
    """

    FATIGUE_THRESHOLD: float = 0.80
    CONFIDENCE_THRESHOLD: float = 0.70

    @property
    def rule_name(self) -> str:
        return "FatigueRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.fatigue_score < self.FATIGUE_THRESHOLD:
            return None
        if context.prediction_confidence < self.CONFIDENCE_THRESHOLD:
            return None

        confidence = min(
            context.fatigue_score * 0.6 + context.prediction_confidence * 0.4,
            1.0,
        )
        expected_impact = (context.fatigue_score - 0.80) * 0.5 + 0.15

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.START_EXPERIMENT,
            confidence=confidence,
            reasons=[
                f"Creative fatigue detected (score={context.fatigue_score:.2f})",
                f"Prediction confidence sufficient ({context.prediction_confidence:.2f})",
                f"Active experiments: {context.active_experiments}",
            ],
            expected_impact=expected_impact,
            context_snapshot=context.to_dict(),
        )


# ── Rule 2: ROAS 增长 → SCALE_WINNER ──────────────────────


class RoasGrowthRule(DecisionPolicy):
    """ROAS 增长检测规则。

    条件: roas_trend > 0.15 AND fatigue_score < 0.40
    输出: SCALE_WINNER
    """

    ROAS_TREND_THRESHOLD: float = 0.15
    FATIGUE_THRESHOLD: float = 0.40

    @property
    def rule_name(self) -> str:
        return "RoasGrowthRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.roas_trend <= self.ROAS_TREND_THRESHOLD:
            return None
        if context.fatigue_score >= self.FATIGUE_THRESHOLD:
            return None

        confidence = min(
            context.roas_trend * 2.0 + context.prediction_confidence * 0.3,
            1.0,
        )
        expected_impact = context.roas_trend * 0.8

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.SCALE_WINNER,
            confidence=confidence,
            reasons=[
                f"ROAS growing (trend={context.roas_trend:+.2f})",
                f"Fatigue low ({context.fatigue_score:.2f})",
                f"Recent ROAS: {context.recent_roas:.2f}",
            ],
            expected_impact=expected_impact,
            context_snapshot=context.to_dict(),
        )


# ── Rule 3: 实验失败 → STOP_EXPERIMENT ────────────────────


class ExperimentFailureRule(DecisionPolicy):
    """实验失败检测规则。

    条件: roas_drop_pct > 0.30 OR (roas_trend < -0.20 AND active_experiments > 0)
    输出: STOP_EXPERIMENT
    """

    ROAS_DROP_THRESHOLD: float = 0.30
    ROAS_TREND_THRESHOLD: float = -0.20

    @property
    def rule_name(self) -> str:
        return "ExperimentFailureRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.active_experiments == 0:
            return None

        drop_severe = context.roas_drop_pct >= self.ROAS_DROP_THRESHOLD
        trend_bad = context.roas_trend < self.ROAS_TREND_THRESHOLD

        if not drop_severe and not trend_bad:
            return None

        if drop_severe:
            confidence = min(context.roas_drop_pct, 1.0)
            reasons = [f"ROAS dropped {context.roas_drop_pct:.0%} (threshold: {self.ROAS_DROP_THRESHOLD:.0%})"]
        else:
            confidence = abs(context.roas_trend) * 3.0
            reasons = [f"ROAS trend declining ({context.roas_trend:+.2f}) with {context.active_experiments} active experiments"]

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.STOP_EXPERIMENT,
            confidence=min(confidence, 1.0),
            reasons=reasons + [
                f"Active experiments: {context.active_experiments}",
                f"Recent ROAS: {context.recent_roas:.2f}",
            ],
            expected_impact=0.0,
            context_snapshot=context.to_dict(),
        )


# ── Rule 4: 数据不足 → WAIT ───────────────────────────────


class InsufficientDataRule(DecisionPolicy):
    """数据不足检测规则。

    条件: prediction_confidence < 0.50
    输出: WAIT
    """

    CONFIDENCE_THRESHOLD: float = 0.50

    @property
    def rule_name(self) -> str:
        return "InsufficientDataRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.prediction_confidence >= self.CONFIDENCE_THRESHOLD:
            return None

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.WAIT,
            confidence=1.0 - context.prediction_confidence,
            reasons=[
                f"Prediction confidence too low ({context.prediction_confidence:.2f} < {self.CONFIDENCE_THRESHOLD:.2f})",
                f"Need more data before making decisions",
            ],
            expected_impact=0.0,
            context_snapshot=context.to_dict(),
        )


# ── Rule 5: 种群退化 → START_LEARNING ─────────────────────


class PopulationDegradationRule(DecisionPolicy):
    """种群退化检测规则。

    条件: population_diversity < 0.20
    输出: START_LEARNING
    """

    DIVERSITY_THRESHOLD: float = 0.20

    @property
    def rule_name(self) -> str:
        return "PopulationDegradationRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.population_diversity >= self.DIVERSITY_THRESHOLD:
            return None

        confidence = 1.0 - context.population_diversity
        expected_impact = (self.DIVERSITY_THRESHOLD - context.population_diversity) * 0.5

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.START_LEARNING,
            confidence=confidence,
            reasons=[
                f"Population diversity critically low ({context.population_diversity:.2f} < {self.DIVERSITY_THRESHOLD:.2f})",
                f"Need to learn new patterns to restore diversity",
            ],
            expected_impact=expected_impact,
            context_snapshot=context.to_dict(),
        )


# ── Rule 6: 持续进化 → CONTINUE_EVOLUTION ─────────────────


class ContinueEvolutionRule(DecisionPolicy):
    """持续进化检测规则。

    条件: diversity > 0.30 AND fatigue < 0.60 AND prediction_confidence >= 0.60
    输出: CONTINUE_EVOLUTION
    """

    DIVERSITY_THRESHOLD: float = 0.30
    FATIGUE_THRESHOLD: float = 0.60
    CONFIDENCE_THRESHOLD: float = 0.60

    @property
    def rule_name(self) -> str:
        return "ContinueEvolutionRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.population_diversity <= self.DIVERSITY_THRESHOLD:
            return None
        if context.fatigue_score >= self.FATIGUE_THRESHOLD:
            return None
        if context.prediction_confidence < self.CONFIDENCE_THRESHOLD:
            return None

        confidence = (
            context.population_diversity * 0.3
            + (1.0 - context.fatigue_score) * 0.3
            + context.prediction_confidence * 0.4
        )

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.CONTINUE_EVOLUTION,
            confidence=confidence,
            reasons=[
                f"Population diversity healthy ({context.population_diversity:.2f})",
                f"Fatigue acceptable ({context.fatigue_score:.2f})",
                f"Prediction confidence sufficient ({context.prediction_confidence:.2f})",
            ],
            expected_impact=0.05,
            context_snapshot=context.to_dict(),
        )


# ── Rule 7: ROAS 严重下降 → ROLLBACK ──────────────────────


class RollbackRule(DecisionPolicy):
    """严重下降回滚规则。

    条件: roas_trend < -0.30 AND recent_roas < 0.80
    输出: ROLLBACK
    """

    ROAS_TREND_THRESHOLD: float = -0.30
    ROAS_THRESHOLD: float = 0.80

    @property
    def rule_name(self) -> str:
        return "RollbackRule"

    def evaluate(self, context: DecisionContext) -> MetaDecision | None:
        if context.roas_trend >= self.ROAS_TREND_THRESHOLD:
            return None
        if context.recent_roas >= self.ROAS_THRESHOLD:
            return None

        confidence = min(abs(context.roas_trend) * 3.0, 1.0)

        return MetaDecision(
            product_id=context.product_id,
            action=MetaDecisionType.ROLLBACK,
            confidence=confidence,
            reasons=[
                f"ROAS critically declining (trend={context.roas_trend:+.2f})",
                f"Recent ROAS below threshold ({context.recent_roas:.2f} < {self.ROAS_THRESHOLD:.2f})",
                f"Recommend rollback to previous stable state",
            ],
            expected_impact=abs(context.roas_trend) * 0.5,
            context_snapshot=context.to_dict(),
        )


# ── Policy Registry ────────────────────────────────────────


DEFAULT_POLICIES: list[DecisionPolicy] = [
    RollbackRule(),           # 最高优先级（在 Engine 中排序）
    ExperimentFailureRule(),
    FatigueRule(),
    PopulationDegradationRule(),
    RoasGrowthRule(),
    ContinueEvolutionRule(),
    InsufficientDataRule(),
]