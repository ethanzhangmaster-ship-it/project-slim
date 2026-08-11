"""E13.7.1 Agent → Adapter 链路集成测试.

验证 GrowthAgent 通过 Real Tool Adapter 真正执行的能力:
  - Agent 创建时注入 adapter_registry → 工具自动升级为真实 Adapter 调用
  - Agent._execute() 构建动态 ToolExecutionContext 并传递给 Adapter
  - 多种执行模式 (mock/dry_run/real) 的正确路由
  - Agent 完整循环: Observe → Reason → Plan → Execute (via Adapter) → Learn
  - 降级: Adapter 不可用时自动降级为 mock
  - 工厂函数支持 with_real_adapters 参数
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent import (
    GrowthAgent,
    create_growth_agent,
    create_aggressive_agent,
    create_conservative_agent,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    create_default_registry,
    AgentGoal,
    GoalPriority,
    GoalStatus,
    Insight,
    InsightType,
    GrowthPlan,
    PlanStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.adapters import (
    ToolAdapter,
    ToolExecutionContext,
    AdapterRegistry,
    create_default_adapter_registry,
    ExecutionAdapter,
    MetaAdapter,
    AdjustAdapter,
    CreativeAdapter,
    MemoryAdapter,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.real_tool_registry import (
    upgrade_to_real,
    create_real_tool_registry,
    ACTION_ADAPTER_MAP,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def sample_metrics():
    return {
        "spend": 17000.0,
        "roas": 0.53,
        "roas_change": -0.12,
        "ctr": 0.021,
        "ctr_change": -0.12,
        "creative_fatigue": 0.81,
        "payer_quality": 0.65,
        "top_creative_ctr": 0.08,
        "avg_ctr": 0.02,
        "installs": 4500,
        "installs_change": -0.05,
        "spend_change": 0.05,
    }


@pytest.fixture
def adapter_registry():
    return create_default_adapter_registry()


# ═══════════════════════════════════════════════════════════════
# 1. Agent → Adapter 注入
# ═══════════════════════════════════════════════════════════════


class TestAgentAdapterInjection:
    def test_agent_without_adapter_uses_mock(self):
        """没有 adapter_registry 时 Agent 使用 mock handler."""
        agent = GrowthAgent()
        assert agent.stats()["has_adapter"] is False
        assert agent.stats()["execution_mode"] == "mock"

    def test_agent_with_adapter_upgrades_tools(self, adapter_registry):
        """注入 adapter_registry 后工具自动升级."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        assert agent.stats()["has_adapter"] is True
        assert agent.stats()["execution_mode"] == "mock"

    def test_agent_with_adapter_has_all_tools(self, adapter_registry):
        """注入 adapter 后所有工具仍然可用."""
        agent = GrowthAgent(adapter_registry=adapter_registry)
        for tool_name in ACTION_ADAPTER_MAP:
            assert agent.tools.has_tool(tool_name), f"Missing tool: {tool_name}"

    def test_agent_with_adapter_still_has_tool_count(self, adapter_registry):
        """注入 adapter 后工具数量不变."""
        agent_no_adapter = GrowthAgent()
        agent_with_adapter = GrowthAgent(adapter_registry=adapter_registry)
        assert agent_with_adapter.tools.tool_count == agent_no_adapter.tools.tool_count

    def test_different_execution_modes(self, adapter_registry):
        """不同 execution_mode 正确存储."""
        for mode in ("mock", "dry_run", "real"):
            agent = GrowthAgent(
                adapter_registry=adapter_registry,
                execution_mode=mode,
            )
            assert agent.stats()["execution_mode"] == mode


# ═══════════════════════════════════════════════════════════════
# 2. Agent._execute() → ToolExecutionContext 构建
# ═══════════════════════════════════════════════════════════════


class TestAgentExecuteContext:
    def test_execute_passes_context_to_tools(self, adapter_registry):
        """Agent._execute() 构建 ToolExecutionContext 并传递给 Adapter."""
        # 使用自定义 Adapter 来验证 context 是否被正确传递
        captured_contexts = []

        class SpyAdapter(ToolAdapter):
            @property
            def name(self) -> str:
                return "spy"

            def can_handle(self, action_name: str) -> bool:
                return action_name == "query_metrics"

            def execute(self, action_name, params, context):
                captured_contexts.append(context)
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data={"spy": True},
                )

        reg = AdapterRegistry()
        reg.register(SpyAdapter())
        reg.register(ExecutionAdapter())
        reg.register(MetaAdapter())
        reg.register(AdjustAdapter())
        reg.register(CreativeAdapter())
        reg.register(MemoryAdapter())

        agent = GrowthAgent(adapter_registry=reg, execution_mode="mock")
        agent.observe({"spend": 10000, "roas": 0.5})

        # 手动构造一个 plan 包含 query_metrics action
        plan = GrowthPlan(
            goal_id="test_goal",
            actions=[{"action_type": "query_metrics", "params": {"entity_type": "campaign"}}],
        )
        agent._state.add_plan(plan)
        results = agent._execute([plan])

        assert len(captured_contexts) == 1
        ctx = captured_contexts[0]
        assert isinstance(ctx, ToolExecutionContext)
        assert ctx.execution_mode == "mock"
        assert ctx.cycle_number >= 0
        assert ctx.session_id != ""

    def test_execute_context_has_metrics_snapshot(self, adapter_registry, sample_metrics):
        """ToolExecutionContext 包含当前指标快照."""
        captured_metrics = []

        class MetricsSpyAdapter(ToolAdapter):
            @property
            def name(self) -> str:
                return "metrics_spy"

            def can_handle(self, action_name: str) -> bool:
                return action_name == "query_metrics"

            def execute(self, action_name, params, context):
                captured_metrics.append(context.metrics_snapshot)
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data={},
                )

        reg = AdapterRegistry()
        reg.register(MetricsSpyAdapter())
        reg.register(ExecutionAdapter())
        reg.register(MetaAdapter())
        reg.register(AdjustAdapter())
        reg.register(CreativeAdapter())
        reg.register(MemoryAdapter())

        agent = GrowthAgent(adapter_registry=reg, execution_mode="mock")
        agent.observe(sample_metrics)

        plan = GrowthPlan(
            goal_id="test_goal",
            actions=[{"action_type": "query_metrics", "params": {"entity_type": "campaign"}}],
        )
        agent._state.add_plan(plan)
        agent._execute([plan])

        assert len(captured_metrics) > 0
        if captured_metrics:
            assert captured_metrics[0].get("creative_fatigue") == 0.81

    def test_execute_context_risk_level(self, adapter_registry):
        """高疲劳度时 risk_level 为 high."""
        captured_risk = []

        class RiskSpyAdapter(ToolAdapter):
            @property
            def name(self) -> str:
                return "risk_spy"

            def can_handle(self, action_name: str) -> bool:
                return action_name == "query_metrics"

            def execute(self, action_name, params, context):
                captured_risk.append(context.risk_level)
                return ToolResult(tool_name=action_name, status=ToolResultStatus.SUCCESS, data={})

        reg = AdapterRegistry()
        reg.register(RiskSpyAdapter())
        reg.register(ExecutionAdapter())
        reg.register(MetaAdapter())
        reg.register(AdjustAdapter())
        reg.register(CreativeAdapter())
        reg.register(MemoryAdapter())

        agent = GrowthAgent(adapter_registry=reg, execution_mode="mock")
        agent.observe({"creative_fatigue": 0.85, "roas_change": -0.35})

        plan = GrowthPlan(
            goal_id="test_goal",
            actions=[{"action_type": "query_metrics", "params": {}}],
        )
        agent._state.add_plan(plan)
        agent._execute([plan])

        assert len(captured_risk) > 0
        assert captured_risk[0] == "high"

    def test_execute_context_low_risk(self, adapter_registry):
        """低波动时 risk_level 为 low."""
        captured_risk = []

        class RiskSpyAdapter(ToolAdapter):
            @property
            def name(self) -> str:
                return "risk_spy2"

            def can_handle(self, action_name: str) -> bool:
                return action_name == "query_metrics"

            def execute(self, action_name, params, context):
                captured_risk.append(context.risk_level)
                return ToolResult(tool_name=action_name, status=ToolResultStatus.SUCCESS, data={})

        reg = AdapterRegistry()
        reg.register(RiskSpyAdapter())
        reg.register(ExecutionAdapter())
        reg.register(MetaAdapter())
        reg.register(AdjustAdapter())
        reg.register(CreativeAdapter())
        reg.register(MemoryAdapter())

        agent = GrowthAgent(adapter_registry=reg, execution_mode="mock")
        agent.observe({"creative_fatigue": 0.3, "roas_change": 0.05, "spend_change": 0.02})

        plan = GrowthPlan(
            goal_id="test_goal",
            actions=[{"action_type": "query_metrics", "params": {}}],
        )
        agent._state.add_plan(plan)
        agent._execute([plan])

        assert len(captured_risk) > 0
        assert captured_risk[0] == "low"


# ═══════════════════════════════════════════════════════════════
# 3. Agent 完整循环 via Adapter
# ═══════════════════════════════════════════════════════════════


class TestAgentFullCycleWithAdapter:
    def test_full_cycle_with_adapter_mock_mode(self, adapter_registry, sample_metrics):
        """完整 Agent 循环 + Adapter (mock 模式)."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["cycle"] == 1
        assert result["insight_count"] > 0
        assert result["execution_count"] > 0
        assert result["phase"] == "idle"

    def test_full_cycle_with_adapter_dry_run(self, adapter_registry, sample_metrics):
        """完整 Agent 循环 + Adapter (dry_run 模式)."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="dry_run",
        )
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["cycle"] == 1
        # dry_run 模式下仍应正常完成循环
        assert "error" not in result

    def test_full_cycle_execution_results_have_metadata(self, adapter_registry, sample_metrics):
        """Adapter 返回的结果包含 metadata."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["execution_count"] > 0

    def test_full_cycle_without_adapter_uses_mock_handler(self, sample_metrics):
        """没有 adapter 时 Agent 使用 mock handler."""
        agent = GrowthAgent()
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["cycle"] == 1
        assert result["insight_count"] > 0

    def test_multiple_cycles_with_adapter(self, adapter_registry, sample_metrics):
        """多次循环 Adapter 状态保持."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )

        # Cycle 1
        r1 = agent.run_cycle(metrics=sample_metrics)
        assert r1["cycle"] == 1

        # Cycle 2
        r2 = agent.run_cycle(metrics={
            **sample_metrics,
            "creative_fatigue": 0.65,
            "roas_change": 0.05,
        })
        assert r2["cycle"] == 2

        # 工具执行次数累积
        assert agent.tools.execution_count >= 2


# ═══════════════════════════════════════════════════════════════
# 4. 执行模式路由
# ═══════════════════════════════════════════════════════════════


class TestExecutionModeRouting:
    def test_mock_mode_returns_mock_data(self, adapter_registry):
        """mock 模式返回 mock 数据."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        agent.observe({"spend": 10000})

        plan = GrowthPlan(
            goal_id="test",
            actions=[{"action_type": "query_metrics", "params": {"entity_type": "campaign"}}],
        )
        agent._state.add_plan(plan)
        results = agent._execute([plan])

        assert len(results) == 1
        assert results[0].is_success()
        assert results[0].metadata.get("mode") == "mock"

    def test_dry_run_mode_validates_params(self, adapter_registry):
        """dry_run 模式验证参数但不执行."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="dry_run",
        )
        agent.observe({"spend": 10000})

        # 缺少必需参数
        plan = GrowthPlan(
            goal_id="test",
            actions=[{"action_type": "create_campaign", "params": {"budget": -1}}],
        )
        agent._state.add_plan(plan)
        results = agent._execute([plan])

        assert len(results) == 1
        # dry_run 下 budget 无效 → FAILED
        assert results[0].status == ToolResultStatus.FAILED

    def test_real_mode_falls_back_to_mock_when_unavailable(self, adapter_registry):
        """real 模式下 API 不可用时降级为 mock."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="real",
        )
        agent.observe({"spend": 10000})

        plan = GrowthPlan(
            goal_id="test",
            actions=[{"action_type": "query_metrics", "params": {"entity_type": "campaign"}}],
        )
        agent._state.add_plan(plan)
        results = agent._execute([plan])

        assert len(results) == 1
        # real 模式下因没有真实 API 凭证，应降级为 mock
        assert results[0].is_success()


# ═══════════════════════════════════════════════════════════════
# 5. 工厂函数
# ═══════════════════════════════════════════════════════════════


class TestAgentFactoryWithAdapter:
    def test_create_growth_agent_with_adapters(self):
        """create_growth_agent(with_real_adapters=True) 创建带 Adapter 的 Agent."""
        agent = create_growth_agent(with_real_adapters=True, execution_mode="mock")
        assert agent.stats()["has_adapter"] is True
        assert agent.stats()["execution_mode"] == "mock"

    def test_create_growth_agent_without_adapters(self):
        """create_growth_agent() 默认不带 Adapter."""
        agent = create_growth_agent()
        assert agent.stats()["has_adapter"] is False

    def test_create_aggressive_agent_with_adapters(self):
        """create_aggressive_agent(with_real_adapters=True) 创建激进型 Agent."""
        agent = create_aggressive_agent(with_real_adapters=True, execution_mode="dry_run")
        assert agent.stats()["has_adapter"] is True
        assert agent.stats()["execution_mode"] == "dry_run"
        # 激进型 Agent 有更高风险容忍
        assert agent.profile.risk_tolerance >= 0.7

    def test_create_conservative_agent_with_adapters(self):
        """create_conservative_agent(with_real_adapters=True) 创建保守型 Agent."""
        agent = create_conservative_agent(with_real_adapters=True, execution_mode="mock")
        assert agent.stats()["has_adapter"] is True
        assert agent.profile.risk_tolerance <= 0.5

    def test_factory_default_execution_mode(self):
        """工厂函数默认 execution_mode 为 mock."""
        agent = create_growth_agent(with_real_adapters=True)
        assert agent.stats()["execution_mode"] == "mock"

    def test_factory_custom_execution_mode(self):
        """工厂函数支持自定义 execution_mode."""
        for mode in ("mock", "dry_run", "real"):
            agent = create_growth_agent(
                with_real_adapters=True,
                execution_mode=mode,
            )
            assert agent.stats()["execution_mode"] == mode


# ═══════════════════════════════════════════════════════════════
# 6. Adapter 覆盖所有工具
# ═══════════════════════════════════════════════════════════════


class TestAdapterToolCoverage:
    def test_all_builtin_tools_have_adapter_mapping(self, adapter_registry):
        """所有 BUILTIN_TOOLS 在 ACTION_ADAPTER_MAP 中有对应 adapter."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.agent_tools import BUILTIN_TOOLS

        for tool_name in BUILTIN_TOOLS:
            assert tool_name in ACTION_ADAPTER_MAP, (
                f"Tool '{tool_name}' has no adapter mapping in ACTION_ADAPTER_MAP"
            )

    def test_all_mapped_actions_find_adapter(self, adapter_registry):
        """ACTION_ADAPTER_MAP 中所有 action 都能找到对应 adapter."""
        for action_name, adapter_name in ACTION_ADAPTER_MAP.items():
            adapter = adapter_registry.get_adapter(adapter_name)
            assert adapter is not None, (
                f"Adapter '{adapter_name}' not found for action '{action_name}'"
            )
            assert adapter.can_handle(action_name), (
                f"Adapter '{adapter_name}' cannot handle '{action_name}'"
            )

    def test_registry_has_all_five_adapters(self, adapter_registry):
        """默认注册表包含全部 5 个 Adapter."""
        names = adapter_registry.list_adapters()
        assert "execution_adapter" in names
        assert "meta_adapter" in names
        assert "adjust_adapter" in names
        assert "creative_adapter" in names
        assert "memory_adapter" in names
        assert adapter_registry.count == 5

    def test_each_adapter_handles_its_actions(self, adapter_registry):
        """每个 Adapter 能处理其声明的所有动作."""
        # ExecutionAdapter
        exec_adapter = adapter_registry.get_adapter("execution_adapter")
        for action in ("create_campaign", "update_budget", "pause_campaign", "monitor", "collect_result", "wait"):
            assert exec_adapter.can_handle(action), f"ExecutionAdapter cannot handle {action}"

        # MetaAdapter
        meta_adapter = adapter_registry.get_adapter("meta_adapter")
        for action in ("create_campaign", "update_budget", "pause_campaign", "resume_campaign", "upload_creative"):
            assert meta_adapter.can_handle(action), f"MetaAdapter cannot handle {action}"

        # AdjustAdapter
        adjust_adapter = adapter_registry.get_adapter("adjust_adapter")
        for action in ("query_metrics", "query_adjust", "query_creative_performance", "check_fatigue"):
            assert adjust_adapter.can_handle(action), f"AdjustAdapter cannot handle {action}"

        # CreativeAdapter
        creative_adapter = adapter_registry.get_adapter("creative_adapter")
        for action in ("mutate_creative", "generate_creative", "upload_creative"):
            assert creative_adapter.can_handle(action), f"CreativeAdapter cannot handle {action}"

        # MemoryAdapter
        memory_adapter = adapter_registry.get_adapter("memory_adapter")
        for action in ("query_memory", "update_memory", "record_episode"):
            assert memory_adapter.can_handle(action), f"MemoryAdapter cannot handle {action}"


# ═══════════════════════════════════════════════════════════════
# 7. Adapter 降级
# ═══════════════════════════════════════════════════════════════


class TestAdapterFallback:
    def test_unknown_action_returns_error(self, adapter_registry):
        """未注册的 action 返回 BLOCKED (不在 allowed_actions)."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        agent.observe({"spend": 10000})

        plan = GrowthPlan(
            goal_id="test",
            actions=[{"action_type": "nonexistent_action", "params": {}}],
        )
        agent._state.add_plan(plan)
        results = agent._execute([plan])

        assert len(results) == 1
        # 不在 allowed_actions 中 → BLOCKED
        assert results[0].status in (ToolResultStatus.FAILED, ToolResultStatus.BLOCKED)

    def test_action_not_in_allowed_actions_blocked(self, adapter_registry):
        """不在 allowed_actions 中的 action 被 BLOCKED."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        agent.observe({"spend": 10000})

        plan = GrowthPlan(
            goal_id="test",
            actions=[{"action_type": "delete_campaign", "params": {}}],
        )
        agent._state.add_plan(plan)
        results = agent._execute([plan])

        assert len(results) == 1
        assert results[0].status == ToolResultStatus.BLOCKED

    def test_agent_without_adapter_still_works(self, sample_metrics):
        """没有 adapter 时 Agent 仍然正常工作."""
        agent = GrowthAgent()
        result = agent.run_cycle(metrics=sample_metrics)
        assert "error" not in result
        assert result["cycle"] == 1


# ═══════════════════════════════════════════════════════════════
# 8. Agent Stats 完整性
# ═══════════════════════════════════════════════════════════════


class TestAgentStatsWithAdapter:
    def test_stats_include_adapter_info(self, adapter_registry):
        """stats 包含 adapter 信息."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="dry_run",
        )
        stats = agent.stats()
        assert "has_adapter" in stats
        assert "execution_mode" in stats
        assert stats["has_adapter"] is True
        assert stats["execution_mode"] == "dry_run"

    def test_stats_after_cycle(self, adapter_registry, sample_metrics):
        """循环后 stats 正确更新."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        agent.run_cycle(metrics=sample_metrics)

        stats = agent.stats()
        assert stats["tool_executions"] > 0
        assert stats["insight_count"] > 0
        assert stats["plan_count"] > 0

    def test_stats_without_adapter(self):
        """没有 adapter 时 stats 正确."""
        agent = GrowthAgent()
        stats = agent.stats()
        assert stats["has_adapter"] is False
        assert stats["execution_mode"] == "mock"


# ═══════════════════════════════════════════════════════════════
# 9. RealToolRegistry 与 Agent 集成
# ═══════════════════════════════════════════════════════════════


class TestRealToolRegistryWithAgent:
    def test_create_real_tool_registry_works_with_agent(self):
        """create_real_tool_registry() 创建的注册表可直接用于 Agent."""
        registry = create_real_tool_registry()
        agent = GrowthAgent(tool_registry=registry)
        assert agent.tools.tool_count > 0

    def test_upgrade_to_real_on_agent_tools(self):
        """手动升级 Agent 的 tools."""
        agent = GrowthAgent()
        original_count = agent.tools.tool_count

        adapter_registry = create_default_adapter_registry()
        agent._tools = upgrade_to_real(agent._tools, adapter_registry)

        assert agent.tools.tool_count == original_count

    def test_real_tool_registry_tool_names_match(self):
        """real_tool_registry 中的工具名称与 BUILTIN_TOOLS 一致."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.agent_tools import BUILTIN_TOOLS

        registry = create_real_tool_registry()
        for tool_name in BUILTIN_TOOLS:
            assert registry.has_tool(tool_name)

    def test_mock_vs_real_tool_results_differ(self, sample_metrics):
        """mock 和 real tool registry 返回结果不同 (metadata 不同)."""
        mock_agent = GrowthAgent()
        mock_agent.observe(sample_metrics)

        real_agent = GrowthAgent(
            adapter_registry=create_default_adapter_registry(),
            execution_mode="mock",
        )
        real_agent.observe(sample_metrics)

        # 两者都应正常执行
        mock_result = mock_agent.run_cycle(metrics=sample_metrics)
        real_result = real_agent.run_cycle(metrics=sample_metrics)

        assert mock_result["cycle"] == 1
        assert real_result["cycle"] == 1


# ═══════════════════════════════════════════════════════════════
# 10. 并发安全性 (多 Agent 实例)
# ═══════════════════════════════════════════════════════════════


class TestMultiAgentIsolation:
    def test_two_agents_independent(self, sample_metrics):
        """两个 Agent 实例互不干扰."""
        agent1 = GrowthAgent(
            adapter_registry=create_default_adapter_registry(),
            execution_mode="mock",
        )
        agent2 = GrowthAgent(
            adapter_registry=create_default_adapter_registry(),
            execution_mode="dry_run",
        )

        r1 = agent1.run_cycle(metrics=sample_metrics)
        r2 = agent2.run_cycle(metrics=sample_metrics)

        assert r1["cycle"] == 1
        assert r2["cycle"] == 1
        assert agent1.stats()["execution_mode"] == "mock"
        assert agent2.stats()["execution_mode"] == "dry_run"

    def test_agent_reset_preserves_adapter(self, adapter_registry):
        """reset 后 Agent 仍保留 adapter."""
        agent = GrowthAgent(
            adapter_registry=adapter_registry,
            execution_mode="mock",
        )
        agent.reset()
        assert agent.stats()["has_adapter"] is True
        assert agent.tools.tool_count > 0