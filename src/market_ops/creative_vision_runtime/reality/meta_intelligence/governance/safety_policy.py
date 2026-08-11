"""E12.6.3 — Safety Policy。

治理规则层。

5 条安全策略:
  - HighMutationPolicy:     高突变 → MODIFY（限制 mutation_distance < 0.3）
  - LargeSpendPolicy:       大额 + 低置信度 → BLOCK
  - InsufficientDataPolicy: 数据不足 → REQUIRE_REVIEW
  - WinnerProtectionPolicy: winner 相似度低 → BLOCK
  - PopulationCollapsePolicy: 多样性低 → ROLLBACK
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    SafetyAction,
    SafetyContext,
    SafetyDecision,
    RiskLevel,
    RiskReport,
)


class SafetyPolicy(ABC):
    """安全策略基类。"""

    name: str = "base"
    priority: int = 0

    def evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        """评估安全上下文，返回安全决策。

        Returns:
            SafetyDecision 或 None（不触发）
        """
        return self._evaluate(context, risk_report)

    @abstractmethod
    def _evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ── HighMutationPolicy ──────────────────────────────────────


class HighMutationPolicy(SafetyPolicy):
    """高风险突变策略。

    条件:
      - mutation_distance > 0.7

    动作:
      - MODIFY: 限制 mutation_distance < 0.3
    """

    name = "high_mutation"
    priority = 70

    DISTANCE_THRESHOLD = 0.70
    RESTRICTED_DISTANCE = 0.30

    def _evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        if context.mutation_distance <= self.DISTANCE_THRESHOLD:
            return None

        return SafetyDecision(
            product_id=context.product_id,
            action=SafetyAction.MODIFY,
            risk_level=RiskLevel.HIGH,
            score=context.mutation_distance,
            reasons=[
                f"Mutation distance ({context.mutation_distance:.2f}) exceeds safe threshold ({self.DISTANCE_THRESHOLD})",
                f"Restricting mutation to max {self.RESTRICTED_DISTANCE}",
            ],
            constraints={
                "max_mutation_distance": self.RESTRICTED_DISTANCE,
                "original_mutation_distance": context.mutation_distance,
            },
        )


# ── LargeSpendPolicy ────────────────────────────────────────


class LargeSpendPolicy(SafetyPolicy):
    """大额花费策略。

    条件:
      - spend_amount > $5000
      - confidence < 0.8

    动作:
      - BLOCK
    """

    name = "large_spend"
    priority = 80

    SPEND_THRESHOLD = 5000.0
    CONFIDENCE_THRESHOLD = 0.80

    def _evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        if context.spend_amount <= self.SPEND_THRESHOLD:
            return None
        if context.confidence >= self.CONFIDENCE_THRESHOLD:
            return None

        return SafetyDecision(
            product_id=context.product_id,
            action=SafetyAction.BLOCK,
            risk_level=RiskLevel.HIGH,
            score=min(1.0, context.spend_amount / 10000.0),
            reasons=[
                f"Large spend (${context.spend_amount:.0f}) with low confidence ({context.confidence:.2f})",
                f"Confidence must be >= {self.CONFIDENCE_THRESHOLD} for spends > ${self.SPEND_THRESHOLD:.0f}",
            ],
            constraints={
                "max_spend": self.SPEND_THRESHOLD,
                "required_confidence": self.CONFIDENCE_THRESHOLD,
            },
        )


# ── InsufficientDataPolicy ──────────────────────────────────


class InsufficientDataPolicy(SafetyPolicy):
    """数据不足策略。

    条件:
      - experiment_count < 3

    动作:
      - REQUIRE_REVIEW
    """

    name = "insufficient_data"
    priority = 40

    MIN_EXPERIMENTS = 3

    def _evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        if context.experiment_count >= self.MIN_EXPERIMENTS:
            return None

        return SafetyDecision(
            product_id=context.product_id,
            action=SafetyAction.REQUIRE_REVIEW,
            risk_level=RiskLevel.MEDIUM,
            score=0.40,
            reasons=[
                f"Insufficient experiment data: only {context.experiment_count} experiments "
                f"(minimum {self.MIN_EXPERIMENTS} required)",
                "Requires human review before proceeding",
            ],
            constraints={
                "min_experiments": self.MIN_EXPERIMENTS,
                "current_experiments": context.experiment_count,
            },
        )


# ── WinnerProtectionPolicy ──────────────────────────────────


class WinnerProtectionPolicy(SafetyPolicy):
    """Winner 保护策略。

    条件:
      - historical_winner_similarity < 0.2

    动作:
      - BLOCK: 防止完全破坏 winner DNA
    """

    name = "winner_protection"
    priority = 90

    SIMILARITY_THRESHOLD = 0.20

    def _evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        if context.historical_winner_similarity >= self.SIMILARITY_THRESHOLD:
            return None

        return SafetyDecision(
            product_id=context.product_id,
            action=SafetyAction.BLOCK,
            risk_level=RiskLevel.HIGH,
            score=1.0 - context.historical_winner_similarity,
            reasons=[
                f"Winner DNA protection: similarity to winner is only "
                f"{context.historical_winner_similarity:.2f} "
                f"(minimum {self.SIMILARITY_THRESHOLD})",
                "Blocking to prevent destruction of historical winner DNA",
            ],
            constraints={
                "min_winner_similarity": self.SIMILARITY_THRESHOLD,
                "current_similarity": context.historical_winner_similarity,
            },
        )


# ── PopulationCollapsePolicy ────────────────────────────────


class PopulationCollapsePolicy(SafetyPolicy):
    """种群崩溃策略。

    条件:
      - population_diversity < 0.15

    动作:
      - ROLLBACK: 回滚到上一个安全状态
    """

    name = "population_collapse"
    priority = 100

    DIVERSITY_THRESHOLD = 0.15

    def _evaluate(
        self,
        context: SafetyContext,
        risk_report: RiskReport | None = None,
    ) -> SafetyDecision | None:
        if context.population_diversity >= self.DIVERSITY_THRESHOLD:
            return None

        return SafetyDecision(
            product_id=context.product_id,
            action=SafetyAction.ROLLBACK,
            risk_level=RiskLevel.CRITICAL,
            score=1.0 - context.population_diversity,
            reasons=[
                f"Population collapse detected: diversity {context.population_diversity:.2f} "
                f"below critical threshold ({self.DIVERSITY_THRESHOLD})",
                "Initiating rollback to previous safe state",
            ],
            constraints={
                "rollback_type": "population",
                "diversity_threshold": self.DIVERSITY_THRESHOLD,
                "current_diversity": context.population_diversity,
            },
        )


# ── Default Policies ────────────────────────────────────────


DEFAULT_SAFETY_POLICIES: list[SafetyPolicy] = [
    PopulationCollapsePolicy(),
    WinnerProtectionPolicy(),
    LargeSpendPolicy(),
    HighMutationPolicy(),
    InsufficientDataPolicy(),
]