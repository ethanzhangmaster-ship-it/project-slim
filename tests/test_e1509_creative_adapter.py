"""E15.0.9 CreativeAdapter — 单元测试.

验证 CreativeAdapter 的完整功能:
  - 生成素材: 正常/带 hypothesis (3 tests)
  - 变异素材: 正常/不同变异类型 (3 tests)
  - 校验: validate (4 tests)
  - 回滚: rollback (2 tests)
  - 统计: stats (2 tests)
  - 边界: 不支持的动作/错误处理 (3 tests)

总计: 17 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.adapters.creative import (
    CreativeAdapter,
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
# Test Generate Creative
# ═══════════════════════════════════════════════════════════


class TestGenerateCreative:
    """生成素材测试."""

    def test_generate_with_dna(self):
        """通过 Creative DNA 生成."""
        adapter = CreativeAdapter()
        creative_dna = {"visual": "bright", "hook": "mystery"}
        action = make_action(ActionType.GENERATE_CREATIVE, creative_dna=creative_dna)
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("creative_asset_")
        assert result.metadata["platform"] == "creative"

    def test_generate_with_hypothesis(self):
        """通过 hypothesis_id 生成."""
        adapter = CreativeAdapter()
        action = make_action(ActionType.GENERATE_CREATIVE, hypothesis_id="hyp_001")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["hypothesis_id"] == "hyp_001"

    def test_generate_video_type(self):
        """生成视频类型."""
        adapter = CreativeAdapter()
        action = make_action(ActionType.GENERATE_CREATIVE, creative_dna={"visual": "dark"}, asset_type="VIDEO")
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["asset_type"] == "VIDEO"


# ═══════════════════════════════════════════════════════════
# Test Mutate Creative
# ═══════════════════════════════════════════════════════════


class TestMutateCreative:
    """变异素材测试."""

    def test_mutate_visual(self):
        """视觉变异."""
        adapter = CreativeAdapter()
        action = make_action(ActionType.MUTATE_CREATIVE, source_creative_id="src_001", mutation_type="visual")
        result = adapter.execute(action)
        assert result.success
        assert result.external_id.startswith("creative_mutant_")
        assert result.metadata["mutation_type"] == "visual"

    def test_mutate_hook(self):
        """Hook 变异."""
        adapter = CreativeAdapter()
        action = make_action(ActionType.MUTATE_CREATIVE, source_creative_id="src_001", mutation_type="hook", mutation_params={"target_hook": "rescue"})
        result = adapter.execute(action)
        assert result.success
        assert result.metadata["mutation_type"] == "hook"

    def test_mutate_accumulates_assets(self):
        """变异资产累积."""
        adapter = CreativeAdapter()
        adapter.execute(make_action(ActionType.MUTATE_CREATIVE, source_creative_id="src_001"))
        adapter.execute(make_action(ActionType.MUTATE_CREATIVE, source_creative_id="src_002"))
        assert len(adapter._mutated_assets) == 2


# ═══════════════════════════════════════════════════════════
# Test Validation
# ═══════════════════════════════════════════════════════════


class TestValidation:
    """校验测试."""

    def test_validate_generate_with_dna(self):
        """校验通过 DNA 生成."""
        adapter = CreativeAdapter()
        assert adapter.validate(make_action(ActionType.GENERATE_CREATIVE, creative_dna={"visual": "bright"}))

    def test_validate_generate_with_hypothesis(self):
        """校验通过 hypothesis 生成."""
        adapter = CreativeAdapter()
        assert adapter.validate(make_action(ActionType.GENERATE_CREATIVE, hypothesis_id="hyp_001"))

    def test_validate_generate_empty(self):
        """校验空参数生成."""
        adapter = CreativeAdapter()
        assert not adapter.validate(make_action(ActionType.GENERATE_CREATIVE))

    def test_validate_mutate(self):
        """校验变异."""
        adapter = CreativeAdapter()
        assert adapter.validate(make_action(ActionType.MUTATE_CREATIVE, source_creative_id="src_001"))
        assert not adapter.validate(make_action(ActionType.MUTATE_CREATIVE))


# ═══════════════════════════════════════════════════════════
# Test Rollback
# ═══════════════════════════════════════════════════════════


class TestRollback:
    """回滚测试."""

    def test_rollback_generate(self):
        """回滚生成 (删除素材)."""
        adapter = CreativeAdapter()
        action = make_action(ActionType.GENERATE_CREATIVE, creative_dna={"visual": "bright"})
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "delete_asset"

    def test_rollback_mutate(self):
        """回滚变异."""
        adapter = CreativeAdapter()
        action = make_action(ActionType.MUTATE_CREATIVE, source_creative_id="src_001")
        result = adapter.execute(action)
        rollback = adapter.rollback(action, result)
        assert rollback.success
        assert rollback.metadata.get("rollback_action") == "delete_asset"


# ═══════════════════════════════════════════════════════════
# Test Stats
# ═══════════════════════════════════════════════════════════


class TestStats:
    """统计测试."""

    def test_stats(self):
        """获取统计."""
        adapter = CreativeAdapter()
        adapter.execute(make_action(ActionType.GENERATE_CREATIVE, creative_dna={"visual": "bright"}))
        s = adapter.stats()
        assert s["execution_count"] == 1
        assert s["generated_assets"] == 1

    def test_stats_initial(self):
        """初始统计."""
        adapter = CreativeAdapter()
        s = adapter.stats()
        assert s["generated_assets"] == 0
        assert s["mutated_assets"] == 0


# ═══════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_unsupported_action(self):
        """不支持的动作."""
        adapter = CreativeAdapter()
        result = adapter.execute(make_action(ActionType.PAUSE_CAMPAIGN, "camp_001"))
        assert not result.success
        assert "Unsupported action" in result.error

    def test_repr(self):
        """__repr__."""
        adapter = CreativeAdapter()
        assert "CreativeAdapter" in repr(adapter)

    def test_name_property(self):
        """name 属性."""
        adapter = CreativeAdapter(name="CustomCreative")
        assert adapter.name == "CustomCreative"