"""E14.8 Autonomous Growth Agent — 自主增长代理.

E14.8 核心:
  目标驱动的自主控制层，负责回答:
    "当前业务目标是什么？距离目标差多少？下一步应该调用哪个能力？"

核心循环:
  Observe → Analyze → Retrieve → Plan → Check → Execute → Learn → Loop

组件:
  - GoalManager: 目标管理
  - StateAnalyzer: 状态分析
  - StrategyRetriever: 策略检索
  - GrowthPlanner: 计划生成
  - SafetyGuard: 安全检查
  - AutonomousGrowthAgent: 主 Runtime

完整的 E14.8 数据流:
  Reality Data
      ↓
  StateAnalyzer.analyze()
      ↓
  GrowthState
      ↓
  StrategyRetriever.retrieve()
      ↓
  StrategyMatch[]
      ↓
  GrowthPlanner.plan()
      ↓
  GrowthPlan
      ↓
  SafetyGuard.check()
      ↓
  SafetyDecision
      ↓
  ExecutionEngine.execute()
      ↓
  FeedbackCollector.collect()
      ↓
  StrategyMemory.update()
      ↓
  Next Cycle
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .goal_models import (
    GrowthGoal,
    GoalGap,
    GoalManager,
    GoalPriority,
    GoalStatus,
    create_goal_manager,
)
from .growth_state_analyzer import (
    GrowthState,
    StateAnalyzer,
    create_state_analyzer,
)
from .strategy_retriever import (
    StrategyMatch,
    StrategyRetriever,
    create_strategy_retriever,
)
from .growth_planner import (
    GrowthPlan,
    PlanStep,
    GrowthPlanner,
    create_growth_planner,
)
from .safety_guard import (
    GrowthSafetyGuard,
    SafetyDecision,
    SafetyDecisionType,
    BudgetLimit,
    FrequencyLimit,
    create_safety_guard,
)
from .growth_action_router import (
    GrowthAction,
    GrowthActionType,
    ActionStatus,
)
from .growth_execution_engine import (
    ExecutionOutcome,
    ExecutionStatus,
)


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class AgentState(str, Enum):
    """Agent 运行状态."""
    IDLE = "idle"
    OBSERVING = "observing"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    LEARNING = "learning"
    PAUSED = "paused"
    ERROR = "error"


class CycleResult(str, Enum):
    """单次循环结果."""
    SUCCESS = "success"
    PARTIAL = "partial"        # 部分执行
    SKIPPED = "skipped"        # 无需执行
    BLOCKED = "blocked"        # 安全阻止
    ERROR = "error"


# ═══════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════

@dataclass
class CycleResult:
    """循环结果 — 单次 Agent 循环的输出.

    Attributes:
        cycle_id: 循环 ID
        state: 当前状态
        goal_gap: 目标差距
        plan: 生成的计划 (可选)
        safety_decision: 安全检查决策 (可选)
        outcomes: 执行结果列表
        status: 循环状态
        timestamp: 时间戳
        summary: 摘要
    """
    cycle_id: str = field(default_factory=lambda: f"cycle_{uuid.uuid4().hex[:8]}")
    state: GrowthState | None = None
    goal_gap: GoalGap | None = None
    plan: GrowthPlan | None = None
    safety_decision: SafetyDecision | None = None
    outcomes: list[ExecutionOutcome] = field(default_factory=list)
    status: str = "success"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "state": self.state.to_dict() if self.state else {},
            "goal_gap": self.goal_gap.to_dict() if self.goal_gap else {},
            "plan": self.plan.to_dict() if self.plan else {},
            "safety": self.safety_decision.to_dict() if self.safety_decision else {},
            "outcome_count": len(self.outcomes),
            "status": self.status,
            "timestamp": self.timestamp,
            "summary": self.summary,
        }


# ═══════════════════════════════════════════════════════════
# AutonomousGrowthAgent
# ═══════════════════════════════════════════════════════════

class AutonomousGrowthAgent:
    """自主增长代理 — E14.8 核心 Runtime.

    目标驱动的自主控制层，管理完整的 Observe → Think → Plan → Act → Learn 循环.

    用法:
        # 默认模式 (mock execution)
        agent = AutonomousGrowthAgent(
            goal_manager=GoalManager(),
            state_analyzer=StateAnalyzer(),
            strategy_retriever=StrategyRetriever(strategy_memory),
            planner=GrowthPlanner(),
            safety_guard=GrowthSafetyGuard(),
            execution_engine=GrowthExecutionEngine(),
            feedback_collector=ExecutionFeedbackCollector(),
        )

        # 注入真实执行能力 (MediaBuyingAgent)
        from .media_buying_agent import create_media_buying_agent
        buying_agent = create_media_buying_agent()
        engine = create_growth_execution_engine(media_buying_agent=buying_agent)
        agent = AutonomousGrowthAgent(execution_engine=engine)

        # 设置目标
        agent.set_goal(GrowthGoal(metric="D30_ROAS", target_value=1.0, current_value=0.53))

        # 运行一个循环
        result = agent.run_cycle(reality_data={"roas": 0.55, "fatigue": 0.6})

        # 查看状态
        print(agent.get_status())
    """

    def __init__(
        self,
        goal_manager: GoalManager | None = None,
        state_analyzer: StateAnalyzer | None = None,
        strategy_retriever: StrategyRetriever | None = None,
        planner: GrowthPlanner | None = None,
        safety_guard: GrowthSafetyGuard | None = None,
        execution_engine: Any = None,
        feedback_collector: Any = None,
        experience_store: Any = None,
        strategy_memory: Any = None,
    ):
        self._goal_manager = goal_manager or GoalManager()
        self._state_analyzer = state_analyzer or StateAnalyzer()
        self._planner = planner or GrowthPlanner()
        self._safety_guard = safety_guard or GrowthSafetyGuard()
        self._execution_engine = execution_engine
        self._feedback_collector = feedback_collector
        self._experience_store = experience_store
        self._strategy_memory = strategy_memory

        # 如果传入了 strategy_memory，自动创建 StrategyRetriever
        if strategy_retriever is not None:
            self._strategy_retriever = strategy_retriever
        elif strategy_memory is not None:
            self._strategy_retriever = StrategyRetriever(strategy_memory)
        else:
            self._strategy_retriever = None

        self._agent_state: AgentState = AgentState.IDLE
        self._current_goal: GrowthGoal | None = None
        self._current_state: GrowthState | None = None
        self._cycle_count: int = 0
        self._cycle_history: list[CycleResult] = []
        self._max_cycle_history: int = 100

    # ═══════════════════════════════════════════════════════
    # Goal Management
    # ═══════════════════════════════════════════════════════

    def set_goal(self, goal: GrowthGoal) -> str:
        """设置当前优化目标."""
        goal_id = self._goal_manager.add_goal(goal)
        self._current_goal = goal
        self._agent_state = AgentState.IDLE
        return goal_id

    def get_current_goal(self) -> GrowthGoal | None:
        return self._current_goal

    def get_goal_gap(self) -> GoalGap | None:
        if self._current_goal is None:
            return None
        return GoalGap.analyze(self._current_goal)

    # ═══════════════════════════════════════════════════════
    # Core Loop
    # ═══════════════════════════════════════════════════════

    def run_cycle(
        self,
        reality_data: dict[str, Any] | None = None,
        action_history: dict[str, list[str]] | None = None,
    ) -> CycleResult:
        """运行一个完整的 Observe → Plan → Act → Learn 循环.

        Args:
            reality_data: Reality 数据 (来自 E12 / E13)
            action_history: 历史动作记录

        Returns:
            CycleResult: 循环结果
        """
        self._cycle_count += 1

        # 1. Observe: 观察现实
        self._agent_state = AgentState.OBSERVING
        state = self._observe(reality_data)

        # 2. Analyze: 分析目标差距
        self._agent_state = AgentState.ANALYZING
        goal_gap = self._analyze()

        # 3. 如果目标已达成，跳过
        if goal_gap is not None and goal_gap.status_label == "achieved":
            return CycleResult(
                state=state,
                goal_gap=goal_gap,
                status="success",
                summary="Goal already achieved",
            )

        # 4. Retrieve: 检索策略
        if self._strategy_retriever is not None:
            strategy_matches = self._strategy_retriever.retrieve(state)
        else:
            strategy_matches = []

        # 5. Plan: 生成计划
        self._agent_state = AgentState.PLANNING
        plan = self._plan(state, strategy_matches)

        # 6. Check: 安全检查
        safety = self._safety_guard.check(plan, action_history)

        if safety.decision == SafetyDecisionType.BLOCKED:
            return CycleResult(
                state=state,
                goal_gap=goal_gap,
                plan=plan,
                safety_decision=safety,
                status="blocked",
                summary=f"Blocked by safety: {safety.reason}",
            )

        if safety.decision == SafetyDecisionType.NEEDS_REVIEW:
            return CycleResult(
                state=state,
                goal_gap=goal_gap,
                plan=plan,
                safety_decision=safety,
                status="partial",
                summary=f"Needs review: {safety.reason}",
            )

        # 7. Execute: 执行动作
        self._agent_state = AgentState.EXECUTING
        outcomes = self._execute(safety.modified_actions)

        # 8. Learn: 学习反馈
        self._agent_state = AgentState.LEARNING
        self._learn(outcomes, state, plan)

        # 9. 记录循环
        result = CycleResult(
            state=state,
            goal_gap=goal_gap,
            plan=plan,
            safety_decision=safety,
            outcomes=outcomes,
            status="success",
            summary=f"Executed {len(outcomes)} actions",
        )
        self._cycle_history.append(result)
        if len(self._cycle_history) > self._max_cycle_history:
            self._cycle_history = self._cycle_history[-self._max_cycle_history:]

        self._agent_state = AgentState.IDLE
        return result

    def _observe(self, reality_data: dict[str, Any] | None) -> GrowthState:
        """观察: RealityData → GrowthState."""
        state = self._state_analyzer.analyze(reality_data)
        self._current_state = state

        # 更新目标的当前值
        if self._current_goal is not None and reality_data:
            metric = self._current_goal.metric.lower()
            for key, value in reality_data.items():
                if key.lower() in metric or metric in key.lower():
                    self._goal_manager.update_goal(
                        self._current_goal.goal_id,
                        float(value),
                    )
                    break

        return state

    def _analyze(self) -> GoalGap | None:
        """分析: 计算目标差距."""
        if self._current_goal is None:
            return None
        return GoalGap.analyze(self._current_goal)

    def _plan(
        self,
        state: GrowthState,
        strategy_matches: list[StrategyMatch],
    ) -> GrowthPlan:
        """规划: 生成 GrowthPlan."""
        return self._planner.plan(
            goal=self._current_goal,
            state=state,
            strategy_matches=strategy_matches,
        )

    def _execute(
        self,
        actions: list[GrowthAction],
    ) -> list[ExecutionOutcome]:
        """执行: 通过 ExecutionEngine 执行动作."""
        if self._execution_engine is None:
            return []

        outcomes: list[ExecutionOutcome] = []
        for action in actions:
            try:
                outcome = self._execution_engine.execute(action)
                outcomes.append(outcome)
                action.status = ActionStatus.COMPLETED
            except Exception:
                outcome = ExecutionOutcome(
                    action_id=action.action_id,
                    action_type=action.action_type.value,
                    status=ExecutionStatus.FAILED,
                    executor=action.executor,
                )
                outcomes.append(outcome)
                action.status = ActionStatus.FAILED

        return outcomes

    def _learn(
        self,
        outcomes: list[ExecutionOutcome],
        state: GrowthState,
        plan: GrowthPlan,
    ) -> None:
        """学习: 收集反馈并更新记忆."""
        if self._feedback_collector is None or self._experience_store is None:
            return

        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            ExperienceContext,
        )
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern,
            StrategyCategory,
            StrategyPerformance,
            StrategyQuality,
            StrategyStep,
            StrategyTriggerCondition,
        )

        for outcome in outcomes:
            ctx = ExperienceContext(
                product_id=getattr(self._current_goal, "metadata", {}).get("product_id", ""),
                opportunity_type=state.primary_opportunity,
                action_type=outcome.action_type,
                audience_segment="",
            )
            self._feedback_collector.collect_and_store(
                outcome, ctx, self._experience_store,
            )

        # 更新 StrategyMemory
        if self._strategy_memory is not None and plan.source_strategy_ids:
            for strategy_id in plan.source_strategy_ids:
                existing = self._strategy_memory.get_all()
                for s in existing:
                    if s.strategy_id == strategy_id:
                        s.performance.total_executions += 1
                        s.updated_at = datetime.now(timezone.utc).isoformat()
                        s.compute_score()
                        break

    # ═══════════════════════════════════════════════════════
    # Convenience
    # ═══════════════════════════════════════════════════════

    def observe(self, reality_data: dict[str, Any] | None = None) -> GrowthState:
        """仅观察，不执行."""
        return self._state_analyzer.analyze(reality_data)

    def analyze(self) -> GoalGap | None:
        """仅分析目标差距."""
        return self._analyze()

    def plan_only(
        self,
        reality_data: dict[str, Any] | None = None,
    ) -> GrowthPlan | None:
        """仅生成计划，不执行."""
        state = self._observe(reality_data)
        if self._strategy_retriever is not None:
            matches = self._strategy_retriever.retrieve(state)
        else:
            matches = []
        return self._plan(state, matches)

    def get_status(self) -> dict[str, Any]:
        """获取 Agent 状态."""
        return {
            "agent_state": self._agent_state.value,
            "cycle_count": self._cycle_count,
            "current_goal": self._current_goal.to_dict() if self._current_goal else None,
            "current_state": self._current_state.to_dict() if self._current_state else None,
            "goal_stats": self._goal_manager.get_stats(),
            "history_count": len(self._cycle_history),
            "last_cycle": self._cycle_history[-1].to_dict() if self._cycle_history else None,
        }

    def get_cycle_history(self, n: int = 10) -> list[dict[str, Any]]:
        """获取最近 N 个循环记录."""
        return [c.to_dict() for c in self._cycle_history[-n:]]

    @property
    def agent_state(self) -> AgentState:
        return self._agent_state

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def goal_manager(self) -> GoalManager:
        return self._goal_manager

    @property
    def state_analyzer(self) -> StateAnalyzer:
        return self._state_analyzer

    def pause(self) -> None:
        self._agent_state = AgentState.PAUSED

    def resume(self) -> None:
        if self._agent_state == AgentState.PAUSED:
            self._agent_state = AgentState.IDLE

    def reset(self) -> None:
        self._agent_state = AgentState.IDLE
        self._current_goal = None
        self._current_state = None
        self._cycle_count = 0
        self._cycle_history.clear()
        self._goal_manager.reset()
        self._safety_guard.reset()


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_autonomous_growth_agent(
    strategy_memory: Any = None,
    execution_engine: Any = None,
    feedback_collector: Any = None,
    experience_store: Any = None,
    roas_target: float = 1.0,
    max_actions: int = 5,
    min_confidence_auto: float = 0.8,
) -> AutonomousGrowthAgent:
    """创建默认 AutonomousGrowthAgent.

    Args:
        strategy_memory: E13.4.3 StrategyMemory 实例
        execution_engine: E14.7.2 GrowthExecutionEngine 实例
        feedback_collector: E14.7.3 ExecutionFeedbackCollector 实例
        experience_store: E13.4.1 ExperienceStore 实例
        roas_target: 默认 ROAS 目标
        max_actions: 每周期最大动作数
        min_confidence_auto: 自动批准置信度阈值

    Returns:
        AutonomousGrowthAgent: 配置好的 Agent
    """
    return AutonomousGrowthAgent(
        goal_manager=create_goal_manager(),
        state_analyzer=create_state_analyzer(roas_target=roas_target),
        strategy_retriever=create_strategy_retriever(strategy_memory) if strategy_memory else None,
        planner=create_growth_planner(max_actions=max_actions),
        safety_guard=create_safety_guard(min_confidence_auto=min_confidence_auto),
        execution_engine=execution_engine,
        feedback_collector=feedback_collector,
        experience_store=experience_store,
        strategy_memory=strategy_memory,
    )