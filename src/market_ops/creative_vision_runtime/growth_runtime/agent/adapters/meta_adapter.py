"""E13.7.1 Meta Adapter — 连接 Meta Ads API.

将 Agent 的 Meta 平台操作转换为对 Meta Ads API 的真实调用。

处理的工具:
  - create_campaign → Meta Ads API
  - update_budget → Meta Ads API
  - pause_campaign → Meta Ads API
  - resume_campaign → Meta Ads API
  - upload_creative → Meta Ads API

支持执行模式:
  - MOCK: 返回模拟数据
  - DRY_RUN: 校验但不执行
  - REAL: 真实 API 调用 (需要 Meta 凭证)

连接:
  Agent Tool → MetaAdapter → MetaAPIClient → Meta Ads API
"""

from __future__ import annotations

from typing import Any

from ..agent_tools import ToolResult, ToolResultStatus
from .tool_adapter import ToolAdapter, ToolExecutionContext


class MetaAdapter(ToolAdapter):
    """Meta 适配器 — 连接 Meta Ads API.

    封装 Meta 广告平台的创建/更新/暂停/恢复操作。
    支持降级: 当 Meta API 不可用时自动降级为 mock。
    """

    HANDLED_ACTIONS = {
        "create_campaign",
        "update_budget",
        "pause_campaign",
        "resume_campaign",
        "upload_creative",
    }

    @property
    def name(self) -> str:
        return "meta_adapter"

    def can_handle(self, action_name: str) -> bool:
        return action_name in self.HANDLED_ACTIONS

    def execute(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        platform = params.get("platform", "").lower()

        # 只处理 Meta 平台的请求
        if platform and platform not in ("meta", "facebook"):
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"MetaAdapter does not handle platform '{platform}'",
            )

        # 按模式执行
        mode = context.execution_mode
        if mode == "mock":
            return self._execute_mock(action_name, params)
        elif mode == "dry_run":
            return self._execute_dry_run(action_name, params)
        elif mode == "real":
            return self._execute_real(action_name, params, context)
        else:
            return self._execute_mock(action_name, params)

    def _execute_real(
        self,
        action_name: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """真实 Meta API 调用."""
        try:
            from ..execution.adapters.adapter_models import (
                APIRequest,
                APIResponse,
                PlatformType,
            )
            from ..execution.adapters.meta_executor import MetaAPIClient

            client = MetaAPIClient()

            if action_name == "create_campaign":
                response = client.create_campaign(
                    name=params.get("name", "Auto Campaign"),
                    budget=params.get("budget", 500),
                    daily=params.get("daily", True),
                    objective=params.get("objective", "INSTALLS"),
                )
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data={"campaign_id": response.get("campaign_id", ""), "status": "ACTIVE"},
                )

            elif action_name == "update_budget":
                response = client.update_budget(
                    campaign_id=params.get("campaign_id", ""),
                    new_budget=params.get("new_budget"),
                    scale_factor=params.get("scale_factor"),
                )
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data=response,
                )

            elif action_name == "pause_campaign":
                response = client.pause_campaign(
                    campaign_id=params.get("campaign_id", ""),
                )
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data={"campaign_id": params.get("campaign_id"), "status": "PAUSED"},
                )

            elif action_name == "resume_campaign":
                response = client.resume_campaign(
                    campaign_id=params.get("campaign_id", ""),
                )
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data={"campaign_id": params.get("campaign_id"), "status": "ACTIVE"},
                )

            elif action_name == "upload_creative":
                response = client.upload_creative(
                    creative_ids=params.get("creative_ids", []),
                )
                return ToolResult(
                    tool_name=action_name,
                    status=ToolResultStatus.SUCCESS,
                    data=response,
                )

            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"Unknown action: {action_name}",
            )

        except ImportError:
            return self._execute_mock(action_name, params)
        except Exception as e:
            return ToolResult(
                tool_name=action_name,
                status=ToolResultStatus.FAILED,
                error=f"Meta API error: {str(e)}",
            )

    def _execute_dry_run(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """干运行 — 校验参数但不执行."""
        # 基本参数校验
        if action_name == "create_campaign":
            if "budget" not in params or params["budget"] <= 0:
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

    def _execute_mock(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """Mock 执行."""
        mock_results = {
            "create_campaign": {
                "campaign_id": "meta_mock_campaign_001",
                "status": "ACTIVE",
                "platform": "meta",
            },
            "update_budget": {
                "campaign_id": params.get("campaign_id", "mock"),
                "new_budget": params.get("new_budget", 0),
                "platform": "meta",
            },
            "pause_campaign": {
                "campaign_id": params.get("campaign_id", "mock"),
                "status": "PAUSED",
                "platform": "meta",
            },
            "resume_campaign": {
                "campaign_id": params.get("campaign_id", "mock"),
                "status": "ACTIVE",
                "platform": "meta",
            },
            "upload_creative": {
                "uploaded_ids": params.get("creative_ids", []),
                "platform": "meta",
                "status": "uploaded",
            },
        }

        return ToolResult(
            tool_name=action_name,
            status=ToolResultStatus.SUCCESS,
            data=mock_results.get(action_name, {"status": "ok"}),
            metadata={"mode": "mock", "platform": "meta"},
        )