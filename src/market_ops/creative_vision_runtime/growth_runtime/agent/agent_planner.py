"""E13.7.2 Agent Planner — 目标→策略→计划生成.

Agent Planner 将高层目标和洞察转化为可执行的 GrowthPlan:
  - 策略选择: 根据洞察类型匹配最佳策略
  - 动作生成: 将策略展开为具体动作序列
  - 预算估算: 基于风险和历史数据估算预算
  - 风险评估: 评估计划风险等级
  - 计划验证: 确保计划的完整性和可执行性

流程:
  AgentGoal[] + Insight[] → AgentPlanner → GrowthPlan

连接:
  Agent Planner → Agent Core → Execution Engine
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_models import (
    AgentGoal,
    GoalPriority,
    GrowthPlan,
    Insight,
    InsightType,
    PlanStatus,
)


# ═══════════════════════════════════════════════════════════════
# Strategy Templates
# ═══════════════════════════════════════════════════════════════


class StrategyTemplate:
    """策略模板 — 预定义的策略-动作映射.

    Attributes:
        name: 策略名称
        description: 策略描述
        applies_to: 适用洞察类型
        default_actions: 默认动作序列
        default_budget: 默认预算
        default_risk: 默认风险等级
        expected_metrics: 预期指标变化
    """

    def __init__(
        self,
        name: str,
        description: str,
        applies_to: list[InsightType],
        default_actions: list[dict[str, Any]],
        default_budget: float = 0.0,
        default_risk: str = "safe",
        expected_metrics: dict[str, float] | None = None,
    ):
        self.name = name
        self.description = description
        self.applies_to = applies_to
        self.default_actions = default_actions
        self.default_budget = default_budget
        self.default_risk = default_risk
        self.expected_metrics = expected_metrics or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "applies_to": [t.value for t in self.applies_to],
            "default_actions": self.default_actions,
            "default_budget": self.default_budget,
            "default_risk": self.default_risk,
            "expected_metrics": self.expected_metrics,
        }


# ═══════════════════════════════════════════════════════════════
# Built-in Strategy Templates
# ═══════════════════════════════════════════════════════════════

BUILTIN_STRATEGIES: dict[str, StrategyTemplate] = {
    "creative_mutation": StrategyTemplate(
        name="creative_mutation",
        description="素材变异 — 基于赢家素材生成新 DNA 变体",
        applies_to=[InsightType.THREAT, InsightType.OPPORTUNITY],
        default_actions=[
            {"action_type": "MUTATE_CREATIVE", "params": {"variants": 5}, "priority": "high"},
            {"action_type": "UPLOAD_CREATIVE", "params": {}, "priority": "high"},
            {"action_type": "CREATE_CAMPAIGN", "params": {"budget": 500, "daily": True}, "priority": "high"},
            {"action_type": "MONITOR", "params": {"duration_hours": 72}, "priority": "medium"},
        ],
        default_budget=500.0,
        default_risk="low",
        expected_metrics={"ctr": 0.15, "roas_d7": 0.10},
    ),

    "budget_scale": StrategyTemplate(
        name="budget_scale",
        description="预算放大 — 在 ROAS 上升时增加预算",
        applies_to=[InsightType.OPPORTUNITY],
        default_actions=[
            {"action_type": "UPDATE_BUDGET", "params": {"scale_factor": 1.2}, "priority": "high"},
            {"action_type": "MONITOR", "params": {"duration_hours": 48}, "priority": "high"},
        ],
        default_budget=0.0,
        default_risk="medium",
        expected_metrics={"roas": 0.0, "spend": 0.20},
    ),

    "budget_reduce": StrategyTemplate(
        name="budget_reduce",
        description="预算缩减 — 在 ROAS 下降时降低预算",
        applies_to=[InsightType.THREAT],
        default_actions=[
            {"action_type": "UPDATE_BUDGET", "params": {"scale_factor": 0.8}, "priority": "high"},
            {"action_type": "MONITOR", "params": {"duration_hours": 24}, "priority": "high"},
        ],
        default_budget=0.0,
        default_risk="low",
        expected_metrics={"spend": -0.20, "roas": 0.05},
    ),

    "creative_test": StrategyTemplate(
        name="creative_test",
        description="素材测试 — 创建 A/B 测试活动",
        applies_to=[InsightType.OPPORTUNITY, InsightType.PATTERN],
        default_actions=[
            {"action_type": "MUTATE_CREATIVE", "params": {"variants": 3}, "priority": "high"},
            {"action_type": "UPLOAD_CREATIVE", "params": {}, "priority": "high"},
            {"action_type": "CREATE_CAMPAIGN", "params": {"budget": 300, "daily": True, "test_mode": True}, "priority": "high"},
            {"action_type": "MONITOR", "params": {"duration_hours": 48}, "priority": "medium"},
            {"action_type": "COLLECT_RESULT", "params": {}, "priority": "medium"},
        ],
        default_budget=300.0,
        default_risk="low",
        expected_metrics={"ctr": 0.0, "install_rate": 0.0},
    ),

    "pause_underperforming": StrategyTemplate(
        name="pause_underperforming",
        description="暂停低效 — 暂停表现不佳的广告",
        applies_to=[InsightType.THREAT, InsightType.ANOMALY],
        default_actions=[
            {"action_type": "PAUSE_CAMPAIGN", "params": {"reason": "underperforming"}, "priority": "high"},
            {"action_type": "MONITOR", "params": {"duration_hours": 24}, "priority": "medium"},
        ],
        default_budget=0.0,
        default_risk="low",
        expected_metrics={"spend": -1.0, "roas": 0.0},
    ),

    "monitor_only": StrategyTemplate(
        name="monitor_only",
        description="仅监控 — 观察数据变化，暂不执行动作",
        applies_to=[InsightType.ANOMALY, InsightType.CONFIRMATION],
        default_actions=[
            {"action_type": "MONITOR", "params": {"duration_hours": 24}, "priority": "high"},
        ],
        default_budget=0.0,
        default_risk="safe",
        expected_metrics={},
    ),

    "scale_winner": StrategyTemplate(
        name="scale_winner",
        description="放大赢家 — 对高表现素材增加预算和投放",
        applies_to=[InsightType.OPPORTUNITY, InsightType.CONFIRMATION],
        default_actions=[
            {"action_type": "UPDATE_BUDGET", "params": {"scale_factor": 1.5}, "priority": "high"},
            {"action_type": "MUTATE_CREATIVE", "params": {"variants": 3, "based_on_winner": True}, "priority": "high"},
            {"action_type": "UPLOAD_CREATIVE", "params": {}, "priority": "high"},
            {"action_type": "CREATE_CAMPAIGN", "params": {"budget": 1000, "daily": True}, "priority": "high"},
            {"action_type": "MONITOR", "params": {"duration_hours": 72}, "priority": "medium"},
            {"action_type": "COLLECT_RESULT", "params": {}, "priority": "medium"},
        ],
        default_budget=1000.0,
        default_risk="medium",
        expected_metrics={"ctr": 0.05, "roas_d7": 0.15, "spend": 1.0},
    ),
}


# ═══════════════════════════════════════════════════════════════
# Agent Planner
# ═══════════════════════════════════════════════════════════════


class AgentPlanner:
    """Agent 规划器 — 将目标和洞察转化为增长计划.

    职责:
      1. 策略匹配: 根据洞察类型匹配最佳策略模板
      2. 动作生成: 展开策略模板为具体动作序列
      3. 预算估算: 基于风险容忍度和历史数据估算预算
      4. 风险评估: 评估计划风险等级
      5. 计划优化: 调整和优化计划参数

    用法:
        planner = AgentPlanner(risk_tolerance=0.5)
        plan = planner.plan(goal, insights)
    """

    # 风险等级排序
    RISK_ORDER = ["safe", "low", "medium", "high", "critical"]

    def __init__(
        self,
        risk_tolerance: float = 0.5,
        max_budget_per_cycle: float = 5000.0,
        strategies: dict[str, StrategyTemplate] | None = None,
    ):
        self._risk_tolerance = risk_tolerance
        self._max_budget_per_cycle = max_budget_per_cycle
        self._strategies = strategies or BUILTIN_STRATEGIES.copy()
        self._plan_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def plan(
        self,
        goal: AgentGoal,
        insights: list[Insight],
        extra_context: dict[str, Any] | None = None,
    ) -> GrowthPlan:
        """生成增长计划.

        Args:
            goal: 当前目标
            insights: 相关洞察
            extra_context: 额外上下文 (如历史数据、当前指标)

        Returns:
            GrowthPlan: 增长计划
        """
        # 1. 选择策略
        strategy = self._select_strategy(insights)

        # 2. 生成动作
        actions = self._generate_actions(strategy, insights, goal)

        # 3. 估算预算
        budget = self._estimate_budget(strategy, goal, extra_context or {})

        # 4. 评估风险
        risk_level = self._assess_risk(strategy, insights, goal)

        # 5. 生成预期结果
        expected_outcome = self._generate_outcome(strategy, insights, goal)

        # 6. 生成回滚计划
        rollback = self._generate_rollback(actions)

        self._plan_count += 1

        return GrowthPlan(
            goal_id=goal.goal_id,
            title=f"Growth Plan: {goal.title}",
            description=f"Plan for goal '{goal.title}' using strategy '{strategy.name}'",
            strategy=strategy.name,
            actions=actions,
            expected_outcome=expected_outcome,
            expected_metrics=strategy.expected_metrics,
            budget=budget,
            risk_level=risk_level,
            confidence=self._calculate_confidence(strategy, insights),
            status=PlanStatus.DRAFT,
            timeline=self._generate_timeline(actions),
            rollback_plan=rollback,
        )

    def plan_batch(
        self,
        goals: list[AgentGoal],
        insights: list[Insight],
        extra_context: dict[str, Any] | None = None,
    ) -> list[GrowthPlan]:
        """批量生成计划 — 为多个目标生成计划.

        Args:
            goals: 目标列表
            insights: 所有洞察
            extra_context: 额外上下文

        Returns:
            list[GrowthPlan]: 计划列表 (按优先级排序)
        """
        plans = []
        for goal in goals:
            # 筛选与目标相关的洞察
            related_insights = [
                i for i in insights
                if i.suggested_action and goal.title.lower() in i.title.lower()
            ]
            if not related_insights:
                related_insights = insights  # 使用所有洞察

            plan = self.plan(goal, related_insights, extra_context)
            plans.append(plan)

        # 按优先级排序
        priority_order = {GoalPriority.CRITICAL: 0, GoalPriority.HIGH: 1, GoalPriority.MEDIUM: 2, GoalPriority.LOW: 3}
        plans.sort(key=lambda p: (
            priority_order.get(
                next((g.priority for g in goals if g.goal_id == p.goal_id), GoalPriority.MEDIUM),
                2,
            )
        ))

        return plans

    # ── 策略选择 ──────────────────────────────────────────────

    def _select_strategy(self, insights: list[Insight]) -> StrategyTemplate:
        """根据洞察选择最佳策略.

        匹配规则:
          1. 高紧急度威胁 → creative_mutation / budget_reduce
          2. 高置信度机会 → scale_winner / budget_scale
          3. 异常检测 → monitor_only
          4. 模式发现 → creative_test
          5. 默认 → monitor_only
        """
        if not insights:
            return self._strategies["monitor_only"]

        # 按优先级排序洞察
        sorted_insights = sorted(
            insights,
            key=lambda i: (i.urgency * 0.6 + i.confidence * 0.4),
            reverse=True,
        )
        top = sorted_insights[0]

        # 威胁 → 紧急响应
        if top.insight_type == InsightType.THREAT and top.urgency > 0.7:
            sa = top.suggested_action.lower()
            title = top.title.lower()
            if "mutate" in sa or "mutation" in sa or "fatigue" in title or "疲劳" in title:
                return self._strategies["creative_mutation"]
            if "reduce" in sa or "roas" in title:
                return self._strategies["budget_reduce"]
            return self._strategies["pause_underperforming"]

        # 机会 → 放大
        if top.insight_type == InsightType.OPPORTUNITY and top.confidence > 0.7:
            if "winner" in top.title.lower() or "scale" in top.suggested_action.lower():
                return self._strategies["scale_winner"]
            if "scale" in top.suggested_action.lower() or "budget" in top.suggested_action.lower():
                return self._strategies["budget_scale"]
            return self._strategies["creative_test"]

        # 异常 → 监控
        if top.insight_type == InsightType.ANOMALY:
            return self._strategies["monitor_only"]

        # 模式 → 测试
        if top.insight_type == InsightType.PATTERN:
            return self._strategies["creative_test"]

        return self._strategies["monitor_only"]

    # ── 动作生成 ──────────────────────────────────────────────

    def _generate_actions(
        self,
        strategy: StrategyTemplate,
        insights: list[Insight],
        goal: AgentGoal,
    ) -> list[dict[str, Any]]:
        """生成动作序列 — 基于策略模板和洞察定制动作."""
        actions = []

        for i, template in enumerate(strategy.default_actions):
            action = dict(template)  # 复制模板

            # 注入洞察信息
            if insights:
                action["params"] = dict(action.get("params", {}))
                action["params"]["insight_count"] = len(insights)
                action["params"]["top_insight"] = insights[0].insight_id

            # 注入目标信息
            action["params"]["goal_id"] = goal.goal_id

            # 设置顺序
            action["step"] = i + 1

            actions.append(action)

        return actions

    # ── 预算估算 ──────────────────────────────────────────────

    def _estimate_budget(
        self,
        strategy: StrategyTemplate,
        goal: AgentGoal,
        extra_context: dict[str, Any],
    ) -> float:
        """估算预算.

        考虑因素:
          - 策略默认预算
          - 风险容忍度
          - 目标优先级
          - 历史预算上限
        """
        base_budget = strategy.default_budget

        # 风险容忍度调整
        if strategy.default_risk in ["high", "critical"]:
            base_budget *= self._risk_tolerance

        # 优先级调整
        if goal.priority == GoalPriority.CRITICAL:
            base_budget *= 1.3
        elif goal.priority == GoalPriority.LOW:
            base_budget *= 0.5

        # 预算上限
        base_budget = min(base_budget, self._max_budget_per_cycle)

        return round(base_budget, 2)

    # ── 风险评估 ──────────────────────────────────────────────

    def _assess_risk(
        self,
        strategy: StrategyTemplate,
        insights: list[Insight],
        goal: AgentGoal,
    ) -> str:
        """评估计划风险等级.

        风险因素:
          - 策略固有风险
          - 洞察置信度
          - 预算规模
          - 目标优先级
        """
        base_risk = self.RISK_ORDER.index(strategy.default_risk)

        # 置信度低 → 风险升高
        avg_confidence = sum(i.confidence for i in insights) / max(len(insights), 1)
        if avg_confidence < 0.5:
            base_risk += 1
        elif avg_confidence > 0.8:
            base_risk -= 1

        # 高优先级 → 允许更高风险
        if goal.priority == GoalPriority.CRITICAL:
            base_risk -= 1

        # 边界约束
        base_risk = max(0, min(base_risk, len(self.RISK_ORDER) - 1))

        return self.RISK_ORDER[base_risk]

    # ── 置信度计算 ────────────────────────────────────────────

    def _calculate_confidence(
        self,
        strategy: StrategyTemplate,
        insights: list[Insight],
    ) -> float:
        """计算计划置信度.

        基于:
          - 洞察平均置信度 × 0.6
          - 策略匹配度 × 0.4
        """
        if not insights:
            return 0.3

        avg_insight_confidence = sum(i.confidence for i in insights) / len(insights)

        # 策略匹配度: 直接匹配洞察类型的比例
        matching = sum(1 for i in insights if i.insight_type in strategy.applies_to)
        match_rate = matching / len(insights) if insights else 0

        return round(avg_insight_confidence * 0.6 + match_rate * 0.4, 4)

    # ── 结果生成 ──────────────────────────────────────────────

    def _generate_outcome(
        self,
        strategy: StrategyTemplate,
        insights: list[Insight],
        goal: AgentGoal,
    ) -> str:
        """生成预期结果描述."""
        if not insights:
            return f"Execute {strategy.name} strategy for goal: {goal.title}"

        top = insights[0]
        return (
            f"Strategy '{strategy.name}' targets {top.insight_type.value}: "
            f"{top.title}. Expected to {strategy.description}. "
            f"Confidence: {self._calculate_confidence(strategy, insights):.0%}."
        )

    # ── 回滚计划 ──────────────────────────────────────────────

    def _generate_rollback(self, actions: list[dict[str, Any]]) -> str:
        """生成回滚计划."""
        rollback_actions = []
        for action in reversed(actions):
            action_type = action.get("action_type", "")
            if action_type == "CREATE_CAMPAIGN":
                rollback_actions.append("PAUSE campaign")
            elif action_type == "UPDATE_BUDGET":
                rollback_actions.append("REVERT budget to original")
            elif action_type == "MUTATE_CREATIVE":
                rollback_actions.append("ARCHIVE generated creatives")
            elif action_type == "UPLOAD_CREATIVE":
                rollback_actions.append("REMOVE uploaded creatives")

        if rollback_actions:
            return "Rollback sequence: " + " → ".join(rollback_actions)
        return "No rollback needed (read-only operations)"

    # ── 时间线生成 ────────────────────────────────────────────

    def _generate_timeline(self, actions: list[dict[str, Any]]) -> list[dict[str, str]]:
        """生成计划时间线."""
        timeline = []
        current = datetime.now(timezone.utc)

        for i, action in enumerate(actions):
            step_time = current
            timeline.append({
                "step": str(i + 1),
                "action": action.get("action_type", "UNKNOWN"),
                "planned_at": step_time.isoformat(),
            })

        return timeline

    # ── 策略管理 ──────────────────────────────────────────────

    def register_strategy(self, strategy: StrategyTemplate) -> None:
        """注册自定义策略."""
        self._strategies[strategy.name] = strategy

    def get_strategy(self, name: str) -> StrategyTemplate | None:
        """获取策略."""
        return self._strategies.get(name)

    def list_strategies(self) -> list[str]:
        """列出所有策略名称."""
        return list(self._strategies.keys())

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def plan_count(self) -> int:
        return self._plan_count

    @property
    def risk_tolerance(self) -> float:
        return self._risk_tolerance

    def reset(self) -> None:
        self._plan_count = 0