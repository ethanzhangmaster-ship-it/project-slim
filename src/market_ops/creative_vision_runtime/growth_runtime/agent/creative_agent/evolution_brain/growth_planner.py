"""E14.8.4 Growth Planner — 增长规划器.

E14.8 Autonomous Growth Agent 第四层:
  将 Goal + GrowthState + Strategy 整合为可执行的 GrowthPlan.

输入: GrowthGoal, GrowthState, StrategyMatch[]
输出: GrowthPlan (含 GrowthAction 列表)

核心模型:
  - GrowthPlan: 增长执行计划
  - PlanStep: 计划步骤
  - GrowthPlanner: 规划器
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
    GrowthAction,
    GrowthActionType,
    ActionPriority,
    ActionSource,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
    GrowthStrategyPattern,
    StrategyStep,
)


# ═══════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════

@dataclass
class PlanStep:
    """计划步骤 — 计划中的一个执行步骤.

    Attributes:
        order: 执行顺序
        action_type: 动作类型
        description: 步骤描述
        expected_impact: 预期影响
        action_params: 动作参数
        approval_level: 审批级别
    """
    order: int = 1
    action_type: str = ""
    description: str = ""
    expected_impact: str = ""
    action_params: dict[str, Any] = field(default_factory=dict)
    approval_level: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action_type": self.action_type,
            "description": self.description,
            "expected_impact": self.expected_impact,
            "action_params": self.action_params,
            "approval_level": self.approval_level,
        }


@dataclass
class GrowthPlan:
    """增长计划 — Agent 自主决策的完整执行计划.

    Attributes:
        plan_id: 计划 ID
        goal_id: 关联目标 ID
        reasoning: 决策理由
        steps: 执行步骤
        actions: 对应的 GrowthAction 列表
        expected_reward: 预期总奖励
        confidence: 计划置信度
        source_strategy_ids: 来源策略 ID
        risk_level: 风险等级 (low / medium / high)
        requires_approval: 是否需要人工审批
        created_at: 创建时间
        metadata: 扩展元数据
    """
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    goal_id: str = ""
    reasoning: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    actions: list[GrowthAction] = field(default_factory=list)
    expected_reward: float = 0.0
    confidence: float = 0.0
    source_strategy_ids: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    requires_approval: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def add_step(self, step: PlanStep) -> None:
        self.steps.append(step)

    def add_action(self, action: GrowthAction) -> None:
        self.actions.append(action)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "reasoning": self.reasoning,
            "steps": [s.to_dict() for s in self.steps],
            "actions": [a.to_dict() for a in self.actions],
            "expected_reward": self.expected_reward,
            "confidence": self.confidence,
            "source_strategy_ids": self.source_strategy_ids,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "action_count": self.action_count,
            "step_count": self.step_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════
# GrowthPlanner
# ═══════════════════════════════════════════════════════════

class GrowthPlanner:
    """增长规划器 — 将目标、状态、策略整合为可执行计划.

    用法:
        planner = GrowthPlanner()
        plan = planner.plan(goal, state, strategy_matches)
    """

    def __init__(self, max_actions: int = 5):
        self._max_actions = max_actions
        self._plan_count: int = 0

    def plan(
        self,
        goal: Any,         # GrowthGoal
        state: Any,        # GrowthState
        strategy_matches: list[Any] = None,  # list[StrategyMatch]
    ) -> GrowthPlan:
        """生成增长计划.

        Args:
            goal: 当前增长目标
            state: 当前增长状态
            strategy_matches: 策略匹配结果 (可选)

        Returns:
            GrowthPlan: 可执行计划
        """
        self._plan_count += 1
        matches = strategy_matches or []

        plan = GrowthPlan(goal_id=getattr(goal, "goal_id", ""))

        # Step 1: 生成推理理由
        plan.reasoning = self._generate_reasoning(goal, state, matches)

        # Step 2: 从策略匹配中提取步骤
        for match in matches[:2]:  # 最多取前 2 个策略
            strategy = match.strategy if hasattr(match, "strategy") else match
            if isinstance(strategy, GrowthStrategyPattern):
                plan.source_strategy_ids.append(strategy.strategy_id)
                for step in strategy.steps:
                    plan_step = self._convert_strategy_step(step, state)
                    plan.add_step(plan_step)

        # Step 3: 如果没有策略步骤，生成默认步骤
        if not plan.steps:
            default_steps = self._generate_default_steps(state)
            for s in default_steps:
                plan.add_step(s)

        # Step 4: 生成 GrowthAction
        plan.actions = self._generate_actions(plan.steps, goal, state)

        # Step 5: 计算预期奖励
        plan.expected_reward = self._compute_expected_reward(plan, matches, state)

        # Step 6: 计算置信度
        plan.confidence = self._compute_confidence(plan, matches, state)

        # Step 7: 评估风险等级
        plan.risk_level = self._assess_risk(plan, state)

        # Step 8: 判断是否需要审批
        plan.requires_approval = self._needs_approval(plan, state)

        return plan

    def _generate_reasoning(
        self,
        goal: Any,
        state: Any,
        matches: list[Any],
    ) -> str:
        """生成决策理由."""
        parts: list[str] = []

        # 目标信息
        goal_name = getattr(goal, "name", "") or getattr(goal, "metric", "")
        target = getattr(goal, "target_value", 0)
        current = getattr(goal, "current_value", 0)
        if goal_name:
            parts.append(
                f"目标: {goal_name} ({current} → {target})"
            )

        # 状态信息
        primary_opp = getattr(state, "primary_opportunity", "")
        fatigue = getattr(state, "creative_fatigue", 0)
        if primary_opp:
            parts.append(f"状态: {primary_opp}")
        if fatigue > 0.6:
            parts.append(f"创意疲劳度: {fatigue:.0%}")

        # 策略信息
        if matches:
            top = matches[0]
            strat = top.strategy if hasattr(top, "strategy") else top
            name = getattr(strat, "name", "unknown")
            parts.append(f"策略: {name}")

        return "; ".join(parts) if parts else "基于当前状态自主规划"

    def _convert_strategy_step(
        self,
        step: StrategyStep,
        state: Any,
    ) -> PlanStep:
        """将 StrategyStep 转换为 PlanStep."""
        return PlanStep(
            order=step.order,
            action_type=step.action_type,
            description=step.expected_impact,
            expected_impact=step.expected_impact,
            action_params=dict(step.action_params),
            approval_level=step.approval_level,
        )

    def _generate_default_steps(self, state: Any) -> list[PlanStep]:
        """当没有策略时，根据状态生成默认步骤."""
        steps: list[PlanStep] = []
        opportunities = getattr(state, "opportunities", [])
        fatigue = getattr(state, "creative_fatigue", 0)

        order = 1
        if "creative_refresh" in opportunities or fatigue > 0.6:
            steps.append(PlanStep(
                order=order,
                action_type="create_variants",
                description="生成新创意变体以缓解疲劳",
                expected_impact="创意疲劳度降低",
                action_params={"variant_count": 5},
            ))
            order += 1

        if "scale_up" in opportunities or "aggressive_scale" in opportunities:
            steps.append(PlanStep(
                order=order,
                action_type="scale_campaign",
                description="放量高效广告系列",
                expected_impact="ROAS 提升 10-20%",
                action_params={"budget_multiplier": 1.3},
                approval_level="review",
            ))
            order += 1

        if "roas_improvement" in opportunities:
            steps.append(PlanStep(
                order=order,
                action_type="reduce_budget",
                description="降低低效广告预算",
                expected_impact="ROAS 改善",
                action_params={"budget_multiplier": 0.7},
            ))
            order += 1

        if not steps:
            steps.append(PlanStep(
                order=1,
                action_type="hold",
                description="保持现状，等待更多数据",
                expected_impact="维持当前状态",
            ))

        return steps

    def _generate_actions(
        self,
        steps: list[PlanStep],
        goal: Any,
        state: Any,
    ) -> list[GrowthAction]:
        """将 PlanStep 转换为 GrowthAction."""
        actions: list[GrowthAction] = []
        action_type_map = {
            "create_variants": GrowthActionType.CREATE_VARIANTS,
            "scale_campaign": GrowthActionType.SCALE_CAMPAIGN,
            "reduce_budget": GrowthActionType.REDUCE_BUDGET,
            "pause_campaign": GrowthActionType.PAUSE_CAMPAIGN,
            "promote_winner": GrowthActionType.PROMOTE_WINNER,
            "start_experiment": GrowthActionType.START_EXPERIMENT,
            "diversify_population": GrowthActionType.DIVERSIFY_POPULATION,
            "hold": GrowthActionType.HOLD,
        }

        for step in steps[:self._max_actions]:
            action_type = action_type_map.get(step.action_type, GrowthActionType.HOLD)
            priority = self._map_priority(step, state)
            confidence = self._estimate_confidence(step, state)

            action = GrowthAction(
                action_type=action_type,
                source=ActionSource.GROWTH_OPPORTUNITY,
                priority=priority,
                confidence=confidence,
                payload=step.action_params,
                expected_reward=0.1,
                reasoning=step.description,
            )
            actions.append(action)

        return actions

    def _map_priority(self, step: PlanStep, state: Any) -> ActionPriority:
        """映射优先级."""
        if step.approval_level == "manual":
            return ActionPriority.LOW
        fatigue = getattr(state, "creative_fatigue", 0)
        if fatigue > 0.8 and step.action_type in ("create_variants", "pause_campaign"):
            return ActionPriority.HIGH
        if step.action_type in ("reduce_budget", "scale_campaign"):
            return ActionPriority.HIGH
        return ActionPriority.MEDIUM

    def _estimate_confidence(self, step: PlanStep, state: Any) -> float:
        """估算步骤置信度."""
        base = 0.6
        if step.approval_level == "auto":
            base += 0.1
        if step.action_type == "hold":
            return 0.95
        return min(base, 0.95)

    def _compute_expected_reward(
        self,
        plan: GrowthPlan,
        matches: list[Any],
        state: Any,
    ) -> float:
        """计算预期总奖励."""
        if not matches:
            return round(0.1 * len(plan.actions), 4)

        top = matches[0]
        strat = top.strategy if hasattr(top, "strategy") else top
        base_reward = getattr(strat, "score", 0.1)
        step_bonus = min(len(plan.steps) * 0.02, 0.1)
        return round(base_reward + step_bonus, 4)

    def _compute_confidence(
        self,
        plan: GrowthPlan,
        matches: list[Any],
        state: Any,
    ) -> float:
        """计算计划置信度."""
        if not matches:
            return 0.5

        top = matches[0]
        strat = top.strategy if hasattr(top, "strategy") else top
        match_score = getattr(top, "match_score", 0.5)
        strat_confidence = getattr(strat, "confidence", 0.5)

        return round((match_score * 0.5 + strat_confidence * 0.5), 4)

    def _assess_risk(self, plan: GrowthPlan, state: Any) -> str:
        """评估风险等级."""
        fatigue = getattr(state, "creative_fatigue", 0)
        needs_intervention = getattr(state, "needs_intervention", False)

        if needs_intervention or fatigue > 0.85:
            return "high"
        if fatigue > 0.6 or plan.action_count >= 4:
            return "medium"
        return "low"

    def _needs_approval(self, plan: GrowthPlan, state: Any) -> bool:
        """判断是否需要人工审批."""
        if plan.risk_level == "high":
            return True
        if plan.confidence < 0.5:
            return True
        if any(s.action_type in ("reduce_budget", "pause_campaign") for s in plan.steps):
            return True
        return False

    @property
    def plan_count(self) -> int:
        return self._plan_count


def create_growth_planner(max_actions: int = 5) -> GrowthPlanner:
    """创建默认 GrowthPlanner."""
    return GrowthPlanner(max_actions=max_actions)