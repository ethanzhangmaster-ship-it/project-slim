"""E15.0.9 ExecutionRouter — 单元测试.

验证 ExecutionRouter 的完整功能:
  - 路由: 正确路由到适配器 (5 tests)
  - 安全: Safety Governor 集成 (4 tests)
  - 审计: Audit Hook 集成 (3 tests)
  - 钩子: Pre/Post hooks (3 tests)
  - 批量: execute_batch (3 tests)
  - 回滚: rollback (3 tests)
  - 统计: stats (2 tests)
  - 边界: 无适配器/无安全/异常 (7 tests)

总计: 30 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.adapter_router import (
    ExecutionRouter,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapter_registry import (
    AdapterRegistry,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapter_base import (
    ExecutionAdapter,
    AdapterExecutionResult,
    AdapterResultStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.growth_action import (
    ActionType,
    GrowthAction,
)


# ═══════════════════════════════════════════════════════════
# Mock Adapter
# ═══════════════════════════════════════════════════════════


class MockAdapter(ExecutionAdapter):
    """Mock 适配器."""

    def __init__(self, name: str = "MockAdapter", should_fail: bool = False):
        super().__init__(name=name)
        self.should_fail = should_fail
        self.executed_actions: list[GrowthAction] = []
        self.rollback_calls: list = []

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        self.executed_actions.append(action)
        if self.should_fail:
            self._record_failure()
            return AdapterExecutionResult.failure_result(action, error="mock failure", adapter_name=self._name)
        self._record_success()
        return AdapterExecutionResult.success_result(action, external_id="ext_123", adapter_name=self._name)

    def validate(self, action: GrowthAction) -> bool:
        return True

    def rollback(self, action, result):
        self.rollback_calls.append((action, result))
        return AdapterExecutionResult.success_result(action, adapter_name=self._name, rollback_action="restored")


class FailingValidateAdapter(MockAdapter):
    """校验失败的适配器."""

    def validate(self, action: GrowthAction) -> bool:
        return False


class ThrowingAdapter(MockAdapter):
    """执行时抛异常的适配器."""

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        raise RuntimeError("adapter crash")


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_action(action_type: ActionType = ActionType.PAUSE_CAMPAIGN, game_id: str = "P04", target: str = "camp_001") -> GrowthAction:
    return GrowthAction(game_id=game_id, action_type=action_type, target=target)


def make_router_with_adapter(adapter: ExecutionAdapter | None = None) -> ExecutionRouter:
    registry = AdapterRegistry()
    adapter = adapter or MockAdapter()
    registry.register(ActionType.PAUSE_CAMPAIGN, adapter)
    registry.register(ActionType.UPDATE_CAMPAIGN_BUDGET, adapter)
    return ExecutionRouter(registry)


# ═══════════════════════════════════════════════════════════
# Test Routing
# ═══════════════════════════════════════════════════════════


class TestRouting:
    """路由测试."""

    def test_execute_success(self):
        """成功执行."""
        adapter = MockAdapter()
        router = make_router_with_adapter(adapter)
        action = make_action()
        result = router.execute(action)
        assert result.success
        assert result.status == AdapterResultStatus.SUCCESS
        assert len(adapter.executed_actions) == 1

    def test_execute_failure(self):
        """执行失败."""
        adapter = MockAdapter(should_fail=True)
        router = make_router_with_adapter(adapter)
        result = router.execute(make_action())
        assert not result.success
        assert result.status == AdapterResultStatus.FAILED

    def test_no_adapter_registered(self):
        """无适配器注册."""
        registry = AdapterRegistry()
        router = ExecutionRouter(registry)
        result = router.execute(make_action())
        assert not result.success
        assert "No adapter registered" in result.error

    def test_validation_failed(self):
        """校验失败."""
        adapter = FailingValidateAdapter()
        router = make_router_with_adapter(adapter)
        result = router.execute(make_action())
        assert result.status == AdapterResultStatus.SKIPPED
        assert "Validation failed" in result.error

    def test_adapter_throws(self):
        """适配器抛出异常."""
        adapter = ThrowingAdapter()
        router = make_router_with_adapter(adapter)
        result = router.execute(make_action())
        assert not result.success
        assert "adapter crash" in result.error


# ═══════════════════════════════════════════════════════════
# Test Safety Governor Integration
# ═══════════════════════════════════════════════════════════


class TestSafetyIntegration:
    """Safety Governor 集成测试."""

    def test_safety_blocks_action(self):
        """安全策略阻止动作."""
        router = make_router_with_adapter()
        router.register_safety_governor(lambda a: False)
        result = router.execute(make_action())
        assert result.status == AdapterResultStatus.BLOCKED
        assert "Blocked by Safety Governor" in result.error

    def test_safety_allows_action(self):
        """安全策略允许动作."""
        router = make_router_with_adapter()
        router.register_safety_governor(lambda a: True)
        result = router.execute(make_action())
        assert result.success

    def test_safety_governor_exception(self):
        """安全策略异常."""
        router = make_router_with_adapter()
        router.register_safety_governor(lambda a: (_ for _ in ()).throw(RuntimeError("crash")))
        result = router.execute(make_action())
        assert result.status == AdapterResultStatus.BLOCKED
        assert "Safety governor error" in result.error

    def test_no_safety_governor(self):
        """无安全策略时正常执行."""
        router = make_router_with_adapter()
        result = router.execute(make_action())
        assert result.success


# ═══════════════════════════════════════════════════════════
# Test Hooks
# ═══════════════════════════════════════════════════════════


class TestHooks:
    """钩子测试."""

    def test_audit_hook_called(self):
        """审计钩子被调用."""
        router = make_router_with_adapter()
        audit_calls: list = []
        router.register_audit_hook(lambda a, r: audit_calls.append((a, r)))
        router.execute(make_action())
        assert len(audit_calls) == 1

    def test_pre_hook_called(self):
        """前置钩子被调用."""
        router = make_router_with_adapter()
        pre_calls: list = []
        router.register_pre_hook(lambda a: pre_calls.append(a))
        router.execute(make_action())
        assert len(pre_calls) == 1

    def test_post_hook_called(self):
        """后置钩子被调用."""
        router = make_router_with_adapter()
        post_calls: list = []
        router.register_post_hook(lambda a, r: post_calls.append((a, r)))
        router.execute(make_action())
        assert len(post_calls) == 1

    def test_multiple_audit_hooks(self):
        """多个审计钩子都被调用."""
        router = make_router_with_adapter()
        calls: list = []
        router.register_audit_hook(lambda a, r: calls.append(1))
        router.register_audit_hook(lambda a, r: calls.append(2))
        router.execute(make_action())
        assert len(calls) == 2

    def test_hook_exception_does_not_crash(self):
        """钩子异常不影响主流程."""
        router = make_router_with_adapter()
        router.register_pre_hook(lambda a: (_ for _ in ()).throw(RuntimeError("hook crash")))
        router.register_post_hook(lambda a, r: (_ for _ in ()).throw(RuntimeError("hook crash")))
        router.register_audit_hook(lambda a, r: (_ for _ in ()).throw(RuntimeError("audit crash")))
        result = router.execute(make_action())
        assert result.success  # 主流程不受影响


# ═══════════════════════════════════════════════════════════
# Test Batch Execution
# ═══════════════════════════════════════════════════════════


class TestBatchExecution:
    """批量执行测试."""

    def test_execute_batch_all_success(self):
        """批量执行全部成功."""
        router = make_router_with_adapter()
        actions = [make_action() for _ in range(5)]
        results = router.execute_batch(actions)
        assert len(results) == 5
        assert all(r.success for r in results)

    def test_execute_batch_stop_on_failure(self):
        """失败时停止."""
        adapter = MockAdapter(should_fail=True)
        router = make_router_with_adapter(adapter)
        actions = [make_action() for _ in range(5)]
        results = router.execute_batch(actions, stop_on_failure=True)
        assert len(results) == 5
        assert not results[0].success
        # 剩余动作被标记为跳过
        assert results[1].status == AdapterResultStatus.SKIPPED

    def test_execute_batch_continue_on_failure(self):
        """失败时继续."""
        adapter = MockAdapter(should_fail=True)
        router = make_router_with_adapter(adapter)
        actions = [make_action() for _ in range(3)]
        results = router.execute_batch(actions, stop_on_failure=False)
        assert len(results) == 3
        assert all(not r.success for r in results)


# ═══════════════════════════════════════════════════════════
# Test Rollback
# ═══════════════════════════════════════════════════════════


class TestRollback:
    """回滚测试."""

    def test_rollback_success(self):
        """成功回滚."""
        adapter = MockAdapter()
        router = make_router_with_adapter(adapter)
        action = make_action()
        result = router.execute(action)
        rollback_result = router.rollback(action, result)
        assert rollback_result.success
        assert len(adapter.rollback_calls) == 1

    def test_rollback_no_adapter(self):
        """回滚时无适配器."""
        registry = AdapterRegistry()
        router = ExecutionRouter(registry)
        result = router.rollback(make_action(), AdapterExecutionResult())
        assert not result.success
        assert "No adapter registered" in result.error

    def test_rollback_adapter_throws(self):
        """回滚时适配器异常."""
        class ThrowingRollbackAdapter(MockAdapter):
            def rollback(self, action, result):
                raise RuntimeError("rollback crash")

        router = make_router_with_adapter(ThrowingRollbackAdapter())
        action = make_action()
        result = router.execute(action)
        rollback_result = router.rollback(action, result)
        assert not rollback_result.success
        assert "rollback crash" in rollback_result.error


# ═══════════════════════════════════════════════════════════
# Test Stats
# ═══════════════════════════════════════════════════════════


class TestRouterStats:
    """路由器统计测试."""

    def test_stats_initial(self):
        """初始统计."""
        router = make_router_with_adapter()
        s = router.stats()
        assert s["route_count"] == 0
        assert s["success_count"] == 0
        assert s["blocked_count"] == 0

    def test_stats_after_execution(self):
        """执行后统计."""
        router = make_router_with_adapter()
        router.execute(make_action())
        s = router.stats()
        assert s["route_count"] == 1
        assert s["success_count"] == 1
        assert s["success_rate"] == 1.0

    def test_stats_after_blocked(self):
        """被阻止后统计."""
        router = make_router_with_adapter()
        router.register_safety_governor(lambda a: False)
        router.execute(make_action())
        s = router.stats()
        assert s["blocked_count"] == 1
        assert s["has_safety_governor"]


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_empty_registry(self):
        """空注册表."""
        router = ExecutionRouter()
        result = router.execute(make_action())
        assert not result.success

    def test_repr(self):
        """__repr__."""
        router = make_router_with_adapter()
        r = repr(router)
        assert "ExecutionRouter" in r

    def test_registry_property(self):
        """registry 属性."""
        registry = AdapterRegistry()
        router = ExecutionRouter(registry)
        assert router.registry is registry

    def test_safety_governor_receives_action(self):
        """Safety Governor 接收正确的 action."""
        router = make_router_with_adapter()
        received: list = []
        router.register_safety_governor(lambda a: received.append(a) or True)
        action = make_action()
        router.execute(action)
        assert len(received) == 1
        assert received[0] is action

    def test_audit_hook_receives_result(self):
        """审计钩子接收正确的结果."""
        router = make_router_with_adapter()
        received: list = []
        router.register_audit_hook(lambda a, r: received.append(r))
        action = make_action()
        result = router.execute(action)
        assert received[0] is result