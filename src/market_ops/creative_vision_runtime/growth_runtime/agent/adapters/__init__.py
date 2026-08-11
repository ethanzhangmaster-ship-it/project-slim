"""E13.7.1 Real Tool Adapters — 真实工具适配器包.

将 Agent 工具调用连接到真实的 E13 系统组件。

适配器:
  - ExecutionAdapter: → E13.6 Execution Engine
  - MetaAdapter: → Meta Ads API
  - AdjustAdapter: → Adjust 数据 API
  - CreativeAdapter: → E11 Creative Evolution
  - MemoryAdapter: → E13.4 Memory Kernel

基础:
  - ToolAdapter: 适配器基类
  - AdapterRegistry: 适配器注册表
  - ToolExecutionContext: 执行上下文
"""

from .adjust_adapter import AdjustAdapter
from .creative_adapter import CreativeAdapter
from .execution_adapter import ExecutionAdapter
from .memory_adapter import MemoryAdapter
from .meta_adapter import MetaAdapter
from .tool_adapter import (
    AdapterRegistry,
    ToolAdapter,
    ToolExecutionContext,
    create_default_adapter_registry,
)

__all__ = [
    # Base
    "ToolAdapter",
    "ToolExecutionContext",
    "AdapterRegistry",
    "create_default_adapter_registry",
    # Adapters
    "ExecutionAdapter",
    "MetaAdapter",
    "AdjustAdapter",
    "CreativeAdapter",
    "MemoryAdapter",
]