"""E12.6.3 — Risk Detector。

风险评估引擎。

计算 5 个风险维度并合成总风险评分:

  Risk Score = mutation_risk × 0.30 + spend_risk × 0.25
             + prediction_risk × 0.25 + knowledge_risk × 0.20
"""

from __future__ import annotations

from .models import (
    RiskLevel,
    RiskReport,
    SafetyContext,
    risk_level_from_score,
)


class RiskDetector:
    """风险评估器。

    计算操作的风险评分和等级。
    """

    # 风险权重
    MUTATION_WEIGHT = 0.30
    SPEND_WEIGHT = 0.25
    PREDICTION_WEIGHT = 0.25
    KNOWLEDGE_WEIGHT = 0.20

    def __init__(
        self,
        mutation_weight: float | None = None,
        spend_weight: float | None = None,
        prediction_weight: float | None = None,
        knowledge_weight: float | None = None,
    ) -> None:
        self.mutation_weight = mutation_weight if mutation_weight is not None else self.MUTATION_WEIGHT
        self.spend_weight = spend_weight if spend_weight is not None else self.SPEND_WEIGHT
        self.prediction_weight = prediction_weight if prediction_weight is not None else self.PREDICTION_WEIGHT
        self.knowledge_weight = knowledge_weight if knowledge_weight is not None else self.KNOWLEDGE_WEIGHT

    def evaluate(self, context: SafetyContext) -> RiskReport:
        """评估风险。

        Args:
            context: 安全评估上下文

        Returns:
            RiskReport 包含所有风险维度评分
        """
        mutation_risk = self._calc_mutation_risk(context)
        spend_risk = self._calc_spend_risk(context)
        prediction_risk = self._calc_prediction_risk(context)
        knowledge_risk = self._calc_knowledge_risk(context)
        diversity_risk = self._calc_diversity_risk(context)

        total_score = self._calc_total_score(
            mutation_risk, spend_risk, prediction_risk, knowledge_risk
        )
        risk_level = risk_level_from_score(total_score)

        details = self._build_details(
            context, mutation_risk, spend_risk, prediction_risk,
            knowledge_risk, diversity_risk, total_score,
        )

        return RiskReport(
            product_id=context.product_id,
            total_score=round(total_score, 4),
            risk_level=risk_level,
            mutation_risk=round(mutation_risk, 4),
            spend_risk=round(spend_risk, 4),
            prediction_risk=round(prediction_risk, 4),
            knowledge_risk=round(knowledge_risk, 4),
            diversity_risk=round(diversity_risk, 4),
            details=details,
        )

    def _calc_mutation_risk(self, context: SafetyContext) -> float:
        """计算突变风险。

        公式: mutation_risk = min(mutation_distance / max_mutation_distance, 1.0)

        高突变距离 → 高风险（新 DNA 远离历史 winner）
        """
        if context.max_mutation_distance <= 0:
            return 1.0 if context.mutation_distance > 0 else 0.0
        return max(0.0, min(1.0, context.mutation_distance / context.max_mutation_distance))

    def _calc_spend_risk(self, context: SafetyContext) -> float:
        """计算花费风险。

        公式: spend_risk = min(spend_amount / daily_budget_limit, 1.0)

        高花费 → 高风险
        """
        if context.daily_budget_limit <= 0:
            return 1.0 if context.spend_amount > 0 else 0.0
        return max(0.0, min(1.0, context.spend_amount / context.daily_budget_limit))

    def _calc_prediction_risk(self, context: SafetyContext) -> float:
        """计算预测风险。

        公式: prediction_risk = 1 - confidence

        低置信度 → 高风险
        """
        return max(0.0, min(1.0, 1.0 - context.confidence))

    def _calc_knowledge_risk(self, context: SafetyContext) -> float:
        """计算知识风险。

        公式: knowledge_risk = 1 - knowledge_confidence

        低知识置信度 → 高风险
        """
        return max(0.0, min(1.0, 1.0 - context.knowledge_confidence))

    def _calc_diversity_risk(self, context: SafetyContext) -> float:
        """计算多样性风险。

        公式: diversity_risk = 1 - population_diversity

        低多样性 → 高风险（种群崩溃）
        """
        return max(0.0, min(1.0, 1.0 - context.population_diversity))

    def _calc_total_score(
        self,
        mutation_risk: float,
        spend_risk: float,
        prediction_risk: float,
        knowledge_risk: float,
    ) -> float:
        """计算总风险评分。

        公式:
          total = mutation × 0.30 + spend × 0.25
                + prediction × 0.25 + knowledge × 0.20
        """
        score = (
            mutation_risk * self.mutation_weight
            + spend_risk * self.spend_weight
            + prediction_risk * self.prediction_weight
            + knowledge_risk * self.knowledge_weight
        )
        return max(0.0, min(1.0, score))

    def _build_details(
        self,
        context: SafetyContext,
        mutation_risk: float,
        spend_risk: float,
        prediction_risk: float,
        knowledge_risk: float,
        diversity_risk: float,
        total_score: float,
    ) -> list[str]:
        """构建风险详情。"""
        details: list[str] = []

        if mutation_risk >= 0.70:
            details.append(
                f"High mutation risk ({mutation_risk:.2f}): "
                f"mutation distance {context.mutation_distance:.2f} "
                f"exceeds safe threshold"
            )
        elif mutation_risk >= 0.40:
            details.append(
                f"Medium mutation risk ({mutation_risk:.2f}): "
                f"mutation distance {context.mutation_distance:.2f}"
            )

        if spend_risk >= 0.70:
            details.append(
                f"High spend risk ({spend_risk:.2f}): "
                f"spend ${context.spend_amount:.0f} / "
                f"limit ${context.daily_budget_limit:.0f}"
            )
        elif spend_risk >= 0.40:
            details.append(
                f"Medium spend risk ({spend_risk:.2f}): "
                f"spend ${context.spend_amount:.0f}"
            )

        if prediction_risk >= 0.70:
            details.append(
                f"High prediction risk ({prediction_risk:.2f}): "
                f"confidence {context.confidence:.2f} is low"
            )

        if knowledge_risk >= 0.70:
            details.append(
                f"High knowledge risk ({knowledge_risk:.2f}): "
                f"knowledge confidence {context.knowledge_confidence:.2f} is low"
            )

        if diversity_risk >= 0.80:
            details.append(
                f"Critical diversity risk ({diversity_risk:.2f}): "
                f"population diversity {context.population_diversity:.2f} — possible collapse"
            )

        if not details:
            details.append(f"Risk within acceptable range (total={total_score:.2f})")

        return details

    def __repr__(self) -> str:
        return (
            f"RiskDetector(mutation={self.mutation_weight:.2f}, "
            f"spend={self.spend_weight:.2f}, "
            f"prediction={self.prediction_weight:.2f}, "
            f"knowledge={self.knowledge_weight:.2f})"
        )