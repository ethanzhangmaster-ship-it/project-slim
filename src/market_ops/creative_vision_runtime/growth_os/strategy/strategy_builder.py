"""E12.7.3 — Strategy Builder。

策略构建器 —— 从假设和目标生成完整策略。

职责:
  1. 接收 GrowthHypothesis + StrategyObjective
  2. 选择策略模板
  3. 填充策略骨架
  4. 输出 GrowthStrategy
"""

from __future__ import annotations

from typing import Any

from ..agent.models import GrowthHypothesis
from .models import (
    GrowthStrategy,
    RiskLevel,
    StrategyObjective,
    StrategyStatus,
    StrategyTemplateType,
)


# 策略模板定义
# 格式: {
#   template_type: {
#     conditions, base_impact, base_confidence, risk_level, risk_score,
#     duration, description_template, action_types
#   }
# }
_STRATEGY_TEMPLATES: dict[StrategyTemplateType, dict[str, Any]] = {
    StrategyTemplateType.RECOVERY: {
        "conditions": {
            "root_cause_categories": [
                "creative_fatigue", "roas_decline", "roas_critical",
                "ctr_decline", "combined_fatigue_roas",
            ],
        },
        "base_impact": 0.70,
        "base_confidence": 0.75,
        "risk_level": RiskLevel.MEDIUM,
        "risk_score": 0.40,
        "duration_days": 14,
        "description_template": "Recovery strategy for {product}: {objective}",
        "action_types": [
            "decrease_budget",
            "refresh_creative",
            "mutate_dna",
            "launch_experiment",
            "evaluate_experiment",
        ],
    },
    StrategyTemplateType.SCALE: {
        "conditions": {
            "root_cause_categories": ["scale"],
        },
        "base_impact": 0.65,
        "base_confidence": 0.70,
        "risk_level": RiskLevel.MEDIUM,
        "risk_score": 0.50,
        "duration_days": 21,
        "description_template": "Scale strategy for {product}: {objective}",
        "action_types": [
            "increase_budget",
            "create_creative",
            "expand_audience",
            "launch_experiment",
        ],
    },
    StrategyTemplateType.EXPLORATION: {
        "conditions": {
            "root_cause_categories": [
                "creative_diversity_low", "winner_scarcity",
                "cpi_inflation", "high_competition",
            ],
        },
        "base_impact": 0.50,
        "base_confidence": 0.60,
        "risk_level": RiskLevel.MEDIUM,
        "risk_score": 0.55,
        "duration_days": 14,
        "description_template": "Exploration strategy for {product}: {objective}",
        "action_types": [
            "mutate_dna",
            "create_creative",
            "launch_experiment",
            "expand_audience",
        ],
    },
    StrategyTemplateType.MAINTAIN: {
        "conditions": {
            "root_cause_categories": [],
        },
        "base_impact": 0.30,
        "base_confidence": 0.80,
        "risk_level": RiskLevel.LOW,
        "risk_score": 0.20,
        "duration_days": 7,
        "description_template": "Maintain strategy for {product}: {objective}",
        "action_types": [
            "reallocate_budget",
            "evaluate_experiment",
        ],
    },
    StrategyTemplateType.SUNSET: {
        "conditions": {
            "root_cause_categories": ["market_decline"],
        },
        "base_impact": 0.20,
        "base_confidence": 0.75,
        "risk_level": RiskLevel.LOW,
        "risk_score": 0.15,
        "duration_days": 30,
        "description_template": "Sunset strategy for {product}: {objective}",
        "action_types": [
            "decrease_budget",
            "sunset_product",
        ],
    },
}


class StrategyBuilder:
    """策略构建器。

    从假设和目标构建完整增长策略。
    """

    def __init__(self) -> None:
        self._templates = dict(_STRATEGY_TEMPLATES)

    def build(
        self,
        hypothesis: GrowthHypothesis,
        objective: StrategyObjective,
        template_type: StrategyTemplateType | None = None,
        custom_actions: list[str] | None = None,
    ) -> GrowthStrategy:
        """构建增长策略。

        Args:
            hypothesis:   增长假设
            objective:    增长目标
            template_type: 策略模板类型（None 则自动选择）
            custom_actions: 自定义动作类型列表

        Returns:
            GrowthStrategy
        """
        # 选择模板
        if template_type is None:
            template_type = self._select_template(hypothesis)
        template = self._templates.get(template_type, self._templates[StrategyTemplateType.MAINTAIN])

        # 调整参数
        expected_impact = self._estimate_impact(
            template["base_impact"], hypothesis.confidence, hypothesis.expected_impact
        )
        confidence = min(1.0, template["base_confidence"] * hypothesis.confidence)
        action_types = custom_actions or template["action_types"]

        description = template["description_template"].format(
            product=objective.product_id,
            objective=objective.description,
        )

        strategy = GrowthStrategy(
            product_id=hypothesis.metadata.get("product_id", ""),
            objective=objective,
            template_type=template_type,
            hypothesis_id=hypothesis.hypothesis_id,
            expected_impact=round(expected_impact, 4),
            confidence=round(confidence, 4),
            risk_level=template["risk_level"],
            risk_score=template["risk_score"],
            duration_days=template["duration_days"],
            status=StrategyStatus.DRAFT,
            description=description,
        )

        return strategy

    def build_from_hypotheses(
        self,
        hypotheses: list[GrowthHypothesis],
        objectives: list[StrategyObjective],
        product_id: str = "",
    ) -> list[GrowthStrategy]:
        """从多个假设和目标构建策略列表。

        Args:
            hypotheses: 假设列表
            objectives: 目标列表
            product_id: 产品 ID

        Returns:
            策略列表
        """
        strategies: list[GrowthStrategy] = []
        objective_map = {o.objective_id: o for o in objectives}

        for h in hypotheses:
            # 优先匹配同产品的目标
            matching = [
                o for o in objectives
                if o.product_id == product_id or o.product_id == ""
            ]
            if matching:
                strategy = self.build(h, matching[0])
                strategies.append(strategy)

        return strategies

    def _select_template(
        self, hypothesis: GrowthHypothesis
    ) -> StrategyTemplateType:
        """根据假设自动选择模板。

        Args:
            hypothesis: 增长假设

        Returns:
            StrategyTemplateType
        """
        category = hypothesis.root_cause_category

        for template_type, template in self._templates.items():
            if category in template["conditions"]["root_cause_categories"]:
                return template_type

        return StrategyTemplateType.MAINTAIN

    def _estimate_impact(
        self,
        base_impact: float,
        hypothesis_confidence: float,
        hypothesis_impact: float,
    ) -> float:
        """估算策略预期影响。

        公式: base_impact × 0.4 + hypothesis_confidence × hypothesis_impact × 0.6
        """
        return min(1.0, base_impact * 0.4 + hypothesis_confidence * hypothesis_impact * 0.6)

    def get_template(self, template_type: StrategyTemplateType) -> dict[str, Any] | None:
        """获取模板定义。"""
        return self._templates.get(template_type)

    def add_template(
        self,
        template_type: StrategyTemplateType,
        template: dict[str, Any],
    ) -> None:
        """添加自定义模板。"""
        self._templates[template_type] = template

    @property
    def template_count(self) -> int:
        return len(self._templates)

    def __repr__(self) -> str:
        return f"StrategyBuilder(templates={self.template_count})"