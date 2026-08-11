"""E15.2.4 Hypothesis Engine — 假设生成引擎.

基于观测数据生成关于「当前为什么发生」的假设。

内置规则:
  - creative_fatigue:   ROAS↓ + CTR↓ + Frequency↑
  - audience_saturation: ROAS↓ + Reach→ 平稳
  - budget_insufficient: ROAS↑ + 预算触顶
  - underperforming_creative: CTR↓ + CVR↓
  - scaling_opportunity:  ROAS↑ + CTR↑ + 预算未满
  - market_shift:        所有指标异常波动
"""

from __future__ import annotations

from typing import Any

from .models import Hypothesis, Observation, ObservationTrend, ReasoningContext


# ═══════════════════════════════════════════════════════════════
# Built-in Hypothesis Rules
# ═══════════════════════════════════════════════════════════════


CREATIVE_FATIGUE_RULE = {
    "name": "creative_fatigue",
    "description": "创意素材出现疲劳信号，用户对同一素材响应下降",
    "conditions": [
        {"metric": "roas", "trend": "down"},
        {"metric": "ctr", "trend": "down"},
        {"metric": "frequency", "trend": "up"},
    ],
    "impact": "high",
    "suggested_action": "replace_creative",
}

AUDIENCE_SATURATION_RULE = {
    "name": "audience_saturation",
    "description": "目标受众已饱和，新增受众获取成本上升",
    "conditions": [
        {"metric": "roas", "trend": "down"},
        {"metric": "cpm", "trend": "up"},
        {"metric": "frequency", "trend": "up"},
    ],
    "impact": "high",
    "suggested_action": "expand_audience",
}

BUDGET_INSUFFICIENT_RULE = {
    "name": "budget_insufficient",
    "description": "预算不足，限制广告投放量",
    "conditions": [
        {"metric": "roas", "trend": "up"},
        {"metric": "spend", "trend": "stable"},
    ],
    "impact": "medium",
    "suggested_action": "increase_budget",
}

UNDERPERFORMING_CREATIVE_RULE = {
    "name": "underperforming_creative",
    "description": "创意素材表现不佳",
    "conditions": [
        {"metric": "ctr", "trend": "down"},
        {"metric": "cvr", "trend": "down"},
    ],
    "impact": "medium",
    "suggested_action": "pause_campaign",
}

SCALING_OPPORTUNITY_RULE = {
    "name": "scaling_opportunity",
    "description": "存在放量机会，ROAS 和 CTR 同时上升",
    "conditions": [
        {"metric": "roas", "trend": "up"},
        {"metric": "ctr", "trend": "up"},
    ],
    "impact": "high",
    "suggested_action": "scale_budget",
}

MARKET_SHIFT_RULE = {
    "name": "market_shift",
    "description": "市场环境变化导致多个指标异常波动",
    "conditions": [
        {"metric": "roas", "trend": "down"},
        {"metric": "ctr", "trend": "down"},
        {"metric": "cpm", "trend": "up"},
    ],
    "impact": "high",
    "suggested_action": "monitor",
}

DEFAULT_RULES = [
    CREATIVE_FATIGUE_RULE,
    AUDIENCE_SATURATION_RULE,
    BUDGET_INSUFFICIENT_RULE,
    UNDERPERFORMING_CREATIVE_RULE,
    SCALING_OPPORTUNITY_RULE,
    MARKET_SHIFT_RULE,
]


# ═══════════════════════════════════════════════════════════════
# Hypothesis Engine
# ═══════════════════════════════════════════════════════════════


class HypothesisEngine:
    """E15.2.4 假设生成引擎.

    基于观测数据和内置规则，生成关于当前状态的假设。

    用法:
        engine = HypothesisEngine()
        hypotheses = engine.generate(observations)
    """

    def __init__(self, rules: list[dict[str, Any]] | None = None):
        """初始化.

        Args:
            rules: 自定义规则列表 (默认使用内置规则)
        """
        self._rules = rules or DEFAULT_RULES

    def generate(self, observations: list[Observation]) -> list[Hypothesis]:
        """基于观测数据生成假设.

        Args:
            observations: 观测数据列表

        Returns:
            list[Hypothesis]: 按置信度降序排列
        """
        hypotheses: list[Hypothesis] = []
        obs_map = {o.metric: o for o in observations}

        for rule in self._rules:
            hypothesis = self._evaluate_rule(rule, obs_map)
            if hypothesis is not None and hypothesis.confidence > 0:
                hypotheses.append(hypothesis)

        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    def generate_from_context(self, context: ReasoningContext) -> list[Hypothesis]:
        """从推理上下文生成假设.

        Args:
            context: 推理上下文

        Returns:
            list[Hypothesis]
        """
        return self.generate(context.observations)

    def add_rule(self, rule: dict[str, Any]) -> None:
        """添加自定义规则."""
        self._rules.append(rule)

    def get_rules(self) -> list[dict[str, Any]]:
        """获取所有规则."""
        return list(self._rules)

    def _evaluate_rule(
        self, rule: dict[str, Any], obs_map: dict[str, Observation]
    ) -> Hypothesis | None:
        """评估单条规则.

        Args:
            rule:   规则定义
            obs_map: 观测映射

        Returns:
            Hypothesis | None
        """
        conditions = rule.get("conditions", [])
        if not conditions:
            return None

        matched: list[str] = []
        total = len(conditions)

        for cond in conditions:
            obs = obs_map.get(cond["metric"])
            if obs is None:
                continue

            if obs.trend.value == cond["trend"]:
                evidence = (
                    f"{cond['metric']} trend is {cond['trend']} "
                    f"(value: {obs.value}, delta: {obs.delta_pct()}%)"
                )
                matched.append(evidence)

        if not matched:
            return None

        confidence = round(len(matched) / total, 2)

        return Hypothesis(
            name=rule["name"],
            description=rule["description"],
            evidence=matched,
            confidence=confidence,
            impact=rule.get("impact", "medium"),
            suggested_action=rule.get("suggested_action"),
        )


__all__ = [
    "DEFAULT_RULES",
    "CREATIVE_FATIGUE_RULE",
    "AUDIENCE_SATURATION_RULE",
    "BUDGET_INSUFFICIENT_RULE",
    "UNDERPERFORMING_CREATIVE_RULE",
    "SCALING_OPPORTUNITY_RULE",
    "MARKET_SHIFT_RULE",
    "HypothesisEngine",
]