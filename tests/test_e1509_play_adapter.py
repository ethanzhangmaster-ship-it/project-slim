"""E15.0.9 GooglePlayAdapter — 单元测试.

验证 GooglePlayAdapter 的完整功能:
  - 发布版本: 正常/指定 track (3 tests)
  - 更新元数据 (2 tests)
  - 分阶段发布 (2 tests)
  - 校验: validate (4 tests)
  - 回滚: rollback (3 tests)
  - 统计: stats (2 tests)
  - 边界: 不支持的动作/错误处理 (4 tests)

总计: 20 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.google_play import (
    GooglePlayAdapter,
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


def make_action(action_type: ActionType, target: str = "com.example.game", **params) -> GrowthAction:
    return GrowthAction(
        game_id="P04",
        action_type=action_type,
        target=target,
        parameters=params,
    )


# ═══════════════════════════════════════════════════════════
# Test Publish Release
# ═══════════════════════════════════════════════════════════


class TestPublishRelease:
    """发布版本测试."""

    def test_publish_release_success(self):
        """成功发布版本."""
        adapter = GooglePlayAdapter()
        action = make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.2.0")
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("play_release_")
        assert result.metadata["version"] == "1.2.0"
        assert result.metadata["track"] == "production"

    def test_publish_to_custom_track(self):
        """发布到自定义 track."""
        adapter = GooglePlayAdapter()
        action = make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.3.0", track="beta")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["track"] == "beta"

    def test_releases_accumulated(self):
        """发布记录累积."""
        adapter = GooglePlayAdapter()
        adapter.execute(make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.0"))
        adapter.execute(make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.1"))
        assert len(adapter._releases) == 2


# ═══════════════════════════════════════════════════════════
# Test Update Metadata
# ═══════════════════════════════════════════════════════════


class TestUpdateMetadata:
    """更新元数据测试."""

    def test_update_metadata_success(self):
        """成功更新元数据."""
        adapter = GooglePlayAdapter()
        metadata = {"title": "New Game Title", "description": "Updated description"}
        action = make_action(ActionType.UPDATE_STORE_METADATA, "com.example.game", metadata=metadata)
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("play_meta_")

    def test_metadata_stored(self):
        """元数据已存储."""
        adapter = GooglePlayAdapter()
        metadata = {"title": "New Title"}
        action = make_action(ActionType.UPDATE_STORE_METADATA, "com.example.game", metadata=metadata)
        adapter.execute(action)
        assert "com.example.game" in adapter._current_metadata


# ═══════════════════════════════════════════════════════════
# Test Start Rollout
# ═══════════════════════════════════════════════════════════


class TestStartRollout:
    """分阶段发布测试."""

    def test_start_rollout_success(self):
        """成功开始分阶段发布."""
        adapter = GooglePlayAdapter()
        action = make_action(ActionType.START_ROLLOUT, "com.example.game", version="1.2.0", percentage=25)
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["percentage"] == 25
        assert result.external_id.startswith("play_rollout_")

    def test_rollout_added_to_releases(self):
        """Rollout 添加到 releases 列表."""
        adapter = GooglePlayAdapter()
        adapter.execute(make_action(ActionType.START_ROLLOUT, "com.example.game", version="1.2.0", percentage=50))
        assert len(adapter._releases) == 1


# ═══════════════════════════════════════════════════════════
# Test Validation
# ═══════════════════════════════════════════════════════════


class TestValidation:
    """校验测试."""

    def test_validate_publish_release(self):
        """校验发布版本."""
        adapter = GooglePlayAdapter()
        assert adapter.validate(make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.0"))
        assert not adapter.validate(make_action(ActionType.PUBLISH_RELEASE, "com.example.game"))

    def test_validate_update_metadata(self):
        """校验更新元数据."""
        adapter = GooglePlayAdapter()
        assert adapter.validate(make_action(ActionType.UPDATE_STORE_METADATA, "com.example.game", metadata={"title": "T"}))
        assert not adapter.validate(make_action(ActionType.UPDATE_STORE_METADATA, "com.example.game"))

    def test_validate_start_rollout(self):
        """校验分阶段发布."""
        adapter = GooglePlayAdapter()
        assert adapter.validate(make_action(ActionType.START_ROLLOUT, "com.example.game", version="1.0", percentage=50))
        assert not adapter.validate(make_action(ActionType.START_ROLLOUT, "com.example.game", version="1.0"))

    def test_validate_unsupported_action(self):
        """校验不支持的动作."""
        adapter = GooglePlayAdapter()
        assert not adapter.validate(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))


# ═══════════════════════════════════════════════════════════
# Test Rollback
# ═══════════════════════════════════════════════════════════


class TestRollback:
    """回滚测试."""

    def test_rollback_publish_release(self):
        """回滚发布."""
        adapter = GooglePlayAdapter()
        action = make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.0")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "halt_release"

    def test_rollback_update_metadata(self):
        """回滚元数据更新."""
        adapter = GooglePlayAdapter()
        action = make_action(ActionType.UPDATE_STORE_METADATA, "com.example.game", metadata={"title": "T"})
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "restore_metadata"

    def test_rollback_start_rollout(self):
        """回滚分阶段发布."""
        adapter = GooglePlayAdapter()
        action = make_action(ActionType.START_ROLLOUT, "com.example.game", version="1.0", percentage=50)
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "halt_rollout"


# ═══════════════════════════════════════════════════════════
# Test Stats
# ═══════════════════════════════════════════════════════════


class TestStats:
    """统计测试."""

    def test_stats(self):
        """获取统计."""
        adapter = GooglePlayAdapter()
        adapter.execute(make_action(ActionType.PUBLISH_RELEASE, "com.example.game", version="1.0"))
        s = adapter.stats()
        assert s["execution_count"] == 1
        assert s["releases_count"] == 1

    def test_stats_initial(self):
        """初始统计."""
        adapter = GooglePlayAdapter()
        s = adapter.stats()
        assert s["execution_count"] == 0
        assert s["releases_count"] == 0


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_unsupported_action(self):
        """不支持的动作."""
        adapter = GooglePlayAdapter()
        result = adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        assert not result.success
        assert "Unsupported action" in result.error

    def test_package_name_from_init(self):
        """使用初始化时的 package_name."""
        adapter = GooglePlayAdapter(package_name="com.default.game")
        action = make_action(ActionType.PUBLISH_RELEASE, "", version="1.0")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["package_name"] == "com.default.game"

    def test_repr(self):
        """__repr__."""
        adapter = GooglePlayAdapter()
        assert "GooglePlayAdapter" in repr(adapter)

    def test_name_property(self):
        """name 属性."""
        adapter = GooglePlayAdapter(name="CustomPlay")
        assert adapter.name == "CustomPlay"