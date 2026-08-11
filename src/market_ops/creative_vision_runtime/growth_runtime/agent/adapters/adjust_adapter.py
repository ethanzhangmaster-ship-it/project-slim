"""E13.7.1 Adjust Adapter — 连接 Adjust 数据 API.

将 Agent 的数据查询操作转换为对 Adjust API 的调用。

处理的工具:
  - query_metrics → Adjust API
  - query_adjust → Adjust API
  - query_creative_performance → Adjust API
  - check_fatigue → Adjust API + 内部计算

连接:
  Agent Tool → AdjustAdapter → AdjustDataClient → Adjust API
"""

from __future__ import annotations

from typing import Any

from ..agent_tools import ToolResult, ToolResultStatus
from .tool_adapter import ToolAdapter, ToolExecutionContext


class AdjustAdapter(ToolAdapter):
    """Adjust 适配器 — 连接 Adjust 归因和数据分析 API.

    提供:
      - 花费/收入/ROAS 查询
      - 素材表现查询
      - 疲劳度计算
    """

    HANDLED_ACTIONS = {
        "query_metrics",
        "query_adjust",
        "query_creative_performance",
        "check_fatigue",
    }

    @property
    def name(self) -> str:
        return "adjust_adapter"

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
        """真实 Adjust API 调用."""
        try:
            from ..execution.adapters.adjust_verifier import AdjustDataClient

            client = AdjustDataClient()

            if action_name == "query_metrics":
                return self._query_metrics_real(client, params)
            elif action_name == "query_adjust":
                return self._query_adjust_real(client, params)
            elif action_name == "query_creative_performance":
                return self._query_creative_performance_real(client, params)
            elif action_name == "check_fatigue":
                return self._check_fatigue_real(client, params)

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
                error=f"Adjust API error: {str(e)}",
            )

    def _query_metrics_real(self, client, params: dict[str, Any]) -> ToolResult:
        """查询广告指标."""
        entity_type = params.get("entity_type", "campaign")
        entity_id = params.get("entity_id", "")
        metrics = params.get("metrics", ["spend", "roas", "installs"])
        date_range = params.get("date_range", "last_7d")

        result = client.query_metrics(
            entity_type=entity_type,
            entity_id=entity_id,
            metrics=metrics,
            date_range=date_range,
        )
        return ToolResult(
            tool_name="query_metrics",
            status=ToolResultStatus.SUCCESS,
            data=result,
        )

    def _query_adjust_real(self, client, params: dict[str, Any]) -> ToolResult:
        """查询 Adjust 归因数据."""
        app_id = params.get("app_id", "")
        metrics = params.get("metrics", ["installs", "ltv", "roas"])
        date_range = params.get("date_range", "last_7d")

        result = client.query_adjust(
            app_id=app_id,
            metrics=metrics,
            date_range=date_range,
        )
        return ToolResult(
            tool_name="query_adjust",
            status=ToolResultStatus.SUCCESS,
            data=result,
        )

    def _query_creative_performance_real(self, client, params: dict[str, Any]) -> ToolResult:
        """查询素材表现."""
        creative_id = params.get("creative_id", "")
        date_range = params.get("date_range", "last_7d")

        result = client.query_creative_performance(
            creative_id=creative_id,
            date_range=date_range,
        )
        return ToolResult(
            tool_name="query_creative_performance",
            status=ToolResultStatus.SUCCESS,
            data=result,
        )

    def _check_fatigue_real(self, client, params: dict[str, Any]) -> ToolResult:
        """检查素材疲劳度."""
        creative_id = params.get("creative_id", "")
        threshold = params.get("threshold", 0.7)

        result = client.check_fatigue(
            creative_id=creative_id,
            threshold=threshold,
        )
        return ToolResult(
            tool_name="check_fatigue",
            status=ToolResultStatus.SUCCESS,
            data=result,
        )

    def _execute_mock(self, action_name: str, params: dict[str, Any]) -> ToolResult:
        """Mock 数据查询."""
        mock_data = {
            "query_metrics": {
                "spend": 17000.0,
                "roas": 0.53,
                "installs": 4500,
                "ctr": 0.021,
                "cpm": 15.5,
                "impressions": 800000,
                "clicks": 16800,
            },
            "query_adjust": {
                "installs": 4500,
                "d1_retention": 0.35,
                "d7_retention": 0.12,
                "d30_ltv": 2.5,
                "roas_d1": 0.15,
                "roas_d7": 0.53,
                "roas_d30": 0.85,
                "payer_rate": 0.03,
            },
            "query_creative_performance": {
                "creatives": [
                    {"creative_id": "c001", "ctr": 0.08, "roas": 1.2, "fatigue": 0.45},
                    {"creative_id": "c002", "ctr": 0.03, "roas": 0.4, "fatigue": 0.81},
                    {"creative_id": "c003", "ctr": 0.05, "roas": 0.7, "fatigue": 0.62},
                ],
            },
            "check_fatigue": {
                "creative_id": params.get("creative_id", "all"),
                "fatigue_score": 0.81,
                "is_fatigued": True,
                "threshold": params.get("threshold", 0.7),
                "recommendation": "MUTATE" if 0.81 > params.get("threshold", 0.7) else "KEEP",
            },
        }

        return ToolResult(
            tool_name=action_name,
            status=ToolResultStatus.SUCCESS,
            data=mock_data.get(action_name, {"status": "ok"}),
            metadata={"mode": "mock", "source": "adjust"},
        )