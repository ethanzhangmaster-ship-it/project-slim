"""E13.7.4 Agent Tool System — Agent 工具系统.

将系统已有能力包装为 Agent 可调用的工具:
  - Tool 定义: 工具名、描述、参数、权限
  - Tool Registry: 工具注册和发现
  - Tool Executor: 工具执行和结果收集
  - 安全控制: 权限检查、审批流程

工具分类:
  - Campaign Tools: 广告系列管理
  - Creative Tools: 创意素材管理
  - Data Tools: 数据查询和分析
  - Memory Tools: 记忆查询和更新
  - Control Tools: 系统控制

连接:
  Agent Tools → Execution Engine, Meta API, Adjust, Memory, Decision Engine
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# Tool Models
# ═══════════════════════════════════════════════════════════════


class ToolCategory(str, Enum):
    """工具分类."""
    CAMPAIGN = "campaign"        # 广告系列管理
    CREATIVE = "creative"        # 创意素材管理
    DATA = "data"                # 数据查询和分析
    MEMORY = "memory"            # 记忆查询和更新
    CONTROL = "control"          # 系统控制
    UTILITY = "utility"          # 通用工具


class ToolPermission(str, Enum):
    """工具权限等级."""
    READ_ONLY = "read_only"      # 只读 (安全)
    SAFE_WRITE = "safe_write"    # 安全写入 (低风险)
    WRITE = "write"              # 写入 (中风险)
    DANGEROUS = "dangerous"      # 危险操作 (需要审批)


class ToolResultStatus(str, Enum):
    """工具执行结果状态."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class ToolDefinition:
    """工具定义 — 描述 Agent 可调用的工具.

    Attributes:
        name: 工具名称 (唯一标识)
        description: 工具描述
        category: 工具分类
        permission: 权限等级
        parameters: 参数定义
        examples: 使用示例
        requires_approval: 是否需要审批
        timeout_seconds: 超时时间
        is_async: 是否异步
    """
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.UTILITY
    permission: ToolPermission = ToolPermission.READ_ONLY
    parameters: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    requires_approval: bool = False
    timeout_seconds: int = 60
    is_async: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "permission": self.permission.value,
            "parameters": self.parameters,
            "examples": self.examples,
            "requires_approval": self.requires_approval,
            "timeout_seconds": self.timeout_seconds,
            "is_async": self.is_async,
        }


@dataclass
class ToolResult:
    """工具执行结果.

    Attributes:
        tool_name: 工具名称
        status: 执行状态
        data: 返回数据
        error: 错误信息
        duration_ms: 执行耗时
        execution_id: 执行 ID
        timestamp: 执行时间
        metadata: 扩展元数据
    """
    tool_name: str = ""
    status: ToolResultStatus = ToolResultStatus.SUCCESS
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status == ToolResultStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Built-in Tool Definitions
# ═══════════════════════════════════════════════════════════════

BUILTIN_TOOLS: dict[str, ToolDefinition] = {
    # ── Campaign Tools ──
    "create_campaign": ToolDefinition(
        name="create_campaign",
        description="创建广告系列 — 在 Meta/Google/TikTok 等平台创建新的广告系列",
        category=ToolCategory.CAMPAIGN,
        permission=ToolPermission.WRITE,
        parameters={
            "platform": {"type": "string", "required": True, "description": "平台 (meta/google/tiktok)"},
            "name": {"type": "string", "required": True, "description": "广告系列名称"},
            "budget": {"type": "number", "required": True, "description": "预算 (美元)"},
            "daily": {"type": "boolean", "required": False, "description": "是否日预算"},
            "objective": {"type": "string", "required": False, "description": "目标 (INSTALLS/CONVERSIONS)"},
        },
        examples=["create_campaign(platform='meta', name='Test_V1', budget=500, daily=True)"],
    ),

    "update_budget": ToolDefinition(
        name="update_budget",
        description="更新预算 — 调整现有广告系列或广告组的预算",
        category=ToolCategory.CAMPAIGN,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "campaign_id": {"type": "string", "required": True, "description": "广告系列 ID"},
            "new_budget": {"type": "number", "required": False, "description": "新预算"},
            "scale_factor": {"type": "number", "required": False, "description": "缩放因子 (1.2=+20%)"},
        },
        examples=["update_budget(campaign_id='123', scale_factor=1.2)"],
    ),

    "pause_campaign": ToolDefinition(
        name="pause_campaign",
        description="暂停广告系列 — 暂停表现不佳的广告系列",
        category=ToolCategory.CAMPAIGN,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "campaign_id": {"type": "string", "required": True, "description": "广告系列 ID"},
            "reason": {"type": "string", "required": False, "description": "暂停原因"},
        },
        examples=["pause_campaign(campaign_id='123', reason='underperforming')"],
    ),

    "resume_campaign": ToolDefinition(
        name="resume_campaign",
        description="恢复广告系列 — 重新激活已暂停的广告系列",
        category=ToolCategory.CAMPAIGN,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "campaign_id": {"type": "string", "required": True, "description": "广告系列 ID"},
        },
        examples=["resume_campaign(campaign_id='123')"],
    ),

    # ── Creative Tools ──
    "mutate_creative": ToolDefinition(
        name="mutate_creative",
        description="素材变异 — 基于现有素材生成新的 DNA 变体",
        category=ToolCategory.CREATIVE,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "variants": {"type": "integer", "required": True, "description": "生成变体数量"},
            "strategy": {"type": "string", "required": False, "description": "变异策略"},
            "based_on_winner": {"type": "boolean", "required": False, "description": "是否基于赢家"},
        },
        examples=["mutate_creative(variants=5, based_on_winner=True)"],
    ),

    "upload_creative": ToolDefinition(
        name="upload_creative",
        description="上传素材 — 将生成的素材上传到广告平台",
        category=ToolCategory.CREATIVE,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "creative_ids": {"type": "array", "required": True, "description": "素材 ID 列表"},
            "platform": {"type": "string", "required": True, "description": "目标平台"},
        },
        examples=["upload_creative(creative_ids=['c1','c2'], platform='meta')"],
    ),

    "generate_creative": ToolDefinition(
        name="generate_creative",
        description="生成素材 — 从零创建新素材 (通过 Lovart 等工具)",
        category=ToolCategory.CREATIVE,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "count": {"type": "integer", "required": True, "description": "生成数量"},
            "template": {"type": "string", "required": False, "description": "模板名称"},
            "specs": {"type": "object", "required": False, "description": "规格参数"},
        },
        examples=["generate_creative(count=3, template='merge_gameplay')"],
    ),

    # ── Data Tools ──
    "query_metrics": ToolDefinition(
        name="query_metrics",
        description="查询指标 — 查询广告系列/素材的实时指标数据",
        category=ToolCategory.DATA,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "entity_type": {"type": "string", "required": True, "description": "实体类型 (campaign/adset/ad)"},
            "entity_id": {"type": "string", "required": False, "description": "实体 ID"},
            "metrics": {"type": "array", "required": True, "description": "指标列表 (spend/impressions/clicks/installs/roas)"},
            "date_range": {"type": "string", "required": True, "description": "日期范围 (today/yesterday/last_7d/last_30d)"},
        },
        examples=["query_metrics(entity_type='campaign', metrics=['spend','roas'], date_range='last_7d')"],
    ),

    "query_adjust": ToolDefinition(
        name="query_adjust",
        description="查询 Adjust 数据 — 查询归因和 LTV 数据",
        category=ToolCategory.DATA,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "app_id": {"type": "string", "required": True, "description": "应用 ID"},
            "metrics": {"type": "array", "required": True, "description": "指标列表"},
            "date_range": {"type": "string", "required": True, "description": "日期范围"},
        },
        examples=["query_adjust(app_id='com.game.app', metrics=['installs','ltv','roas'], date_range='last_7d')"],
    ),

    "query_creative_performance": ToolDefinition(
        name="query_creative_performance",
        description="查询素材表现 — 查询素材级别的表现数据",
        category=ToolCategory.DATA,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "creative_id": {"type": "string", "required": False, "description": "素材 ID (为空则查询所有)"},
            "date_range": {"type": "string", "required": True, "description": "日期范围"},
        },
        examples=["query_creative_performance(date_range='last_7d')"],
    ),

    "check_fatigue": ToolDefinition(
        name="check_fatigue",
        description="检查疲劳 — 检查素材疲劳度",
        category=ToolCategory.DATA,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "creative_id": {"type": "string", "required": False, "description": "素材 ID"},
            "threshold": {"type": "number", "required": False, "description": "疲劳阈值"},
        },
        examples=["check_fatigue(threshold=0.7)"],
    ),

    # ── Memory Tools ──
    "query_memory": ToolDefinition(
        name="query_memory",
        description="查询记忆 — 搜索历史经验、模式和策略记忆",
        category=ToolCategory.MEMORY,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "query": {"type": "string", "required": True, "description": "搜索关键词"},
            "memory_type": {"type": "string", "required": False, "description": "记忆类型 (pattern/strategy/experience/failure)"},
            "top_k": {"type": "integer", "required": False, "description": "返回数量"},
        },
        examples=["query_memory(query='creative fatigue', memory_type='pattern', top_k=5)"],
    ),

    "update_memory": ToolDefinition(
        name="update_memory",
        description="更新记忆 — 写入新的经验或更新已有知识",
        category=ToolCategory.MEMORY,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "concept": {"type": "string", "required": True, "description": "概念/主题"},
            "description": {"type": "string", "required": True, "description": "描述"},
            "confidence": {"type": "number", "required": False, "description": "置信度"},
        },
        examples=["update_memory(concept='Merge素材', description='女性25-44用户CTR+32%', confidence=0.85)"],
    ),

    "record_episode": ToolDefinition(
        name="record_episode",
        description="记录情景 — 记录完整的决策→执行→结果循环",
        category=ToolCategory.MEMORY,
        permission=ToolPermission.SAFE_WRITE,
        parameters={
            "goal": {"type": "object", "required": True, "description": "目标"},
            "plan": {"type": "object", "required": True, "description": "计划"},
            "actions": {"type": "array", "required": True, "description": "执行的动作"},
            "results": {"type": "array", "required": True, "description": "执行结果"},
            "outcome": {"type": "string", "required": True, "description": "结果评估"},
            "lessons": {"type": "array", "required": False, "description": "经验教训"},
        },
        examples=["record_episode(goal={...}, plan={...}, actions=[...], results=[...], outcome='positive')"],
    ),

    # ── Control Tools ──
    "monitor": ToolDefinition(
        name="monitor",
        description="监控 — 持续监控指标变化",
        category=ToolCategory.CONTROL,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "duration_hours": {"type": "integer", "required": True, "description": "监控时长 (小时)"},
            "metrics": {"type": "array", "required": False, "description": "监控指标"},
            "alert_threshold": {"type": "object", "required": False, "description": "告警阈值"},
        },
        examples=["monitor(duration_hours=24, metrics=['spend','roas'])"],
    ),

    "collect_result": ToolDefinition(
        name="collect_result",
        description="收集结果 — 收集执行结果和反馈数据",
        category=ToolCategory.CONTROL,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "plan_id": {"type": "string", "required": True, "description": "计划 ID"},
            "wait_for_data": {"type": "boolean", "required": False, "description": "是否等待数据回流"},
        },
        examples=["collect_result(plan_id='plan_123', wait_for_data=True)"],
    ),

    "wait": ToolDefinition(
        name="wait",
        description="等待 — 等待指定时间或外部条件",
        category=ToolCategory.CONTROL,
        permission=ToolPermission.READ_ONLY,
        parameters={
            "duration_hours": {"type": "number", "required": False, "description": "等待时长 (小时)"},
            "condition": {"type": "string", "required": False, "description": "等待条件"},
        },
        examples=["wait(duration_hours=4)"],
    ),
}


# ═══════════════════════════════════════════════════════════════
# Tool Registry
# ═══════════════════════════════════════════════════════════════


class ToolRegistry:
    """工具注册表 — 管理所有 Agent 可用的工具.

    用法:
        registry = ToolRegistry()
        registry.register("create_campaign", ToolDefinition(...), handler_func)
        result = registry.execute("create_campaign", {"platform": "meta", "budget": 500})
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}
        self._execution_count: int = 0
        self._execution_history: list[ToolResult] = []

    # ── 注册 ──────────────────────────────────────────────────

    def register(
        self,
        name: str,
        definition: ToolDefinition,
        handler: Callable[..., ToolResult],
    ) -> None:
        """注册工具.

        Args:
            name: 工具名称
            definition: 工具定义
            handler: 执行函数
        """
        self._tools[name] = definition
        self._handlers[name] = handler

    def register_batch(
        self,
        tools: dict[str, tuple[ToolDefinition, Callable[..., ToolResult]]],
    ) -> None:
        """批量注册工具."""
        for name, (definition, handler) in tools.items():
            self.register(name, definition, handler)

    def unregister(self, name: str) -> bool:
        """注销工具."""
        if name in self._tools:
            del self._tools[name]
            self._handlers.pop(name, None)
            return True
        return False

    # ── 查询 ──────────────────────────────────────────────────

    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取工具定义."""
        return self._tools.get(name)

    def list_tools(self, category: ToolCategory | None = None) -> list[ToolDefinition]:
        """列出工具."""
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def list_tool_names(self) -> list[str]:
        """列出工具名称."""
        return list(self._tools.keys())

    def get_tools_by_permission(self, permission: ToolPermission) -> list[ToolDefinition]:
        """按权限列出工具."""
        return [t for t in self._tools.values() if t.permission == permission]

    def get_categories(self) -> list[ToolCategory]:
        """获取所有工具分类."""
        return list({t.category for t in self._tools.values()})

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在."""
        return name in self._tools

    # ── 执行 ──────────────────────────────────────────────────

    def execute(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
        require_approval_check: bool = True,
        execution_context: Any | None = None,
    ) -> ToolResult:
        """执行工具.

        Args:
            tool_name: 工具名称
            params: 参数
            require_approval_check: 是否检查审批
            execution_context: 执行上下文 (ToolExecutionContext) — 传递给 Adapter

        Returns:
            ToolResult: 执行结果
        """
        params = params or {}

        # 检查工具是否存在
        if tool_name not in self._tools:
            return ToolResult(
                tool_name=tool_name,
                status=ToolResultStatus.FAILED,
                error=f"Tool '{tool_name}' not found",
            )

        definition = self._tools[tool_name]

        # 审批检查
        if require_approval_check and definition.requires_approval:
            return ToolResult(
                tool_name=tool_name,
                status=ToolResultStatus.APPROVAL_REQUIRED,
                error=f"Tool '{tool_name}' requires approval",
            )

        # 执行
        handler = self._handlers.get(tool_name)
        if not handler:
            return ToolResult(
                tool_name=tool_name,
                status=ToolResultStatus.FAILED,
                error=f"No handler for tool '{tool_name}'",
            )

        start = datetime.now(timezone.utc)
        try:
            # 传递 execution_context 给 handler (Adapter handler 需要)
            if execution_context is not None:
                result = handler(**params, execution_context=execution_context)
            else:
                result = handler(**params)
            if isinstance(result, ToolResult):
                result.tool_name = tool_name
                result.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                self._execution_count += 1
                self._execution_history.append(result)
                return result
            else:
                tool_result = ToolResult(
                    tool_name=tool_name,
                    status=ToolResultStatus.SUCCESS,
                    data=result,
                    duration_ms=(datetime.now(timezone.utc) - start).total_seconds() * 1000,
                )
                self._execution_count += 1
                self._execution_history.append(tool_result)
                return tool_result
        except Exception as e:
            error_result = ToolResult(
                tool_name=tool_name,
                status=ToolResultStatus.FAILED,
                error=str(e),
                duration_ms=(datetime.now(timezone.utc) - start).total_seconds() * 1000,
            )
            self._execution_history.append(error_result)
            return error_result

    def execute_batch(
        self,
        calls: list[tuple[str, dict[str, Any]]],
    ) -> list[ToolResult]:
        """批量执行工具."""
        results = []
        for tool_name, params in calls:
            result = self.execute(tool_name, params)
            results.append(result)
        return results

    # ── 工具描述 (供 LLM 使用) ────────────────────────────────

    def generate_tool_prompt(self) -> str:
        """生成工具描述 prompt (供 LLM 函数调用)."""
        lines = ["Available Tools:"]
        for name, tool in self._tools.items():
            lines.append(f"\n## {name}")
            lines.append(f"Description: {tool.description}")
            lines.append(f"Category: {tool.category.value}")
            lines.append(f"Permission: {tool.permission.value}")
            lines.append(f"Parameters: {tool.parameters}")
            if tool.examples:
                lines.append(f"Examples: {tool.examples}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """序列化所有工具定义."""
        return {name: tool.to_dict() for name, tool in self._tools.items()}

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def execution_count(self) -> int:
        return self._execution_count

    def get_execution_history(self, n: int = 20) -> list[ToolResult]:
        """获取执行历史."""
        return self._execution_history[-n:]

    def reset(self) -> None:
        self._execution_count = 0
        self._execution_history.clear()


# ═══════════════════════════════════════════════════════════════
# Mock Tool Handlers
# ═══════════════════════════════════════════════════════════════


def _mock_handler(**kwargs) -> ToolResult:
    """通用 mock 处理器 — 返回模拟成功结果."""
    return ToolResult(
        status=ToolResultStatus.SUCCESS,
        data={"mock": True, "params": kwargs},
    )


def create_default_registry() -> ToolRegistry:
    """创建默认工具注册表 — 注册所有内置工具 (mock 模式).

    Returns:
        ToolRegistry: 预配置的工具注册表
    """
    registry = ToolRegistry()

    for name, definition in BUILTIN_TOOLS.items():
        registry.register(name, definition, _mock_handler)

    return registry


def create_registry_with_handlers(
    handlers: dict[str, Callable[..., ToolResult]],
) -> ToolRegistry:
    """创建带自定义处理器的工具注册表.

    Args:
        handlers: 工具名 → 处理函数的映射

    Returns:
        ToolRegistry: 预配置的工具注册表
    """
    registry = ToolRegistry()

    for name, definition in BUILTIN_TOOLS.items():
        handler = handlers.get(name, _mock_handler)
        registry.register(name, definition, handler)

    return registry