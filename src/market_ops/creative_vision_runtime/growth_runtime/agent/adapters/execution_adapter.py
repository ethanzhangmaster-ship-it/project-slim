"""E13.7.1 Execution Adapter — 连接 E13.6 Execution Engine.

将 Agent 的执行动作转换为 ExecutionTask 并提交给 Execution Engine 执行。

处理的工具:
  - create_campaign → ExecutionEngine
  - update_budget → ExecutionEngine
  - pause_campaign → ExecutionEngine
  - resume_campaign → ExecutionEngine
  - monitor → ExecutionEngine
  - collect_result → ExecutionEngine

连接:
  Agent Tool → ExecutionAdapter → ExecutionEngine → Executor → AuditLog
"""

from __future__ import annotations

from typing import Any

from ..agent_tools import ToolResult, ToolResultStatus
from .tool_adapter import ToolAdapter, ToolExecutionContext


class ExecutionAdapter(ToolAdapter):
    """执行适配器 — 连接 E13.6 Execution Engine.

    将 Agent 的工具调用转换为 ExecutionTask 并提交给 Execution Engine。
    如果 Execution Engine 不可用，降级为 mock 模式返回合理结果。
    """

    # 该适配器处理的动作
    HANDLED_ACTIONS = {
        "create_campaign",
        "update_budget",
        "pause_campaign",
        "resume_campaign",
        "monitor",
        "collect_result",
        "wait",
    }

    @property
    def name(self) -> str:
        return "execution_adapter"

    def can_handle(self, action_name: str) -> bool:
        return action_name in self.HANDLED_ACTIONS

    def execute(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        mode = context.execution_mode

        if mode == "mock":
            return self._execute_mock(action_name, params)
        elif mode == "dry_run":
            return self._execute_dry_run(action_name, params)
        elif mode == "real":
            return self._execute_via_engine(action_name, params, context)

        return self._execute_mock(action_name, params)

    def _execute_via_engine(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """通过 Execution Engine 执行 (real 模式)."""
        try:
            return self._execute_engine_internal(action_name, params, context)
        except ImportError:
            return self._execute_mock(action_name, params)

    def _execute_engine_internal(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """内部调用 Execution Engine."""
        from ..execution.models import (
            ExecutionAction,
            ExecutionActionType,
            ExecutionDomain,
            ExecutionPriority,
            ExecutionStatus,
        )
        from ..execution.execution_core import ExecutionEngine, EngineResult

        # 映射动作名称到 ExecutionActionType
        action_type_map = {
            "create_campaign": ExecutionActionType.CREATE_CAMPAIGN,
            "update_budget": ExecutionActionType.UPDATE_BUDGET,
            "pause_campaign": ExecutionActionType.PAUSE_CAMPAIGN,
            "resume_campaign": ExecutionActionType.UPDATE_CAMPAIGN,
            "monitor": ExecutionActionType.MONITOR,
            "collect_result": ExecutionActionType.COLLECT_RESULT,
        }

        exec_action_type = action_type_map.get(action_name)
        if exec_action_type is None:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"Unknown action type: {action_name}",
            )

        # 构建 ExecutionAction
        action = ExecutionAction(
            action_type=exec_action_type,
            domain=ExecutionDomain.BUDGET if "budget" in action_name else ExecutionDomain.GROWTH,
            priority=ExecutionPriority.HIGH,
            parameters=params,
        )

        # 创建 ExecutionEngine 并执行
        engine = ExecutionEngine()
        result = engine.execute_action(action)

        if result.status == ExecutionStatus.SUCCESS:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.SUCCESS,
                data={
                    "action_id": action.action_id,
                    "status": result.status.value,
                    "message": "Execution completed",
                },
            )
        else:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"Execution failed: {result.status.value}",
                data={"action_id": action.action_id},
            )

    def _execute_mock(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """降级 mock 执行."""
        mock_results = {
            "create_campaign": {"campaign_id": "mock_campaign_001", "status": "ACTIVE"},
            "update_budget": {"campaign_id": params.get("campaign_id", "mock"), "new_budget": params.get("new_budget", 0)},
            "pause_campaign": {"campaign_id": params.get("campaign_id", "mock"), "status": "PAUSED"},
            "resume_campaign": {"campaign_id": params.get("campaign_id", "mock"), "status": "ACTIVE"},
            "monitor": {"status": "monitoring", "duration_hours": params.get("duration_hours", 24)},
            "collect_result": {"status": "collected", "data_available": True},
            "wait": {"status": "waited", "duration_seconds": params.get("seconds", 60)},
        }

        return ToolResult(
            tool_name=action_name,
            status=ToolResultStatus.SUCCESS,
            data=mock_results.get(action_name, {"status": "ok"}),
            metadata={"mode": "mock", "reason": "ExecutionEngine not available"},
        )

    def _execute_dry_run(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """干运行 — 校验参数但不执行."""
        # 基本参数校验
        if action_name == "create_campaign":
            if "budget" not in params or params.get("budget", 0) <= 0:
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.FAILED,
                    error="Invalid budget",
                )
        elif action_name in ("update_budget", "pause_campaign", "resume_campaign"):
            if "campaign_id" not in params:
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.FAILED,
                    error="Missing campaign_id",
                )

        return ToolResult(
            tool_name=action_name,
            status=ToolResultStatus.SUCCESS,
            data={"dry_run": True, "params": params},
            metadata={"mode": "dry_run"},
        )