"""E15.0.9 MetaAdsAdapter — 单元测试.

验证 MetaAdsAdapter 的完整功能:
  - 预算调整: 正常/边界/无效 (5 tests)
  - 暂停/恢复 Campaign (4 tests)
  - 创建 Campaign (3 tests)
  - 上传/暂停 Creative (3 tests)
  - 校验: validate (5 tests)
  - 回滚: rollback (5 tests)
  - 统计: stats (2 tests)
  - 边界: 不支持的动作/错误处理 (3 tests)

总计: 30 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.meta_ads import (
    MetaAdsAdapter,
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


def make_action(action_type: ActionType, target: str = "camp_001", **params) -> GrowthAction:
    return GrowthAction(
        game_id="P04",
        action_type=action_type,
        target=target,
        parameters=params,
    )


# ═══════════════════════════════════════════════════════════
# Test Budget Update
# ═══════════════════════════════════════════════════════════


class TestBudgetUpdate:
    """预算调整测试."""

    def test_update_budget_success(self):
        """正常调整预算."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", old_budget=100, new_budget=120)
        result = adapter.execute(action)
        assert result.success
        assert result.external_id == "camp_001"
        assert result.metadata["old_budget"] == 100
        assert result.metadata["new_budget"] == 120

    def test_update_budget_decrease(self):
        """降低预算."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", old_budget=200, new_budget=150)
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["new_budget"] == 150

    def test_update_budget_increase(self):
        """增加预算."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", old_budget=100, new_budget=200)
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["new_budget"] == 200

    def test_update_budget_increments_count(self):
        """执行次数递增."""
        adapter = MetaAdsAdapter()
        adapter.execute(make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", old_budget=100, new_budget=120))
        assert adapter.execution_count == 1
        assert adapter.success_rate == 1.0

    def test_update_budget_campaign_cache_updated(self):
        """Campaign 缓存更新."""
        adapter = MetaAdsAdapter()
        adapter.execute(make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", old_budget=100, new_budget=120))
        assert adapter._campaign_cache["camp_001"]["budget"] == 120


# ═══════════════════════════════════════════════════════════
# Test Pause/Resume Campaign
# ═══════════════════════════════════════════════════════════


class TestPauseResume:
    """暂停/恢复测试."""

    def test_pause_campaign(self):
        """暂停 Campaign."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.PAUSE_CAMPAIGN, "camp_001")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["new_status"] == "PAUSED"
        assert adapter._campaign_cache["camp_001"]["status"] == "PAUSED"

    def test_resume_campaign(self):
        """恢复 Campaign."""
        adapter = MetaAdsAdapter()
        # 先暂停
        adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        # 再恢复
        action = make_action(ActionType.RESUME_CAMPAIGN, "camp_001")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["new_status"] == "ACTIVE"

    def test_pause_then_resume(self):
        """暂停后恢复."""
        adapter = MetaAdsAdapter()
        adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        adapter.execute(make_action(ActionType.RESUME_CAMPAIGN, "camp_001"))
        assert adapter._campaign_cache["camp_001"]["status"] == "ACTIVE"

    def test_pause_unknown_campaign(self):
        """暂停未知 Campaign (自动创建)."""
        adapter = MetaAdsAdapter()
        result = adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "unknown_camp"))
        assert result.success
        assert "unknown_camp" in adapter._campaign_cache


# ═══════════════════════════════════════════════════════════
# Test Create Campaign
# ═══════════════════════════════════════════════════════════


class TestCreateCampaign:
    """创建 Campaign 测试."""

    def test_create_campaign_default(self):
        """默认参数创建."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.CREATE_CAMPAIGN, name="Test Campaign")
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("meta_campaign_")
        assert result.metadata["campaign_name"] == "Test Campaign"

    def test_create_campaign_with_objective(self):
        """带 objective 创建."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.CREATE_CAMPAIGN, name="Test", objective="CONVERSIONS", daily_budget=200.0)
        result = adapter.execute(action)
        assert result.success
        assert adapter._campaign_cache[result.external_id]["objective"] == "CONVERSIONS"
        assert adapter._campaign_cache[result.external_id]["budget"] == 200.0

    def test_create_campaign_status_is_paused(self):
        """新创建的 Campaign 默认为 PAUSED."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.CREATE_CAMPAIGN, name="Test")
        result = adapter.execute(action)
        assert adapter._campaign_cache[result.external_id]["status"] == "PAUSED"


# ═══════════════════════════════════════════════════════════
# Test Creative Operations
# ═══════════════════════════════════════════════════════════


class TestCreativeOperations:
    """素材操作测试."""

    def test_upload_creative(self):
        """上传素材."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.UPLOAD_CREATIVE, "meta", asset_id="asset_001")
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("meta_creative_")
        assert result.metadata["asset_id"] == "asset_001"

    def test_pause_creative(self):
        """暂停素材."""
        adapter = MetaAdsAdapter()
        # 先上传
        upload_result = adapter.execute(make_action(ActionType.UPLOAD_CREATIVE, "meta", asset_id="asset_001"))
        creative_id = upload_result.external_id
        # 暂停
        result = adapter.execute(make_action(ActionType.PAUSE_CREATIVE, creative_id))
        assert result.success
        assert adapter._creative_cache[creative_id]["status"] == "PAUSED"

    def test_upload_creative_cache(self):
        """素材缓存."""
        adapter = MetaAdsAdapter()
        result = adapter.execute(make_action(ActionType.UPLOAD_CREATIVE, "meta", asset_id="asset_001"))
        assert result.external_id in adapter._creative_cache


# ═══════════════════════════════════════════════════════════
# Test Validation
# ═══════════════════════════════════════════════════════════


class TestValidation:
    """校验测试."""

    def test_validate_budget_action(self):
        """校验预算动作."""
        adapter = MetaAdsAdapter()
        assert adapter.validate(make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", new_budget=120))
        assert not adapter.validate(make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001"))
        assert not adapter.validate(make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", new_budget=-1))

    def test_validate_pause_action(self):
        """校验暂停动作."""
        adapter = MetaAdsAdapter()
        assert adapter.validate(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        assert not adapter.validate(make_action(ActionType.PAUSE_CAMPAIGN, ""))

    def test_validate_create_campaign(self):
        """校验创建 Campaign."""
        adapter = MetaAdsAdapter()
        assert adapter.validate(make_action(ActionType.CREATE_CAMPAIGN, name="Test"))
        assert not adapter.validate(make_action(ActionType.CREATE_CAMPAIGN))

    def test_validate_upload_creative(self):
        """校验上传素材."""
        adapter = MetaAdsAdapter()
        assert adapter.validate(make_action(ActionType.UPLOAD_CREATIVE, "meta", asset_id="asset_001"))
        assert not adapter.validate(make_action(ActionType.UPLOAD_CREATIVE, "meta"))

    def test_validate_unsupported_action(self):
        """校验不支持的动作."""
        adapter = MetaAdsAdapter()
        assert not adapter.validate(make_action(ActionType.PUBLISH_RELEASE, "pkg"))


# ═══════════════════════════════════════════════════════════
# Test Rollback
# ═══════════════════════════════════════════════════════════


class TestRollback:
    """回滚测试."""

    def test_rollback_budget(self):
        """回滚预算."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.UPDATE_CAMPAIGN_BUDGET, "camp_001", old_budget=100, new_budget=120)
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("restored_budget") == 100

    def test_rollback_create_campaign(self):
        """回滚创建 Campaign."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.CREATE_CAMPAIGN, name="Test")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "pause_created_campaign"

    def test_rollback_pause_campaign(self):
        """回滚暂停 (恢复)."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.PAUSE_CAMPAIGN, "camp_001")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "resume_campaign"

    def test_rollback_resume_campaign(self):
        """回滚恢复 (暂停)."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.RESUME_CAMPAIGN, "camp_001")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "pause_campaign"

    def test_rollback_not_implemented(self):
        """不支持的回滚."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.UPLOAD_CREATIVE, "meta", asset_id="asset_001")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.status == AdapterResultStatus.ROLLED_BACK


# ═══════════════════════════════════════════════════════════
# Test Stats
# ═══════════════════════════════════════════════════════════


class TestStats:
    """统计测试."""

    def test_stats(self):
        """获取统计."""
        adapter = MetaAdsAdapter()
        adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        s = adapter.stats()
        assert s["execution_count"] == 1
        assert s["success_rate"] == 1.0
        assert "campaigns_cached" in s

    def test_stats_after_failure(self):
        """失败后的统计."""
        adapter = MetaAdsAdapter()
        action = make_action(ActionType.PUBLISH_RELEASE, "pkg")
        adapter.execute(action)
        s = adapter.stats()
        assert s["failure_count"] >= 1


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_unsupported_action(self):
        """不支持的动作."""
        adapter = MetaAdsAdapter()
        result = adapter.execute(make_action(ActionType.PUBLISH_RELEASE, "pkg"))
        assert not result.success
        assert "Unsupported action" in result.error

    def test_repr(self):
        """__repr__."""
        adapter = MetaAdsAdapter()
        assert "MetaAdsAdapter" in repr(adapter)

    def test_name_property(self):
        """name 属性."""
        adapter = MetaAdsAdapter(name="CustomMeta")
        assert adapter.name == "CustomMeta"