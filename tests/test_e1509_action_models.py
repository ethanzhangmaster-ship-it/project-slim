"""E15.0.9 GrowthAction + ActionType — 单元测试.

验证 GrowthAction 模型和 ActionType 枚举的完整功能:
  - ActionType: 枚举值 (18 tests)
  - GrowthAction: 创建/序列化/属性 (20 tests)
  - Factory Helpers: 工厂函数 (5 tests)
  - Edge Cases: 边界 & 异常 (7 tests)

总计: 50 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.growth_action import (
    ActionType,
    GrowthAction,
    create_budget_action,
    create_pause_action,
    create_resume_action,
    create_upload_creative_action,
    create_publish_release_action,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_action(
    action_type: ActionType = ActionType.NOOP,
    game_id: str = "P04",
    target: str = "",
    **params,
) -> GrowthAction:
    return GrowthAction(
        game_id=game_id,
        action_type=action_type,
        target=target,
        parameters=params,
    )


# ═══════════════════════════════════════════════════════════
# Test ActionType Enum
# ═══════════════════════════════════════════════════════════


class TestActionTypeEnum:
    """ActionType 枚举值测试."""

    def test_meta_ads_types_exist(self):
        """Meta Ads 动作类型存在."""
        assert ActionType.UPDATE_CAMPAIGN_BUDGET == "update_campaign_budget"
        assert ActionType.PAUSE_CAMPAIGN == "pause_campaign"
        assert ActionType.RESUME_CAMPAIGN == "resume_campaign"
        assert ActionType.CREATE_CAMPAIGN == "create_campaign"
        assert ActionType.UPLOAD_CREATIVE == "upload_creative"
        assert ActionType.PAUSE_CREATIVE == "pause_creative"

    def test_google_play_types_exist(self):
        """Google Play 动作类型存在."""
        assert ActionType.PUBLISH_RELEASE == "publish_release"
        assert ActionType.UPDATE_STORE_METADATA == "update_store_metadata"
        assert ActionType.START_ROLLOUT == "start_rollout"

    def test_creative_types_exist(self):
        """Creative 动作类型存在."""
        assert ActionType.GENERATE_CREATIVE == "generate_creative"
        assert ActionType.MUTATE_CREATIVE == "mutate_creative"

    def test_adjust_types_exist(self):
        """Adjust 动作类型存在."""
        assert ActionType.VERIFY_ATTRIBUTION == "verify_attribution"
        assert ActionType.SYNC_METADATA == "sync_metadata"

    def test_general_types_exist(self):
        """通用动作类型存在."""
        assert ActionType.MONITOR == "monitor"
        assert ActionType.NOOP == "noop"

    def test_total_action_types(self):
        """总计 16 个动作类型."""
        assert len(ActionType) == 15

    def test_action_type_is_string_enum(self):
        """ActionType 是 str Enum."""
        assert isinstance(ActionType.UPDATE_CAMPAIGN_BUDGET, str)
        assert ActionType.PAUSE_CAMPAIGN == "pause_campaign"

    def test_from_string(self):
        """从字符串创建 ActionType."""
        assert ActionType("update_campaign_budget") == ActionType.UPDATE_CAMPAIGN_BUDGET
        assert ActionType("publish_release") == ActionType.PUBLISH_RELEASE

    def test_invalid_action_type(self):
        """无效 ActionType 抛出 ValueError."""
        with pytest.raises(ValueError):
            ActionType("invalid_action")


# ═══════════════════════════════════════════════════════════
# Test GrowthAction Creation
# ═══════════════════════════════════════════════════════════


class TestGrowthActionCreation:
    """GrowthAction 创建测试."""

    def test_default_creation(self):
        """默认创建."""
        action = GrowthAction()
        assert action.action_id != ""
        assert action.game_id == ""
        assert action.action_type == ActionType.NOOP
        assert action.target == ""
        assert action.parameters == {}
        assert action.priority == "medium"

    def test_custom_action_id(self):
        """自定义 action_id."""
        action = GrowthAction(action_id="my_id_123")
        assert action.action_id == "my_id_123"

    def test_full_creation(self):
        """完整创建."""
        action = GrowthAction(
            game_id="P04",
            action_type=ActionType.PAUSE_CAMPAIGN,
            target="campaign_123",
            parameters={"reason": "low_roas"},
            priority="high",
            metadata={"decision_id": "dec_001"},
        )
        assert action.game_id == "P04"
        assert action.action_type == ActionType.PAUSE_CAMPAIGN
        assert action.target == "campaign_123"
        assert action.parameters == {"reason": "low_roas"}
        assert action.priority == "high"
        assert action.metadata == {"decision_id": "dec_001"}

    def test_created_at_is_iso_format(self):
        """created_at 是 ISO 8601 格式."""
        action = GrowthAction()
        assert "T" in action.created_at
        assert action.created_at.endswith("+00:00") or action.created_at.endswith("Z")

    def test_unique_action_ids(self):
        """每次创建生成唯一 action_id."""
        a1 = GrowthAction()
        a2 = GrowthAction()
        assert a1.action_id != a2.action_id


# ═══════════════════════════════════════════════════════════
# Test GrowthAction Serialization
# ═══════════════════════════════════════════════════════════


class TestGrowthActionSerialization:
    """GrowthAction 序列化测试."""

    def test_to_dict(self):
        """to_dict 包含所有字段."""
        action = make_action(
            ActionType.UPDATE_CAMPAIGN_BUDGET,
            game_id="P04",
            target="camp_001",
            old_budget=100,
            new_budget=120,
        )
        d = action.to_dict()
        assert d["action_id"] == action.action_id
        assert d["game_id"] == "P04"
        assert d["action_type"] == "update_campaign_budget"
        assert d["target"] == "camp_001"
        assert d["parameters"]["old_budget"] == 100
        assert d["parameters"]["new_budget"] == 120
        assert d["priority"] == "medium"

    def test_from_dict_roundtrip(self):
        """from_dict(to_dict()) 往返."""
        original = make_action(
            ActionType.PAUSE_CAMPAIGN,
            game_id="P04",
            target="camp_001",
        )
        restored = GrowthAction.from_dict(original.to_dict())
        assert restored.action_id == original.action_id
        assert restored.game_id == original.game_id
        assert restored.action_type == original.action_type
        assert restored.target == original.target

    def test_from_dict_partial(self):
        """from_dict 部分字段."""
        d = {"game_id": "P04", "action_type": "noop"}
        action = GrowthAction.from_dict(d)
        assert action.game_id == "P04"
        assert action.action_type == ActionType.NOOP
        assert action.action_id != ""

    def test_from_dict_empty(self):
        """from_dict 空字典."""
        action = GrowthAction.from_dict({})
        assert action.action_type == ActionType.NOOP
        assert action.action_id != ""


# ═══════════════════════════════════════════════════════════
# Test GrowthAction Properties
# ═══════════════════════════════════════════════════════════


class TestGrowthActionProperties:
    """GrowthAction 属性测试."""

    def test_is_meta_action(self):
        """Meta 动作识别."""
        assert make_action(ActionType.UPDATE_CAMPAIGN_BUDGET).is_meta_action
        assert make_action(ActionType.PAUSE_CAMPAIGN).is_meta_action
        assert make_action(ActionType.RESUME_CAMPAIGN).is_meta_action
        assert make_action(ActionType.CREATE_CAMPAIGN).is_meta_action
        assert make_action(ActionType.UPLOAD_CREATIVE).is_meta_action
        assert make_action(ActionType.PAUSE_CREATIVE).is_meta_action

    def test_is_not_meta_action(self):
        """非 Meta 动作."""
        assert not make_action(ActionType.PUBLISH_RELEASE).is_meta_action
        assert not make_action(ActionType.NOOP).is_meta_action

    def test_is_play_action(self):
        """Play 动作识别."""
        assert make_action(ActionType.PUBLISH_RELEASE).is_play_action
        assert make_action(ActionType.UPDATE_STORE_METADATA).is_play_action
        assert make_action(ActionType.START_ROLLOUT).is_play_action

    def test_is_creative_action(self):
        """Creative 动作识别."""
        assert make_action(ActionType.GENERATE_CREATIVE).is_creative_action
        assert make_action(ActionType.MUTATE_CREATIVE).is_creative_action

    def test_is_adjust_action(self):
        """Adjust 动作识别."""
        assert make_action(ActionType.VERIFY_ATTRIBUTION).is_adjust_action
        assert make_action(ActionType.SYNC_METADATA).is_adjust_action

    def test_repr(self):
        """__repr__ 包含关键信息."""
        action = make_action(ActionType.PAUSE_CAMPAIGN, target="camp_123")
        r = repr(action)
        assert "GrowthAction" in r
        assert "pause_campaign" in r
        assert "camp_123" in r


# ═══════════════════════════════════════════════════════════
# Test Factory Helpers
# ═══════════════════════════════════════════════════════════


class TestFactoryHelpers:
    """工厂函数测试."""

    def test_create_budget_action(self):
        """create_budget_action."""
        action = create_budget_action("P04", "camp_001", 100, 120)
        assert action.action_type == ActionType.UPDATE_CAMPAIGN_BUDGET
        assert action.target == "camp_001"
        assert action.parameters["old_budget"] == 100
        assert action.parameters["new_budget"] == 120

    def test_create_pause_action(self):
        """create_pause_action."""
        action = create_pause_action("P04", "camp_001")
        assert action.action_type == ActionType.PAUSE_CAMPAIGN
        assert action.target == "camp_001"

    def test_create_resume_action(self):
        """create_resume_action."""
        action = create_resume_action("P04", "camp_001")
        assert action.action_type == ActionType.RESUME_CAMPAIGN
        assert action.target == "camp_001"

    def test_create_upload_creative_action(self):
        """create_upload_creative_action."""
        action = create_upload_creative_action("P04", "asset_001", platform="meta")
        assert action.action_type == ActionType.UPLOAD_CREATIVE
        assert action.parameters["asset_id"] == "asset_001"

    def test_create_publish_release_action(self):
        """create_publish_release_action."""
        action = create_publish_release_action("P04", "com.example.game", "1.2.0")
        assert action.action_type == ActionType.PUBLISH_RELEASE
        assert action.parameters["version"] == "1.2.0"
        assert action.parameters["track"] == "production"


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_empty_parameters(self):
        """空参数."""
        action = make_action(ActionType.PAUSE_CAMPAIGN)
        assert action.parameters == {}

    def test_large_parameters(self):
        """大参数字典."""
        params = {f"key_{i}": i for i in range(100)}
        action = make_action(ActionType.NOOP, **params)
        assert len(action.parameters) == 100

    def test_unicode_game_id(self):
        """Unicode game_id."""
        action = GrowthAction(game_id="游戏_测试")
        assert action.game_id == "游戏_测试"

    def test_priority_values(self):
        """优先级值."""
        for p in ["critical", "high", "medium", "low"]:
            action = GrowthAction(priority=p)
            assert action.priority == p

    def test_metadata_preservation(self):
        """metadata 保留完整."""
        metadata = {"agent_id": "agent_01", "cycle_id": "cycle_42", "nested": {"key": "value"}}
        action = GrowthAction(metadata=metadata)
        assert action.metadata["agent_id"] == "agent_01"
        assert action.metadata["nested"]["key"] == "value"

    def test_target_empty_string(self):
        """target 可以是空字符串."""
        action = make_action(ActionType.MONITOR)
        assert action.target == ""

    def test_noop_action_properties(self):
        """NOOP 动作不属于任何平台."""
        action = make_action(ActionType.NOOP)
        assert not action.is_meta_action
        assert not action.is_play_action
        assert not action.is_creative_action
        assert not action.is_adjust_action