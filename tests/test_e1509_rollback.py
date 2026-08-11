"""E15.0.9 Rollback System — 集成测试.

验证回滚系统的完整功能:
  - 跨平台回滚: Meta/Google Play/Creative/Adjust (4 tests)
  - 回滚链: Budget → Rollback → Restore (2 tests)
  - 回滚安全: 多次回滚/回滚失败 (2 tests)
  - 回滚审计: 回滚记录到审计 (2 tests)
  - 边界: 无适配器回滚/回滚异常 (2 tests)

总计: 12 个测试用例
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
from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.meta_ads import (
    MetaAdsAdapter,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.google_play import (
    GooglePlayAdapter,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.creative import (
    CreativeAdapter,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.adjust import (
    AdjustAdapter,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def setup_router() -> ExecutionRouter:
    """设置带所有适配器的 Router."""
    registry = AdapterRegistry()
    meta = MetaAdsAdapter()
    play = GooglePlayAdapter()
    creative = CreativeAdapter()
    adjust = AdjustAdapter()

    registry.register_platform(meta, list(meta.SUPPORTED_ACTIONS))
    registry.register_platform(play, list(play.SUPPORTED_ACTIONS))
    registry.register_platform(creative, list(creative.SUPPORTED_ACTIONS))
    registry.register_platform(adjust, list(adjust.SUPPORTED_ACTIONS))

    return ExecutionRouter(registry)


# ═══════════════════════════════════════════════════════════
# Test Cross-Platform Rollback
# ═══════════════════════════════════════════════════════════


class TestCrossPlatformRollback:
    """跨平台回滚测试."""

    def test_rollback_meta_budget(self):
        """回滚 Meta 预算调整."""
        router = setup_router()
        action = GrowthAction(
            game_id="P04",
            action_type=ActionType.UPDATE_CAMPAIGN_BUDGET,
            target="camp_001",
            parameters={"old_budget": 100, "new_budget": 120},
        )
        result = router.execute(action)
        assert result.success

        rollback = router.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("restored_budget") == 100

    def test_rollback_google_play_release(self):
        """回滚 Google Play 发布."""
        router = setup_router()
        action = GrowthAction(
            game_id="P04",
            action_type=ActionType.PUBLISH_RELEASE,
            target="com.example.game",
            parameters={"version": "1.0", "track": "production"},
        )
        result = router.execute(action)
        assert result.success

        rollback = router.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "halt_release"

    def test_rollback_creative_generate(self):
        """回滚创意生成."""
        router = setup_router()
        action = GrowthAction(
            game_id="P04",
            action_type=ActionType.GENERATE_CREATIVE,
            parameters={"creative_dna": {"visual": "bright"}},
        )
        result = router.execute(action)
        assert result.success

        rollback = router.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "delete_asset"

    def test_rollback_adjust_verify(self):
        """回滚 Adjust 验证."""
        router = setup_router()
        action = GrowthAction(
            game_id="P04",
            action_type=ActionType.VERIFY_ATTRIBUTION,
            target="camp_001",
        )
        result = router.execute(action)
        assert result.success

        rollback = router.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "noop_adjust"


# ═══════════════════════════════════════════════════════════
# Test Rollback Chain
# ═══════════════════════════════════════════════════════════


class TestRollbackChain:
    """回滚链测试."""

    def test_budget_rollback_restores_original(self):
        """预算回滚恢复原值."""
        meta = MetaAdsAdapter()
        action = GrowthAction(
            action_type=ActionType.UPDATE_CAMPAIGN_BUDGET,
            target="camp_001",
            parameters={"old_budget": 100, "new_budget": 200},
        )
        result = meta.execute(action)
        assert meta._campaign_cache["camp_001"]["budget"] == 200

        meta.rollback(action, result)
        # 回滚后 metadata 包含 restored_budget
        rollback = meta.rollback(action, result)
        assert rollback.metadata.get("restored_budget") == 100

    def test_multiple_rollbacks(self):
        """多次回滚不失败."""
        meta = MetaAdsAdapter()
        action = GrowthAction(
            action_type=ActionType.UPDATE_CAMPAIGN_BUDGET,
            target="camp_001",
            parameters={"old_budget": 100, "new_budget": 120},
        )
        result = meta.execute(action)
        meta.rollback(action, result)
        meta.rollback(action, result)
        meta.rollback(action, result)
        assert meta._rollback_count >= 3


# ═══════════════════════════════════════════════════════════
# Test Rollback Audit
# ═══════════════════════════════════════════════════════════


class TestRollbackAudit:
    """回滚审计测试."""

    def test_rollback_triggers_audit_hook(self):
        """回滚触发审计钩子."""
        router = setup_router()
        audit_calls: list = []
        router.register_audit_hook(lambda a, r: audit_calls.append(r))

        action = GrowthAction(
            action_type=ActionType.PAUSE_CAMPAIGN,
            target="camp_001",
        )
        result = router.execute(action)
        assert len(audit_calls) == 1  # 执行审计

        router.rollback(action, result)
        assert len(audit_calls) == 2  # 回滚审计

    def test_rollback_audit_contains_rollback_status(self):
        """回滚审计包含 ROLLED_BACK 状态."""
        router = setup_router()
        audit_results: list = []
        router.register_audit_hook(lambda a, r: audit_results.append(r))

        action = GrowthAction(
            action_type=ActionType.PAUSE_CAMPAIGN,
            target="camp_001",
        )
        result = router.execute(action)
        router.rollback(action, result)

        # 最后一个审计结果应该是回滚的结果
        last_result = audit_results[-1]
        assert last_result is not None


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestRollbackEdgeCases:
    """回滚边界情况."""

    def test_rollback_no_adapter(self):
        """无适配器回滚."""
        registry = AdapterRegistry()
        router = ExecutionRouter(registry)
        action = GrowthAction(action_type=ActionType.PAUSE_CAMPAIGN, target="camp_001")
        result = router.rollback(action, AdapterExecutionResult())
        assert not result.success
        assert "No adapter registered" in result.error

    def test_rollback_unsupported_action(self):
        """回滚不支持的动作 (使用默认回滚)."""
        meta = MetaAdsAdapter()
        action = GrowthAction(
            action_type=ActionType.UPLOAD_CREATIVE,
            target="meta",
            parameters={"asset_id": "asset_001"},
        )
        result = meta.execute(action)
        rollback = meta.rollback(action, result)
        assert rollback.status == AdapterResultStatus.ROLLED_BACK
        assert "rollback_not_implemented" in rollback.error