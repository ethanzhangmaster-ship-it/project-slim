"""E13.7.1 Agent Core — GrowthAgent 核心.

GrowthAgent 是将整个系统封装为一个自主 Agent 的核心类:
  - 状态机: AgentPhase 生命周期管理
  - 推理循环: Observe → Reason → Plan → Execute → Learn
  - 组件集成: 统一管理 State, Memory, Reasoning, Planner, Tools
  - 会话管理: 支持多会话、多循环

GrowthAgent 是 E13.7 的核心入口，连接:
  State → Memory → Reasoning → Planner → Tools → Execution

用法:
    agent = GrowthAgent(profile=create_growth_agent_profile())
    agent.observe(metrics_data)
    result = agent.run_cycle()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_memory import (
    EpisodicMemory,
    SemanticMemory,
    WorkingMemory,
)
from .agent_models import (
    AgentContext,
    AgentGoal,
    AgentPhase,
    AgentProfile,
    GoalPriority,
    GoalStatus,
    GrowthPlan,
    Insight,
    Observation,
    PlanStatus,
    create_growth_agent_profile,
)
from .agent_planner import AgentPlanner
from .agent_reasoning import ReasoningContext, ReasoningEngine
from .agent_state import AgentStateManager
from .agent_tools import (
    BUILTIN_TOOLS,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    create_default_registry,
)
from .real_tool_registry import upgrade_to_real
from .adapters import (
    AdapterRegistry,
    ToolExecutionContext,
    create_default_adapter_registry,
)


# ═══════════════════════════════════════════════════════════════
# Growth Agent
# ═══════════════════════════════════════════════════════════════


class GrowthAgent:
    """GrowthAgent — 自主增长 Agent.

    将整个系统封装为一个自主 Agent，具备:
      - 观察: 接收环境数据 (指标、事件)
      - 推理: 从观察中生成洞察
      - 规划: 基于洞察生成增长计划
      - 执行: 通过工具系统执行计划
      - 学习: 从结果中更新记忆

    生命周期:
      IDLE → OBSERVING → REASONING → PLANNING → EXECUTING → LEARNING → IDLE

    用法:
        agent = GrowthAgent(profile=create_growth_agent_profile())
        agent.observe({"spend": 17000, "roas": 0.53, "creative_fatigue": 0.81})
        result = agent.run_cycle()
    """

    def __init__(
        self,
        profile: AgentProfile | None = None,
        state_manager: AgentStateManager | None = None,
        working_memory: WorkingMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
        reasoning_engine: ReasoningEngine | None = None,
        planner: AgentPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
        adapter_registry: AdapterRegistry | None = None,
        execution_mode: str = "mock",
    ):
        """初始化 GrowthAgent.

        Args:
            profile: Agent 配置
            state_manager: 状态管理器
            working_memory: 工作记忆
            episodic_memory: 情景记忆
            semantic_memory: 语义记忆
            reasoning_engine: 推理引擎
            planner: 规划器
            tool_registry: 工具注册表 (默认创建 mock 注册表)
            adapter_registry: 适配器注册表 — 传入后自动升级工具注册表为真实 Adapter 调用
            execution_mode: 执行模式 (mock/dry_run/real) — 通过 ToolExecutionContext 传递给 Adapter
        """
        # 配置
        self._profile = profile or create_growth_agent_profile()

        # 状态
        self._state = state_manager or AgentStateManager(profile=self._profile)

        # 记忆
        self._working_memory = working_memory or WorkingMemory()
        self._episodic_memory = episodic_memory or EpisodicMemory()
        self._semantic_memory = semantic_memory or SemanticMemory()

        # 推理
        self._reasoning = reasoning_engine or ReasoningEngine(
            working_memory=self._working_memory,
            episodic_memory=self._episodic_memory,
            semantic_memory=self._semantic_memory,
        )

        # 规划
        self._planner = planner or AgentPlanner(
            risk_tolerance=self._profile.risk_tolerance,
            max_budget_per_cycle=self._profile.max_cycle_budget,
        )

        # 工具
        self._tools = tool_registry or create_default_registry()
        self._adapter_registry = adapter_registry
        self._execution_mode = execution_mode

        # 如果提供了 adapter_registry，升级工具注册表为真实 Adapter 调用
        if adapter_registry is not None:
            adapter_ctx = ToolExecutionContext(execution_mode=execution_mode)
            self._tools = upgrade_to_real(self._tools, adapter_registry, context=adapter_ctx)

        # 日志
        self._log: list[dict[str, Any]] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def phase(self) -> AgentPhase:
        return self._state.phase

    @property
    def profile(self) -> AgentProfile:
        return self._profile

    @property
    def state(self) -> AgentStateManager:
        return self._state

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    # ── 主循环: 完整推理-执行循环 ────────────────────────────

    def run_cycle(
        self,
        metrics: dict[str, Any] | None = None,
        external_goals: list[AgentGoal] | None = None,
    ) -> dict[str, Any]:
        """执行一次完整的 Agent 循环.

        IDLE → OBSERVING → REASONING → PLANNING → EXECUTING → LEARNING → IDLE

        Args:
            metrics: 当前指标数据 (可选)
            external_goals: 外部注入的目标 (可选)

        Returns:
            dict: 循环结果摘要
        """
        cycle_start = datetime.now(timezone.utc)
        self._state.increment_cycle()

        try:
            # 1. 观察
            self._log_phase("observing_start")
            observations = self._observe(metrics)

            # 2. 推理
            self._log_phase("reasoning_start")
            insights = self._reason(observations)

            # 3. 规划
            self._log_phase("planning_start")
            plans = self._plan(insights, external_goals)

            # 4. 执行
            self._log_phase("executing_start")
            results = self._execute(plans)

            # 5. 学习
            self._log_phase("learning_start")
            lessons = self._learn(plans, results, insights)

            duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()

            summary = {
                "cycle": self._state.context.cycle_count,
                "phase": self._state.phase.value,
                "observation_count": len(observations),
                "insight_count": len(insights),
                "plan_count": len(plans),
                "execution_count": len(results),
                "lesson_count": len(lessons),
                "duration_seconds": round(duration, 2),
                "timestamp": cycle_start.isoformat(),
            }

            self._log.append(summary)
            return summary

        except Exception as e:
            self._state.transition(AgentPhase.ERROR)
            return {
                "cycle": self._state.context.cycle_count,
                "phase": "error",
                "error": str(e),
                "duration_seconds": (datetime.now(timezone.utc) - cycle_start).total_seconds(),
                "timestamp": cycle_start.isoformat(),
            }

    # ── 观察阶段 ──────────────────────────────────────────────

    def observe(self, data: dict[str, Any], source: str = "manual") -> list[Observation]:
        """接收外部观察数据.

        Args:
            data: 观察数据
            source: 数据来源

        Returns:
            list[Observation]: 创建的观察对象
        """
        observations = self._observe(data, source)
        return observations

    def _observe(
        self,
        metrics: dict[str, Any] | None = None,
        source: str = "agent_cycle",
    ) -> list[Observation]:
        """观察阶段: 收集环境数据."""
        self._state.transition(AgentPhase.OBSERVING)

        observations = []

        if metrics:
            # 更新指标快照
            self._state.update_metrics(metrics)

            # 创建观察
            significance = self._calculate_significance(metrics)
            summary = self._summarize_metrics(metrics)

            obs = Observation(
                phase=AgentPhase.OBSERVING,
                source=source,
                data=metrics,
                summary=summary,
                significance=significance,
            )
            self._state.add_observation(obs)
            self._working_memory.add_observation(obs)
            observations.append(obs)

        # 从记忆系统收集最近状态
        active_memories = self._working_memory.get_active()
        if active_memories:
            recent = Observation(
                phase=AgentPhase.OBSERVING,
                source="memory",
                data={"active_memories": len(active_memories)},
                summary=self._working_memory.summarize(),
                significance=0.3,
            )
            self._state.add_observation(recent)
            observations.append(recent)

        return observations

    def _calculate_significance(self, metrics: dict[str, Any]) -> float:
        """计算观察的重要性.

        高重要性信号:
          - ROAS 大幅变化
          - 素材疲劳超过阈值
          - 花费异常
        """
        significance = 0.3  # 基础

        roas_change = metrics.get("roas_change", 0)
        if abs(roas_change) > 0.3:
            significance += 0.3

        fatigue = metrics.get("creative_fatigue", 0)
        if fatigue > 0.7:
            significance += 0.3

        spend_change = metrics.get("spend_change", 0)
        if abs(spend_change) > 0.5:
            significance += 0.2

        return min(1.0, significance)

    def _summarize_metrics(self, metrics: dict[str, Any]) -> str:
        """生成指标摘要."""
        parts = []
        if "spend" in metrics:
            parts.append(f"Spend=${metrics['spend']:,.0f}")
        if "roas" in metrics:
            parts.append(f"ROAS={metrics['roas']:.2f}")
        if "roas_change" in metrics:
            parts.append(f"ROAS Δ={metrics['roas_change']:+.0%}")
        if "creative_fatigue" in metrics:
            parts.append(f"Fatigue={metrics['creative_fatigue']:.0%}")
        if "ctr" in metrics:
            parts.append(f"CTR={metrics['ctr']:.1%}")
        return " | ".join(parts) if parts else "No metrics"

    # ── 推理阶段 ──────────────────────────────────────────────

    def reason(self, extra_context: dict[str, Any] | None = None) -> list[Insight]:
        """手动触发推理.

        Args:
            extra_context: 额外上下文

        Returns:
            list[Insight]: 洞察列表
        """
        observations = self._state.get_recent_observations(10)
        return self._reason(observations, extra_context)

    def _reason(
        self,
        observations: list[Observation],
        extra_context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """推理阶段: 从观察中生成洞察."""
        self._state.transition(AgentPhase.REASONING)

        context = ReasoningContext(
            observations=observations,
            working_memory=self._working_memory,
            episodic_memory=self._episodic_memory,
            semantic_memory=self._semantic_memory,
            metrics=self._state.context.metrics_snapshot,
            active_goals=[g.goal_id for g in self._state.active_goals],
            cycle=self._state.context.cycle_count,
        )

        insights = self._reasoning.reason(context)

        # 存储洞察
        for insight in insights:
            self._state.add_insight(insight)
            self._working_memory.add_insight(insight)

        return insights

    # ── 规划阶段 ──────────────────────────────────────────────

    def plan(self, goals: list[AgentGoal] | None = None) -> list[GrowthPlan]:
        """手动触发规划.

        Args:
            goals: 目标列表 (为空则使用当前活动目标)

        Returns:
            list[GrowthPlan]: 计划列表
        """
        insights = self._state.get_recent_insights(20)
        return self._plan(insights, goals)

    def _plan(
        self,
        insights: list[Insight],
        external_goals: list[AgentGoal] | None = None,
    ) -> list[GrowthPlan]:
        """规划阶段: 基于洞察生成计划."""
        self._state.transition(AgentPhase.PLANNING)

        # 确定目标
        goals = external_goals or self._state.active_goals
        if not goals:
            # 从洞察自动生成目标
            goals = self._generate_goals_from_insights(insights)

        if not goals:
            self._log.append({"phase": "planning", "result": "no_goals"})
            return []

        plans = self._planner.plan_batch(
            goals=goals,
            insights=insights,
            extra_context=self._state.context.metrics_snapshot,
        )

        # 存储计划
        for plan in plans:
            self._state.add_plan(plan)

        return plans

    def _generate_goals_from_insights(self, insights: list[Insight]) -> list[AgentGoal]:
        """从洞察自动生成目标."""
        goals = []
        for insight in insights:
            if insight.confidence < 0.5:
                continue

            priority = GoalPriority.MEDIUM
            if insight.urgency > 0.8:
                priority = GoalPriority.CRITICAL
            elif insight.urgency > 0.6:
                priority = GoalPriority.HIGH
            elif insight.urgency < 0.3:
                priority = GoalPriority.LOW

            goal = AgentGoal(
                title=f"Address: {insight.title}",
                description=insight.description,
                priority=priority,
                success_criteria=insight.suggested_action,
                target_metric="resolution",
                target_value=1.0,
            )
            goals.append(goal)
            self._state.add_goal(goal)

        return goals

    # ── 执行阶段 ──────────────────────────────────────────────

    def execute_plan(self, plan: GrowthPlan) -> list[ToolResult]:
        """执行单个计划.

        Args:
            plan: 增长计划

        Returns:
            list[ToolResult]: 执行结果列表
        """
        return self._execute([plan])

    def _execute(self, plans: list[GrowthPlan]) -> list[ToolResult]:
        """执行阶段: 通过工具系统执行计划."""
        self._state.transition(AgentPhase.EXECUTING)

        all_results = []

        for plan in plans:
            if plan.status != PlanStatus.DRAFT:
                continue

            # 标记为执行中
            self._state.update_plan(plan.plan_id, status=PlanStatus.EXECUTING)

            for action in plan.actions:
                action_type = action.get("action_type", "").lower()
                params = action.get("params", {})

                # 检查是否允许执行
                if action_type not in self._profile.allowed_actions:
                    all_results.append(ToolResult(
                        tool_name=action_type,
                        status=ToolResultStatus.BLOCKED,
                        error=f"Action '{action_type}' not in allowed actions",
                    ))
                    continue

                # 检查是否需要审批
                requires_approval = action_type in self._profile.require_approval_for

                # 构建动态执行上下文
                exec_ctx = ToolExecutionContext(
                    session_id=self._state.context.session_id,
                    cycle_number=self._state.context.cycle_count,
                    agent_phase=self._state.phase.value,
                    metrics_snapshot=self._state.context.metrics_snapshot,
                    risk_level=self._calculate_risk_level(),
                    execution_mode=self._execution_mode,
                    require_approval=requires_approval,
                )

                # 执行工具
                if self._tools.has_tool(action_type):
                    result = self._tools.execute(
                        action_type,
                        params,
                        require_approval_check=not requires_approval,
                        execution_context=exec_ctx,
                    )
                else:
                    result = ToolResult(
                        tool_name=action_type,
                        status=ToolResultStatus.FAILED,
                        error=f"No tool registered for '{action_type}'",
                    )

                all_results.append(result)

            # 更新计划状态
            success = all(r.is_success() for r in all_results)
            self._state.update_plan(
                plan.plan_id,
                status=PlanStatus.COMPLETED if success else PlanStatus.FAILED,
            )

        return all_results

    # ── 学习阶段 ──────────────────────────────────────────────

    def _learn(
        self,
        plans: list[GrowthPlan],
        results: list[ToolResult],
        insights: list[Insight],
    ) -> list[str]:
        """学习阶段: 从执行结果中学习."""
        self._state.transition(AgentPhase.LEARNING)

        lessons = []

        # 分析结果
        success_count = sum(1 for r in results if r.is_success())
        fail_count = len(results) - success_count

        if fail_count > 0:
            lesson = f"{fail_count}/{len(results)} actions failed"
            lessons.append(lesson)
            self._semantic_memory.add_knowledge(
                concept="execution_failure",
                description=lesson,
                confidence=0.7,
            )

        # 记录完整情景
        if plans:
            from .agent_memory import Episode

            for plan in plans:
                plan_results = [
                    r.to_dict() for r in results
                    if r.tool_name in [a.get("action_type", "").lower() for a in plan.actions]
                ]

                episode = Episode(
                    session_id=self._state.context.session_id,
                    cycle=self._state.context.cycle_count,
                    goal=next(
                        (g.to_dict() for g in self._state.goals if g.goal_id == plan.goal_id),
                        {},
                    ),
                    plan=plan.to_dict(),
                    actions=plan.actions,
                    results=plan_results,
                    outcome="positive" if success_count > fail_count else "negative",
                    lessons=lessons,
                )
                self._episodic_memory.record(episode)

        # 推进记忆循环
        self._working_memory.advance_cycle()

        # 更新目标状态
        for plan in plans:
            goal = self._state.get_goal(plan.goal_id)
            if goal:
                if plan.status == PlanStatus.COMPLETED:
                    self._state.complete_goal(plan.goal_id)
                elif plan.status == PlanStatus.FAILED:
                    self._state.fail_goal(plan.goal_id)

        # 返回 IDLE
        self._state.transition(AgentPhase.IDLE)

        return lessons

    # ── 目标管理 ──────────────────────────────────────────────

    def add_goal(self, goal: AgentGoal) -> None:
        """添加目标."""
        self._state.add_goal(goal)

    def get_active_goals(self) -> list[AgentGoal]:
        """获取活动目标."""
        return self._state.active_goals

    def complete_goal(self, goal_id: str) -> bool:
        """完成目标."""
        return self._state.complete_goal(goal_id)

    # ── 日志和统计 ────────────────────────────────────────────

    def _log_phase(self, phase: str) -> None:
        """记录阶段日志."""
        self._log.append({
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self._state.context.cycle_count,
        })

    def get_log(self, n: int = 20) -> list[dict[str, Any]]:
        """获取最近日志."""
        return self._log[-n:]

    def stats(self) -> dict[str, Any]:
        """获取 Agent 统计."""
        return {
            **self._state.stats(),
            "working_memory_size": self._working_memory.size,
            "working_memory_active": self._working_memory.active_count,
            "episodic_memory_size": self._episodic_memory.size,
            "semantic_memory_size": self._semantic_memory.size,
            "insight_count": self._reasoning.insight_count,
            "plan_count": self._planner.plan_count,
            "tool_count": self._tools.tool_count,
            "tool_executions": self._tools.execution_count,
            "log_count": len(self._log),
            "has_adapter": self._adapter_registry is not None,
            "execution_mode": self._execution_mode,
        }

    def _calculate_risk_level(self) -> str:
        """根据当前指标状态计算风险等级."""
        metrics = self._state.context.metrics_snapshot
        fatigue = metrics.get("creative_fatigue", 0)
        roas_change = metrics.get("roas_change", 0)
        spend_change = metrics.get("spend_change", 0)

        if fatigue > 0.8 or abs(roas_change) > 0.3 or abs(spend_change) > 0.5:
            return "high"
        elif fatigue > 0.6 or abs(roas_change) > 0.15:
            return "medium"
        return "low"

    def reset(self) -> None:
        """重置 Agent."""
        self._state.reset()
        self._working_memory.clear()
        self._episodic_memory.clear()
        self._semantic_memory.clear()
        self._reasoning.reset()
        self._planner.reset()
        self._tools.reset()
        self._log.clear()


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_growth_agent(
    profile: AgentProfile | None = None,
    with_tools: bool = True,
    with_real_adapters: bool = False,
    execution_mode: str = "mock",
) -> GrowthAgent:
    """创建默认 GrowthAgent 实例.

    Args:
        profile: Agent 配置 (默认使用标准配置)
        with_tools: 是否注册默认工具 (True)
        with_real_adapters: 是否使用真实 Adapter 替换 Mock Handler
        execution_mode: 执行模式 (mock/dry_run/real)

    Returns:
        GrowthAgent: 预配置的 Agent 实例
    """
    adapter_registry = None
    if with_real_adapters:
        adapter_registry = create_default_adapter_registry()

    return GrowthAgent(
        profile=profile,
        adapter_registry=adapter_registry,
        execution_mode=execution_mode,
    )


def create_aggressive_agent(
    with_real_adapters: bool = False,
    execution_mode: str = "mock",
) -> GrowthAgent:
    """创建激进型 Agent (高自主性、高风险容忍)."""
    from .agent_models import create_aggressive_agent_profile
    return GrowthAgent(
        profile=create_aggressive_agent_profile(),
        adapter_registry=create_default_adapter_registry() if with_real_adapters else None,
        execution_mode=execution_mode,
    )


def create_conservative_agent(
    with_real_adapters: bool = False,
    execution_mode: str = "mock",
) -> GrowthAgent:
    """创建保守型 Agent (低自主性、低风险容忍)."""
    from .agent_models import create_conservative_agent_profile
    return GrowthAgent(
        profile=create_conservative_agent_profile(),
        adapter_registry=create_default_adapter_registry() if with_real_adapters else None,
        execution_mode=execution_mode,
    )