"""E15.0.9 Adapter Registry — 适配器注册表.

将 ActionType 映射到具体的 ExecutionAdapter 实例，实现 Action → Adapter 的解耦。

与 E13.6 ExecutorRegistry 的关系:
  - AdapterRegistry: ActionType → ExecutionAdapter (高层)
  - ExecutorRegistry: ExecutionActionType → BaseExecutor (底层)
  - Adapter 内部使用 ExecutorRegistry 完成底层执行

设计原则:
  - 避免 if-else 地狱: 通过注册表查找而非条件分支
  - 平台分组: 支持按平台批量注册 (meta / play / creative / adjust)
  - 默认适配器: 未注册的 ActionType 使用默认适配器
"""

from __future__ import annotations

from typing import Any

from .adapter_base import ExecutionAdapter
from .growth_action import ActionType


class AdapterRegistry:
    """E15.0.9 适配器注册表 — 管理 ActionType → ExecutionAdapter 映射.

    与 ExecutorRegistry 的区别:
      - ExecutorRegistry 映射 ExecutionActionType → BaseExecutor (底层原子操作)
      - AdapterRegistry 映射 ActionType → ExecutionAdapter (高层业务动作)
      - 一个 Adapter 可能内部使用多个 Executor

    用法:
        registry = AdapterRegistry()
        registry.register(ActionType.PAUSE_CAMPAIGN, meta_adapter)
        registry.register_many({
            ActionType.UPDATE_CAMPAIGN_BUDGET: meta_adapter,
            ActionType.RESUME_CAMPAIGN: meta_adapter,
        })

        adapter = registry.get(ActionType.PAUSE_CAMPAIGN)
        result = adapter.execute(action)
    """

    def __init__(self):
        self._registry: dict[ActionType, ExecutionAdapter] = {}
        self._default_adapter: ExecutionAdapter | None = None

    # ── 注册 ──────────────────────────────────────────────────

    def register(
        self,
        action_type: ActionType,
        adapter: ExecutionAdapter,
    ) -> None:
        """注册单个适配器.

        Args:
            action_type: 动作类型
            adapter:     适配器实例
        """
        self._registry[action_type] = adapter

    def register_many(
        self,
        mappings: dict[ActionType, ExecutionAdapter],
    ) -> None:
        """批量注册适配器.

        Args:
            mappings: {ActionType: ExecutionAdapter} 映射
        """
        for action_type, adapter in mappings.items():
            self._registry[action_type] = adapter

    def register_platform(
        self,
        adapter: ExecutionAdapter,
        action_types: list[ActionType],
    ) -> None:
        """为一个平台适配器注册多个动作类型.

        Args:
            adapter:      平台适配器实例
            action_types: 该适配器支持的动作类型列表
        """
        for action_type in action_types:
            self._registry[action_type] = adapter

    def set_default(self, adapter: ExecutionAdapter) -> None:
        """设置默认适配器 (未注册 ActionType 时使用)."""
        self._default_adapter = adapter

    def unregister(self, action_type: ActionType) -> None:
        """取消注册."""
        self._registry.pop(action_type, None)

    # ── 查询 ──────────────────────────────────────────────────

    def get(self, action_type: ActionType) -> ExecutionAdapter | None:
        """根据动作类型获取适配器.

        Args:
            action_type: 动作类型

        Returns:
            ExecutionAdapter | None: 适配器实例，未注册时返回默认适配器或 None
        """
        return self._registry.get(action_type, self._default_adapter)

    def has(self, action_type: ActionType) -> bool:
        """检查是否有注册的适配器."""
        return action_type in self._registry

    def get_all(self) -> dict[ActionType, ExecutionAdapter]:
        """获取所有注册的适配器映射."""
        return dict(self._registry)

    def get_registered_types(self) -> list[ActionType]:
        """获取所有已注册的动作类型."""
        return list(self._registry.keys())

    def get_unique_adapters(self) -> list[ExecutionAdapter]:
        """获取所有唯一的适配器实例 (去重)."""
        seen: set[int] = set()
        unique: list[ExecutionAdapter] = []
        for adapter in self._registry.values():
            if id(adapter) not in seen:
                seen.add(id(adapter))
                unique.append(adapter)
        return unique

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取注册表统计."""
        adapter_stats = {}
        for adapter in self.get_unique_adapters():
            adapter_stats[adapter.name] = adapter.stats()

        return {
            "total_registered": len(self._registry),
            "registered_types": [t.value for t in self._registry],
            "unique_adapters": len(adapter_stats),
            "has_default": self._default_adapter is not None,
            "adapters": adapter_stats,
        }

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, action_type: ActionType) -> bool:
        return self.has(action_type)

    def __repr__(self) -> str:
        return f"AdapterRegistry(types={len(self._registry)}, adapters={len(self.get_unique_adapters())})"


__all__ = ["AdapterRegistry"]