"""E12.7.3 — Tactic Generator。

战术生成器 —— 将策略拆解为具体可执行动作。

职责:
  1. 接收 GrowthStrategy
  2. 根据模板类型生成具体 StrategyAction 列表
  3. 设置动作优先级和依赖关系
  4. 连接 E11/E12/E12.6 模块
"""

from __future__ import annotations

from typing import Any

from .models import (
    ActionType,
    GrowthStrategy,
    StrategyAction,
    StrategyTemplateType,
)


def _mk_action(
    action_type: ActionType,
    target_module: str,
    priority: int,
    expected_result: str,
    expected_impact: float,
    duration_days: int = 1,
    parameters: dict[str, Any] | None = None,
    dependencies: list[str] | None = None,
) -> StrategyAction:
    return StrategyAction(
        action_type=action_type,
        target_module=target_module,
        priority=priority,
        expected_result=expected_result,
        expected_impact=expected_impact,
        duration_days=duration_days,
        parameters=parameters or {},
        dependencies=dependencies or [],
    )


# 模板 → 动作生成规则
_TEMPLATE_ACTION_RULES: dict[StrategyTemplateType, list[dict[str, Any]]] = {
    StrategyTemplateType.RECOVERY: [
        {
            "action_type": ActionType.DECREASE_BUDGET,
            "target_module": "E12.6.2_ResourceController",
            "priority": 90,
            "expected_result": "Reduce budget by 20% to stop bleeding",
            "expected_impact": 0.30,
            "duration_days": 1,
            "parameters": {"change_pct": -0.20},
        },
        {
            "action_type": ActionType.REFRESH_CREATIVE,
            "target_module": "E11_CreativeEvolution",
            "priority": 85,
            "expected_result": "Generate 50 new creative variants with fresh DNA",
            "expected_impact": 0.50,
            "duration_days": 3,
            "parameters": {"count": 50, "mutation": "freshness"},
        },
        {
            "action_type": ActionType.MUTATE_DNA,
            "target_module": "E11_CreativeEvolution",
            "priority": 80,
            "expected_result": "Mutate top-performing DNA to create new variants",
            "expected_impact": 0.45,
            "duration_days": 2,
            "parameters": {"count": 30, "mutation": "targeted"},
        },
        {
            "action_type": ActionType.LAUNCH_EXPERIMENT,
            "target_module": "E12.4_ExperimentEngine",
            "priority": 75,
            "expected_result": "Launch experiment to test new creatives",
            "expected_impact": 0.40,
            "duration_days": 7,
            "parameters": {"duration_days": 7, "min_impressions": 5000},
        },
        {
            "action_type": ActionType.EVALUATE_EXPERIMENT,
            "target_module": "E12.4_ExperimentEngine",
            "priority": 70,
            "expected_result": "Evaluate experiment results and identify winners",
            "expected_impact": 0.35,
            "duration_days": 1,
            "parameters": {},
        },
    ],
    StrategyTemplateType.SCALE: [
        {
            "action_type": ActionType.INCREASE_BUDGET,
            "target_module": "E12.6.2_ResourceController",
            "priority": 90,
            "expected_result": "Increase budget by 30% to capture growth",
            "expected_impact": 0.40,
            "duration_days": 1,
            "parameters": {"change_pct": 0.30},
        },
        {
            "action_type": ActionType.CREATE_CREATIVE,
            "target_module": "E11_CreativeEvolution",
            "priority": 80,
            "expected_result": "Generate 100 new creatives to support scale",
            "expected_impact": 0.35,
            "duration_days": 3,
            "parameters": {"count": 100, "mutation": "scale"},
        },
        {
            "action_type": ActionType.EXPAND_AUDIENCE,
            "target_module": "E12.6.4_CrossProductIntelligence",
            "priority": 75,
            "expected_result": "Expand to new audience segments",
            "expected_impact": 0.35,
            "duration_days": 2,
            "parameters": {"expansion_factor": 1.5},
        },
        {
            "action_type": ActionType.LAUNCH_EXPERIMENT,
            "target_module": "E12.4_ExperimentEngine",
            "priority": 70,
            "expected_result": "Test new creatives and audiences at scale",
            "expected_impact": 0.30,
            "duration_days": 14,
            "parameters": {"duration_days": 14, "min_impressions": 10000},
        },
    ],
    StrategyTemplateType.EXPLORATION: [
        {
            "action_type": ActionType.MUTATE_DNA,
            "target_module": "E11_CreativeEvolution",
            "priority": 85,
            "expected_result": "Explore new DNA combinations for diversity",
            "expected_impact": 0.35,
            "duration_days": 2,
            "parameters": {"count": 50, "mutation": "exploratory"},
        },
        {
            "action_type": ActionType.CREATE_CREATIVE,
            "target_module": "E11_CreativeEvolution",
            "priority": 80,
            "expected_result": "Generate diverse creative variants",
            "expected_impact": 0.30,
            "duration_days": 3,
            "parameters": {"count": 80, "mutation": "diverse"},
        },
        {
            "action_type": ActionType.LAUNCH_EXPERIMENT,
            "target_module": "E12.4_ExperimentEngine",
            "priority": 75,
            "expected_result": "Launch high-volume experiment for exploration",
            "expected_impact": 0.30,
            "duration_days": 7,
            "parameters": {"duration_days": 7, "min_impressions": 3000},
        },
        {
            "action_type": ActionType.EXPAND_AUDIENCE,
            "target_module": "E12.6.4_CrossProductIntelligence",
            "priority": 65,
            "expected_result": "Test new audience segments",
            "expected_impact": 0.25,
            "duration_days": 2,
            "parameters": {"expansion_factor": 2.0},
        },
    ],
    StrategyTemplateType.MAINTAIN: [
        {
            "action_type": ActionType.REALLOCATE_BUDGET,
            "target_module": "E12.6.2_ResourceController",
            "priority": 60,
            "expected_result": "Fine-tune budget allocation for efficiency",
            "expected_impact": 0.15,
            "duration_days": 1,
            "parameters": {"optimization": "efficiency"},
        },
        {
            "action_type": ActionType.EVALUATE_EXPERIMENT,
            "target_module": "E12.4_ExperimentEngine",
            "priority": 55,
            "expected_result": "Monitor ongoing experiments",
            "expected_impact": 0.10,
            "duration_days": 1,
            "parameters": {},
        },
    ],
    StrategyTemplateType.SUNSET: [
        {
            "action_type": ActionType.DECREASE_BUDGET,
            "target_module": "E12.6.2_ResourceController",
            "priority": 85,
            "expected_result": "Gradually decrease budget to zero",
            "expected_impact": 0.20,
            "duration_days": 7,
            "parameters": {"change_pct": -0.50, "phased": True},
        },
        {
            "action_type": ActionType.SUNSET_PRODUCT,
            "target_module": "E12.6.5_PortfolioOptimizer",
            "priority": 80,
            "expected_result": "Retire product from active portfolio",
            "expected_impact": 0.15,
            "duration_days": 21,
            "parameters": {"phase": "sunset"},
        },
    ],
}


class TacticGenerator:
    """战术生成器。

    将策略拆解为具体可执行动作。
    """

    def __init__(self) -> None:
        self._rules = dict(_TEMPLATE_ACTION_RULES)

    def generate(self, strategy: GrowthStrategy) -> list[StrategyAction]:
        """为策略生成战术动作。

        Args:
            strategy: 增长策略

        Returns:
            StrategyAction 列表
        """
        rules = self._rules.get(strategy.template_type, [])
        actions: list[StrategyAction] = []

        for rule in rules:
            # 调整优先级（基于策略置信度）
            priority = min(100, rule["priority"] + int(strategy.confidence * 10))

            action = StrategyAction(
                action_type=rule["action_type"],
                target_module=rule["target_module"],
                priority=priority,
                expected_result=rule["expected_result"],
                expected_impact=round(
                    rule["expected_impact"] * strategy.confidence, 4
                ),
                duration_days=rule["duration_days"],
                parameters=dict(rule["parameters"]),
            )
            actions.append(action)

        # 设置依赖关系（前一个动作完成后才能开始下一个）
        for i in range(1, len(actions)):
            actions[i].dependencies = [actions[i - 1].action_id]

        return actions

    def generate_and_attach(self, strategy: GrowthStrategy) -> GrowthStrategy:
        """生成战术并附加到策略。

        Args:
            strategy: 增长策略

        Returns:
            更新后的策略（含动作列表）
        """
        actions = self.generate(strategy)
        strategy.actions = actions
        return strategy

    def add_rules(
        self,
        template_type: StrategyTemplateType,
        rules: list[dict[str, Any]],
    ) -> None:
        """添加自定义模板的战术规则。"""
        self._rules[template_type] = rules

    def get_rules(
        self, template_type: StrategyTemplateType
    ) -> list[dict[str, Any]] | None:
        """获取模板的战术规则。"""
        return self._rules.get(template_type)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"TacticGenerator(templates={self.rule_count})"