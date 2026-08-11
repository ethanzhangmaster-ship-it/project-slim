"""E15.3.3 Goal Decomposer — 目标分解器.

将高层业务目标拆解为可执行的子目标。

拆解策略:
  ROAS 提升 → CTR 提升 + CPI 降低 + Payer Rate 提升 + Retention 改善
  Revenue 增长 → 用户增长 + ARPU 提升 + 留存改善
  CPI 降低 → 创意优化 + 受众精准化 + 出价优化

用法:
    decomposer = GoalDecomposer()
    subgoals = decomposer.decompose(goal)
"""

from __future__ import annotations

import copy
from typing import Any

from .models import (
    Goal,
    GoalPriority,
    GoalStatus,
    GoalType,
    SubGoal,
    SubGoalStrategy,
)


# ═══════════════════════════════════════════════════════════════
# Decomposition Rules
# ═══════════════════════════════════════════════════════════════

# 指标 → 子目标拆解模板
DECOMPOSITION_RULES: dict[str, list[dict[str, Any]]] = {
    "roas": [
        {"objective": "Improve CTR", "metric": "ctr", "strategy": SubGoalStrategy.CREATIVE_EVOLUTION, "weight": 0.30},
        {"objective": "Reduce CPI", "metric": "cpi", "strategy": SubGoalStrategy.CPI_REDUCTION, "weight": 0.25},
        {"objective": "Improve Payer Conversion", "metric": "payer_rate", "strategy": SubGoalStrategy.MONETIZATION_OPTIMIZATION, "weight": 0.25},
        {"objective": "Improve Retention", "metric": "retention", "strategy": SubGoalStrategy.RETENTION_IMPROVEMENT, "weight": 0.20},
    ],
    "revenue": [
        {"objective": "Increase User Base", "metric": "new_users", "strategy": SubGoalStrategy.AUDIENCE_EXPANSION, "weight": 0.35},
        {"objective": "Improve ARPU", "metric": "arpu", "strategy": SubGoalStrategy.MONETIZATION_OPTIMIZATION, "weight": 0.35},
        {"objective": "Improve Retention", "metric": "retention", "strategy": SubGoalStrategy.RETENTION_IMPROVEMENT, "weight": 0.30},
    ],
    "ctr": [
        {"objective": "Reduce Creative Fatigue", "metric": "fatigue", "strategy": SubGoalStrategy.CREATIVE_EVOLUTION, "weight": 0.40},
        {"objective": "Optimize Audience Targeting", "metric": "ctr", "strategy": SubGoalStrategy.AUDIENCE_EXPANSION, "weight": 0.35},
        {"objective": "A/B Test New Creatives", "metric": "ctr", "strategy": SubGoalStrategy.CREATIVE_EVOLUTION, "weight": 0.25},
    ],
    "cpi": [
        {"objective": "Optimize Bids", "metric": "cpi", "strategy": SubGoalStrategy.BID_OPTIMIZATION, "weight": 0.35},
        {"objective": "Improve Creative Performance", "metric": "ctr", "strategy": SubGoalStrategy.CREATIVE_EVOLUTION, "weight": 0.35},
        {"objective": "Target High-Value Audiences", "metric": "cpi", "strategy": SubGoalStrategy.AUDIENCE_EXPANSION, "weight": 0.30},
    ],
    "payer_rate": [
        {"objective": "Optimize Pricing", "metric": "payer_rate", "strategy": SubGoalStrategy.PRICING_OPTIMIZATION, "weight": 0.40},
        {"objective": "Improve FTUE", "metric": "ftue_completion", "strategy": SubGoalStrategy.RETENTION_IMPROVEMENT, "weight": 0.30},
        {"objective": "Target High-Intent Users", "metric": "payer_rate", "strategy": SubGoalStrategy.AUDIENCE_EXPANSION, "weight": 0.30},
    ],
    "retention": [
        {"objective": "Improve D1 Retention", "metric": "d1_retention", "strategy": SubGoalStrategy.RETENTION_IMPROVEMENT, "weight": 0.40},
        {"objective": "Improve D7 Retention", "metric": "d7_retention", "strategy": SubGoalStrategy.RETENTION_IMPROVEMENT, "weight": 0.35},
        {"objective": "Re-engage Lapsed Users", "metric": "d30_retention", "strategy": SubGoalStrategy.AUDIENCE_EXPANSION, "weight": 0.25},
    ],
    "spend": [
        {"objective": "Reduce Wasted Spend", "metric": "spend", "strategy": SubGoalStrategy.BUDGET_OPTIMIZATION, "weight": 0.45},
        {"objective": "Reallocate to Winners", "metric": "roas", "strategy": SubGoalStrategy.BUDGET_OPTIMIZATION, "weight": 0.30},
        {"objective": "Pause Underperformers", "metric": "spend", "strategy": SubGoalStrategy.BUDGET_OPTIMIZATION, "weight": 0.25},
    ],
}

# 通用回退拆解 (指标无专门规则时使用)
GENERIC_DECOMPOSITION: list[dict[str, Any]] = [
    {"objective": "Optimize Core Metric", "metric": "unknown", "strategy": SubGoalStrategy.CUSTOM, "weight": 0.40},
    {"objective": "Improve Related Performance", "metric": "unknown", "strategy": SubGoalStrategy.CUSTOM, "weight": 0.35},
    {"objective": "Reduce Friction", "metric": "unknown", "strategy": SubGoalStrategy.CUSTOM, "weight": 0.25},
]


# ═══════════════════════════════════════════════════════════════
# Goal Decomposer
# ═══════════════════════════════════════════════════════════════


class GoalDecomposer:
    """E15.3.3 目标分解器 — 将高层目标拆解为子目标.

    根据目标指标和规则库，自动生成子目标列表。

    用法:
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
    """

    def __init__(self, rules: dict[str, list[dict[str, Any]]] | None = None):
        self._rules = copy.deepcopy(rules) if rules else copy.deepcopy(DECOMPOSITION_RULES)
        self._decomposition_count: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def decomposition_count(self) -> int:
        return self._decomposition_count

    # ── Core: Decompose ─────────────────────────────────────────

    def decompose(self, goal: Goal) -> list[SubGoal]:
        """将目标拆解为子目标列表.

        Args:
            goal: 业务目标

        Returns:
            list[SubGoal]: 子目标列表
        """
        self._decomposition_count += 1

        # 获取该指标对应的拆解规则
        rules = self._rules.get(goal.metric.lower(), GENERIC_DECOMPOSITION)

        # 为每个规则生成子目标
        subgoals: list[SubGoal] = []
        for rule in rules:
            sg = self._create_subgoal(goal, rule)
            subgoals.append(sg)

        return subgoals

    def decompose_batch(self, goals: list[Goal]) -> dict[str, list[SubGoal]]:
        """批量拆解.

        Returns:
            dict: goal_id → subgoals
        """
        result: dict[str, list[SubGoal]] = {}
        for goal in goals:
            result[goal.goal_id] = self.decompose(goal)
        return result

    def _create_subgoal(
        self, goal: Goal, rule: dict[str, Any]
    ) -> SubGoal:
        """根据规则创建子目标."""
        weight = float(rule.get("weight", 0.3))
        strategy = rule.get("strategy", SubGoalStrategy.CUSTOM)
        metric = rule.get("metric", goal.metric)
        objective = rule.get("objective", f"Improve {metric}")

        # 根据权重分配目标值
        if goal.direction == "above":
            sub_target = goal.baseline_value + (goal.target_value - goal.baseline_value) * weight
            sub_baseline = goal.baseline_value
        else:
            sub_target = goal.baseline_value - (goal.baseline_value - goal.target_value) * weight
            sub_baseline = goal.baseline_value

        return SubGoal(
            parent_goal_id=goal.goal_id,
            objective=objective,
            metric=metric,
            current_value=goal.current_value,
            target=round(sub_target, 4),
            baseline=round(sub_baseline, 4),
            direction=goal.direction,
            strategy=strategy,
            status=GoalStatus.CREATED,
            priority=goal.priority,
        )

    # ── Custom Rules ────────────────────────────────────────────

    def add_rule(self, metric: str, rules: list[dict[str, Any]]) -> None:
        """添加自定义拆解规则.

        Args:
            metric: 指标名
            rules:  拆解规则列表
        """
        self._rules[metric] = rules

    def remove_rule(self, metric: str) -> bool:
        """移除拆解规则."""
        if metric in self._rules:
            del self._rules[metric]
            return True
        return False

    def get_rules(self) -> dict[str, list[dict[str, Any]]]:
        """获取所有规则."""
        return dict(self._rules)

    def get_supported_metrics(self) -> list[str]:
        """获取支持的指标列表."""
        return list(self._rules.keys())


__all__ = [
    "DECOMPOSITION_RULES",
    "GoalDecomposer",
]