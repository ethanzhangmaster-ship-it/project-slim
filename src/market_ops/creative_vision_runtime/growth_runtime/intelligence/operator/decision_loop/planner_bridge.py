"""E15.3.2 Planner Bridge — 连接 Decision Loop 与 E15.2.1 Planner.

将 DecisionCycle 的候选动作转发给 E15.2.1 ExecutionPlanner，
生成结构化的 ExecutionPlan。

流程:
  DecisionCycle
      ↓
  PlannerBridge.generate_actions(cycle, goals, opportunities)
      ↓
  E15.2.1 ExecutionPlanner.create_plan(opportunity)
      ↓
  candidate_actions
"""

from __future__ import annotations

from typing import Any

from .models import (
    DecisionCycle,
    EnvironmentState,
    GoalEvaluation,
    OpportunitySignal,
)


# ═══════════════════════════════════════════════════════════════
# Planner Bridge
# ═══════════════════════════════════════════════════════════════


class PlannerBridge:
    """E15.3.2 Planner 桥接器 — 连接 Decision Loop 与 E15.2.1 Planner.

    将决策周期的目标和机会转换为候选动作列表。

    用法:
        bridge = PlannerBridge(planner)
        actions = bridge.generate_actions(cycle, goals, opportunities)
    """

    def __init__(self, planner: Any = None):
        """初始化.

        Args:
            planner: E15.2.1 ExecutionPlanner 实例 (可选)
        """
        self._planner = planner
        self._generation_count: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def generation_count(self) -> int:
        return self._generation_count

    # ── Core: Generate Actions ──────────────────────────────────

    def generate_actions(
        self,
        cycle: DecisionCycle,
        goal_evaluations: list[GoalEvaluation],
        opportunities: list[OpportunitySignal],
        environment: EnvironmentState | None = None,
    ) -> list[dict[str, Any]]:
        """生成候选动作列表.

        Args:
            cycle:            当前决策周期
            goal_evaluations: 目标评估结果
            opportunities:    发现的机会
            environment:      环境状态

        Returns:
            list[dict]: 候选动作列表
        """
        self._generation_count += 1
        candidates: list[dict[str, Any]] = []

        # 1. 从机会生成动作
        for opp in opportunities:
            action = self._opportunity_to_action(opp)
            if action:
                candidates.append(action)

        # 2. 从目标差距生成动作
        for ge in goal_evaluations:
            if ge.urgency in ("critical", "high"):
                action = self._goal_to_action(ge)
                if action:
                    candidates.append(action)

        # 3. 如果有 Planner，尝试通过 Planner 生成
        if self._planner is not None:
            try:
                planner_actions = self._generate_via_planner(
                    opportunities, goal_evaluations, environment
                )
                candidates.extend(planner_actions)
            except Exception:
                pass  # Planner 失败时降级使用规则生成

        # 4. 总是包含 DoNothing 作为兜底
        candidates.append({
            "action_type": "do_nothing",
            "description": "No action needed",
            "confidence": 0.3,
            "expected_impact": {},
            "source": "fallback",
        })

        return candidates

    def _opportunity_to_action(
        self, opportunity: OpportunitySignal
    ) -> dict[str, Any] | None:
        """将机会转换为动作."""
        type_mapping: dict[str, str] = {
            "SCALE_WINNER_CREATIVE": "increase_budget",
            "INCREASE_BUDGET": "increase_budget",
            "REPLACE_CREATIVE": "replace_creative",
            "CAPITALIZE_TREND": "increase_budget",
            "INVESTIGATE_DECLINE": "investigate_decline",
        }
        action_type = type_mapping.get(opportunity.type, "investigate")

        if action_type == "investigate" and opportunity.type != "INVESTIGATE_DECLINE":
            return None

        return {
            "action_type": action_type,
            "description": opportunity.description,
            "confidence": opportunity.confidence,
            "expected_impact": opportunity.estimated_impact,
            "opportunity_name": opportunity.name,
            "source": "opportunity",
        }

    def _goal_to_action(
        self, evaluation: GoalEvaluation
    ) -> dict[str, Any] | None:
        """将目标评估转换为动作."""
        if evaluation.health.value in ("achieved", "on_track"):
            return None

        goal_action_map: dict[str, str] = {
            "roas": "adjust_budget",
            "ctr": "replace_creative",
            "cvr": "adjust_bid",
            "revenue": "increase_budget",
            "spend": "reduce_budget",
            "payer_rate": "optimize_pricing",
            "retention": "increase_retention",
        }
        action_type = goal_action_map.get(evaluation.metric, "investigate")

        return {
            "action_type": action_type,
            "description": (
                f"Goal '{evaluation.goal_name}' is {evaluation.health.value} "
                f"(gap: {evaluation.gap:.1%})"
            ),
            "confidence": max(0.5, 1.0 - evaluation.gap),
            "expected_impact": {evaluation.metric: -evaluation.gap},
            "goal_id": evaluation.goal_id,
            "source": "goal",
        }

    def _generate_via_planner(
        self,
        opportunities: list[OpportunitySignal],
        goal_evaluations: list[GoalEvaluation],
        environment: EnvironmentState | None,
    ) -> list[dict[str, Any]]:
        """通过 E15.2.1 Planner 生成动作."""
        actions: list[dict[str, Any]] = []

        for opp in opportunities:
            try:
                opportunity_dict = {
                    "type": opp.type,
                    "confidence": opp.confidence,
                    "description": opp.description,
                    "impacted_metrics": opp.impacted_metrics,
                    "estimated_impact": opp.estimated_impact,
                }
                plan = self._planner.create_plan(opportunity_dict)
                if plan and hasattr(plan, "recommended_actions"):
                    for ra in plan.recommended_actions:
                        actions.append({
                            "action_type": getattr(ra, "action_type", "unknown"),
                            "description": getattr(ra, "description", ""),
                            "confidence": getattr(ra, "confidence", opp.confidence),
                            "expected_impact": getattr(ra, "expected_impact", {}),
                            "source": "planner",
                        })
            except Exception:
                continue

        return actions

    # ── Query ───────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "generation_count": self._generation_count,
            "has_planner": self._planner is not None,
        }


__all__ = ["PlannerBridge"]