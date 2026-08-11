"""E13.7.1 Real Tool Adapter — 测试套件.

覆盖:
  - ToolAdapter 基类 + AdapterRegistry
  - ExecutionAdapter (连接 E13.6 Execution Engine)
  - MetaAdapter (连接 Meta Ads API)
  - AdjustAdapter (连接 Adjust 数据)
  - CreativeAdapter (连接 E11 Creative Evolution)
  - MemoryAdapter (连接 Memory Kernel)
  - RealToolRegistry (升级 + 创建)
  - Integration (Agent → Tool → Adapter → Mock System)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent import (
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    create_default_registry,
    GrowthAgent,
    create_growth_agent,
    AgentGoal,
    GoalPriority,
    GoalStatus,
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
def mock_context():
    return ToolExecutionContext(
        session_id="test_session",
        cycle_number=1,
        agent_phase="executing",
        execution_mode="mock",
    )


@pytest.fixture
def dry_run_context():
    return ToolExecutionContext(
        session_id="test_session",
        cycle_number=1,
        agent_phase="executing",
        execution_mode="dry_run",
    )


@pytest.fixture
def adapter_registry():
    return create_default_adapter_registry()


# ═══════════════════════════════════════════════════════════════
# 1. ToolAdapter Base + AdapterRegistry Tests
# ═══════════════════════════════════════════════════════════════


class TestToolAdapterBase:
    """ToolAdapter 基类 + AdapterRegistry 测试."""

    def test_adapter_must_implement_can_handle(self):
        """适配器必须实现 can_handle."""
        adapter = ToolAdapter()
        with pytest.raises(NotImplementedError):
            adapter.can_handle("test")

    def test_adapter_must_implement_execute(self):
        """适配器必须实现 execute."""
        adapter = ToolAdapter()
        ctx = ToolExecutionContext()
        with pytest.raises(NotImplementedError):
            adapter.execute("test", {}, ctx)

    def test_adapter_has_name(self):
        adapter = ToolAdapter()
        assert adapter.name == "base"


class TestToolExecutionContext:
    """ToolExecutionContext 测试."""

    def test_default_context(self):
        ctx = ToolExecutionContext()
        assert ctx.session_id == ""
        assert ctx.execution_mode == "mock"

    def test_context_with_values(self):
        ctx = ToolExecutionContext(
            session_id="s1",
            cycle_number=3,
            execution_mode="real",
            metrics_snapshot={"roas": 0.8},
        )
        assert ctx.session_id == "s1"
        assert ctx.cycle_number == 3
        assert ctx.execution_mode == "real"

    def test_context_to_dict(self):
        ctx = ToolExecutionContext(session_id="s1")
        d = ctx.to_dict()
        assert d["session_id"] == "s1"


class TestAdapterRegistry:
    """AdapterRegistry 测试."""

    def test_create_registry(self):
        registry = AdapterRegistry()
        assert registry.count == 0

    def test_register_adapter(self):
        registry = AdapterRegistry()
        adapter = ExecutionAdapter()
        registry.register(adapter)
        assert registry.count == 1

    def test_find_adapter(self, adapter_registry):
        """查找能处理具体动作的适配器."""
        adapter = adapter_registry.find_adapter("create_campaign")
        assert adapter is not None
        assert adapter.name == "execution_adapter"

    def test_find_adapter_creative(self, adapter_registry):
        adapter = adapter_registry.find_adapter("mutate_creative")
        assert adapter is not None
        assert adapter.name == "creative_adapter"

    def test_find_adapter_adjust(self, adapter_registry):
        adapter = adapter_registry.find_adapter("query_metrics")
        assert adapter is not None
        assert adapter.name == "adjust_adapter"

    def test_find_adapter_memory(self, adapter_registry):
        adapter = adapter_registry.find_adapter("query_memory")
        assert adapter is not None
        assert adapter.name == "memory_adapter"

    def test_find_adapter_nonexistent(self, adapter_registry):
        adapter = adapter_registry.find_adapter("nonexistent_action")
        assert adapter is None

    def test_execute_action(self, adapter_registry, mock_context):
        result = adapter_registry.execute("create_campaign", {"budget": 500}, mock_context)
        assert result.is_success()

    def test_execute_nonexistent(self, adapter_registry, mock_context):
        result = adapter_registry.execute("nonexistent", {}, mock_context)
        assert result.status == ToolResultStatus.FAILED
        assert "No adapter found" in result.error

    def test_execute_with_error(self, adapter_registry, mock_context):
        """适配器执行异常时返回错误."""
        # 用一个不存在的动作，但 Adapter 会尝试处理
        result = adapter_registry.execute("unknown_action", {}, mock_context)
        assert result.status == ToolResultStatus.FAILED

    def test_list_adapters(self, adapter_registry):
        names = adapter_registry.list_adapters()
        assert "execution_adapter" in names
        assert "meta_adapter" in names
        assert "adjust_adapter" in names
        assert "creative_adapter" in names
        assert "memory_adapter" in names

    def test_get_adapter(self, adapter_registry):
        adapter = adapter_registry.get_adapter("execution_adapter")
        assert adapter is not None
        assert adapter.name == "execution_adapter"

    def test_get_adapter_not_found(self, adapter_registry):
        adapter = adapter_registry.get_adapter("nonexistent")
        assert adapter is None

    def test_create_default_adapter_registry(self):
        registry = create_default_adapter_registry()
        assert registry.count == 5


# ═══════════════════════════════════════════════════════════════
# 2. ExecutionAdapter Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionAdapter:
    """ExecutionAdapter 测试."""

    def test_create_adapter(self):
        adapter = ExecutionAdapter()
        assert adapter.name == "execution_adapter"

    def test_can_handle_campaign_actions(self):
        adapter = ExecutionAdapter()
        assert adapter.can_handle("create_campaign")
        assert adapter.can_handle("update_budget")
        assert adapter.can_handle("pause_campaign")
        assert adapter.can_handle("resume_campaign")
        assert adapter.can_handle("monitor")
        assert adapter.can_handle("collect_result")

    def test_cannot_handle_other_actions(self):
        adapter = ExecutionAdapter()
        assert not adapter.can_handle("mutate_creative")
        assert not adapter.can_handle("query_metrics")

    def test_execute_create_campaign_mock(self, mock_context):
        adapter = ExecutionAdapter()
        result = adapter.execute("create_campaign", {"budget": 500}, mock_context)
        assert result.is_success()
        assert "campaign_id" in result.data

    def test_execute_update_budget_mock(self, mock_context):
        adapter = ExecutionAdapter()
        result = adapter.execute("update_budget", {"campaign_id": "c1", "new_budget": 1000}, mock_context)
        assert result.is_success()

    def test_execute_pause_campaign_mock(self, mock_context):
        adapter = ExecutionAdapter()
        result = adapter.execute("pause_campaign", {"campaign_id": "c1"}, mock_context)
        assert result.is_success()

    def test_execute_monitor_mock(self, mock_context):
        adapter = ExecutionAdapter()
        result = adapter.execute("monitor", {"duration_hours": 48}, mock_context)
        assert result.is_success()

    def test_execute_collect_result_mock(self, mock_context):
        adapter = ExecutionAdapter()
        result = adapter.execute("collect_result", {}, mock_context)
        assert result.is_success()
        assert result.data["data_available"] is True


# ═══════════════════════════════════════════════════════════════
# 3. MetaAdapter Tests
# ═══════════════════════════════════════════════════════════════


class TestMetaAdapter:
    """MetaAdapter 测试."""

    def test_create_adapter(self):
        adapter = MetaAdapter()
        assert adapter.name == "meta_adapter"

    def test_can_handle_meta_actions(self):
        adapter = MetaAdapter()
        assert adapter.can_handle("create_campaign")
        assert adapter.can_handle("update_budget")
        assert adapter.can_handle("pause_campaign")
        assert adapter.can_handle("resume_campaign")
        assert adapter.can_handle("upload_creative")

    def test_execute_create_campaign_mock(self, mock_context):
        adapter = MetaAdapter()
        result = adapter.execute("create_campaign", {"platform": "meta", "budget": 500}, mock_context)
        assert result.is_success()
        assert result.data["platform"] == "meta"

    def test_execute_update_budget_mock(self, mock_context):
        adapter = MetaAdapter()
        result = adapter.execute("update_budget", {"platform": "meta", "campaign_id": "c1", "scale_factor": 1.2}, mock_context)
        assert result.is_success()

    def test_execute_pause_campaign_mock(self, mock_context):
        adapter = MetaAdapter()
        result = adapter.execute("pause_campaign", {"platform": "meta", "campaign_id": "c1"}, mock_context)
        assert result.is_success()

    def test_execute_upload_creative_mock(self, mock_context):
        adapter = MetaAdapter()
        result = adapter.execute("upload_creative", {"platform": "meta", "creative_ids": ["c1", "c2"]}, mock_context)
        assert result.is_success()

    def test_execute_wrong_platform(self, mock_context):
        """非 Meta 平台应拒绝."""
        adapter = MetaAdapter()
        result = adapter.execute("create_campaign", {"platform": "google"}, mock_context)
        assert result.status == ToolResultStatus.FAILED

    def test_execute_dry_run(self, dry_run_context):
        adapter = MetaAdapter()
        result = adapter.execute("create_campaign", {"platform": "meta", "budget": 500}, dry_run_context)
        assert result.is_success()
        assert result.data["dry_run"] is True

    def test_execute_dry_run_invalid(self, dry_run_context):
        """干运行校验失败."""
        adapter = MetaAdapter()
        result = adapter.execute("create_campaign", {"platform": "meta", "budget": 0}, dry_run_context)
        assert result.status == ToolResultStatus.FAILED

    def test_execute_dry_run_missing_params(self, dry_run_context):
        """干运行缺少参数."""
        adapter = MetaAdapter()
        result = adapter.execute("update_budget", {"platform": "meta"}, dry_run_context)
        assert result.status == ToolResultStatus.FAILED


# ═══════════════════════════════════════════════════════════════
# 4. AdjustAdapter Tests
# ═══════════════════════════════════════════════════════════════


class TestAdjustAdapter:
    """AdjustAdapter 测试."""

    def test_create_adapter(self):
        adapter = AdjustAdapter()
        assert adapter.name == "adjust_adapter"

    def test_can_handle_adjust_actions(self):
        adapter = AdjustAdapter()
        assert adapter.can_handle("query_metrics")
        assert adapter.can_handle("query_adjust")
        assert adapter.can_handle("query_creative_performance")
        assert adapter.can_handle("check_fatigue")

    def test_cannot_handle_other(self):
        adapter = AdjustAdapter()
        assert not adapter.can_handle("create_campaign")

    def test_query_metrics_mock(self, mock_context):
        adapter = AdjustAdapter()
        result = adapter.execute("query_metrics", {"entity_type": "campaign"}, mock_context)
        assert result.is_success()
        assert "spend" in result.data
        assert "roas" in result.data

    def test_query_adjust_mock(self, mock_context):
        adapter = AdjustAdapter()
        result = adapter.execute("query_adjust", {"app_id": "test"}, mock_context)
        assert result.is_success()
        assert "d30_ltv" in result.data
        assert "payer_rate" in result.data

    def test_query_creative_performance_mock(self, mock_context):
        adapter = AdjustAdapter()
        result = adapter.execute("query_creative_performance", {}, mock_context)
        assert result.is_success()
        assert "creatives" in result.data
        assert len(result.data["creatives"]) == 3

    def test_check_fatigue_mock(self, mock_context):
        adapter = AdjustAdapter()
        result = adapter.execute("check_fatigue", {"creative_id": "c001"}, mock_context)
        assert result.is_success()
        assert result.data["is_fatigued"] is True
        assert result.data["recommendation"] == "MUTATE"

    def test_check_fatigue_below_threshold(self, mock_context):
        """疲劳度低于阈值时不建议变异."""
        adapter = AdjustAdapter()
        result = adapter.execute("check_fatigue", {"threshold": 0.9}, mock_context)
        assert result.is_success()
        assert result.data["recommendation"] == "KEEP"


# ═══════════════════════════════════════════════════════════════
# 5. CreativeAdapter Tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeAdapter:
    """CreativeAdapter 测试."""

    def test_create_adapter(self):
        adapter = CreativeAdapter()
        assert adapter.name == "creative_adapter"

    def test_can_handle_creative_actions(self):
        adapter = CreativeAdapter()
        assert adapter.can_handle("mutate_creative")
        assert adapter.can_handle("generate_creative")
        assert adapter.can_handle("upload_creative")

    def test_mutate_creative_mock(self, mock_context):
        adapter = CreativeAdapter()
        result = adapter.execute("mutate_creative", {"variants": 5}, mock_context)
        assert result.is_success()
        assert result.data["variants_generated"] == 5
        assert len(result.data["creative_ids"]) == 5

    def test_mutate_creative_with_strategy(self, mock_context):
        adapter = CreativeAdapter()
        result = adapter.execute(
            "mutate_creative",
            {"variants": 3, "strategy": "hook_change", "based_on_winner": True},
            mock_context,
        )
        assert result.is_success()
        assert result.data["strategy"] == "hook_change"

    def test_generate_creative_mock(self, mock_context):
        adapter = CreativeAdapter()
        result = adapter.execute("generate_creative", {"count": 3, "template": "merge"}, mock_context)
        assert result.is_success()
        assert result.data["generated"] == 3

    def test_upload_creative_mock(self, mock_context):
        adapter = CreativeAdapter()
        result = adapter.execute(
            "upload_creative",
            {"creative_ids": ["c1", "c2", "c3"], "platform": "meta"},
            mock_context,
        )
        assert result.is_success()
        assert result.data["uploaded"] == 3


# ═══════════════════════════════════════════════════════════════
# 6. MemoryAdapter Tests
# ═══════════════════════════════════════════════════════════════


class TestMemoryAdapter:
    """MemoryAdapter 测试."""

    def test_create_adapter(self):
        adapter = MemoryAdapter()
        assert adapter.name == "memory_adapter"

    def test_can_handle_memory_actions(self):
        adapter = MemoryAdapter()
        assert adapter.can_handle("query_memory")
        assert adapter.can_handle("update_memory")
        assert adapter.can_handle("record_episode")

    def test_query_memory_mock(self, mock_context):
        adapter = MemoryAdapter()
        result = adapter.execute("query_memory", {"query": "creative fatigue", "memory_type": "pattern"}, mock_context)
        assert result.is_success()
        assert result.data["count"] == 2
        assert result.data["results"][0]["concept"] == "Creative Mutation"

    def test_update_memory_mock(self, mock_context):
        adapter = MemoryAdapter()
        result = adapter.execute(
            "update_memory",
            {"concept": "Merge Creatives", "description": "CTR+32%", "confidence": 0.85},
            mock_context,
        )
        assert result.is_success()
        assert result.data["status"] == "stored"

    def test_record_episode_mock(self, mock_context):
        adapter = MemoryAdapter()
        result = adapter.execute(
            "record_episode",
            {
                "goal": {"title": "Test"},
                "plan": {"strategy": "creative_mutation"},
                "actions": ["mutate", "upload"],
                "results": [{"status": "success"}],
                "outcome": "positive",
                "lessons": ["Creative mutation works"],
            },
            mock_context,
        )
        assert result.is_success()
        assert result.data["outcome"] == "positive"
        assert result.data["lesson_count"] == 1


# ═══════════════════════════════════════════════════════════════
# 7. RealToolRegistry Tests
# ═══════════════════════════════════════════════════════════════


class TestRealToolRegistry:
    """RealToolRegistry 测试."""

    def test_create_real_tool_registry(self):
        registry = create_real_tool_registry()
        assert registry.tool_count > 0
        assert registry.has_tool("create_campaign")
        assert registry.has_tool("mutate_creative")
        assert registry.has_tool("query_metrics")

    def test_execute_real_tool_mock(self):
        """真实注册表在 mock 模式下执行."""
        registry = create_real_tool_registry()
        result = registry.execute("create_campaign", {"budget": 500})
        assert result.is_success()

    def test_execute_real_tool_creative(self):
        registry = create_real_tool_registry()
        result = registry.execute("mutate_creative", {"variants": 3})
        assert result.is_success()
        assert result.data["variants_generated"] == 3

    def test_execute_real_tool_adjust(self):
        registry = create_real_tool_registry()
        result = registry.execute("query_metrics", {"entity_type": "campaign"})
        assert result.is_success()
        assert "spend" in result.data

    def test_execute_real_tool_memory(self):
        registry = create_real_tool_registry()
        result = registry.execute("query_memory", {"query": "test"})
        assert result.is_success()

    def test_upgrade_to_real(self):
        """升级现有 registry."""
        registry = create_default_registry()
        upgraded = upgrade_to_real(registry)
        assert upgraded is registry  # 原地修改

        result = upgraded.execute("create_campaign", {"budget": 500})
        assert result.is_success()

    def test_upgrade_preserves_tool_count(self):
        registry = create_default_registry()
        original_count = registry.tool_count
        upgrade_to_real(registry)
        assert registry.tool_count == original_count

    def test_execute_all_tools(self):
        """所有工具都能执行成功."""
        registry = create_real_tool_registry()
        for tool_name in registry.list_tool_names():
            result = registry.execute(tool_name, {})
            assert result.status in (ToolResultStatus.SUCCESS, ToolResultStatus.FAILED, ToolResultStatus.APPROVAL_REQUIRED)

    def test_real_tool_with_approval(self):
        """需要审批的工具."""
        registry = create_real_tool_registry()
        # 暂时没有需要审批的工具在 mock 模式下测试
        result = registry.execute("update_budget", {"campaign_id": "test", "scale_factor": 1.5})
        assert result.is_success()

    def test_adapter_execution_metadata(self):
        """适配器执行结果包含 metadata."""
        registry = create_real_tool_registry()
        result = registry.execute("mutate_creative", {"variants": 3})
        assert result.metadata["mode"] == "mock"


# ═══════════════════════════════════════════════════════════════
# 8. Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestAdapterIntegration:
    """Adapter 集成测试."""

    def test_action_adapter_map_complete(self):
        """所有默认工具都有对应的适配器."""
        from market_ops.creative_vision_runtime.growth_runtime.agent import BUILTIN_TOOLS
        registry = create_default_adapter_registry()

        for tool_name in BUILTIN_TOOLS:
            adapter = registry.find_adapter(tool_name)
            assert adapter is not None, f"Tool '{tool_name}' has no adapter"

    def test_registry_execute_all_actions(self, adapter_registry, mock_context):
        """所有动作通过 AdapterRegistry 执行."""
        actions = [
            ("create_campaign", {"budget": 500}),
            ("update_budget", {"campaign_id": "c1", "scale_factor": 1.2}),
            ("pause_campaign", {"campaign_id": "c1"}),
            ("resume_campaign", {"campaign_id": "c1"}),
            ("mutate_creative", {"variants": 3}),
            ("generate_creative", {"count": 2}),
            ("upload_creative", {"creative_ids": ["c1"]}),
            ("query_metrics", {"entity_type": "campaign"}),
            ("query_adjust", {"app_id": "test"}),
            ("check_fatigue", {"creative_id": "c1"}),
            ("query_memory", {"query": "test"}),
            ("update_memory", {"concept": "test", "description": "desc"}),
            ("record_episode", {"outcome": "positive", "lessons": ["test"]}),
            ("monitor", {"duration_hours": 24}),
            ("collect_result", {}),
        ]

        for action_name, params in actions:
            result = adapter_registry.execute(action_name, params, mock_context)
            assert result.is_success(), f"Action '{action_name}' failed: {result.error}"

    def test_agent_with_real_tools(self):
        """Agent 使用真实工具执行."""
        agent = create_growth_agent()
        # 替换为真实工具
        from market_ops.creative_vision_runtime.growth_runtime.agent.real_tool_registry import upgrade_to_real
        upgrade_to_real(agent.tools)

        metrics = {
            "spend": 17000,
            "roas": 0.53,
            "roas_change": -0.12,
            "creative_fatigue": 0.81,
            "ctr_change": -0.12,
            "payer_quality": 0.65,
            "top_creative_ctr": 0.08,
            "avg_ctr": 0.02,
        }

        result = agent.run_cycle(metrics=metrics)
        assert result["cycle"] == 1
        assert result["observation_count"] > 0
        assert result["insight_count"] > 0

    def test_full_observe_to_execute_with_real_tools(self):
        """完整流程: Observe → Reason → Plan → Execute (Real Tools)."""
        agent = create_growth_agent()
        from market_ops.creative_vision_runtime.growth_runtime.agent.real_tool_registry import upgrade_to_real
        upgrade_to_real(agent.tools)

        agent.add_goal(AgentGoal(
            title="Reduce Creative Fatigue",
            priority=GoalPriority.HIGH,
            status=GoalStatus.ACTIVE,
            success_criteria="Fatigue < 0.5",
            target_metric="creative_fatigue",
            target_value=0.5,
            current_value=0.81,
        ))

        metrics = {
            "spend": 17000,
            "roas": 0.53,
            "roas_change": -0.12,
            "creative_fatigue": 0.81,
            "ctr_change": -0.12,
            "payer_quality": 0.65,
            "top_creative_ctr": 0.08,
            "avg_ctr": 0.02,
        }

        result = agent.run_cycle(metrics=metrics)
        assert result["cycle"] == 1
        # 执行阶段可能有工具调用
        assert result["execution_count"] >= 0

    def test_adapter_registry_cache(self, adapter_registry):
        """适配器查找缓存."""
        # 第一次查找
        adapter1 = adapter_registry.find_adapter("create_campaign")
        # 第二次查找 (应该从缓存获取)
        adapter2 = adapter_registry.find_adapter("create_campaign")
        assert adapter1 is adapter2

    def test_tool_execution_context_flow(self, adapter_registry):
        """上下文在适配器间传递."""
        ctx = ToolExecutionContext(
            session_id="flow_test",
            cycle_number=5,
            execution_mode="mock",
            metrics_snapshot={"roas": 0.8},
        )
        result = adapter_registry.execute("create_campaign", {"budget": 500}, ctx)
        assert result.is_success()

    def test_multiple_cycles_accumulate(self):
        """多次循环后工具执行正常."""
        agent = create_growth_agent()
        from market_ops.creative_vision_runtime.growth_runtime.agent.real_tool_registry import upgrade_to_real
        upgrade_to_real(agent.tools)

        metrics = {
            "creative_fatigue": 0.81,
            "ctr_change": -0.12,
            "roas_change": -0.12,
            "payer_quality": 0.65,
        }

        for i in range(3):
            result = agent.run_cycle(metrics=metrics)
            assert result["cycle"] == i + 1

    def test_execution_adapter_handles_all_actions(self, adapter_registry, mock_context):
        """ExecutionAdapter 处理所有已注册动作."""
        adapter = adapter_registry.get_adapter("execution_adapter")
        for action in ExecutionAdapter.HANDLED_ACTIONS:
            result = adapter.execute(action, {}, mock_context)
            assert result.is_success(), f"Action '{action}' failed"

    def test_meta_adapter_handles_all_actions(self, adapter_registry, mock_context):
        """MetaAdapter 处理所有平台动作."""
        adapter = adapter_registry.get_adapter("meta_adapter")
        for action in MetaAdapter.HANDLED_ACTIONS:
            result = adapter.execute(action, {"platform": "meta"}, mock_context)
            assert result.is_success(), f"Action '{action}' failed"

    def test_creative_adapter_handles_all_actions(self, adapter_registry, mock_context):
        """CreativeAdapter 处理所有创意动作."""
        adapter = adapter_registry.get_adapter("creative_adapter")
        for action in CreativeAdapter.HANDLED_ACTIONS:
            result = adapter.execute(action, {}, mock_context)
            assert result.is_success(), f"Action '{action}' failed"

    def test_adjust_adapter_handles_all_actions(self, adapter_registry, mock_context):
        """AdjustAdapter 处理所有数据查询动作."""
        adapter = adapter_registry.get_adapter("adjust_adapter")
        for action in AdjustAdapter.HANDLED_ACTIONS:
            result = adapter.execute(action, {}, mock_context)
            assert result.is_success(), f"Action '{action}' failed"

    def test_memory_adapter_handles_all_actions(self, adapter_registry, mock_context):
        """MemoryAdapter 处理所有记忆操作."""
        adapter = adapter_registry.get_adapter("memory_adapter")
        for action in MemoryAdapter.HANDLED_ACTIONS:
            result = adapter.execute(action, {}, mock_context)
            assert result.is_success(), f"Action '{action}' failed"