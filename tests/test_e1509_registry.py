"""E15.0.9 AdapterRegistry — 单元测试.

验证 AdapterRegistry 的完整功能:
  - 注册: 单个/批量/平台/默认 (10 tests)
  - 查询: get/has/get_all/get_unique (7 tests)
  - 取消注册 (2 tests)
  - 统计 (3 tests)
  - 边界: 空注册/重复注册/None (4 tests)

总计: 26 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.adapter_registry import (
    AdapterRegistry,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapter_base import (
    ExecutionAdapter,
    AdapterExecutionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.growth_action import (
    ActionType,
    GrowthAction,
)


# ═══════════════════════════════════════════════════════════
# Mock Adapter
# ═══════════════════════════════════════════════════════════


class MockAdapter(ExecutionAdapter):
    """Mock 适配器 — 用于测试."""

    def __init__(self, name: str = "MockAdapter", should_fail: bool = False):
        super().__init__(name=name)
        self.should_fail = should_fail
        self.executed_actions: list[GrowthAction] = []

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        self.executed_actions.append(action)
        if self.should_fail:
            return AdapterExecutionResult.failure_result(action, error="mock failure", adapter_name=self._name)
        return AdapterExecutionResult.success_result(action, adapter_name=self._name)

    def validate(self, action: GrowthAction) -> bool:
        return True


# ═══════════════════════════════════════════════════════════
# Test Registration
# ═══════════════════════════════════════════════════════════


class TestRegistration:
    """注册测试."""

    def test_register_single(self):
        """注册单个适配器."""
        registry = AdapterRegistry()
        adapter = MockAdapter()
        registry.register(ActionType.PAUSE_CAMPAIGN, adapter)
        assert registry.has(ActionType.PAUSE_CAMPAIGN)
        assert registry.get(ActionType.PAUSE_CAMPAIGN) is adapter

    def test_register_overwrites(self):
        """重复注册覆盖前一个."""
        registry = AdapterRegistry()
        a1 = MockAdapter(name="first")
        a2 = MockAdapter(name="second")
        registry.register(ActionType.PAUSE_CAMPAIGN, a1)
        registry.register(ActionType.PAUSE_CAMPAIGN, a2)
        assert registry.get(ActionType.PAUSE_CAMPAIGN) is a2

    def test_register_many(self):
        """批量注册."""
        registry = AdapterRegistry()
        adapter = MockAdapter()
        registry.register_many({
            ActionType.PAUSE_CAMPAIGN: adapter,
            ActionType.RESUME_CAMPAIGN: adapter,
            ActionType.CREATE_CAMPAIGN: adapter,
        })
        assert len(registry) == 3
        assert registry.has(ActionType.PAUSE_CAMPAIGN)
        assert registry.has(ActionType.RESUME_CAMPAIGN)

    def test_register_platform(self):
        """按平台注册."""
        registry = AdapterRegistry()
        adapter = MockAdapter(name="MetaAdapter")
        meta_actions = [
            ActionType.UPDATE_CAMPAIGN_BUDGET,
            ActionType.PAUSE_CAMPAIGN,
            ActionType.RESUME_CAMPAIGN,
            ActionType.CREATE_CAMPAIGN,
            ActionType.UPLOAD_CREATIVE,
            ActionType.PAUSE_CREATIVE,
        ]
        registry.register_platform(adapter, meta_actions)
        assert len(registry) == 6
        for at in meta_actions:
            assert registry.get(at) is adapter

    def test_set_default_adapter(self):
        """设置默认适配器."""
        registry = AdapterRegistry()
        default = MockAdapter(name="Default")
        registry.set_default(default)
        # 未注册的类型返回默认适配器
        assert registry.get(ActionType.NOOP) is default
        assert registry.get(ActionType.PAUSE_CAMPAIGN) is default

    def test_default_overridden_by_explicit(self):
        """显式注册覆盖默认."""
        registry = AdapterRegistry()
        default = MockAdapter(name="Default")
        explicit = MockAdapter(name="Explicit")
        registry.set_default(default)
        registry.register(ActionType.PAUSE_CAMPAIGN, explicit)
        assert registry.get(ActionType.PAUSE_CAMPAIGN) is explicit
        assert registry.get(ActionType.NOOP) is default

    def test_no_default_returns_none(self):
        """无默认适配器时返回 None."""
        registry = AdapterRegistry()
        assert registry.get(ActionType.NOOP) is None

    def test_unregister(self):
        """取消注册."""
        registry = AdapterRegistry()
        adapter = MockAdapter()
        registry.register(ActionType.PAUSE_CAMPAIGN, adapter)
        registry.unregister(ActionType.PAUSE_CAMPAIGN)
        assert not registry.has(ActionType.PAUSE_CAMPAIGN)

    def test_unregister_nonexistent(self):
        """取消注册不存在的类型不报错."""
        registry = AdapterRegistry()
        registry.unregister(ActionType.NOOP)  # no error

    def test_register_preserves_unique_adapters_count(self):
        """同一适配器注册多个类型只算一个 unique."""
        registry = AdapterRegistry()
        adapter = MockAdapter()
        registry.register_many({
            ActionType.PAUSE_CAMPAIGN: adapter,
            ActionType.RESUME_CAMPAIGN: adapter,
        })
        assert len(registry.get_unique_adapters()) == 1


# ═══════════════════════════════════════════════════════════
# Test Query
# ═══════════════════════════════════════════════════════════


class TestQuery:
    """查询测试."""

    def test_get_registered(self):
        """获取已注册的适配器."""
        registry = AdapterRegistry()
        adapter = MockAdapter()
        registry.register(ActionType.PAUSE_CAMPAIGN, adapter)
        assert registry.get(ActionType.PAUSE_CAMPAIGN) is adapter

    def test_get_unregistered(self):
        """获取未注册的类型."""
        registry = AdapterRegistry()
        assert registry.get(ActionType.NOOP) is None

    def test_has_true(self):
        """has 返回 True."""
        registry = AdapterRegistry()
        registry.register(ActionType.PAUSE_CAMPAIGN, MockAdapter())
        assert registry.has(ActionType.PAUSE_CAMPAIGN)

    def test_has_false(self):
        """has 返回 False."""
        registry = AdapterRegistry()
        assert not registry.has(ActionType.NOOP)

    def test_get_all(self):
        """get_all 返回完整映射."""
        registry = AdapterRegistry()
        a1 = MockAdapter(name="A")
        a2 = MockAdapter(name="B")
        registry.register(ActionType.PAUSE_CAMPAIGN, a1)
        registry.register(ActionType.RESUME_CAMPAIGN, a2)
        all_mappings = registry.get_all()
        assert len(all_mappings) == 2
        assert all_mappings[ActionType.PAUSE_CAMPAIGN] is a1
        assert all_mappings[ActionType.RESUME_CAMPAIGN] is a2

    def test_get_registered_types(self):
        """get_registered_types 返回所有已注册类型."""
        registry = AdapterRegistry()
        registry.register(ActionType.PAUSE_CAMPAIGN, MockAdapter())
        registry.register(ActionType.RESUME_CAMPAIGN, MockAdapter())
        types = registry.get_registered_types()
        assert ActionType.PAUSE_CAMPAIGN in types
        assert ActionType.RESUME_CAMPAIGN in types

    def test_get_unique_adapters(self):
        """get_unique_adapters 去重."""
        registry = AdapterRegistry()
        a1 = MockAdapter(name="Meta")
        a2 = MockAdapter(name="Play")
        registry.register(ActionType.PAUSE_CAMPAIGN, a1)
        registry.register(ActionType.RESUME_CAMPAIGN, a1)
        registry.register(ActionType.PUBLISH_RELEASE, a2)
        unique = registry.get_unique_adapters()
        assert len(unique) == 2


# ═══════════════════════════════════════════════════════════
# Test Stats
# ═══════════════════════════════════════════════════════════


class TestStats:
    """统计测试."""

    def test_stats_empty(self):
        """空注册表统计."""
        registry = AdapterRegistry()
        s = registry.stats()
        assert s["total_registered"] == 0
        assert s["unique_adapters"] == 0
        assert not s["has_default"]

    def test_stats_with_registrations(self):
        """有注册的统计."""
        registry = AdapterRegistry()
        registry.register(ActionType.PAUSE_CAMPAIGN, MockAdapter())
        s = registry.stats()
        assert s["total_registered"] == 1
        assert s["unique_adapters"] == 1

    def test_stats_with_default(self):
        """有默认适配器的统计."""
        registry = AdapterRegistry()
        registry.set_default(MockAdapter())
        s = registry.stats()
        assert s["has_default"]


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_empty_registry(self):
        """空注册表."""
        registry = AdapterRegistry()
        assert len(registry) == 0
        assert registry.get_all() == {}
        assert registry.get_registered_types() == []
        assert registry.get_unique_adapters() == []

    def test_len(self):
        """__len__."""
        registry = AdapterRegistry()
        assert len(registry) == 0
        registry.register(ActionType.PAUSE_CAMPAIGN, MockAdapter())
        registry.register(ActionType.RESUME_CAMPAIGN, MockAdapter())
        assert len(registry) == 2

    def test_contains(self):
        """__contains__."""
        registry = AdapterRegistry()
        registry.register(ActionType.PAUSE_CAMPAIGN, MockAdapter())
        assert ActionType.PAUSE_CAMPAIGN in registry
        assert ActionType.NOOP not in registry

    def test_repr(self):
        """__repr__."""
        registry = AdapterRegistry()
        r = repr(registry)
        assert "AdapterRegistry" in r