"""E13.7.1 Real Tool Adapter — 真实工具适配器.

将 Agent 工具调用连接到真实的 E13 系统组件:
  - ExecutionAdapter: 连接 E13.6 Execution Engine
  - MetaAdapter: 连接 Meta Ads API
  - AdjustAdapter: 连接 Adjust 数据 API
  - CreativeAdapter: 连接 E11 Creative Evolution
  - MemoryAdapter: 连接 E13.4 Memory Kernel
  - KnowledgeAdapter: 连接 Knowledge Graph

架构:
  GrowthAgent
    ↓
  ToolRegistry
    ↓
  RealToolAdapter (基类)
    ↓
  具体 Adapter → E13 系统组件 → 外部 API
    ↓
  ToolResult → 返回给 Agent

所有 Adapter 遵循相同的接口:
  class SpecificAdapter(ToolAdapter):
      @property
      def name(self) -> str:
          return "specific"

      def can_handle(self, action_name: str) -> bool:
          return action_name == "specific_action"

      def execute(self, params: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
          # 实现执行逻辑
          return ToolResult(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ..agent_tools import ToolResult, ToolResultStatus


# ═══════════════════════════════════════════════════════════════
# Tool Execution Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class ToolExecutionContext:
    """工具执行上下文 — 传递给 Adapter 执行的上下文信息.

    Attributes:
        session_id: Agent 会话 ID
        cycle_number: 当前循环编号
        agent_phase: 当前 Agent 阶段
        metrics_snapshot: 当前指标快照
        risk_level: 当前风险等级
        execution_mode: 执行模式 (MOCK/DRY_RUN/REAL)
        require_approval: 是否需要审批
        metadata: 扩展元数据
    """
    session_id: str = ""
    cycle_number: int = 0
    agent_phase: str = ""
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "safe"
    execution_mode: str = "mock"
    require_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cycle_number": self.cycle_number,
            "agent_phase": self.agent_phase,
            "metrics_snapshot": self.metrics_snapshot,
            "risk_level": self.risk_level,
            "execution_mode": self.execution_mode,
            "require_approval": self.require_approval,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Base Tool Adapter
# ═══════════════════════════════════════════════════════════════


class ToolAdapter:
    """工具适配器基类 — 所有 Real Adapter 都继承此类.

    每个 Adapter 负责将 Agent 工具调用转换为对 E13 系统或外部 API 的实际调用。
    子类必须实现:
      - name: 适配器名称
      - can_handle(action_name): 判断是否能处理该动作
      - execute(params, context): 执行并返回 ToolResult
    """

    @property
    def name(self) -> str:
        """适配器名称."""
        return "base"

    def can_handle(self, action_name: str) -> bool:
        """判断此适配器是否能处理该动作.

        Args:
            action_name: 动作名称 (e.g., 'create_campaign', 'mutate_creative')

        Returns:
            bool: 是否可以处理
        """
        raise NotImplementedError("Subclasses must implement can_handle")

    def execute(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """执行工具调用.

        Args:
            action_name: 动作名称
            params: 调用参数
            context: 执行上下文

        Returns:
            ToolResult: 执行结果
        """
        raise NotImplementedError("Subclasses must implement execute")


# ═══════════════════════════════════════════════════════════════
# Adapter Registry
# ═══════════════════════════════════════════════════════════════


class AdapterRegistry:
    """适配器注册表 — 管理所有已注册的 Adapter.

    用法:
        registry = AdapterRegistry()
        registry.register(ExecutionAdapter())
        registry.register(MetaAdapter())
        result = registry.execute(action_name, params, context)
    """

    def __init__(self):
        self._adapters: dict[str, ToolAdapter] = {}
        self._action_map: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        """注册适配器."""
        self._adapters[adapter.name] = adapter
        # 适配器通过 can_handle 声明它能处理哪些动作
        # 这里不预先绑定，让适配器动态判断

    def find_adapter(self, action_name: str) -> ToolAdapter | None:
        """查找能处理该动作的适配器.

        Args:
            action_name: 动作名称

        Returns:
            找到的适配器，None 表示未找到
        """
        # 先检查缓存
        if action_name in self._action_map:
            return self._action_map[action_name]

        # 动态查找
        for adapter in self._adapters.values():
            if adapter.can_handle(action_name):
                self._action_map[action_name] = adapter
                return adapter

        return None

    def execute(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """执行动作.

        Args:
            action_name: 动作名称
            params: 参数
            context: 执行上下文

        Returns:
            ToolResult: 执行结果
        """
        adapter = self.find_adapter(action_name)
        if adapter is None:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"No adapter found for action '{action_name}'",
            )

        start = datetime.now(timezone.utc)
        try:
            result = adapter.execute(action_name, params, context)
            result.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return result
        except Exception as e:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=str(e),
                duration_ms=(datetime.now(timezone.utc) - start).total_seconds() * 1000,
            )

    def list_adapters(self) -> list[str]:
        """列出所有已注册适配器名称."""
        return list(self._adapters.keys())

    def get_adapter(self, name: str) -> ToolAdapter | None:
        """按名称获取适配器."""
        return self._adapters.get(name)

    @property
    def count(self) -> int:
        """已注册适配器数量."""
        return len(self._adapters)


# ═══════════════════════════════════════════════════════════════
# Default Registry Builder
# ═══════════════════════════════════════════════════════════════


def create_default_adapter_registry() -> AdapterRegistry:
    """创建默认适配器注册表，注册所有内置 Adapter.

    Returns:
        预配置的注册表
    """
    from .execution_adapter import ExecutionAdapter
    from .meta_adapter import MetaAdapter
    from .adjust_adapter import AdjustAdapter
    from .creative_adapter import CreativeAdapter
    from .memory_adapter import MemoryAdapter

    registry = AdapterRegistry()
    registry.register(ExecutionAdapter())
    registry.register(MetaAdapter())
    registry.register(AdjustAdapter())
    registry.register(CreativeAdapter())
    registry.register(MemoryAdapter())

    return registry