"""E13.6.3 Executor Registry — 执行器注册表.

将 ExecutionActionType 映射到具体的 Executor 实例，实现 Planner 与 Executor 的解耦。

核心设计:
  - register(action_type, executor): 注册执行器
  - get(action_type): 根据动作类型获取执行器
  - has(action_type): 检查是否有注册的执行器
  - domain_routing: 支持按领域批量注册

连接:
  E13.6.3 ExecutionEngine → ExecutorRegistry → BaseExecutor

未来扩展:
  TikTokExecutor / GoogleAdsExecutor / AppleASAExecutor 只需 register() 即可
"""

from __future__ import annotations

from typing import Any

from .base_executor import BaseExecutor
from .models import ExecutionActionType, ExecutionDomain


class ExecutorRegistry:
    """执行器注册表 — 管理 ActionType → Executor 的映射.

    用法:
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.CREATE_CREATIVE, CreativeExecutor())
        registry.register(ExecutionActionType.UPDATE_BUDGET, MetaBudgetExecutor())

        executor = registry.get(action.action_type)
        result = executor.execute(action, guard_context)
    """

    def __init__(self):
        self._registry: dict[ExecutionActionType, BaseExecutor] = {}
        self._domain_registry: dict[ExecutionDomain, list[BaseExecutor]] = {}
        self._default_executor: BaseExecutor | None = None

    # ── 注册 ──────────────────────────────────────────────────

    def register(
        self,
        action_type: ExecutionActionType,
        executor: BaseExecutor,
    ) -> None:
        """注册执行器.

        Args:
            action_type: 动作类型
            executor: 执行器实例
        """
        self._registry[action_type] = executor

    def register_many(
        self,
        mappings: dict[ExecutionActionType, BaseExecutor],
    ) -> None:
        """批量注册执行器."""
        for action_type, executor in mappings.items():
            self._registry[action_type] = executor

    def set_default(self, executor: BaseExecutor) -> None:
        """设置默认执行器 (当找不到匹配的执行器时使用)."""
        self._default_executor = executor

    def unregister(self, action_type: ExecutionActionType) -> None:
        """取消注册."""
        self._registry.pop(action_type, None)

    # ── 查询 ──────────────────────────────────────────────────

    def get(self, action_type: ExecutionActionType) -> BaseExecutor | None:
        """根据动作类型获取执行器.

        Args:
            action_type: 动作类型

        Returns:
            BaseExecutor | None: 执行器实例，未注册时返回默认执行器或 None
        """
        return self._registry.get(action_type, self._default_executor)

    def has(self, action_type: ExecutionActionType) -> bool:
        """检查是否有注册的执行器."""
        return action_type in self._registry

    def get_all(self) -> dict[ExecutionActionType, BaseExecutor]:
        """获取所有注册的执行器."""
        return dict(self._registry)

    def get_registered_types(self) -> list[ExecutionActionType]:
        """获取所有已注册的动作类型."""
        return list(self._registry.keys())

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取注册表统计."""
        executor_stats = {}
        for action_type, executor in self._registry.items():
            if executor.name not in executor_stats:
                executor_stats[executor.name] = executor.stats()

        return {
            "total_registered": len(self._registry),
            "registered_types": [t.value for t in self._registry],
            "has_default": self._default_executor is not None,
            "executors": executor_stats,
        }

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, action_type: ExecutionActionType) -> bool:
        return self.has(action_type)