"""E13.7 Autonomous Growth Agent Layer.

Growth Agent 将整个系统封装为一个自主 Agent，实现:
  - 观察 (Observe): 接收环境数据
  - 推理 (Reason): 从观察中生成洞察
  - 规划 (Plan): 基于洞察生成增长计划
  - 执行 (Execute): 通过工具系统执行计划
  - 学习 (Learn): 从结果中更新记忆

E13.7.4 Production Growth Agent:
  - runtime/: 生产运行时内核 (Lifecycle, Scheduler, Runtime)
  - agent_policy: 安全策略层 (Level 0/1/2)
  - agent_health: 健康监控
  - production_memory: 生产长期记忆
  - agent_reporter: 人机接口报告

核心组件:
  - agent_models: 核心数据模型
  - agent_state: 状态管理
  - agent_memory: 记忆系统 (工作/情景/语义)
  - agent_reasoning: 推理引擎
  - agent_planner: 计划生成器
  - agent_tools: 工具系统
  - agent_core: GrowthAgent 核心
  - agent_orchestrator: 自主循环编排器

用法:
    from growth_runtime.agent import GrowthAgent, create_growth_agent

    agent = create_growth_agent()
    agent.observe({"spend": 17000, "roas": 0.53, "creative_fatigue": 0.81})
    result = agent.run_cycle()

    # E13.7.4 Production Runtime
    from growth_runtime.agent.runtime import ProductionGrowthRuntime
    runtime = ProductionGrowthRuntime(agent=agent)
    runtime.start()
    runtime.run_cycle(metrics)
    runtime.stop()
"""

from .agent_core import (
    GrowthAgent,
    create_aggressive_agent,
    create_conservative_agent,
    create_growth_agent,
)
from .agent_health import (
    AgentHealthMonitor,
    HealthMetric,
    HealthSnapshot,
    HealthStatus,
    HealthThreshold,
    create_health_monitor,
)
from .agent_memory import (
    EpisodicMemory,
    Episode,
    KnowledgeNode,
    SemanticMemory,
    WorkingMemory,
    WorkingMemoryEntry,
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
    InsightType,
    Observation,
    PlanStatus,
    create_aggressive_agent_profile,
    create_conservative_agent_profile,
    create_growth_agent_profile,
)
from .agent_orchestrator import (
    AgentOrchestrator,
    CycleResult,
    CycleTrigger,
    OrchestratorReport,
    OrchestratorState,
    create_orchestrator,
)
from .agent_planner import (
    AgentPlanner,
    StrategyTemplate,
    BUILTIN_STRATEGIES,
)
from .agent_policy import (
    ActionRule,
    AgentPolicy,
    PolicyAction,
    PolicyLevel,
    create_default_policy,
    create_permissive_policy,
    create_strict_policy,
)
from .agent_reasoning import (
    LLMReasoningEngine,
    ReasoningContext,
    ReasoningEngine,
)
from .agent_reporter import (
    AgentReporter,
    DailyReport,
    WeeklyReport,
    create_reporter,
)
from .agent_state import AgentStateManager
from .agent_tools import (
    BUILTIN_TOOLS,
    ToolCategory,
    ToolDefinition,
    ToolPermission,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    create_default_registry,
    create_registry_with_handlers,
)
from .production_memory import (
    CycleRecord,
    ProductionMemory,
    create_production_memory,
)

__all__ = [
    # Core
    "GrowthAgent",
    "AgentOrchestrator",
    # Models
    "AgentPhase",
    "AgentGoal",
    "AgentProfile",
    "AgentContext",
    "GoalPriority",
    "GoalStatus",
    "Observation",
    "Insight",
    "InsightType",
    "GrowthPlan",
    "PlanStatus",
    # State
    "AgentStateManager",
    # Memory
    "WorkingMemory",
    "WorkingMemoryEntry",
    "EpisodicMemory",
    "Episode",
    "SemanticMemory",
    "KnowledgeNode",
    # Reasoning
    "ReasoningEngine",
    "LLMReasoningEngine",
    "ReasoningContext",
    # Planner
    "AgentPlanner",
    "StrategyTemplate",
    "BUILTIN_STRATEGIES",
    # Tools
    "ToolRegistry",
    "ToolDefinition",
    "ToolResult",
    "ToolCategory",
    "ToolPermission",
    "ToolResultStatus",
    "BUILTIN_TOOLS",
    "create_default_registry",
    "create_registry_with_handlers",
    # Orchestrator
    "CycleResult",
    "CycleTrigger",
    "OrchestratorState",
    "OrchestratorReport",
    # E13.7.4 Policy
    "AgentPolicy",
    "ActionRule",
    "PolicyLevel",
    "PolicyAction",
    "create_default_policy",
    "create_strict_policy",
    "create_permissive_policy",
    # E13.7.4 Health
    "AgentHealthMonitor",
    "HealthStatus",
    "HealthMetric",
    "HealthThreshold",
    "HealthSnapshot",
    "create_health_monitor",
    # E13.7.4 Production Memory
    "ProductionMemory",
    "CycleRecord",
    "create_production_memory",
    # E13.7.4 Reporter
    "AgentReporter",
    "DailyReport",
    "WeeklyReport",
    "create_reporter",
    # Factories
    "create_growth_agent",
    "create_aggressive_agent",
    "create_conservative_agent",
    "create_growth_agent_profile",
    "create_aggressive_agent_profile",
    "create_conservative_agent_profile",
    "create_orchestrator",
]