"""E13.3.5 Action Mapper — 机会到决策动作的映射.

核心职责: 将 GrowthOpportunity 映射为 DecisionAction，包含:
  - 动作类型映射
  - 审批级别判定
  - 预算动作创建
  - 优先级排序

输入: GrowthOpportunity[]
输出: DecisionAction[]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    ActionType,
    BudgetAction,
    DecisionAction,
    GrowthInsight,
    GrowthOpportunity,
    OpportunitySeverity,
)


# ═══════════════════════════════════════════════════════════════
# Action Mapper
# ═══════════════════════════════════════════════════════════════


class ActionMapper:
    """E13.3.5 Action Mapper — 将 GrowthOpportunity 映射为 DecisionAction.

    功能:
      1. 按置信度过滤低质量机会
      2. 按动作类型分配审批级别
      3. 创建 BudgetAction (预算相关动作)
      4. 按优先级排序决策
    """

    # 默认阈值
    DEFAULT_THRESHOLDS = {
        "min_confidence": 0.5,           # 最小置信度 (低于此值不生成决策)
        "stop_approval_threshold": 0.9,  # STOP/PAUSE 低于此置信度需审批
        "scale_approval_multiplier": 2.0, # 放量超过此倍数需审批
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._actions: list[DecisionAction] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def thresholds(self) -> dict[str, float]:
        return self._thresholds

    @property
    def action_count(self) -> int:
        return len(self._actions)

    # ── Core Mapping ──────────────────────────────────────────

    def map_opportunities(
        self, opportunities: list[GrowthOpportunity],
    ) -> list[DecisionAction]:
        """将机会列表映射为决策动作列表.

        Args:
            opportunities: 增长机会列表

        Returns:
            list[DecisionAction]: 决策动作列表 (按优先级排序)
        """
        if not opportunities:
            return []

        self._actions = []

        for idx, opp in enumerate(opportunities):
            action = self._map_single(opp, idx)
            if action:
                self._actions.append(action)

        # 排序: 严重程度高 → 低, 置信度高 → 低
        severity_order = {
            OpportunitySeverity.CRITICAL: 0,
            OpportunitySeverity.HIGH: 1,
            OpportunitySeverity.MEDIUM: 2,
            OpportunitySeverity.LOW: 3,
        }
        self._actions.sort(
            key=lambda a: (severity_order.get(a.severity, 99), -a.confidence)
        )

        # 重新分配优先级
        for i, action in enumerate(self._actions):
            action.priority = i

        return self._actions

    def _map_single(
        self, opportunity: GrowthOpportunity, idx: int,
    ) -> DecisionAction | None:
        """映射单个机会为决策动作."""
        # 置信度过滤
        if opportunity.confidence < self._thresholds["min_confidence"]:
            return None

        # 审批级别
        approval_level, requires_approval = self._determine_approval(opportunity)

        # 预算动作
        budget_action = self._create_budget_action(opportunity)

        # 预期影响
        roas_impact = opportunity.expected_impact.get("roas_improvement", 0.0)
        revenue_impact = opportunity.expected_impact.get(
            "revenue_growth",
            opportunity.expected_impact.get("cost_saved", 0.0),
        )

        return DecisionAction(
            action=opportunity.action,
            creative_id=opportunity.creative_id,
            product_id=opportunity.product_id,
            priority=idx,
            confidence=opportunity.confidence,
            severity=opportunity.severity,
            reason=opportunity.reason,
            expected_roas_impact=roas_impact,
            expected_revenue_impact=revenue_impact,
            budget_action=budget_action,
            source_opportunity=opportunity,
            source_insight=opportunity.source_insight,
            requires_approval=requires_approval,
            approval_level=approval_level,
        )

    # ── Approval Logic ────────────────────────────────────────

    def _determine_approval(
        self, opportunity: GrowthOpportunity,
    ) -> tuple[int, bool]:
        """确定审批级别.

        Level 0: 完全自主 (低风险动作)
        Level 1: 需人工确认 (中等风险)
        Level 2: 需人工审批 (高风险)

        Returns:
            (approval_level, requires_approval)
        """
        action = opportunity.action
        confidence = opportunity.confidence

        # Level 2: 高风险动作 (STOP/PAUSE 低置信度 + 大预算变化)
        if action in {ActionType.STOP, ActionType.PAUSE}:
            if confidence < self._thresholds["stop_approval_threshold"]:
                # 大预算 + 低置信度 → Level 2
                if opportunity.current_budget > 500:
                    return (2, True)
                return (1, True)
            # 高置信度 → Level 1
            if opportunity.current_budget > 1000:
                return (1, True)
            return (1, True)

        # Level 1: 放量超过阈值
        if action in {ActionType.SCALE, ActionType.INCREASE_BUDGET}:
            if opportunity.budget_multiplier > self._thresholds["scale_approval_multiplier"]:
                if opportunity.budget_multiplier > 3.0:
                    return (2, True)
                return (1, True)
            return (0, False)

        # Level 0: 变异和其他低风险动作
        if action == ActionType.MUTATE:
            return (0, False)

        if action == ActionType.LAUNCH_EXPERIMENT:
            return (1, True)

        if action in {ActionType.DECREASE_BUDGET, ActionType.REDISTRIBUTE_BUDGET}:
            return (1, True)

        # Default: 低风险
        return (0, False)

    # ── Budget Action Creation ────────────────────────────────

    def _create_budget_action(
        self, opportunity: GrowthOpportunity,
    ) -> BudgetAction | None:
        """为预算相关动作创建 BudgetAction."""
        budget_actions = {
            ActionType.SCALE, ActionType.INCREASE_BUDGET,
            ActionType.DECREASE_BUDGET, ActionType.STOP,
            ActionType.REDISTRIBUTE_BUDGET,
        }

        if opportunity.action not in budget_actions:
            return None

        return BudgetAction(
            creative_id=opportunity.creative_id,
            current_budget=opportunity.current_budget,
            target_budget=opportunity.target_budget,
            budget_delta=opportunity.target_budget - opportunity.current_budget,
            budget_multiplier=opportunity.budget_multiplier,
            action=opportunity.action,
            reason=opportunity.reason,
            confidence=opportunity.confidence,
        )

    # ── Query ─────────────────────────────────────────────────

    def get_autonomous_actions(self) -> list[DecisionAction]:
        """获取可自主执行的动作 (Level 0)."""
        return [a for a in self._actions if a.is_autonomous]

    def get_approval_actions(self) -> list[DecisionAction]:
        """获取需审批的动作."""
        return [a for a in self._actions if not a.is_autonomous]

    def get_actions_by_type(self, action_type: ActionType) -> list[DecisionAction]:
        """按动作类型获取."""
        return [a for a in self._actions if a.action == action_type]

    def get_actions_by_creative(self, creative_id: str) -> list[DecisionAction]:
        """按创意获取."""
        return [a for a in self._actions if a.creative_id == creative_id]

    def get_actions_by_approval_level(self, level: int) -> list[DecisionAction]:
        """按审批级别获取."""
        return [a for a in self._actions if a.approval_level == level]

    def get_all_actions(self) -> list[DecisionAction]:
        return list(self._actions)

    # ── Lifecycle ─────────────────────────────────────────────

    def reset(self) -> None:
        self._actions.clear()

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_actions": self.action_count,
            "autonomous": len(self.get_autonomous_actions()),
            "requires_approval": len(self.get_approval_actions()),
            "by_level": {
                "level_0": len(self.get_actions_by_approval_level(0)),
                "level_1": len(self.get_actions_by_approval_level(1)),
                "level_2": len(self.get_actions_by_approval_level(2)),
            },
            "by_type": {
                a.value: len(self.get_actions_by_type(a))
                for a in ActionType
                if self.get_actions_by_type(a)
            },
        }