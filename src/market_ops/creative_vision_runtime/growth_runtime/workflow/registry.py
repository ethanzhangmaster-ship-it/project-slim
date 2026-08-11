"""E15.1.1 Workflow Registry — Workflow 注册与查询.

提供 WorkflowDefinition 的注册、查询和版本管理:

    registry = WorkflowRegistry()
    registry.register(workflow)
    workflows = registry.list_all()
    wf = registry.get("creative_refresh")

与 WorkflowDefinition 的关系:
  - WorkflowDefinition: 单个 Workflow 模板
  - WorkflowRegistry:   所有 Workflow 的集中管理
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .models import WorkflowDefinition


# ═══════════════════════════════════════════════════════════════
# Workflow Registry
# ═══════════════════════════════════════════════════════════════


@dataclass
class WorkflowRegistryEntry:
    """注册条目 — 记录 Workflow 的注册时间和状态."""

    workflow: WorkflowDefinition
    registered_at: str = ""
    enabled: bool = True
    tags: list[str] = field(default_factory=list)


class WorkflowRegistry:
    """E15.1.1 Workflow 注册中心 — 集中管理所有 WorkflowDefinition.

    用法:
        registry = WorkflowRegistry()
        registry.register(workflow)
        registry.register(campaign_optimizer, tags=["campaign", "optimization"])

        # 查询
        wf = registry.get("campaign_optimizer")
        wf = registry.get_by_name("Campaign Budget Optimization")

        # 按标签过滤
        campaign_wfs = registry.find_by_tag("campaign")

        # 序列化
        json_data = registry.export_json()
        registry.import_json(json_data)
    """

    def __init__(self):
        self._entries: dict[str, WorkflowRegistryEntry] = {}

    # ── Registration ─────────────────────────────────────────

    def register(
        self,
        workflow: WorkflowDefinition,
        tags: list[str] | None = None,
    ) -> None:
        """注册一个 Workflow.

        Args:
            workflow: WorkflowDefinition 实例
            tags:     标签 (用于分类和过滤)

        Raises:
            ValueError: 同名 Workflow 已存在
        """
        from datetime import datetime, timezone

        key = workflow.workflow_id
        if key in self._entries:
            raise ValueError(
                f"Workflow with id '{key}' is already registered"
            )

        self._entries[key] = WorkflowRegistryEntry(
            workflow=workflow,
            registered_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
        )

    def unregister(self, workflow_id: str) -> bool:
        """注销一个 Workflow.

        Returns:
            bool: 是否成功注销
        """
        if workflow_id in self._entries:
            del self._entries[workflow_id]
            return True
        return False

    # ── Query ────────────────────────────────────────────────

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        """按 ID 获取 Workflow."""
        entry = self._entries.get(workflow_id)
        return entry.workflow if entry else None

    def get_by_name(self, name: str) -> WorkflowDefinition | None:
        """按名称获取 Workflow."""
        for entry in self._entries.values():
            if entry.workflow.name == name:
                return entry.workflow
        return None

    def list_all(self) -> list[WorkflowDefinition]:
        """获取所有 Workflow."""
        return [e.workflow for e in self._entries.values()]

    def list_enabled(self) -> list[WorkflowDefinition]:
        """获取所有启用的 Workflow."""
        return [e.workflow for e in self._entries.values() if e.enabled]

    def find_by_tag(self, tag: str) -> list[WorkflowDefinition]:
        """按标签查找 Workflow."""
        return [
            e.workflow for e in self._entries.values()
            if tag in e.tags
        ]

    def find_by_name_pattern(self, pattern: str) -> list[WorkflowDefinition]:
        """按名称模糊匹配 (简单 contains)."""
        pattern_lower = pattern.lower()
        return [
            e.workflow for e in self._entries.values()
            if pattern_lower in e.workflow.name.lower()
        ]

    # ── Entry Management ─────────────────────────────────────

    def enable(self, workflow_id: str) -> bool:
        """启用 Workflow."""
        entry = self._entries.get(workflow_id)
        if entry:
            entry.enabled = True
            return True
        return False

    def disable(self, workflow_id: str) -> bool:
        """禁用 Workflow."""
        entry = self._entries.get(workflow_id)
        if entry:
            entry.enabled = False
            return True
        return False

    def set_version(self, workflow_id: str, version: str) -> bool:
        """更新 Workflow 版本."""
        entry = self._entries.get(workflow_id)
        if entry:
            entry.workflow.version = version
            return True
        return False

    def add_tag(self, workflow_id: str, tag: str) -> bool:
        """添加标签."""
        entry = self._entries.get(workflow_id)
        if entry and tag not in entry.tags:
            entry.tags.append(tag)
            return True
        return False

    def remove_tag(self, workflow_id: str, tag: str) -> bool:
        """移除标签."""
        entry = self._entries.get(workflow_id)
        if entry and tag in entry.tags:
            entry.tags = [t for t in entry.tags if t != tag]
            return True
        return False

    # ── Serialization ────────────────────────────────────────

    def export_json(self) -> str:
        """导出所有 Workflow 为 JSON 字符串."""
        data = {
            wid: {
                "workflow": entry.workflow.to_dict(),
                "registered_at": entry.registered_at,
                "enabled": entry.enabled,
                "tags": entry.tags,
            }
            for wid, entry in self._entries.items()
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_json(self, json_str: str) -> int:
        """从 JSON 字符串导入 Workflow.

        Returns:
            int: 导入的 Workflow 数量
        """
        data = json.loads(json_str)
        count = 0
        for wid, entry_data in data.items():
            if wid not in self._entries:
                workflow = WorkflowDefinition.from_dict(entry_data["workflow"])
                self._entries[wid] = WorkflowRegistryEntry(
                    workflow=workflow,
                    registered_at=entry_data.get("registered_at", ""),
                    enabled=entry_data.get("enabled", True),
                    tags=entry_data.get("tags", []),
                )
                count += 1
        return count

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "total": len(self._entries),
            "enabled": len([e for e in self._entries.values() if e.enabled]),
            "disabled": len([e for e in self._entries.values() if not e.enabled]),
            "all_tags": list(
                {tag for e in self._entries.values() for tag in e.tags}
            ),
        }

    def clear(self) -> None:
        """清空所有注册."""
        self._entries.clear()

    def __contains__(self, workflow_id: str) -> bool:
        return workflow_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"WorkflowRegistry(entries={len(self._entries)})"


__all__ = ["WorkflowRegistryEntry", "WorkflowRegistry"]