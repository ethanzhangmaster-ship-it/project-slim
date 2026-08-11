"""E13.7.1 Real Tool Registry — 真实工具注册表.

将 Agent 的 ToolRegistry 从 Mock Handler 升级为真实 Adapter 连接。

用法:
    # 替换 Mock Handler 为 Real Adapter
    from growth_runtime.agent import ToolRegistry, create_default_registry
    from growth_runtime.agent.real_tool_registry import upgrade_to_real

    registry = create_default_registry()
    registry = upgrade_to_real(registry)
    # 现在 registry 的工具调用会通过 Real Adapter 执行

    # 或者直接创建带真实适配器的注册表
    registry = create_real_tool_registry()

架构:
    ToolRegistry
        ↓
    Real Tool Registry (本文件)
        ↓
    AdapterRegistry
        ↓
    ExecutionAdapter / MetaAdapter / AdjustAdapter / CreativeAdapter / MemoryAdapter
        ↓
    E13 系统组件 / 外部 API
"""

from __future__ import annotations

from typing import Any

from .adapters import (
    AdapterRegistry,
    AdjustAdapter,
    CreativeAdapter,
    ExecutionAdapter,
    MemoryAdapter,
    MetaAdapter,
    ToolExecutionContext,
    create_default_adapter_registry,
)
from .agent_tools import (
    BUILTIN_TOOLS,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    create_default_registry,
)


# ═══════════════════════════════════════════════════════════════
# Action → Adapter 映射
# ═══════════════════════════════════════════════════════════════

# 定义每个工具操作对应的适配器
ACTION_ADAPTER_MAP: dict[str, str] = {
    # Execution Adapter
    "create_campaign": "execution_adapter",
    "update_budget": "execution_adapter",
    "pause_campaign": "execution_adapter",
    "resume_campaign": "execution_adapter",
    "monitor": "execution_adapter",
    "collect_result": "execution_adapter",
    # Meta Adapter (平台特定)
    # "create_campaign" 和 "update_budget" 等也在 MetaAdapter 中
    # 优先级: ExecutionAdapter > MetaAdapter (先尝试执行引擎)
    # Creative Adapter
    "mutate_creative": "creative_adapter",
    "generate_creative": "creative_adapter",
    "upload_creative": "creative_adapter",
    # Adjust Adapter
    "query_metrics": "adjust_adapter",
    "query_adjust": "adjust_adapter",
    "query_creative_performance": "adjust_adapter",
    "check_fatigue": "adjust_adapter",
    # Memory Adapter
    "query_memory": "memory_adapter",
    "update_memory": "memory_adapter",
    "record_episode": "memory_adapter",
    # Control Tools → Execution Adapter
    "wait": "execution_adapter",
}


# ═══════════════════════════════════════════════════════════════
# Real Tool Handler Factory
# ═══════════════════════════════════════════════════════════════


def create_real_handler(
    adapter_registry: AdapterRegistry,
    context: ToolExecutionContext | None = None,
):
    """创建真实工具处理器 — 将 ToolRegistry 的 handler 替换为真实 Adapter 调用.

    Args:
        adapter_registry: 适配器注册表
        context: 执行上下文

    Returns:
        Callable: 工具处理函数
    """
    def real_handler(**kwargs) -> ToolResult:
        # 从 kwargs 中提取工具名称 (通过闭包)
        tool_name = real_handler._tool_name if hasattr(real_handler, "_tool_name") else "unknown"
        ctx = context or ToolExecutionContext()

        result = adapter_registry.execute(tool_name, kwargs, ctx)
        return result

    return real_handler


# ═══════════════════════════════════════════════════════════════
# Registry Upgrade
# ═══════════════════════════════════════════════════════════════


def upgrade_to_real(
    registry: ToolRegistry,
    adapter_registry: AdapterRegistry | None = None,
    context: ToolExecutionContext | None = None,
) -> ToolRegistry:
    """将 ToolRegistry 升级为真实工具注册表.

    替换所有内置工具的 mock handler 为真实 Adapter 调用。

    Args:
        registry: 现有的 ToolRegistry (通常由 create_default_registry() 创建)
        adapter_registry: 适配器注册表 (默认自动创建)
        context: 执行上下文

    Returns:
        ToolRegistry: 升级后的注册表 (原地修改)
    """
    adapter_registry = adapter_registry or create_default_adapter_registry()
    ctx = context or ToolExecutionContext()

    for tool_name in BUILTIN_TOOLS:
        if registry.has_tool(tool_name):
            # 创建真实 handler
            handler = _make_adapter_handler(tool_name, adapter_registry, ctx)
            # 重新注册
            definition = registry.get_tool(tool_name)
            registry.unregister(tool_name)
            registry.register(tool_name, definition, handler)

    return registry


def create_real_tool_registry(
    context: ToolExecutionContext | None = None,
) -> ToolRegistry:
    """创建带真实适配器的 ToolRegistry.

    直接创建已连接真实 Adapter 的工具注册表。

    Args:
        context: 执行上下文

    Returns:
        ToolRegistry: 预配置的真实工具注册表
    """
    registry = create_default_registry()
    return upgrade_to_real(registry, context=context)


# ═══════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _make_adapter_handler(
    tool_name: str,
    adapter_registry: AdapterRegistry,
    default_context: ToolExecutionContext,
):
    """创建单个工具的适配器处理器.

    handler 通过 execution_context 参数接收动态上下文，
    若未传入则使用 default_context。
    """
    def handler(**kwargs) -> ToolResult:
        # 从 kwargs 中提取 execution_context (ToolRegistry 传入)
        ctx = kwargs.pop("execution_context", default_context)
        if not isinstance(ctx, ToolExecutionContext):
            ctx = default_context
        return adapter_registry.execute(tool_name, kwargs, ctx)

    handler._tool_name = tool_name
    return handler