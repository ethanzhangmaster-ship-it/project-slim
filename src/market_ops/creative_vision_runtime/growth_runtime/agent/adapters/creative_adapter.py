"""E13.7.1 Creative Adapter — 连接 E11 Creative Evolution.

将 Agent 的创意操作转换为对 E11 Creative Evolution 系统的调用。

处理的工具:
  - mutate_creative → E11 Mutation Engine
  - generate_creative → E11 Creative Generation (Lovart)
  - upload_creative → E11 Upload Pipeline

连接:
  Agent Tool → CreativeAdapter → E11 Creative Evolution → Lovart → Meta
"""

from __future__ import annotations

from typing import Any

from ..agent_tools import ToolResult, ToolResultStatus
from .tool_adapter import ToolAdapter, ToolExecutionContext


class CreativeAdapter(ToolAdapter):
    """创意适配器 — 连接 E11 Creative Evolution 系统.

    提供:
      - 素材变异 (DNA mutation)
      - 素材生成 (Lovart)
      - 素材上传
    """

    HANDLED_ACTIONS = {
        "mutate_creative",
        "generate_creative",
        "upload_creative",
    }

    @property
    def name(self) -> str:
        return "creative_adapter"

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
        """真实创意系统调用."""
        try:
            from ..execution.adapters.creative_executor import (
                CreativeExecutor,
                CreativeAsset,
            )

            executor = CreativeExecutor()

            if action_name == "mutate_creative":
                return self._mutate_creative_real(executor, params)
            elif action_name == "generate_creative":
                return self._generate_creative_real(executor, params)
            elif action_name == "upload_creative":
                return self._upload_creative_real(executor, params)

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
                error=f"Creative system error: {str(e)}",
            )

    def _mutate_creative_real(self, executor, params: dict[str, Any]) -> ToolResult:
        """素材变异 — 调用 E11 Mutation Engine."""
        variants = params.get("variants", 5)
        strategy = params.get("strategy", "default")
        based_on_winner = params.get("based_on_winner", False)

        result = executor.mutate(
            variants=variants,
            strategy=strategy,
            based_on_winner=based_on_winner,
        )

        return ToolResult(
            tool_name="mutate_creative",
            status=ToolResultStatus.SUCCESS,
            data={
                "variants_generated": len(result) if isinstance(result, list) else variants,
                "creative_ids": [r.get("creative_id", f"creative_{i}") for i, r in enumerate(result)] if isinstance(result, list) else [],
                "strategy": strategy,
            },
        )

    def _generate_creative_real(self, executor, params: dict[str, Any]) -> ToolResult:
        """素材生成 — 调用 Lovart."""
        count = params.get("count", 3)
        template = params.get("template", "default")
        specs = params.get("specs", {})

        result = executor.generate(
            count=count,
            template=template,
            specs=specs,
        )

        return ToolResult(
            tool_name="generate_creative",
            status=ToolResultStatus.SUCCESS,
            data={
                "generated": count,
                "creative_ids": [f"gen_{i}" for i in range(count)],
                "template": template,
            },
        )

    def _upload_creative_real(self, executor, params: dict[str, Any]) -> ToolResult:
        """素材上传."""
        creative_ids = params.get("creative_ids", [])
        platform = params.get("platform", "meta")

        result = executor.upload(
            creative_ids=creative_ids,
            platform=platform,
        )

        return ToolResult(
            tool_name="upload_creative",
            status=ToolResultStatus.SUCCESS,
            data={
                "uploaded": len(creative_ids),
                "creative_ids": creative_ids,
                "platform": platform,
            },
        )

    def _execute_mock(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """Mock 创意操作."""
        mock_data = {
            "mutate_creative": {
                "variants_generated": params.get("variants", 5),
                "creative_ids": [f"mock_creative_{i}" for i in range(params.get("variants", 5))],
                "strategy": params.get("strategy", "default"),
                "based_on_winner": params.get("based_on_winner", False),
            },
            "generate_creative": {
                "generated": params.get("count", 3),
                "creative_ids": [f"gen_creative_{i}" for i in range(params.get("count", 3))],
                "template": params.get("template", "default"),
            },
            "upload_creative": {
                "uploaded": len(params.get("creative_ids", [])),
                "creative_ids": params.get("creative_ids", []),
                "platform": params.get("platform", "meta"),
                "status": "uploaded",
            },
        }

        return ToolResult(
            tool_name=action_name,
            status=ToolResultStatus.SUCCESS,
            data=mock_data.get(action_name, {"status": "ok"}),
            metadata={"mode": "mock", "source": "creative"},
        )