"""E15.0.9 AdjustAdapter — 单元测试.

验证 AdjustAdapter 的完整功能:
  - 归因验证: 正常/带 metrics (2 tests)
  - 元数据同步 (2 tests)
  - 校验: validate (3 tests)
  - 回滚: rollback (2 tests)
  - 统计: stats (2 tests)
  - 边界: 不支持的动作/错误处理 (3 tests)

总计: 14 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.adjust import (
    AdjustAdapter,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.adapter_base import (
    AdapterExecutionResult,
    AdapterResultStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.growth_action import (
    ActionType,
    GrowthAction,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_action(action_type: ActionType, target: str = "", **params) -> GrowthAction:
    return GrowthAction(
        game_id="P04",
        action_type=action_type,
        target=target,
        parameters=params,
    )


# ═══════════════════════════════════════════════════════════
# Test Verify Attribution
# ═══════════════════════════════════════════════════════════


class TestVerifyAttribution:
    """归因验证测试."""

    def test_verify_with_metrics(self):
        """带指标验证."""
        adapter = AdjustAdapter()
        expected = {"spend": 500, "revenue": 1000, "impressions": 10000, "clicks": 500, "installs": 200, "roas": 2.0}
        action = make_action(ActionType.VERIFY_ATTRIBUTION, "camp_001", expected_metrics=expected)
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("adjust_verify_")
        assert result.metadata["verified"]
        assert result.metadata["metrics"]["spend"] == 500

    def test_verify_empty_metrics(self):
        """空指标验证."""
        adapter = AdjustAdapter()
        action = make_action(ActionType.VERIFY_ATTRIBUTION, "camp_001")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["verified"]


# ═══════════════════════════════════════════════════════════
# Test Sync Metadata
# ═══════════════════════════════════════════════════════════


class TestSyncMetadata:
    """元数据同步测试."""

    def test_sync_metadata_success(self):
        """成功同步元数据."""
        adapter = AdjustAdapter()
        action = make_action(ActionType.SYNC_METADATA, metadata={"campaign_id": "camp_001", "creative_id": "creative_001"})
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("adjust_sync_")
        assert "campaign_id" in result.metadata["synced_fields"]

    def test_sync_accumulates(self):
        """同步记录累积."""
        adapter = AdjustAdapter()
        adapter.execute(make_action(ActionType.SYNC_METADATA, metadata={"key": "val1"}))
        adapter.execute(make_action(ActionType.SYNC_METADATA, metadata={"key": "val2"}))
        assert len(adapter._metadata_syncs) == 2


# ═══════════════════════════════════════════════════════════
# Test Validation
# ═══════════════════════════════════════════════════════════


class TestValidation:
    """校验测试."""

    def test_validate_verify_with_target(self):
        """校验归因验证 (有 target)."""
        adapter = AdjustAdapter()
        assert adapter.validate(make_action(ActionType.VERIFY_ATTRIBUTION, "camp_001"))

    def test_validate_verify_with_metrics(self):
        """校验归因验证 (有 expected_metrics)."""
        adapter = AdjustAdapter()
        assert adapter.validate(make_action(ActionType.VERIFY_ATTRIBUTION, expected_metrics={"spend": 100}))

    def test_validate_sync_metadata(self):
        """校验元数据同步."""
        adapter = AdjustAdapter()
        assert adapter.validate(make_action(ActionType.SYNC_METADATA, metadata={"key": "val"}))
        assert not adapter.validate(make_action(ActionType.SYNC_METADATA))


# ═══════════════════════════════════════════════════════════
# Test Rollback
# ═══════════════════════════════════════════════════════════


class TestRollback:
    """回滚测试."""

    def test_rollback_verify(self):
        """回滚归因验证 (noop)."""
        adapter = AdjustAdapter()
        action = make_action(ActionType.VERIFY_ATTRIBUTION, "camp_001")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "noop_adjust"

    def test_rollback_sync(self):
        """回滚元数据同步."""
        adapter = AdjustAdapter()
        action = make_action(ActionType.SYNC_METADATA, metadata={"key": "val"})
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success


# ═══════════════════════════════════════════════════════════
# Test Stats
# ═══════════════════════════════════════════════════════════


class TestStats:
    """统计测试."""

    def test_stats(self):
        """获取统计."""
        adapter = AdjustAdapter()
        adapter.execute(make_action(ActionType.VERIFY_ATTRIBUTION, "camp_001"))
        s = adapter.stats()
        assert s["execution_count"] == 1
        assert s["verifications"] == 1

    def test_stats_initial(self):
        """初始统计."""
        adapter = AdjustAdapter()
        s = adapter.stats()
        assert s["verifications"] == 0
        assert s["metadata_syncs"] == 0


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_unsupported_action(self):
        """不支持的动作."""
        adapter = AdjustAdapter()
        result = adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        assert not result.success
        assert "Unsupported action" in result.error

    def test_repr(self):
        """__repr__."""
        adapter = AdjustAdapter()
        assert "AdjustAdapter" in repr(adapter)

    def test_name_property(self):
        """name 属性."""
        adapter = AdjustAdapter(name="CustomAdjust")
        assert adapter.name == "CustomAdjust"