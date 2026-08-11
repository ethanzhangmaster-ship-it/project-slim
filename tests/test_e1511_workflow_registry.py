"""E15.1.1 Workflow Registry 测试 — 注册中心测试.

测试覆盖:
  - Workflow 注册/注销
  - 按 ID/名称/标签查询
  - 启用/禁用
  - 版本管理
  - JSON 序列化/反序列化
  - 统计信息
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import (
    WorkflowBuilder,
    create_campaign_optimization_workflow,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.models import (
    WorkflowDefinition,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.registry import (
    WorkflowRegistry,
    WorkflowRegistryEntry,
)


class TestWorkflowRegistryEntry:
    """WorkflowRegistryEntry 单元测试."""

    def test_create_entry(self):
        wf = WorkflowDefinition(name="test")
        entry = WorkflowRegistryEntry(workflow=wf, tags=["campaign"])
        assert entry.workflow is wf
        assert entry.enabled is True
        assert "campaign" in entry.tags


class TestWorkflowRegistry:
    """WorkflowRegistry 单元测试."""

    def setup_method(self):
        self.registry = WorkflowRegistry()
        self.wf1 = create_campaign_optimization_workflow()
        self.wf2 = WorkflowBuilder("Creative Refresh").add_step("A", "analysis").build()

    # ── Registration ─────────────────────────────────────────

    def test_register(self):
        self.registry.register(self.wf1)
        assert self.wf1.workflow_id in self.registry
        assert len(self.registry) == 1

    def test_register_duplicate_raises(self):
        self.registry.register(self.wf1)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(self.wf1)

    def test_register_multiple(self):
        self.registry.register(self.wf1)
        self.registry.register(self.wf2)
        assert len(self.registry) == 2

    def test_register_with_tags(self):
        self.registry.register(self.wf1, tags=["campaign", "optimization"])
        found = self.registry.find_by_tag("campaign")
        assert len(found) == 1

    def test_unregister(self):
        self.registry.register(self.wf1)
        assert self.registry.unregister(self.wf1.workflow_id) is True
        assert len(self.registry) == 0

    def test_unregister_nonexistent(self):
        assert self.registry.unregister("nonexistent") is False

    # ── Query ────────────────────────────────────────────────

    def test_get(self):
        self.registry.register(self.wf1)
        found = self.registry.get(self.wf1.workflow_id)
        assert found is self.wf1

    def test_get_nonexistent(self):
        assert self.registry.get("nonexistent") is None

    def test_get_by_name(self):
        self.registry.register(self.wf1)
        found = self.registry.get_by_name("Campaign Budget Optimization")
        assert found is self.wf1

    def test_get_by_name_nonexistent(self):
        assert self.registry.get_by_name("Nonexistent") is None

    def test_list_all(self):
        self.registry.register(self.wf1)
        self.registry.register(self.wf2)
        assert len(self.registry.list_all()) == 2

    def test_list_enabled(self):
        self.registry.register(self.wf1)
        self.registry.register(self.wf2)
        self.registry.disable(self.wf2.workflow_id)
        assert len(self.registry.list_enabled()) == 1

    def test_find_by_tag(self):
        self.registry.register(self.wf1, tags=["campaign"])
        self.registry.register(self.wf2, tags=["creative"])
        assert len(self.registry.find_by_tag("campaign")) == 1
        assert len(self.registry.find_by_tag("creative")) == 1
        assert len(self.registry.find_by_tag("nonexistent")) == 0

    def test_find_by_name_pattern(self):
        self.registry.register(self.wf1, tags=["campaign"])
        self.registry.register(self.wf2, tags=["creative"])
        found = self.registry.find_by_name_pattern("campaign")
        assert len(found) == 1
        found = self.registry.find_by_name_pattern("creative")
        assert len(found) == 1

    # ── Enable/Disable ───────────────────────────────────────

    def test_enable_disable(self):
        self.registry.register(self.wf1)
        assert self.registry.disable(self.wf1.workflow_id) is True
        assert len(self.registry.list_enabled()) == 0
        assert self.registry.enable(self.wf1.workflow_id) is True
        assert len(self.registry.list_enabled()) == 1

    def test_enable_disable_nonexistent(self):
        assert self.registry.enable("nonexistent") is False
        assert self.registry.disable("nonexistent") is False

    # ── Version Management ───────────────────────────────────

    def test_set_version(self):
        self.registry.register(self.wf1)
        assert self.registry.set_version(self.wf1.workflow_id, "2.0.0") is True
        assert self.wf1.version == "2.0.0"

    def test_set_version_nonexistent(self):
        assert self.registry.set_version("nonexistent", "1.0.0") is False

    # ── Tag Management ───────────────────────────────────────

    def test_add_tag(self):
        self.registry.register(self.wf1)
        assert self.registry.add_tag(self.wf1.workflow_id, "production") is True
        assert len(self.registry.find_by_tag("production")) == 1

    def test_add_tag_nonexistent(self):
        assert self.registry.add_tag("nonexistent", "tag") is False

    def test_remove_tag(self):
        self.registry.register(self.wf1, tags=["campaign", "test"])
        assert self.registry.remove_tag(self.wf1.workflow_id, "test") is True
        assert len(self.registry.find_by_tag("test")) == 0
        assert len(self.registry.find_by_tag("campaign")) == 1

    def test_remove_tag_nonexistent(self):
        self.registry.register(self.wf1, tags=["campaign"])
        assert self.registry.remove_tag(self.wf1.workflow_id, "nonexistent") is False

    # ── Serialization ────────────────────────────────────────

    def test_export_json(self):
        self.registry.register(self.wf1, tags=["campaign"])
        json_str = self.registry.export_json()
        assert "Campaign Budget Optimization" in json_str
        assert "campaign" in json_str

    def test_import_json(self):
        self.registry.register(self.wf1, tags=["campaign"])
        json_str = self.registry.export_json()

        new_registry = WorkflowRegistry()
        count = new_registry.import_json(json_str)
        assert count == 1
        assert new_registry.get_by_name("Campaign Budget Optimization") is not None

    def test_import_json_skips_duplicates(self):
        self.registry.register(self.wf1, tags=["campaign"])
        json_str = self.registry.export_json()

        # 再次导入到同一个 registry — 应跳过
        count = self.registry.import_json(json_str)
        assert count == 0

    def test_roundtrip(self):
        self.registry.register(self.wf1, tags=["campaign", "optimization"])
        self.registry.register(self.wf2, tags=["creative"])

        json_str = self.registry.export_json()
        new_registry = WorkflowRegistry()
        new_registry.import_json(json_str)

        assert len(new_registry) == 2
        assert new_registry.get_by_name("Campaign Budget Optimization") is not None
        assert new_registry.get_by_name("Creative Refresh") is not None

    # ── Stats ────────────────────────────────────────────────

    def test_stats(self):
        self.registry.register(self.wf1, tags=["campaign"])
        self.registry.register(self.wf2, tags=["creative"])
        self.registry.disable(self.wf2.workflow_id)

        stats = self.registry.stats()
        assert stats["total"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1
        assert "campaign" in stats["all_tags"]
        assert "creative" in stats["all_tags"]

    def test_stats_empty(self):
        stats = self.registry.stats()
        assert stats["total"] == 0
        assert stats["enabled"] == 0

    # ── Clear ────────────────────────────────────────────────

    def test_clear(self):
        self.registry.register(self.wf1)
        self.registry.clear()
        assert len(self.registry) == 0

    # ── Contains ─────────────────────────────────────────────

    def test_contains(self):
        self.registry.register(self.wf1)
        assert self.wf1.workflow_id in self.registry
        assert "nonexistent" not in self.registry